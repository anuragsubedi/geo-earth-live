# Roadmap

Long-horizon planning. For what is being built *right now*, see
`implementation_plans/`. For current status, see `PROJECT_STATE.md`.

---

## The goal, stated plainly

A **feed of Earth built from real satellite data**, with the feel of Seán Doran's
*ORBIT — A Journey Around Earth in Real Time*: motion, curvature, terminator
crossings, night passes.

### "Quasi-live" is rhetorical

This is the framing that governs everything below, so it goes first.

**"Quasi-live" does not mean low-latency.** A literal real-time feed would be
unwatchable — geostationary imagery arrives one frame per 600 seconds, and weather
at 1× barely moves. The reference video's appeal comes from *orbital velocity*, not
from real-time observation.

So a sped-up animation is a **legitimate expression of the goal, not a fallback from
it.** Latency still matters — 4.6 minutes from Himawari-9 is worth having, and it is
what makes "today's weather" possible rather than "last week's" — but it is a
secondary quality, not the definition of success.

Consequence: **all three tracks below serve the goal.** None is a compromise.

---

## Three tracks — all in scope

They share most of their infrastructure, and they are complementary rather than
competing. The plan is to **explore all three, compare results, and let the outputs
decide** what gets invested in.

### Track A — Orbital Camera

Live GEO composites textured onto a globe; a synthetic camera flies a chosen orbit.
Camera motion is exact and continuous; cloud evolution stays at its true 10-minute
cadence.

- **Look:** the reference video, at an honest altitude — 4K at ~1,600 km or 1080p at
  ~800 km (`featuredocs/2026-08-04-orbital-camera.md`).
- **Playback:** 1×–10×. Motion comes from the camera, so little or no interpolation.
- **Risk:** depends on byte-range reads of 0.5 km data. Unproven — gate G1.
- **Honesty cost:** the viewpoint is fabricated.

### Track B — Daily Summary

24 hours compressed to ~60 s with the terminator sweep as the clock, plus automated
detection of the day's notable weather and a text recap. The inherited plan.

- **Playback:** 720×–4,500×, i.e. `k` of 4–25 (`featuredocs/2026-08-04-time-compression.md`).
- **Risk:** low. Best-understood path; a plain timelapse is an afternoon's work.
- **Distinctive value:** the only track with a real **analysis** component, and the
  easiest to ship something presentable from. **The best first track for that reason.**
- **Honesty cost:** interpolated frames; whatever the night-side choice requires.

### Track C — Polar Swath

VIIRS strips assembled into motion. 375 m, genuinely observed motion, never dark
(sun-synchronous — `featuredocs/2026-08-04-orbit-selection.md`).

- **Playback:** 60×–600×.
- **Distinctive value:** **zero synthesis.** Every pixel and every motion observed.
  The honest counterweight to A, and the reference point its evaluation is measured against.
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

| Phase | Goal | Definition of done |
|---|---|---|
| **P0** | Documentation & environment | Doc set exists; probe reproducible **← we are here** |
| **P1** | Shared core + first pixels | One full-disk frame fetched, composited, looks like Earth |
| **P2** | First motion, **Track B** | A watchable timelapse exists |
| **P3** | Track A prototype | A virtual camera pass over live imagery |
| **P4** | Track C prototype | A VIIRS swath sequence |
| **P5** | Comparison & investment | All three seen side by side; decide where effort goes |
| **P6** | Automation & publishing | Runs unattended; output published with disclosures |

**Track B leads not because it is the goal but because it is the shortest path to
moving pictures**, and moving pictures are what make the other two judgeable. The
sequencing is about learning rate, not preference.

---

## Evaluation discipline

Because the plan is to explore rather than to choose upfront, exploration needs to
produce **reviewable results** rather than opinions.

Every exploratory branch ends in a `logs/` **experiment record** containing:

1. **What was compared** — the options, and what was held constant.
2. **Cost** — bytes moved, wall-clock, peak RSS, added dependencies.
3. **Quality** — measured where measurable (PSNR / SSIM / LPIPS, stratified), shown
   side by side where not.
4. **Disclosure required** — what each option would force into the output description.
5. **Verdict** — adopt, reject, or defer, with the reason.

Experiments currently specified and awaiting a run:

| Experiment | Specified in | Decides |
|---|---|---|
| **G1** — byte-range reads of C02 | `implementation_plans/2026-08-04-shared-core.md` (`PROPOSED`) | Whether 0.5 km is affordable; camera altitude |
| **Hold-out interpolation** | `featuredocs/2026-08-04-interpolation-and-upscaling.md` | Which interpolation method ships, and its measured cost |
| **Night-side four-way** | `featuredocs/2026-08-04-night-side-compositing.md` | GeoColor vs. IR vs. IR+DNB vs. dark. **Unblocked** — every arm reachable locally |
| **Playback rate ladder** | `featuredocs/2026-08-04-time-compression.md` | Where the terminator stops reading as an event |
| **Mesoscale continuity** | `featuredocs/2026-08-04-time-compression.md` | Whether sector repositioning breaks 24 h sequences |

Completed:

| Experiment | Record | Result |
|---|---|---|
| **VIIRS latency vs. revisit** | `logs/2026-08-04T164009Z-experiment-viirs-latency.md` | **Adopt.** DNB latency 26.8 min, not the 200 min previously recorded — that was a probe defect. Removes a false constraint on D7 |

The **hold-out interpolation experiment is the most valuable single result the
project can produce.** It converts "looks smooth" into a defensible number, and it is
what lets any synthesized output be published with a stated error rather than a hope.

---

## Decision points

| # | Question | Gates | Notes |
|---|---|---|---|
| D1 | Track **sequencing** — which order, how much in parallel? | P2 | No longer a selection. Current proposal: B → A → C. |
| D2 | Unlock EUMETSAT (Meteosat/MTG)? | P3 | Free, needs registration. Only route to Africa/Europe/India. Highest-value single unlock. Host is **blocked in the container, open locally** — so the question is registration and required-path policy, not egress. |
| D3 | Production compute: GitHub Actions, AWS `us-east-1`, or local? | P6 | See below. |
| D4 | Repo public? Output published? | P6 | Publishing raises the disclosure bar. |
| D5 | Live/rolling mode, or batch renders? | P6 | Different architecture. Don't build for it prematurely. |
| D6 | Colour source of record: GOES or Himawari? | P3 | Himawari has a real green band; GOES needs a synthetic one. |
| D7 | Night-side treatment | P3 | Four options open — see the featuredoc. Likely differs per track. All four arms are now runnable locally, and DNB latency is measured at ~27 min, so freshness is not a discriminator. |

---

## Compute strategy

**This workload is I/O-bound, not CPU-bound.** 144 frames/day is embarrassingly
parallel, and a scheduler would spend its time waiting on S3 either way.

The one thing that genuinely pays is **colocation, not distribution.** Every NOAA
Open Data bucket lives in `us-east-1`. Compute there gets near-line-rate transfer and
zero egress — a single well-placed instance beats a distributed cluster elsewhere.

Ranked by value per unit of complexity:

1. **Run in `us-east-1`.** Biggest win, near-zero complexity.
2. **Byte-range reads.** Fetch the bands and sectors you need, not whole files.
3. **Prefer mesoscale where framing allows** — 60 s cadence at ~1/70th the bytes.
4. **Local `multiprocessing` over frames.** Free parallelism, one import.
5. **GitHub Actions matrix sharded by UTC hour** — 24 free parallel runners.
6. **A real cluster.** Only if a measurement demands it. None has.

Rendering and learned interpolation are the CPU/GPU-heavy stages, and both shard
cleanly by time segment — parallelism, not distribution.

---

## Explicitly out of scope

- **Building or launching a satellite.** Analyzed in
  `featuredocs/2026-08-04-orbit-selection.md` as reference only.
- **True real-time.** Physically impossible, and per the framing above, not wanted.
- **Sub-100 m imagery.** Commercial sources, no live cadence.
- **Reimplementing what NOAA already ships.** Use L2 products (fire, cloud height,
  winds) rather than re-deriving them — except where the derivation is the point.

---

## Revisions

- **2026-08-04** — Created.
- **2026-08-04** — Revised: "quasi-live" clarified as rhetorical, so a sped-up
  animation is a legitimate expression of the goal rather than a fallback. All three
  tracks moved in scope; D1 changed from selection to sequencing. Evaluation
  discipline added.
- **2026-08-04 (rev. 3)** — First local probe: all hosts open, so the night-side
  four-way is unblocked and D2 reduces to registration plus required-path policy.
  First completed experiment recorded (VIIRS latency). Corrected the experiments
  table, which pointed at "active plan" when no plan is `ACTIVE`.
