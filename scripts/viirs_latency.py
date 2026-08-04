#!/usr/bin/env python3
"""Measure VIIRS SDR publication latency, separated from revisit gap.

`scripts/probe_env.py` reports the *age of the newest object* in a bucket. For a
polar orbiter that number conflates two unrelated things:

  * **publication latency** -- observation -> available in S3. A pipeline property.
  * **revisit / coverage gap** -- how long since the sensor last observed anything
    it publishes under this product. An orbital property.

Confusing them is how `docs/DATA_SOURCES.md` came to call DNB "anomalously stale"
and defer decision D7. A VIIRS SDR filename carries every timestamp needed to tell
them apart, so no download is required -- listing keys is enough:

    SVDNB_j02_d20260804_t1151103_e1152331_b19340_c20260804121727884000_oeac_ops.h5
              |         |        |               |
              |         |        |               `- c: creation (YYYYMMDDHHMMSS + us)
              |         |        `- e: observation end   (HHMMSS + tenths)
              |         `- t: observation start (HHMMSS + tenths)
              `- d: observation date

Usage:
    python3 scripts/viirs_latency.py                    # default products, today
    python3 scripts/viirs_latency.py --date 2026-08-04 --hours 6

Stdlib only, matching probe_env.py -- this must run before any dependency exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BUCKET = "noaa-nesdis-n21-pds"
DEFAULT_PRODUCTS = ["VIIRS-DNB-SDR", "VIIRS-M5-SDR"]

# SVDNB_j02_d20260804_t1151103_e1152331_b19340_c20260804121727884000_oeac_ops.h5
NAME_RE = re.compile(
    r"_d(?P<d>\d{8})_t(?P<t>\d{7})_e(?P<e>\d{7})_b(?P<orbit>\d+)_c(?P<c>\d{14})"
)


def _ssl_context():
    """Reuse probe_env's trust-store resolution so a broken CA bundle can't
    masquerade as a network failure. See docs/ENVIRONMENTS.md."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import probe_env  # noqa: PLC0415

        ctx, label = probe_env.resolve_trust_store()
        print(f"TLS trust store: {label}", file=sys.stderr)
        return ctx
    except Exception as exc:  # noqa: BLE001
        print(f"warning: falling back to default TLS context ({exc})", file=sys.stderr)
        return None


SSL_CONTEXT = None


def s3_list(prefix: str, token: str | None = None) -> str:
    url = f"https://{BUCKET}.s3.amazonaws.com/?list-type=2&prefix={prefix}&max-keys=1000"
    if token:
        url += f"&continuation-token={urllib.parse.quote(token, safe='')}"
    req = urllib.request.Request(url, headers={"User-Agent": "geo-earth-live/viirs-latency"})
    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as resp:
        return resp.read().decode()


def parse_granule(key: str, s3_modified: str) -> dict | None:
    m = NAME_RE.search(key)
    if not m:
        return None

    day = dt.datetime.strptime(m["d"], "%Y%m%d").replace(tzinfo=dt.timezone.utc)

    def clock(hhmmsss: str) -> dt.timedelta:
        # HHMMSS + tenths of a second
        return dt.timedelta(
            hours=int(hhmmsss[0:2]), minutes=int(hhmmsss[2:4]),
            seconds=int(hhmmsss[4:6]), milliseconds=int(hhmmsss[6]) * 100,
        )

    start = day + clock(m["t"])
    end = day + clock(m["e"])
    if end < start:  # observation crossed UTC midnight
        end += dt.timedelta(days=1)

    created = dt.datetime.strptime(m["c"], "%Y%m%d%H%M%S").replace(tzinfo=dt.timezone.utc)
    published = dt.datetime.fromisoformat(s3_modified.replace("Z", "+00:00"))

    return {
        "key": key.rsplit("/", 1)[-1],
        "orbit": int(m["orbit"]),
        "obs_start": start,
        "obs_end": end,
        "produced_min": (created - end).total_seconds() / 60,
        "published_min": (published - end).total_seconds() / 60,
    }


def collect(product: str, date: dt.date) -> list[dict]:
    prefix = f"{product}/{date:%Y/%m/%d}/"
    granules, token = [], None
    while True:
        body = s3_list(prefix, token)
        for key, modified in re.findall(
            r"<Key>(.*?)</Key>.*?<LastModified>(.*?)</LastModified>", body, re.S
        ):
            # Checksum sidecars land after their data file; counting them would
            # overstate latency and double the granule count.
            if key.endswith((".sha384", ".sha256", ".md5")):
                continue
            g = parse_granule(key, modified)
            if g:
                granules.append(g)
        m = re.search(r"<NextContinuationToken>(.*?)</NextContinuationToken>", body)
        if not m or "<IsTruncated>true</IsTruncated>" not in body:
            break
        token = m.group(1)
    return sorted(granules, key=lambda g: g["obs_end"])


def report(product: str, granules: list[dict]) -> list[str]:
    if not granules:
        return [f"### {product}", "", "No granules found.", ""]

    pub = [g["published_min"] for g in granules]
    newest = granules[-1]
    now = dt.datetime.now(dt.timezone.utc)

    # Revisit gap: spacing between consecutive observations.
    gaps = [
        (b["obs_start"] - a["obs_end"]).total_seconds() / 60
        for a, b in zip(granules, granules[1:])
    ]
    big = [g for g in gaps if g > 5]

    lines = [
        f"### {product}",
        "",
        f"- Granules on this UTC day: **{len(granules)}**, orbits "
        f"{min(g['orbit'] for g in granules)}–{max(g['orbit'] for g in granules)}",
        f"- **Publication latency (obs end → in S3): median {statistics.median(pub):.1f} min**, "
        f"min {min(pub):.1f}, max {max(pub):.1f}",
        f"- Age of newest object right now: **{(now - newest['obs_end']).total_seconds() / 60:.1f} min** "
        f"(observed {newest['obs_end']:%H:%M:%S}Z)",
    ]
    if big:
        lines.append(
            f"- Coverage gaps > 5 min between consecutive observations: **{len(big)}**, "
            f"largest **{max(big):.1f} min**"
        )
    else:
        lines.append("- No coverage gaps > 5 min; observation is effectively continuous")
    lines += ["", f"  Newest key: `{newest['key']}`", ""]
    return lines


def main() -> int:
    global SSL_CONTEXT

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="UTC date YYYY-MM-DD (default: today)")
    ap.add_argument("--products", nargs="*", default=DEFAULT_PRODUCTS)
    args = ap.parse_args()

    SSL_CONTEXT = _ssl_context()
    date = (
        dt.datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else dt.datetime.now(dt.timezone.utc).date()
    )

    out = [
        f"# VIIRS publication latency vs. revisit gap — {date:%Y-%m-%d} UTC",
        "",
        f"Bucket `{BUCKET}`. Generated by `scripts/viirs_latency.py`; timestamps parsed",
        "from granule filenames, no files downloaded.",
        "",
        "**Publication latency** is observation end → object in S3. **Coverage gap** is",
        "the spacing between consecutive observations. `probe_env.py`'s \"age of newest",
        "object\" is the sum of the two and must not be quoted as latency.",
        "",
    ]
    for product in args.products:
        print(f"  listing {product}...", file=sys.stderr)
        out += report(product, collect(product, date))

    text = "\n".join(out)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
