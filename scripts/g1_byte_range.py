#!/usr/bin/env python3
"""G1 -- prove or kill byte-range reads of GOES ABI C02 (0.5 km).

Gate question (implementation_plans/2026-08-04-shared-core.md):
can we read a 2048x2048 sector of a ~318-415 MB CMIPF C02 granule in
**under 25% of the file's bytes**, in under ~30 s, without downloading it?

The measurement is made twice, by two paths that share no code:

  method A  h5py over fsspec/s3fs. Bytes are counted at the transport
            layer by wrapping ``S3File._fetch_range`` -- i.e. actual HTTP
            GET ranges, not what h5py asked for.
  method B  read the HDF5 chunk index, then fetch those byte ranges with
            plain ``urllib`` and decompress with ``zlib`` + a hand-written
            un-shuffle. No fsspec, no h5py read path. The pixels are
            compared against method A's, so this checks correctness as
            well as cost.

Agreement between two runs of the same tool is not corroboration; that
lesson is why this script has a method B at all.

Usage:
    python3 scripts/g1_byte_range.py --json
    python3 scripts/g1_byte_range.py --granule s3://noaa-goes19/... --size 2048
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import time
import urllib.request
import zlib

DEFAULT_BUCKET = "noaa-goes19"
DEFAULT_PRODUCT = "ABI-L2-CMIPF"
DEFAULT_BAND = "C02"
DEFAULT_VAR = "CMI"
PASS_BYTE_FRACTION = 0.25
PASS_SECONDS = 30.0

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# This machine's interpreter default CA bundle does not verify (see
# logs/*-environment-probe.md). Reuse the probe's resolution policy rather
# than inventing a second one -- and never by disabling verification, which
# would turn a real proxy denial into a false success.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from probe_env import resolve_trust_store  # noqa: E402

SSL_CONTEXT, TRUST_STORE_LABEL = resolve_trust_store()


# --------------------------------------------------------------------------
# progress reporting
#
# The slow configurations issue one HTTP round trip per HDF5 chunk -- 342 of
# them for a 2048-row sector -- so a run is minutes of near-silence unless it
# says what it is doing. Progress goes to stderr (stdout stays a clean
# report), and the JSON report is rewritten after every phase so that a run
# killed partway still leaves its evidence in logs/.
# --------------------------------------------------------------------------


class Progress:
    """Live one-line status on stderr, throttled, TTY-aware."""

    def __init__(self, enabled: bool = True, stream=sys.stderr):
        self.enabled = enabled
        self.stream = stream
        self.tty = hasattr(stream, "isatty") and stream.isatty()
        self.interval = 0.2 if self.tty else 5.0
        self.phase = ""
        self.total: int | None = None
        self.base = 0
        self.base_bytes = 0
        self._t0 = time.perf_counter()
        self._last = 0.0
        self._width = 0

    def start(self, phase: str, total: int | None = None,
              base: int = 0, base_bytes: int = 0) -> None:
        """Begin a phase. `base` discounts work already counted by a shared
        counter before this phase started, so the ETA is not flattered by it."""
        self.phase, self.total = phase, total
        self.base, self.base_bytes = base, base_bytes
        self._t0 = time.perf_counter()
        self._last = 0.0

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._t0

    def update(self, done: int = 0, nbytes: int = 0, force: bool = False) -> None:
        if not self.enabled:
            return
        now = time.perf_counter()
        if not force and now - self._last < self.interval:
            return
        self._last = now
        el = now - self._t0
        done = max(0, done - self.base)
        nbytes = max(0, nbytes - self.base_bytes)
        total = (self.total - self.base) if self.total else None
        parts = [f"{self.phase}"]
        if total:
            pct = 100.0 * done / total
            parts.append(f"{done}/{total} ({pct:.0f}%)")
            if done:
                eta = el * (total - done) / done
                parts.append(f"eta {eta:5.1f}s")
        elif done:
            parts.append(f"{done} req")
        if nbytes:
            parts.append(f"{nbytes/1e6:6.2f} MB")
            # Below ~half a second the quotient is dominated by timer noise
            # and reports impossible rates; better to show nothing.
            if el >= 0.5:
                parts.append(f"{nbytes/1e6/el:5.2f} MB/s")
        parts.append(f"{el:5.1f}s")
        line = "  " + "  ".join(parts)
        self._emit(line)

    def _emit(self, line: str) -> None:
        if self.tty:
            pad = " " * max(0, self._width - len(line))
            self.stream.write("\r" + line + pad)
            self._width = len(line)
        else:
            self.stream.write(line + "\n")
        self.stream.flush()

    def finish(self) -> None:
        if self.enabled and self.tty and self._width:
            self.stream.write("\r" + " " * self._width + "\r")
            self.stream.flush()
        self._width = 0


PROGRESS = Progress()


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------


def find_recent_granule(fs, bucket: str, product: str, band: str,
                        lookback_hours: int = 6) -> str:
    """Newest <band> granule within the last few hours.

    GOES partitions by **day-of-year**: PRODUCT/YYYY/DDD/HH/. Walking back
    an hour at a time crosses day and year boundaries correctly because the
    arithmetic is done on the datetime, not on the path components.
    """
    now = dt.datetime.now(dt.timezone.utc)
    for back in range(lookback_hours):
        stamp = now - dt.timedelta(hours=back)
        prefix = (f"{bucket}/{product}/{stamp:%Y}/"
                  f"{stamp.timetuple().tm_yday:03d}/{stamp:%H}/")
        try:
            keys = [k for k in fs.ls(prefix, refresh=True) if f"-M6{band}_" in k]
        except FileNotFoundError:
            continue
        if keys:
            return sorted(keys)[-1]
    raise SystemExit(f"no {band} granule found in the last {lookback_hours} h")


# --------------------------------------------------------------------------
# method A -- h5py over fsspec, bytes counted at the transport layer
# --------------------------------------------------------------------------


class TransportCounter:
    """Counts real HTTP range GETs by wrapping S3File._fetch_range."""

    def __init__(self, progress: Progress | None = None):
        self.calls: list[tuple[int, int]] = []
        self._orig = None
        self._progress = progress

    def __enter__(self):
        import s3fs

        self._orig = s3fs.core.S3File._fetch_range
        calls = self.calls
        progress = self._progress

        def counted(inner_self, start, end):
            calls.append((start, end))
            if progress is not None:
                progress.update(len(calls),
                                sum(e - s for s, e in calls))
            return self._orig(inner_self, start, end)

        s3fs.core.S3File._fetch_range = counted
        return self

    def __exit__(self, *exc):
        import s3fs

        s3fs.core.S3File._fetch_range = self._orig
        return False

    @property
    def bytes(self) -> int:
        return sum(end - start for start, end in self.calls)

    @property
    def requests(self) -> int:
        return len(self.calls)


def method_a(fs, key: str, var: str, row0: int, col0: int, nrows: int,
             ncols: int, cache_type: str, block_size: int) -> dict:
    import h5py

    label = f"{cache_type}/{block_size//1024}KiB {nrows}x{ncols}"
    result: dict = {"cache_type": cache_type, "block_size": block_size}
    with TransportCounter(PROGRESS) as counter:
        t0 = time.perf_counter()
        PROGRESS.start(f"{label} opening")
        with fs.open(key, "rb", cache_type=cache_type,
                     block_size=block_size) as fobj:
            with h5py.File(fobj, "r") as h5:
                dset = h5[var]
                result["shape"] = list(dset.shape)
                result["chunks"] = list(dset.chunks) if dset.chunks else None
                result["dtype"] = str(dset.dtype)
                result["compression"] = dset.compression
                t_open = time.perf_counter()
                result["open_bytes"] = counter.bytes
                result["open_requests"] = counter.requests
                result["open_seconds"] = round(t_open - t0, 3)

                # With cache_type="none" every chunk is its own round trip, so
                # the chunk count is an honest denominator for an ETA. Any
                # caching strategy coalesces them and the bar just runs short.
                expected = None
                if dset.chunks and cache_type == "none":
                    expected = -(-nrows // dset.chunks[0]) + counter.requests
                PROGRESS.start(f"{label} reading", total=expected,
                               base=counter.requests, base_bytes=counter.bytes)
                sector = dset[row0:row0 + nrows, col0:col0 + ncols]
                t_read = time.perf_counter()
    PROGRESS.finish()

    result["sector_seconds"] = round(t_read - t_open, 3)
    result["total_seconds"] = round(t_read - t0, 3)
    result["total_bytes"] = counter.bytes
    result["total_requests"] = counter.requests
    result["sector_bytes"] = counter.bytes - result["open_bytes"]
    result["sector_checksum"] = int(sector.astype("int64").sum())
    result["sector_shape"] = list(sector.shape)
    return result, sector


# --------------------------------------------------------------------------
# method B -- chunk index + raw urllib range GETs + zlib. No fsspec, no
# h5py read path (h5py is used only to enumerate the chunk index).
# --------------------------------------------------------------------------


def chunk_index(fs, key: str, var: str, row0: int, nrows: int) -> tuple[list, tuple]:
    """(offset, nbytes, row) for every chunk overlapping rows [row0, row0+nrows)."""
    import h5py

    with fs.open(key, "rb", cache_type="readahead", block_size=2 ** 20) as fobj:
        with h5py.File(fobj, "r") as h5:
            dset = h5[var]
            chunk_rows = dset.chunks[0]
            dsid = dset.id
            out = []
            first = (row0 // chunk_rows) * chunk_rows
            row = first
            while row < row0 + nrows:
                info = dsid.get_chunk_info_by_coord((row, 0))
                out.append((int(info.byte_offset), int(info.size), row))
                row += chunk_rows
            return out, dset.chunks


def unshuffle(buf: bytes, itemsize: int) -> bytes:
    """Reverse the HDF5 shuffle filter.

    Shuffle writes all byte-0s of every element, then all byte-1s, etc.
    Reversing it is a transpose of an (itemsize, n) byte matrix.
    """
    import numpy as np

    n = len(buf) // itemsize
    arr = np.frombuffer(buf[:n * itemsize], dtype="u1").reshape(itemsize, n)
    return arr.T.copy().tobytes()


def method_b(bucket_url: str, chunks: list, chunk_shape: tuple, dtype_str: str,
             sample: int) -> dict:
    """Fetch chunks by raw HTTP range, decompress, return rows + byte cost."""
    import numpy as np

    picked = chunks[:sample] if sample else chunks
    total_predicted = sum(nbytes for _, nbytes, _ in chunks)
    fetched = 0
    rows = {}
    t0 = time.perf_counter()
    PROGRESS.start("method B raw range GETs", total=len(picked))
    for i, (offset, nbytes, row) in enumerate(picked, 1):
        req = urllib.request.Request(
            bucket_url,
            headers={"Range": f"bytes={offset}-{offset + nbytes - 1}"},
        )
        with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as resp:
            raw = resp.read()
        fetched += len(raw)
        plain = unshuffle(zlib.decompress(raw), np.dtype(dtype_str).itemsize)
        rows[row] = np.frombuffer(plain, dtype=dtype_str).reshape(chunk_shape)
        PROGRESS.update(i, fetched)
    PROGRESS.finish()
    return {
        "chunks_in_sector": len(chunks),
        "chunks_fetched": len(picked),
        "bytes_fetched": fetched,
        "predicted_sector_bytes": total_predicted,
        "seconds": round(time.perf_counter() - t0, 3),
        "contiguous_span_bytes": (chunks[-1][0] + chunks[-1][1] - chunks[0][0]),
    }, rows


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--granule", help="s3://bucket/key (default: newest recent)")
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--product", default=DEFAULT_PRODUCT)
    ap.add_argument("--band", default=DEFAULT_BAND)
    ap.add_argument("--var", default=DEFAULT_VAR)
    ap.add_argument("--size", type=int, default=2048, help="sector edge in px")
    ap.add_argument("--row", type=int, default=None, help="sector top row")
    ap.add_argument("--col", type=int, default=None, help="sector left column")
    ap.add_argument("--verify-chunks", type=int, default=24,
                    help="chunks to re-fetch via method B (0 = all)")
    ap.add_argument("--skip-verify", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="also measure how byte cost scales with geometry")
    ap.add_argument("--json", action="store_true", help="also write JSON to logs/")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the live progress line on stderr")
    args = ap.parse_args()

    # Piped stdout is block-buffered by default, which would land the whole
    # report after the progress trail instead of interleaved with it.
    sys.stdout.reconfigure(line_buffering=True)

    PROGRESS.enabled = not args.quiet
    checkpoint = Checkpoint(args.json)

    import s3fs

    fs = s3fs.S3FileSystem(anon=True)

    PROGRESS.start("discovering granule")
    PROGRESS.update(force=True)
    key = args.granule.replace("s3://", "") if args.granule else \
        find_recent_granule(fs, args.bucket, args.product, args.band)
    PROGRESS.finish()
    info = fs.info(key)
    file_bytes = int(info["size"])

    report: dict = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(
            timespec="seconds"),
        "granule": key,
        "granule_bytes": file_bytes,
        "granule_mb": round(file_bytes / 1e6, 2),
        "variable": args.var,
        "tls_trust_store": TRUST_STORE_LABEL,
        "sector_size": args.size,
        "pass_criteria": {
            "byte_fraction_below": PASS_BYTE_FRACTION,
            "seconds_below": PASS_SECONDS,
        },
    }
    print(f"granule  {key}")
    print(f"size     {file_bytes/1e6:.2f} MB")

    # Probe the shape once, cheaply, so the sector can be centred.
    import h5py

    with fs.open(key, "rb", cache_type="readahead", block_size=2 ** 20) as f:
        with h5py.File(f, "r") as h5:
            shape = h5[args.var].shape
            dtype_str = h5[args.var].dtype.str
    row0 = args.row if args.row is not None else (shape[0] - args.size) // 2
    col0 = args.col if args.col is not None else (shape[1] - args.size) // 2
    report["sector_origin"] = [row0, col0]
    print(f"sector   {args.size}x{args.size} at row {row0}, col {col0}\n")
    checkpoint.save(report)

    # --- method A, across cache strategies -------------------------------
    configs = [
        ("none", 2 ** 20),
        ("readahead", 2 ** 20),
        ("readahead", 2 ** 22),
        ("bytes", 2 ** 22),
    ]
    print(f"method A -- {len(configs)} cache strategies")
    runs = []
    sector_a = None
    report["method_a"] = runs
    for cache_type, block_size in configs:
        try:
            res, sector = method_a(fs, key, args.var, row0, col0, args.size,
                                   args.size, cache_type, block_size)
        except Exception as exc:  # a cache strategy failing is a result too
            runs.append({"cache_type": cache_type, "block_size": block_size,
                         "error": f"{type(exc).__name__}: {exc}"})
            print(f"  {cache_type:<10} block {block_size//1024:>5} KiB  FAILED: {exc}")
            continue
        res["byte_fraction"] = round(res["total_bytes"] / file_bytes, 4)
        res["passes"] = (res["byte_fraction"] < PASS_BYTE_FRACTION
                         and res["total_seconds"] < PASS_SECONDS)
        runs.append(res)
        sector_a = sector
        print(f"  {cache_type:<10} block {block_size//1024:>5} KiB  "
              f"{res['total_bytes']/1e6:>7.2f} MB  "
              f"{res['byte_fraction']*100:>5.1f}%  "
              f"{res['total_seconds']:>6.2f} s  "
              f"{res['total_requests']:>4} req  "
              f"{'PASS' if res['passes'] else 'FAIL'}")
        checkpoint.save(report)

    ok = [r for r in runs if "error" not in r]
    if not ok:
        report["verdict"] = "INCONCLUSIVE -- every cache strategy errored"
        checkpoint.save(report, "complete")
        return 1

    # Two different "best"s, and conflating them misreads the gate.
    #   minimal   -- fewest transport bytes. This is the chunk-cost floor, and
    #                it is what method B's independent prediction is compared
    #                against. It is usually the *slowest* config, because
    #                fetching exactly the needed bytes means one request per
    #                chunk.
    #   practical -- the config that actually passes the gate: fewest seconds
    #                among the runs meeting both criteria.
    minimal = min(ok, key=lambda r: r["total_bytes"])
    passing = [r for r in ok if r["passes"]]
    practical = min(passing, key=lambda r: r["total_seconds"]) if passing else None

    keys = ("cache_type", "block_size", "total_bytes", "byte_fraction",
            "total_seconds", "total_requests", "passes")
    report["method_a_minimal_bytes"] = {k: minimal[k] for k in keys}
    report["method_a_practical"] = {k: practical[k] for k in keys} if practical else None

    # --- method B ---------------------------------------------------------
    if not args.skip_verify:
        bucket, _, obj = key.partition("/")
        url = f"https://{bucket}.s3.amazonaws.com/{obj}"
        chunks, chunk_shape = chunk_index(fs, key, args.var, row0, args.size)
        res_b, rows = method_b(url, chunks, chunk_shape, dtype_str,
                               args.verify_chunks)
        res_b["predicted_byte_fraction"] = round(
            res_b["predicted_sector_bytes"] / file_bytes, 4)
        print(f"\nmethod B  {res_b['chunks_in_sector']} chunks span the sector, "
              f"predicting {res_b['predicted_sector_bytes']/1e6:.2f} MB "
              f"({res_b['predicted_byte_fraction']*100:.1f}%)")

        # cross-check 1: independent byte prediction vs. the measured
        # chunk-cost floor. Compare against `minimal`, not `practical` -- a
        # read-ahead config deliberately over-fetches, so a mismatch there
        # would say nothing about whether the chunk accounting is right.
        delta = minimal["total_bytes"] - res_b["predicted_sector_bytes"]
        res_b["compared_against"] = minimal["cache_type"]
        res_b["method_a_minus_b_bytes"] = delta
        res_b["method_a_over_b_ratio"] = round(
            minimal["total_bytes"] / res_b["predicted_sector_bytes"], 3)
        print(f"          method A moved {delta/1e6:+.2f} MB relative to that "
              f"({res_b['method_a_over_b_ratio']:.2f}x)")

        # cross-check 2: do the pixels agree?
        import numpy as np

        mismatches, compared = 0, 0
        if sector_a is not None:
            for row, block in rows.items():
                for i in range(block.shape[0]):
                    abs_row = row + i
                    if not (row0 <= abs_row < row0 + args.size):
                        continue
                    a = sector_a[abs_row - row0]
                    b = block[i, col0:col0 + args.size]
                    compared += 1
                    if not np.array_equal(a, b):
                        mismatches += 1
        res_b["rows_compared"] = compared
        res_b["rows_mismatched"] = mismatches
        res_b["pixels_agree"] = compared > 0 and mismatches == 0
        print(f"          {compared} rows compared against method A, "
              f"{mismatches} mismatched")
        report["method_b"] = res_b
        checkpoint.save(report)

    # --- sweep: how does cost scale with sector geometry? -----------------
    # The chunk layout is a full-width row strip, so the prediction is that
    # bytes track sector *height* and are indifferent to width. The last
    # entry is the falsification test: a full-width strip of the same height
    # as the 2048 square should cost the same.
    if args.sweep:
        geometries = [(512, 512), (1024, 1024), (2048, 2048), (4096, 4096),
                      (2048, shape[1])]
        chunk_rows = report["method_a"][0].get("chunks", [6])[0]
        est = sum(-(-r // chunk_rows) for r, _ in geometries)
        print(f"\nsweep (cache_type=none, i.e. the chunk-cost floor) -- "
              f"~{est} round trips across {len(geometries)} geometries")
        sweep = []
        report["sweep"] = sweep
        for rows, cols in geometries:
            r0 = (shape[0] - rows) // 2
            c0 = (shape[1] - cols) // 2
            res, _ = method_a(fs, key, args.var, r0, c0, rows, cols,
                              "none", 2 ** 20)
            entry = {
                "rows": rows, "cols": cols,
                "total_bytes": res["total_bytes"],
                "byte_fraction": round(res["total_bytes"] / file_bytes, 4),
                "total_seconds": res["total_seconds"],
                "total_requests": res["total_requests"],
            }
            sweep.append(entry)
            print(f"  {rows:>5} rows x {cols:>5} cols  "
                  f"{entry['total_bytes']/1e6:>7.2f} MB  "
                  f"{entry['byte_fraction']*100:>5.1f}%  "
                  f"{entry['total_seconds']:>6.2f} s")
            checkpoint.save(report)

    # --- verdict ----------------------------------------------------------
    # The gate asks whether the sector is reachable at all under the
    # criteria, so *any* config clearing both bars is a pass.
    if args.skip_verify:
        corroborated = None
    else:
        b = report["method_b"]
        corroborated = b["pixels_agree"] and b["method_a_over_b_ratio"] < 2.0
    if practical is None:
        report["verdict"] = "FAIL"
    elif corroborated is False:
        report["verdict"] = "FAIL -- criteria met but method B disagrees"
    elif corroborated is None:
        report["verdict"] = "PASS (uncorroborated)"
    else:
        report["verdict"] = "PASS"
    print(f"\nverdict  {report['verdict']}"
          + (f"  ({practical['cache_type']} / "
             f"{practical['block_size']//1024} KiB block: "
             f"{practical['byte_fraction']*100:.1f}% of bytes, "
             f"{practical['total_seconds']:.2f} s)" if practical else ""))
    checkpoint.save(report, "complete")
    if args.json:
        print(f"wrote    {checkpoint.path.relative_to(REPO_ROOT)}")
    return 0


class Checkpoint:
    """Rewrites the JSON report after every phase.

    The path is fixed once, at construction, so repeated checkpoints update
    one file instead of littering logs/ with a file per phase. A run that is
    interrupted -- ^C, a reclaimed container -- leaves a report marked
    ``"status": "in_progress"`` plus the phases that did finish, which is
    considerably more useful than nothing.
    """

    def __init__(self, enabled: bool):
        self.enabled = enabled
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        self.path = REPO_ROOT / "logs" / f"{stamp}-experiment-g1-byte-range.json"
        self.announced = False

    def save(self, report: dict, status: str = "in_progress") -> None:
        if not self.enabled:
            return
        report["status"] = status
        self.path.write_text(json.dumps(report, indent=2) + "\n")
        if not self.announced:
            print(f"logging  {self.path.relative_to(REPO_ROOT)} "
                  f"(rewritten after each phase)")
            self.announced = True


if __name__ == "__main__":
    sys.exit(main())
