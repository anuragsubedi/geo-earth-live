# Implementation plan — shared core (P1)

**Status:** `PROPOSED` · **Created:** 2026-08-04 · **Measurements refreshed:**
2026-08-04 · **Gate G1 resolved:** 2026-08-04 · **Supersedes:**
[`archive/2026-08-03-geo-daily-summary.md`](archive/2026-08-03-geo-daily-summary.md)

---

## G1 is answered — PASS

`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`, produced by
`scripts/g1_byte_range.py`. Amended in place rather than superseded: the gate
**confirmed** this plan's load-bearing assumption, so nothing below rests on a wrong
fact (`implementation_plans/README.md` rule 2).

**Measured:** a 2048² sector of a 435.38 MB C02 granule in **15.7% of the file's
bytes, 15.39 s** — against a bar of < 25% and < ~30 s. Corroborated by an independent
`urllib` + `zlib` path agreeing to **0.06%**, with **142 rows bit-identical**.

Three consequences for the work below:

1. **The `Fail` branch is void.** No 2 km `MCMIPF` fallback, no ~6,600 km camera cap.
   Track A is viable at 0.5 km and the honest camera altitude question
   (`featuredocs/2026-08-04-orbital-camera.md`) can assume native resolution.
2. **`fetch.py`'s shape is now determined** — which is precisely what the gate existed
   to decide. See the new design commitment below.
3. **`src/geoearth/` is unblocked.** The only remaining gate on this plan is the
   owner's sign-off, not a technical unknown.

**One number moved:** C02 is scene-dependent and the two G1 granules measured
**435.4 MB**, above the 318–415 MB in the refresh table below. The observed range is
now **318–435 MB**. The threshold was expressed as a fraction precisely so this would
not matter, and it did not.

---

## Measurement refresh — 2026-08-04

Revised in place rather than superseded. `implementation_plans/README.md` rule 2
supersedes a plan that **rests on a wrong assumption**; nothing below did. The
foundation — build the shared core, gate it on G1 — is unchanged, and this plan is
still `PROPOSED`, never signed off and never built from. What changed is the accuracy
of four numbers and the status of one blocker:

| | Was | Now |
|---|---|---|
| C02 frame size | 376–406 MB | **318–415 MB** [measured] — scene-dependent, so G1's threshold stays a *fraction* of the actual file |
| Disk budget basis | container ~30 GB | **local is tighter at 13.3 GB** [measured] — scale from the smaller |
| Night-side four-way | "needs a local machine" | **runnable now** — GeoColor's host answers locally |
| VIIRS DNB latency | "anomalously stale", 200 min | **26.8 min** [measured] — the old figure was a probe defect |

Sources: `logs/2026-08-04T163938Z-environment-probe.md`,
`logs/2026-08-04T164009Z-experiment-viirs-latency.md`.

**None of this changes the gate, the milestones, or the required path.** Egress
findings do not promote blocked hosts to the required path: production may run in the
container, so S3 + PyPI remains the only guaranteed substrate.

---

## What changed from the superseded plan

The inherited plan was sound reasoning on wrong facts about this environment. Three
things broke it, all measured (`logs/2026-08-04T153908Z-environment-probe.md`):

| Inherited assumption | Measured reality |
|---|---|
| Render tier = pre-rendered GeoColor JPEGs from `cdn.star.nesdis.noaa.gov`, ~430 MB/day | **Host blocked by egress policy in the container**, so it cannot be the required path. Reachable on a local machine, so it stays evaluable as a night-side option. |
| Cyclone positions from `nhc.noaa.gov/CurrentStorms.json` | **Blocked in the container** (open locally). Needs derivation or another source to be on the required path. |
| S3 publication latency 30–90 s after scan | **~17 s after scan end.** Better than assumed. |
| satpy avoided because of macOS ARM install pain | Irrelevant on Linux x86; and with GeoColor gone we must composite ourselves, so satpy is back on the table. |

**What did *not* change: the inherited plan's product.** "Quasi-live" in this project
is rhetorical, so a sped-up daily summary is a legitimate expression of the goal
rather than a retreat from it (`docs/ROADMAP.md`). It survives intact as **Track B**,
and it is sequenced *first* — it is the shortest path to moving pictures, and it
carries the project's only analysis component. What was superseded is the plan's data
plumbing, not its idea.

**This plan deliberately commits to no single track.** It builds the ~70% that all
three need, and gates on the one unproven assumption. Every track is a consumer of
this core.

---

## Objective

Get from an empty repo to **one real full-disk frame, fetched from S3, composited
into an image that looks like Earth**, on infrastructure the other tracks can build on.

Plus: **prove or kill the byte-range read assumption**, which is load-bearing for
anything involving 0.5 km data. ✅ **Done — proved** (see above); the rest of this
objective stands.

Not in this plan: video, motion, analysis, automation, publishing.

---

## Gate — G1, closed 2026-08-04 ✅

**G1. Byte-range read prototype.** Using `h5py` over `fsspec`, read a single
spatial sector of GOES-19 C02 (**318–435 MB/frame [measured]**, scene-dependent)
without downloading the file.

- **Pass:** a 2048² sector in **< 25% of the bytes** of the full file, in under
  ~30 s. Track A becomes viable at 0.5 km.
  - The threshold is deliberately a **fraction of the actual file**, which is what
    makes it robust to the ~100 MB spread in C02 size. Record the absolute bytes
    alongside the ratio, and name the granule — a fixed byte target would silently
    pass or fail on scene content rather than on chunk layout.
- ~~**Fail:** the chunk layout defeats partial reads. Fall back to 2 km `MCMIPF`
  (332 MB, all 16 bands, one file), cap the virtual camera at ~6,600 km altitude,
  and record the finding.~~ **Not taken.**

**Result: PASS — 15.7% of bytes in 15.39 s**, corroborated to 0.06% by an
independent path
(`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`). The ingest layer is
cleared to proceed, with the shape given below.

---

## Repository layout

```
geo-earth-live/
├── README.md                    # what this is; honesty disclosures
├── PROJECT_STATE.md             # single source of truth
├── AGENT_HANDOVER.md            # onboarding prompt for any agent
├── pyproject.toml
├── config.yaml                  # satellites, bands, grids, output specs
├── assets/                      # vendored static data (coastlines, base map)
├── docs/                        # DATA_SOURCES, ROADMAP, ENVIRONMENTS
├── featuredocs/                 # dated design rationale
├── implementation_plans/        # this file and its ancestors
├── logs/                        # probe reports, run records
├── scripts/
│   ├── probe_env.py             # ✅ done — stdlib only, must stay that way
│   ├── viirs_latency.py         # ✅ done — latency vs. revisit, stdlib only
│   └── g1_byte_range.py         # ✅ done — the G1 gate; needs h5py/fsspec/s3fs
├── src/geoearth/
│   ├── config.py                # load + validate config.yaml
│   ├── sources.py               # bucket/product/path conventions per satellite
│   ├── discover.py              # granule listing, expected-vs-present, gaps
│   ├── fetch.py                 # anonymous S3; whole-file and row-band reads
│   ├── geo.py                   # +proj=geos ↔ geodetic; viewing zenith; solar
│   ├── calibrate.py             # counts/radiance → reflectance, BT
│   ├── compose.py               # band → RGB, synthetic green, day/night blend
│   ├── cache.py                 # content-addressed local cache with budget
│   └── cli.py                   # `geoearth probe | fetch | frame`
└── tests/
    ├── test_geo.py              # projection round-trip < 1 px
    ├── test_paths.py            # day-of-year and HHMM path construction
    └── test_discover.py         # gap detection on synthetic listings
```

**Dependencies, deliberately small:** `numpy`, `pyproj`, `h5py`, `fsspec`, `s3fs`,
`xarray`, `netCDF4`, `pillow`, `typer`, `pyyaml`, `httpx`. `satpy` is added **only**
if G1 fails or Himawari HSD decoding proves painful — its `ahi_hsd` reader is the
sane way into Himawari's format. Standard `venv` + `pip`; no conda.

---

## Milestones

| | Deliverable | Definition of done |
|---|---|---|
| **G1** ✅ | Byte-range prototype | ~~A `logs/` decision record with measured bytes and seconds~~ **Done** — `logs/2026-08-04T171354Z-experiment-g1-byte-range.md` |
| **M1** | Scaffold + config | `geoearth --help` runs; `config.yaml` validates; tests pass |
| **M2** | Discovery | List every GOES-19 and Himawari-9 full-disk granule for a UTC day; report expected-vs-present with gaps named. **Also handle `CMIPM1`/`CMIPM2` at 60 s** — including detecting sector repositioning, since the footprint moves. **Paginate every listing** (see below) |
| **M3** | Fetch + cache | Pull one frame's bands within a disk budget; re-run hits cache; cache evicts when over budget |
| **M4** | Geolocation | `tests/test_geo.py` round-trips a known landmark to < 1 px; viewing-zenith and solar-geometry helpers verified against hand calculations |
| **M5** | **First frame** | A single composited full-disk PNG from live data that **looks like Earth**, with a coastline overlay landing on the coastlines |

M5 is the "it works" moment. Get there before anything ambitious.

---

## Design commitments

**Memory.** One frame in flight, ever. A decoded 5424² RGB frame is 88 MB; a
float32 band array is 118 MB. Both are fine alone; a hundred of either is not.
Process, write, release. Peak RSS target **< 1.5 GB**, asserted in the end-to-end test.

**Disk.** The container has ~30 GB free and the local machine **13.3 GB [measured]**.
A day of GOES C02 at 10-minute cadence is ~55 GB of whole granules and **fits in
neither** — streaming and discarding is mandatory. Row-band reads change the scale of
the problem without removing it: a 2160-row band (4K frame height at native 0.5 km)
is **~57 MB per frame**, so a 24 h sequence moves **~8.2 GB instead of ~63 GB**, a
7.6× reduction (arithmetic from G1's measured 26.4 kB/row, not itself measured).
Still streamed, still budgeted. `cache.py` enforces a configured byte budget with LRU
eviction and refuses to start a job whose worst case exceeds free space. **Read free
space at runtime and scale from it**; do not hardcode either figure, and never assume
the roomier environment.

**Sectors are row bands, not tiles** [measured — G1]. ABI `CMI` is chunked
**(6, 21696)**: full-width 6-row strips, gzip-5 + shuffle. Byte cost is therefore a
function of sector **height alone** and is indifferent to width — a 2048-row band
costs **54.05 MB whether it is 2048 or 21696 px wide, the same figure to the byte**.
Cost is **26.4 kB per row**, linear. So `fetch.py`:

1. Expresses a request as a **row range**, and returns the full width. A caller
   wanting a narrow sector crops *after* the read; it has already paid for the
   columns. **Do not build a 2-D tiling scheme** — splitting horizontally multiplies
   requests while moving identical bytes.
2. Sets `cache_type="readahead"` with a ~4 MiB block **explicitly**. This is not a
   tuning detail: `"bytes"`, a common fsspec default, over-fetches enough to **fail**
   the 25% budget outright (27.1% vs 15.7%), and `"none"` fetches the theoretical
   minimum (12.4%) but takes 2× longer because it serializes one round trip per chunk.
3. Treats **~4096 rows as the practical ceiling** (24.8% of the file). Above that,
   fetching the whole granule is competitive and simpler.

The consequence worth carrying into the camera work: **panning east–west within a
fetched band is free; panning north–south costs bytes.**

**Satellite abstraction.** GOES and Himawari differ in path convention, file format,
band numbering, and grid. `sources.py` isolates all of it behind one interface so
that adding Meteosat later (decision D2) touches one file. Do this from the first
commit; retrofitting it is much worse.

**UTC only.** Every timestamp, path and filename. GOES partitions by day-of-year
(`YYYY/DDD/HH/`), Himawari by calendar date and scan minute (`YYYY/MM/DD/HHMM/`).
Both are unit-tested — `test_paths.py` exists because this is where the silent
off-by-one-hour bugs live.

**Gaps are normal.** Build the expected timestamp list, fetch what exists, log what
is missing. Outages cluster around local midnight near equinoxes (solar keep-out)
and during calibration. Missing frames are a logged condition, never an exception.

**Always paginate S3 listings — `discover.py` must never trust one page.** A
ListObjectsV2 response caps at 1000 keys and returns them **lexicographically**, not
by time. VIIRS puts a whole UTC day in one flat prefix of several thousand objects,
so page one is the *oldest* part of the day. This already produced a wrong published
number once (`logs/2026-08-04T164009Z-experiment-viirs-latency.md`), and it fails in
the nastiest way: silently, with plausible-looking data, and *only* on the
high-volume products. Two consequences for `discover.py`:

1. Follow `NextContinuationToken` to exhaustion, and treat a truncated listing as an
   error rather than a partial result.
2. **A gap report built from a truncated listing is worse than no gap report**, since
   it fabricates missing frames at whichever end sorted last. `test_discover.py`
   must cover a >1000-key prefix.

**Offline-capable rendering.** Coastlines and base map vendored into `assets/` at
M4. No network dependency in the render path.

**Anything long-running reports progress and checkpoints its output.** A fetch or
render job is minutes of network-bound work, and a tool that prints nothing for four
minutes is indistinguishable from one that has hung. `scripts/g1_byte_range.py` is
the reference implementation: a throttled status line on **stderr** (so stdout stays
a clean report), and the run record rewritten to `logs/` **after every phase**, marked
`"status": "in_progress"` until it completes. An interrupted run — ^C, or a reclaimed
container — then still leaves its evidence behind, which is the whole point given
that the container can vanish mid-job.

---

## Verification

1. **Projection round-trip** — known lat/lon → fixed-grid pixel → back, asserting
   < 1 px. Then the visual check that actually catches errors: overlay a coastline
   vector on a real frame and look at it.
2. **Path construction** — day-of-year and `HHMM` conversions across a year
   boundary, a leap year, and hour 00.
3. **Gap detection** — synthetic listings with holes; assert the expected timestamps
   are reported missing.
4. **Memory guardrail** — peak RSS via `resource.getrusage` in the end-to-end test;
   fail above 2 GB.
5. **Cache budget** — fill past the budget, assert eviction and that the budget holds.
6. **End-to-end** — from an empty cache, produce one composited frame.

**Verify the projection origin against real data.** GOES-19 sits at 75.2°W, but
older granules carry −75.0 in `goes_imager_projection`. Read
`longitude_of_projection_origin` from an actual granule once, pin it in
`config.yaml`, and note the source. The mismatch is ~15 km of annotation offset.

---

## Risks

| Risk | Mitigation |
|---|---|
| ~~G1 fails → 0.5 km too expensive~~ | **Retired 2026-08-04 — G1 passed at 15.7%.** The `MCMIPF` fallback is not needed. |
| Timings measured from a laptop are mistaken for portable facts | Every wall-clock number in `logs/` so far is latency-bound from outside AWS and is an **upper bound**. Byte counts port; seconds do not. Re-measure timings once anything runs in `us-east-1`, and label which is which. |
| Himawari HSD decoding is a swamp | Time-box hand-rolling to one session, then take `satpy`'s `ahi_hsd`. |
| GOES synthetic green looks wrong | Make Himawari the colour source of record (decision D6); it has a real green band. |
| Container reclaimed mid-work | Commit and push early and often. Nothing uncommitted survives. |
| Two agents build the same module | Claim it in `PROJECT_STATE.md` first. |
| A measuring tool is itself wrong, and its output gets published as fact | Has happened twice already, both in `probe_env.py`. Cross-check any load-bearing number by a second method that shares no code with the first — the filename-derived VIIRS latency did not depend on our listing being complete. Agreement between two runs of the same tool is **not** corroboration. |

---

## Out of scope for this plan

Video encoding and interpolation · the virtual camera · feature detection and text
recaps · VIIRS ingest · scheduling and publishing · Meteosat · the night-side
four-way comparison (**no longer blocked** — every arm is reachable locally — but
still a separate plan, since it needs frames this one produces).

Each is a follow-on plan. Sequencing is decision D1 — current proposal B → A → C,
with Track B first because it reaches moving pictures soonest.

**One forward-looking requirement, though:** the composite stage must treat the
night-side treatment as a **swappable stage**, not a baked-in assumption. Four options
are open (`featuredocs/2026-08-04-night-side-compositing.md`) and the choice is
expected to differ per track. Designing that seam now costs almost nothing;
retrofitting it costs a rewrite.
