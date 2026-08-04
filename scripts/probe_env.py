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
import subprocess
import sys
import urllib.error
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


def check_host(host: str, note: str) -> dict:
    """Probe one host. Distinguishes proxy denial from DNS/connection failure."""
    url = f"https://{host}/"
    started = _now()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "geo-earth-live/probe"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status, detail = resp.status, "ok"
    except urllib.error.HTTPError as exc:
        # An HTTP error still proves we reached the origin. 404 on a bucket root
        # means "wrong bucket name", not "blocked".
        status, detail = exc.code, "reached origin"
    except urllib.error.URLError as exc:
        status, detail = None, str(exc.reason)[:120]
    except Exception as exc:  # noqa: BLE001 - report anything, never crash the probe
        status, detail = None, f"{type(exc).__name__}: {exc}"[:120]

    elapsed = (_now() - started).total_seconds()
    reachable = status is not None
    return {
        "host": host,
        "note": note,
        "status": status,
        "reachable": reachable,
        "detail": detail,
        "seconds": round(elapsed, 2),
    }


def s3_list(bucket: str, prefix: str, delimiter: str = "/", max_keys: int = 1000) -> str:
    url = (
        f"https://{bucket}.s3.amazonaws.com/?list-type=2"
        f"&prefix={prefix}&delimiter={delimiter}&max-keys={max_keys}"
    )
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode()


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

        body = s3_list(bucket, path, delimiter="")
        rows = re.findall(
            r"<Key>(.*?)</Key>.*?<LastModified>(.*?)</LastModified>.*?<Size>(\d+)</Size>",
            body,
            re.S,
        )
        if not rows:
            return {"ok": False, "error": f"no keys under {path}"}

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
    for group, results in host_results.items():
        lines += [f"### {group}", "", "| Host | Status | Verdict | Purpose |", "|---|---|---|---|"]
        for r in results:
            if r["reachable"]:
                verdict = "**OPEN**" if r["status"] < 400 else f"reached ({r['status']})"
            else:
                verdict = "**BLOCKED**"
            status = r["status"] if r["status"] is not None else "--"
            lines.append(f"| `{r['host']}` | {status} | {verdict} | {r['note']} |")
        lines.append("")

    lines += [
        "## Data freshness",
        "",
        "Latency here is *publication* latency: wall-clock age of the newest object.",
        "",
        "| Source | Latest object | Size | Age | Deepest prefix |",
        "|---|---|---|---|---|",
    ]
    for f in freshness:
        if f["result"].get("ok"):
            r = f["result"]
            lines.append(
                f"| {f['note']} | `{r['latest_key'][:56]}` | {r['size_mb']} MB | "
                f"{r['age_minutes']} min | `{r['deepest_prefix']}` |"
            )
        else:
            lines.append(f"| {f['note']} | -- | -- | -- | ERROR: {f['result'].get('error')} |")

    lines += [
        "",
        "## How to read this",
        "",
        "- **BLOCKED** in a cloud container means an org egress-policy denial. Do not",
        "  route around it -- record it and design for the sources that are open.",
        "- A `404` is *not* blocked: the host answered, the bucket name was wrong.",
        "- If a host is BLOCKED here but OPEN on your laptop, that is expected. Any",
        "  design that depends on it must be optional, with a reachable fallback.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="also write a .json sidecar")
    parser.add_argument("--quiet", action="store_true", help="suppress stdout report")
    args = parser.parse_args()

    print("Probing environment...", file=sys.stderr)
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
