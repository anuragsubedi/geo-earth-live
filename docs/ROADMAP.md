# Roadmap

Long-horizon planning. Direction is **not yet fixed** — the repo owner is still
deciding. This document exists to make the choice concrete rather than to
pre-empt it.

For what is being built *right now*, see `implementation_plans/`. For current
status, see `PROJECT_STATE.md`.

---

## The goal, stated plainly

A **quasi-live feed of Earth** with the feel of Seán Doran's *ORBIT — A Journey
Around Earth in Real Time*: motion, curvature, terminator crossings, night passes.
Built from real satellite data, as close to live as the data allows.

"Quasi-live" is the honest word. The best case with reachable sources is roughly
**5–15 minutes behind reality** — Himawari-9 publishes at ~4.6 min, GOES-19 at
~8 min from scan start (`logs/`). That is genuinely good. It is not real-time, and
no amount of engineering makes it real-time.

---

## Three candidate tracks

They are not exclusive. **They share most of their infrastructure**, which is why
the near-term plan builds the shared core rather than committing to one.

### Track A — Orbital Camera *(closest to the stated goal)*

Live GEO composites textured onto a globe; a synthetic camera flies a chosen orbit;
render at any frame rate. Camera motion is exact; cloud evolution is real at
10-minute cadence.

- **Latency:** 5–15 min. Genuinely quasi-live.
- **Look:** the reference video, at an honest altitude (4K at ~1,600 km, or 1080p
  at ~800 km — see `featuredocs/2026-08-04-orbital-camera.md`).
- **Risk:** depends on byte-range reads of 0.5 km data being cheap. Unproven.
- **Honesty cost:** the viewpoint is fabricated and must be labelled as such.

### Track B — Daily Summary *(the inherited plan)*

24 hours of full-disk imagery compressed to ~60 s, with the terminator sweep as the
clock, plus automated detection of the day's notable weather and a text recap.

- **Latency:** a day. Not live by design.
- **Risk:** low. Best-understood path; a plain timelapse is achievable in an afternoon.
- **Value:** the only track with a real *analysis* component, and the easiest to
  ship something presentable from.

### Track C — Polar Swath *(the authentic one)*

VIIRS strips assembled into motion. 375 m resolution, genuinely observed motion,
never dark (sun-synchronous — see `featuredocs/2026-08-04-orbit-selection.md`).

- **Latency:** ~36 min, 12 h revisit.
- **Look:** a moving strip, not a flyover. Different, and beautiful.
- **Value:** **zero synthesis.** Every pixel and every bit of motion is observed.
  The honest counterweight to Track A.
- **Risk:** swath geometry, bow-tie deletion, granule stitching. Real work.

### Shared core (~70% of all three)

```
ingest  ── anonymous S3, granule discovery, gap handling, caching
geo     ── +proj=geos ↔ geodetic, viewing zenith, solar geometry
compose ── band → radiance → RGB, day/night blend, multi-satellite mosaic
render  ── frame writing, ffmpeg encode, titling
assets  ── vendored coastlines, base map, colour tables
```

Building this first is why the near-term plan is track-agnostic.

---

## Phases

| Phase | Goal | Definition of done | Gate |
|---|---|---|---|
| **P0** | Documentation & environment | Doc set exists; probe reproducible; direction discussion is grounded in measurements | **← we are here** |
| **P1** | Shared core + first pixels | One full-disk GEO frame fetched, composited, written as an image that looks like Earth | Byte-range read prototype must succeed |
| **P2** | First motion | A short video exists. Track chosen; whichever it is, it produces moving pictures | Owner picks a track |
| **P3** | The product | The chosen track's full output, with honesty labelling | — |
| **P4** | Automation | Runs unattended on a schedule, publishes somewhere | Decide GitHub Actions vs. AWS vs. local |
| **P5** | Expansion | Second track, or global coverage, or continuous streaming | — |

**P1 is deliberately unglamorous and deliberately first.** Every track needs it, and
it is where the unknowns are.

---

## Decision points

Open questions that change the shape of the work. None need answering today, but
each should be answered *before* the phase it gates.

| # | Question | Gates | Notes |
|---|---|---|---|
| D1 | Which track leads? | P2 | A matches the goal; B ships soonest; C is the most honest. |
| D2 | Unlock EUMETSAT (Meteosat/MTG)? | P3 | Free, needs registration. The only way to cover Africa/Europe/India. Highest-value single unlock. |
| D3 | Where does it run in production? | P4 | See compute note below. |
| D4 | Public repo, and published output? | P4 | Currently private. Publishing raises the honesty-labelling bar. |
| D5 | Live/rolling mode, or batch renders? | P5 | Continuous RTMP is a different architecture from batch. Don't build for it prematurely. |
| D6 | Colour source of record: GOES or Himawari? | P3 | Himawari has a real green band; GOES needs a synthetic one. |

---

## Compute strategy

The instinct to reach for a distributed system should be resisted here, at least
until something is actually slow.

**This workload is I/O-bound, not CPU-bound.** 144 frames/day is embarrassingly
parallel, and a scheduler would spend its time waiting on S3 either way. Adding a
cluster costs more in complexity than it returns in wall-clock time.

The one thing that genuinely pays is **colocation, not distribution**. Every NOAA
Open Data bucket lives in `us-east-1`. Compute in that region gets near-line-rate
transfer and zero egress. A single well-placed instance beats a distributed cluster
elsewhere by a wide margin, and costs less.

Ranked by value per unit of complexity:

1. **Run in `us-east-1`.** Biggest win available, near-zero complexity.
2. **Byte-range reads.** Fetch the bands and sectors you need, not whole files.
   Turns a ~48 GB/day pull into a fraction of that. See `docs/DATA_SOURCES.md`.
3. **Local `multiprocessing` over frames.** Free parallelism, one import.
4. **GitHub Actions matrix sharded by UTC hour** — 24 free parallel runners, each
   handling a slice that fits comfortably in a runner's disk. Good fit for P4 if
   the job stays modest.
5. **A real cluster.** Only if a measurement demands it. It has not.

Rendering is the one genuinely CPU-heavy stage, and it shards cleanly by time
segment — so even that is parallelism, not distribution.

---

## Explicitly out of scope

Recorded so they stop being reconsidered:

- **Building or launching a satellite.** $10–80M, years of ITU/FCC coordination.
  Analyzed in `featuredocs/2026-08-04-orbit-selection.md` as reference only.
- **True real-time.** Physically impossible from these sources.
- **Sub-100 m imagery.** Requires commercial sources with no live cadence.
- **Reimplementing what NOAA already ships.** Use L2 products (fire, cloud height,
  winds) rather than re-deriving them, except where the derivation *is* the point.

---

## Revisions

- **2026-08-04** — Created. Three-track framing; shared-core-first sequencing.
