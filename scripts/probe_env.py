#!/usr/bin/env python3
"""Probe the current environment's capabilities and write a timestamped report to logs/.

This project is developed from more than one place: a cloud container with a
policy-filtered egress proxy, and ordinary local machines (VS Code / Cursor).
Those environments differ in ways that change the *design*, not just the setup
-- most importantly, which data hosts are reachable.

Run this first, in any new environment, before trusting any doc that claims a
source is available:

    python3 scripts/probe_env.py

Stdlib only, on purpose: it must run before any dependency is installed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_ROOT / "logs"

TIMEOUT = 15

# Hosts whose reachability changes what we can build. Grouped by role so the
# report reads as a capability matrix rather than a list of URLs.
HOSTS: dict[str, list[tuple[str, str]]] = {
    "GEO imagery (primary pixel sources)": [
        ("noaa-goes19.s3.amazonaws.com", "GOES-19 / GOES-East @ 75.2W -- ABI L1b+L2"),
        ("noaa-goes18.s3.amazonaws.com", "GOES-18 / GOES-West @ 137W -- ABI L1b+L2"),
        ("noaa-goes16.s3.amazonaws.com", "GOES-16 archive (retired from East 2025-04)"),
        ("noaa-himawari9.s3.amazonaws.com", "Himawari-9 @ 140.7E -- AHI L1b FLDK"),
        ("noaa-himawari8.s3.amazonaws.com", "Himawari-8 archive"),
    ],
    "LEO imagery (polar orbiters)": [
        ("noaa-nesdis-n21-pds.s3.amazonaws.com", "NOAA-21 VIIRS SDR incl. DNB (live city lights)"),
        ("noaa-nesdis-n20-pds.s3.amazonaws.com", "NOAA-20 VIIRS SDR"),
        ("noaa-nesdis-snpp-pds.s3.amazonaws.com", "Suomi-NPP VIIRS SDR"),
        ("noaa-jpss.s3.amazonaws.com", "JPSS blended / flood products"),
        ("sentinel-s2-l1c.s3.amazonaws.com", "Sentinel-2 L1C (requester-pays)"),
    ],
    "Pre-rendered composites (cheap pixels, if reachable)": [
        ("cdn.star.nesdis.noaa.gov", "NOAA STAR CDN -- GeoColor JPEG, the v1-draft render tier"),
        ("www.star.nesdis.noaa.gov", "NOAA STAR web"),
        ("rammb-slider.cira.colostate.edu", "CIRA SLIDER tiles"),
    ],
    "Ancillary / metadata": [
        ("www.nhc.noaa.gov", "National Hurricane Center CurrentStorms.json"),
        ("celestrak.org", "TLE orbital elements"),
        ("gibs.earthdata.nasa.gov", "NASA GIBS -- Blue Marble, global base layers"),
        ("epic.gsfc.nasa.gov", "DSCOVR/EPIC at Sun-Earth L1 -- always-lit full disk"),
        ("naturalearthdata.com", "Natural Earth coastline vectors"),
        ("data.eumetsat.int", "EUMETSAT -- Meteosat/MTG (fills the 20W-100E gap)"),
    ],
    "Toolchain / distribution": [
        ("pypi.org", "Python packages"),
        ("files.pythonhosted.org", "Python wheels"),
        ("api.github.com", "GitHub API"),
        ("www.youtube.com", "reference videos / eventual RTMP target"),
    ],
}

# Buckets we walk to confirm data is not just reachable but *current*.
FRESHNESS_PROBES: list[tuple[str, str, str]] = [
    ("noaa-goes19", "ABI-L2-CMIPF/", "GOES-19 full-disk multiband CMI"),
    ("noaa-goes18", "ABI-L2-CMIPF/", "GOES-18 full-disk multiband CMI"),
    ("noaa-himawari9", "AHI-L1b-FLDK/", "Himawari-9 full-disk L1b"),
    ("noaa-nesdis-n21-pds", "VIIRS-M5-SDR/", "NOAA-21 VIIRS M5 (0.67um)"),
    ("noaa-nesdis-n21-pds", "VIIRS-DNB-SDR/", "NOAA-21 VIIRS day-night band"),
]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


# --- TLS trust ------------------------------------------------------------
#
# A failed TLS handshake is NOT evidence of an egress block, but the probe used
# to report it as one. On a python.org framework build for macOS the configured
# CA bundle path often does not exist, so *every* host fails to verify and the
# whole report reads BLOCKED -- including PyPI and S3, which is never true.
#
# So: resolve a working trust store once, up front, against control hosts that
# are open in every environment we care about. Prefer the interpreter default
# (in the filtered container the proxy presents its own CA, and the default
# store is the one that trusts it -- switching stores there would break a
# working setup). Fall back only when the default cannot verify.
#
# We never disable verification. Turning verification off would convert a real
# MITM-proxy denial into a false OPEN, which is a worse lie than the one we are
# fixing.

TRUST_CONTROL_HOSTS = ("pypi.org", "noaa-goes19.s3.amazonaws.com")

# Resolved by resolve_trust_store(); every request in this run uses it.
SSL_CONTEXT: ssl.SSLContext | None = None
TRUST_STORE_LABEL = "unresolved"


def _cert_candidates() -> list[tuple[str, str | None]]:
    """(label, cafile) pairs to try, best-supported first. None = interpreter default."""
    candidates: list[tuple[str, str | None]] = [("interpreter default", None)]

    env_file = os.environ.get("SSL_CERT_FILE")
    if env_file:
        candidates.append(("$SSL_CERT_FILE", env_file))

    try:
        import certifi  # noqa: PLC0415 - optional; absent on a bare interpreter

        candidates.append(("certifi", certifi.where()))
    except Exception:  # noqa: BLE001
        pass

    candidates += [
        ("/etc/ssl/cert.pem", "/etc/ssl/cert.pem"),
        ("/opt/homebrew/etc/ca-certificates/cert.pem",
         "/opt/homebrew/etc/ca-certificates/cert.pem"),
        ("/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/certs/ca-certificates.crt"),
    ]
    return [(label, f) for label, f in candidates if f is None or Path(f).is_file()]


def _handshake_ok(ctx: ssl.SSLContext) -> tuple[bool, str]:
    """True if any control host completes a verified TLS handshake."""
    last = "no control host answered"
    for host in TRUST_CONTROL_HOSTS:
        try:
            req = urllib.request.Request(
                f"https://{host}/", method="HEAD",
                headers={"User-Agent": "geo-earth-live/probe"},
            )
            urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx).close()
            return True, host
        except urllib.error.HTTPError:
            return True, host  # origin answered: handshake succeeded
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            last = reason[:120]
            if "CERTIFICATE_VERIFY_FAILED" not in reason:
                # Reachability problem, not a trust problem. This store is fine.
                return True, f"{host} (assumed; {reason[:60]})"
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"[:120]
    return False, last


def resolve_trust_store() -> tuple[ssl.SSLContext, str]:
    """Pick the first CA bundle that can actually verify a control host."""
    failures: list[str] = []
    for label, cafile in _cert_candidates():
        try:
            ctx = ssl.create_default_context(cafile=cafile)
        except Exception as exc:  # noqa: BLE001 - unreadable/corrupt bundle; try the next
            failures.append(f"{label} ({type(exc).__name__})")
            continue
        ok, detail = _handshake_ok(ctx)
        if ok:
            suffix = "" if not failures else f" (after {', '.join(failures)} failed to verify)"
            return ctx, f"{label}{suffix}"
        failures.append(label)
    # Nothing verified. Keep the default and let per-host classification say so,
    # rather than silently weakening verification.
    return ssl.create_default_context(), (
        f"NONE VERIFIED -- tried {', '.join(failures) or 'no candidates'}"
    )


def _open(url: str, timeout: int = TIMEOUT, method: str = "GET"):
    req = urllib.request.Request(
        url, method=method, headers={"User-Agent": "geo-earth-live/probe"}
    )
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT)


def classify_failure(reason: str) -> tuple[str, str]:
    """Map a connection failure to (verdict, kind).

    The distinction that matters: a policy denial is a decision to design
    around; a local trust or DNS failure is a broken toolchain that says
    nothing about what this environment is allowed to reach.
    """
    low = reason.lower()
    if "tunnel connection failed" in low or "403" in low or "proxy" in low:
        return "**BLOCKED**", "policy"
    if "certificate_verify_failed" in low or "unable to get local issuer" in low:
        return "TLS TRUST?", "tls-trust"
    if "certificate" in low or "ssl" in low:
        return "TLS ERROR", "tls"
    if "name or service not known" in low or "nodename nor servname" in low \
            or "getaddrinfo" in low or "name resolution" in low:
        return "DNS FAIL", "dns"
    if "timed out" in low or "timeout" in low:
        return "TIMEOUT", "timeout"
    if "refused" in low:
        return "REFUSED", "refused"
    return "UNREACHABLE", "other"


def check_host(host: str, note: str) -> dict:
    """Probe one host, classifying *why* it failed rather than assuming a block."""
    url = f"https://{host}/"
    started = _now()
    verdict = kind = None
    try:
        with _open(url) as resp:
            status, detail = resp.status, "ok"
    except urllib.error.HTTPError as exc:
        # An HTTP error still proves we reached the origin. 404 on a bucket root
        # means "wrong bucket name", not "blocked". But a proxy denial also
        # arrives as 403, so let classification see it.
        status, detail = exc.code, "reached origin"
        if exc.code == 403 and "amazonaws.com" not in host:
            verdict, kind = classify_failure(f"403 {exc.reason}")
    except urllib.error.URLError as exc:
        status, detail = None, str(exc.reason)[:120]
        verdict, kind = classify_failure(str(exc.reason))
    except Exception as exc:  # noqa: BLE001 - report anything, never crash the probe
        status, detail = None, f"{type(exc).__name__}: {exc}"[:120]
        verdict, kind = classify_failure(detail)

    if verdict is None:
        verdict = "**OPEN**" if status is not None and status < 400 else f"reached ({status})"
        kind = "open" if status is not None and status < 400 else "reached"

    elapsed = (_now() - started).total_seconds()
    return {
        "host": host,
        "note": note,
        "status": status,
        "reachable": status is not None,
        "verdict": verdict,
        "kind": kind,
        "detail": detail,
        "seconds": round(elapsed, 2),
    }


def s3_list(bucket: str, prefix: str, delimiter: str = "/", max_keys: int = 1000,
            token: str | None = None) -> str:
    url = (
        f"https://{bucket}.s3.amazonaws.com/?list-type=2"
        f"&prefix={prefix}&delimiter={delimiter}&max-keys={max_keys}"
    )
    if token:
        url += f"&continuation-token={urllib.parse.quote(token, safe='')}"
    with _open(url, timeout=60) as resp:
        return resp.read().decode()


# A ListObjectsV2 page caps at 1000 keys. VIIRS partitions a whole UTC day into one
# flat prefix holding thousands of objects, and S3 returns them in *lexicographic*
# order -- which for VIIRS filenames is observation order. Reading only the first
# page therefore yields the newest of the OLDEST 1000 keys.
#
# That is not hypothetical: it is why two probes reported the DNB day-night band as
# 200 and 249 minutes stale and docs/DATA_SOURCES.md called it "anomalously stale".
# Measured properly, DNB publishes continuously at ~27 min. Always paginate.
MAX_LIST_PAGES = 40


def s3_list_all(bucket: str, prefix: str) -> tuple[list[tuple[str, str, str]], bool]:
    """Every (key, last_modified, size) under a prefix. Returns (rows, complete)."""
    rows: list[tuple[str, str, str]] = []
    token, complete = None, True
    for page in range(MAX_LIST_PAGES):
        body = s3_list(bucket, prefix, delimiter="", token=token)
        rows += re.findall(
            r"<Key>(.*?)</Key>.*?<LastModified>(.*?)</LastModified>.*?<Size>(\d+)</Size>",
            body,
            re.S,
        )
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", body)
        if "<IsTruncated>true</IsTruncated>" not in body or not m:
            break
        token = m.group(1)
    else:
        complete = False  # hit the page cap; the newest key may be beyond it
    return rows, complete


def latest_granule(bucket: str, prefix: str) -> dict:
    """Walk lexicographically-last prefixes down to keys.

    Every bucket here partitions by time in a path that sorts chronologically
    (YYYY/DDD/HH or YYYY/MM/DD/HHMM), so "last prefix" is "most recent".
    """
    try:
        path = prefix
        for _ in range(6):
            body = s3_list(bucket, path)
            subs = [p for p in re.findall(r"<Prefix>(.*?)</Prefix>", body) if p and p != path]
            if not subs:
                break
            path = sorted(subs)[-1]

        rows, complete = s3_list_all(bucket, path)
        if not rows:
            return {"ok": False, "error": f"no keys under {path}"}

        # Checksum sidecars are published after the data they describe; ranking on
        # them would overstate freshness.
        data_rows = [r for r in rows if not r[0].endswith((".sha384", ".sha256", ".md5"))]
        rows = data_rows or rows

        key, modified, size = sorted(rows, key=lambda r: r[1])[-1]
        mod_dt = dt.datetime.fromisoformat(modified.replace("Z", "+00:00"))
        return {
            "ok": True,
            "deepest_prefix": path,
            "latest_key": key.rsplit("/", 1)[-1],
            "size_mb": round(int(size) / 1048576, 2),
            "modified": modified,
            "age_minutes": round((_now() - mod_dt).total_seconds() / 60, 1),
            "keys_in_partition": len(rows),
            "listing_complete": complete,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]}


def local_facts() -> dict:
    def cmd(args: list[str]) -> str | None:
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=20)
            return out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
        except Exception:  # noqa: BLE001
            return None

    total_gb = free_gb = None
    try:
        usage = shutil.disk_usage(REPO_ROOT)
        total_gb = round(usage.total / 1024**3, 1)
        free_gb = round(usage.free / 1024**3, 1)
    except Exception:  # noqa: BLE001
        pass

    mem_gb = None
    try:
        if hasattr(os, "sysconf") and "SC_PAGE_SIZE" in os.sysconf_names:
            mem_gb = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1)
    except Exception:  # noqa: BLE001
        pass

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "cpu_count": os.cpu_count(),
        "memory_gb": mem_gb,
        "disk_total_gb": total_gb,
        "disk_free_gb": free_gb,
        "ffmpeg": cmd(["ffmpeg", "-version"]) or "NOT INSTALLED",
        "git": cmd(["git", "--version"]) or "NOT INSTALLED",
        "https_proxy": os.environ.get("HTTPS_PROXY", "(unset)"),
        "in_container_proxy": bool(os.environ.get("HTTPS_PROXY")),
        "tls_trust_store": TRUST_STORE_LABEL,
    }


def render_report(facts: dict, host_results: dict, freshness: list[dict]) -> str:
    stamp = _now().strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = [
        f"# Environment probe -- {stamp}",
        "",
        "Generated by `scripts/probe_env.py`. Regenerate in any new environment before",
        "relying on `docs/DATA_SOURCES.md`; reachability is environment-specific.",
        "",
        "## Machine",
        "",
        "| Property | Value |",
        "|---|---|",
    ]
    for key, value in facts.items():
        lines.append(f"| `{key}` | {value} |")

    lines += ["", "## Host reachability", ""]

    tls_broken = [
        r for results in host_results.values() for r in results if r.get("kind") == "tls-trust"
    ]
    if tls_broken:
        lines += [
            "> **This report is not trustworthy.** "
            f"{len(tls_broken)} host(s) failed TLS certificate verification, which is a",
            "> broken local trust store -- *not* an egress policy denial. Fix the CA bundle",
            "> and re-run before recording any verdict from this file. Do not commit these",
            "> results as reachability facts.",
            "",
        ]

    for group, results in host_results.items():
        lines += [f"### {group}", "", "| Host | Status | Verdict | Purpose |", "|---|---|---|---|"]
        for r in results:
            status = r["status"] if r["status"] is not None else "--"
            lines.append(f"| `{r['host']}` | {status} | {r['verdict']} | {r['note']} |")
        lines.append("")

    lines += [
        "## Data freshness",
        "",
        "**Age is the wall-clock age of the newest object -- it is NOT publication",
        "latency.** For a geostationary sensor scanning on a fixed schedule the two are",
        "close. For a polar orbiter they are not: age there is publication latency *plus*",
        "the revisit gap since the sensor last observed. To measure VIIRS latency alone,",
        "use `scripts/viirs_latency.py`, which reads the observation and creation",
        "timestamps out of the granule filenames.",
        "",
        "| Source | Latest object | Size | Age | Deepest prefix |",
        "|---|---|---|---|---|",
    ]
    for f in freshness:
        if f["result"].get("ok"):
            r = f["result"]
            flag = "" if r.get("listing_complete", True) else " ⚠️ listing truncated"
            lines.append(
                f"| {f['note']} | `{r['latest_key'][:56]}` | {r['size_mb']} MB | "
                f"{r['age_minutes']} min{flag} | `{r['deepest_prefix']}` |"
            )
        else:
            lines.append(f"| {f['note']} | -- | -- | -- | ERROR: {f['result'].get('error')} |")

    lines += [
        "",
        "## How to read this",
        "",
        "- **OPEN** -- the origin answered with a non-error status.",
        "- **BLOCKED** -- a proxy refused the tunnel. In a cloud container this is an",
        "  org egress-policy denial. Do not route around it: record it and design for",
        "  the sources that are open.",
        "- `reached (NNN)` -- the origin answered with an error. A `404` is *not*",
        "  blocked; the host answered and the bucket name was wrong.",
        "- **TLS TRUST?** -- the handshake failed to verify. This says nothing about",
        "  whether the host is reachable; it means this machine's CA bundle is broken or",
        "  incomplete. Fix the trust store and re-run. Never record it as BLOCKED, and",
        "  never 'fix' it by disabling verification -- that would turn a real",
        "  MITM-proxy denial into a false OPEN.",
        "- **DNS FAIL / TIMEOUT / REFUSED** -- network-layer failures, also not policy.",
        "- If a host is BLOCKED here but OPEN on your laptop, that is expected. Any",
        "  design that depends on it must be optional, with a reachable fallback.",
        "",
        f"TLS trust store used for this run: `{facts.get('tls_trust_store', 'unknown')}`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="also write a .json sidecar")
    parser.add_argument("--quiet", action="store_true", help="suppress stdout report")
    args = parser.parse_args()

    global SSL_CONTEXT, TRUST_STORE_LABEL

    print("Probing environment...", file=sys.stderr)
    SSL_CONTEXT, TRUST_STORE_LABEL = resolve_trust_store()
    print(f"  TLS trust store: {TRUST_STORE_LABEL}", file=sys.stderr)

    facts = local_facts()

    host_results: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        for group, entries in HOSTS.items():
            host_results[group] = list(pool.map(lambda e: check_host(*e), entries))

    freshness = []
    for bucket, prefix, note in FRESHNESS_PROBES:
        print(f"  freshness: {bucket}/{prefix}", file=sys.stderr)
        freshness.append({"bucket": bucket, "prefix": prefix, "note": note,
                          "result": latest_granule(bucket, prefix)})

    report = render_report(facts, host_results, freshness)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y-%m-%dT%H%M%SZ")
    out_path = LOGS_DIR / f"{stamp}-environment-probe.md"
    out_path.write_text(report, encoding="utf-8")

    if args.json:
        (LOGS_DIR / f"{stamp}-environment-probe.json").write_text(
            json.dumps({"machine": facts, "hosts": host_results, "freshness": freshness},
                       indent=2, default=str),
            encoding="utf-8",
        )

    if not args.quiet:
        print(report)
    print(f"\nWrote {out_path.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
