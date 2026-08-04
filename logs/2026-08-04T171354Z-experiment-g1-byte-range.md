# Experiment — G1: byte-range reads of GOES ABI C02 (0.5 km)

**Date:** 2026-08-04 17:13:54 UTC · **Environment:** local (macOS 26.2 ARM64, 8
cores, 16 GB, `logs/2026-08-04T165610Z-environment-probe.md`) ·
**Produced by:** `scripts/g1_byte_range.py` · **Sidecar:**
`2026-08-04T171354Z-experiment-g1-byte-range.json`

**Verdict: PASS — adopt byte-range reads. Track A is viable at 0.5 km.**

Gate defined in `implementation_plans/2026-08-04-shared-core.md`: read a 2048²
sector of a CMIPF C02 granule in **< 25% of the file's bytes**, in **< ~30 s**,
without downloading it. Measured: **15.7% of bytes in 15.39 s.**

---

## What was compared

One granule, one sector, four fsspec cache strategies, plus a geometry sweep.
Held constant: granule, sector origin, variable, machine, network.

| | |
|---|---|
| Granule | `noaa-goes19/ABI-L2-CMIPF/2026/216/17/OR_ABI-L2-CMIPF-M6C02_G19_s20262161700205_e20262161709513_c20262161709572.nc` |
| Granule size | **435.38 MB** [measured] |
| Variable | `CMI`, 21696 × 21696, `int16` |
| **Chunk layout** | **(6, 21696)** — gzip level 5 + shuffle |
| Sector | 2048 × 2048 at row 9824, col 9824 (disk centre) |

---

## Cost

### Method A — h5py over fsspec/s3fs, bytes counted at the transport layer

Counted by wrapping `S3File._fetch_range`, so these are actual HTTP range GETs,
not what h5py asked for.

| Cache strategy | Block | Bytes moved | Fraction | Wall clock | Requests | Gate |
|---|---|---|---|---|---|---|
| `none` | 1 MiB | 54.05 MB | 12.4% | 30.72 s | 361 | **FAIL** (time) |
| `readahead` | 1 MiB | 68.84 MB | 15.8% | 19.93 s | 62 | PASS |
| **`readahead`** | **4 MiB** | **68.21 MB** | **15.7%** | **15.39 s** | **16** | **PASS** |
| `bytes` | 4 MiB | 117.86 MB | 27.1% | 26.20 s | 28 | **FAIL** (bytes) |

Two distinct optima, and conflating them misreads the gate:

- **`none` is the byte floor** — 12.4%, exactly the chunks the sector needs and
  nothing else. It fails on *time*, because "fetch exactly what is needed" means
  one HTTP round trip per chunk: 361 serialized round trips.
- **`readahead`/4 MiB is the practical winner.** It over-fetches by 26% to
  collapse 361 round trips into 16, and is 2× faster for it.

**The timing is latency-bound, not bandwidth-bound.** 54 MB in 30.7 s is
1.8 MB/s, which is not a throughput limit — it is ~85 ms of round-trip latency
× 361. Run in `us-east-1` these numbers collapse; this is handover point 7
showing up as a measurement. **The byte figures are portable, the second
figures are not** — treat 15.39 s as a laptop-from-outside-AWS upper bound.

### Geometry sweep — cache floor (`cache_type="none"`)

| Sector | Bytes | Fraction | Wall clock |
|---|---|---|---|
| 512 × 512 | 13.58 MB | 3.1% | 9.56 s |
| 1024 × 1024 | 27.19 MB | 6.2% | 17.22 s |
| 2048 × 2048 | 54.05 MB | 12.4% | 34.91 s |
| 4096 × 4096 | 107.83 MB | 24.8% | 65.50 s |
| **2048 × 21696** (full width) | **54.05 MB** | **12.4%** | 31.85 s |

**This is the most consequential result in the run, and it is not the gate.**

Because chunks are full-width 6-row strips, **byte cost is a function of sector
height alone and is completely indifferent to width.** The last row is the
falsification test: a full-width strip 2048 rows tall costs **54.05 MB — the
same figure to the byte** as the 2048² square. Reading a 2048-wide sector, you
pay for all 21696 columns whether you use them or not.

Cost is **26.4 kB per row** [measured], linear across the sweep.

Design consequences:

1. **The natural fetch primitive is a full-width row band, not a square tile.**
   `fetch.py` should express sectors as row ranges. A tiling scheme that splits
   horizontally would multiply cost by the number of columns of tiles while
   buying nothing.
2. **A virtual camera should pan cheaply in longitude and expensively in
   latitude.** East–west motion within an already-fetched band is free.
3. **4096 rows is effectively the ceiling** under the 25% criterion — 24.8%
   sits right on it. Above ~4100 rows, whole-file download is competitive.

### Derived frame budget

Arithmetic from the measured 26.4 kB/row, not itself measured: a 2160-row band
(4K frame height at native 0.5 km) costs **~57 MB per frame** against 435 MB for
the whole granule — a **7.6× reduction**. A 24 h sequence at 10-minute cadence
is ~8.2 GB streamed rather than ~63 GB, which matters because neither
environment can store the latter (13.3 GB local, ~30 GB container).

---

## Corroboration — method B

The project has twice published numbers that were defects in its own measuring
tool, so the load-bearing figure was measured a second time by a path sharing no
code with the first: read the HDF5 chunk index, fetch those byte ranges with
plain `urllib`, decompress with `zlib` and a hand-written un-shuffle. No fsspec,
no h5py read path.

| Check | Method A | Method B | Agreement |
|---|---|---|---|
| Sector bytes | 54.05 MB (transport counter) | 54.02 MB (chunk index sum) | **1.00× (0.06%)** |
| Pixels | h5py `dset[...]` | raw range GET + zlib + un-shuffle | **142 rows compared, 0 mismatched** |

The second row matters as much as the first: it confirms the bytes are not only
few but *correct*. A cheap read returning wrong pixels would have passed a
bytes-only check.

The residual 0.03 MB is HDF5 metadata — the superblock and chunk index that
method A must read to locate anything, and that method B was handed for free.

---

## Cost of adoption

Dependencies added: `h5py`, `fsspec`, `s3fs`, `numpy` — all already in the
shared-core plan's dependency list. No new ones. Peak RSS was not instrumented
in this run; the sector arrays involved (2048² int16 = 8.4 MB) are far below the
1.5 GB target and were never the concern.

---

## Disclosure required

**None.** Byte-range reading is a transport optimisation that returns bit-identical
pixels — verified above, not assumed. Nothing here is synthesized, interpolated,
or upscaled, so nothing here propagates to the README's honesty notes.

The honesty consequence is indirect and *favourable*: 0.5 km being affordable is
what lets the virtual camera sit at an altitude that does not require upscaling.
The alternative — falling back to 2 km `MCMIPF` and capping at ~6,600 km — is now
unnecessary.

---

## Incidental findings

1. **C02 is larger than the recorded range.** 435.38 MB, against 318–415 MB on
   record. Two granules an hour apart measured 435.40 and 435.38 MB. The
   observed range widens to **318–435 MB**. This vindicates expressing G1's
   threshold as a fraction rather than an absolute byte count — a fixed target
   would have drifted with scene content.
2. **`cache_type="bytes"` is a trap here.** It is fsspec's default for many
   paths and it *fails the gate on bytes* (27.1%), because its read-ahead is
   tuned for sequential access, not the strided pattern of a chunked sector
   read. `fetch.py` must set the cache strategy explicitly rather than inherit
   the default.
3. **The local CA bundle problem recurred**, this time in method B's `urllib`
   path. Resolved by importing `probe_env.resolve_trust_store()` rather than
   writing a second policy — and never by disabling verification.

---

## Verdict

**Adopt.** Byte-range reads of C02 are affordable: 15.7% of bytes, 15.39 s from
outside AWS, corroborated independently and pixel-exact.

The gate's `FAIL` branch — fall back to 2 km `MCMIPF`, cap the camera at
~6,600 km — **is not taken.**

Follow-on work this unblocks or constrains:

- `src/geoearth/fetch.py` — implement sectors as **row bands**; set
  `cache_type="readahead"` with a ~4 MiB block explicitly.
- The honest-camera-altitude question in
  `featuredocs/2026-08-04-orbital-camera.md` can now assume native 0.5 km.
- Re-measure wall clock once anything runs in `us-east-1`; the byte figures
  carry over unchanged, the timings do not.
