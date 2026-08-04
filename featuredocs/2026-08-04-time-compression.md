# Time compression and playback rate

**Created:** 2026-08-04 · **Status:** reference analysis · **Supersedes:** nothing

---

## Problem

"Quasi-live" in this project is **rhetorical, not literal**. A true real-time feed
of Earth is unwatchable: geostationary imagery arrives one frame per 600 seconds,
and even if it arrived continuously, weather at 1× is close to motionless. The
appeal of the reference video comes from *orbital velocity*, not from real-time
observation.

So playback rate is an editorial parameter, and it is the parameter that decides
how much synthesis a product requires. This document works out the relationship.

## The invariant

For a source of cadence `C` seconds played at `F` frames per second, with each real
frame interval subdivided into `k` output frames:

```
speedup × k = C × F
```

Derivation: `k` output frames cover `C` seconds of real time and occupy `k/F`
seconds of screen time, so `speedup = C·F/k`.

**For 10-minute GEO full disk at 30 fps, that constant is 18,000.** The entire
design space is one-dimensional. You cannot independently choose "slow, smooth, and
un-synthesized" — pick two.

| Source | Cadence | Constant @ 30 fps | @ 60 fps |
|---|---|---|---|
| ABI/AHI full disk | 600 s | **18,000** | 36,000 |
| ABI CONUS | 300 s **[measured]** | 9,000 | 18,000 |
| **ABI mesoscale** | **60 s [measured]** | **1,800** | 3,600 |

### What this buys, concretely

| Interpolation `k` | Speedup | 24 h renders in | Honesty cost |
|---|---|---|---|
| 1 (none) | 18,000× | 4.8 s | **none — every frame observed** |
| 4 | 4,500× | 19 s | low |
| 12.5 | 1,440× | 60 s | moderate |
| 25 | 720× | 120 s | high |
| 50 | 360× | 240 s | very high — 98% of frames fabricated |

The inherited plan's 60-second daily summary sits at `k = 12.5`, i.e. 1,440×. That
is a defensible middle, and it is a *choice*, not a constraint.

## The mesoscale finding

**[measured]** 2026-08-04, `noaa-goes19/ABI-L2-CMIPM/2026/216/14/`:

> Two mesoscale sectors (`CMIPM1`, `CMIPM2`), **60 frames per hour each — a 60-second
> cadence**, all 16 bands. And they are tiny: **C13 at 0.31 MB, C02 at 4.4 MB per
> frame**, against 22.7 MB and 318–435 MB for the full-disk equivalents.

That is **10× the cadence at ~1/70th the bytes.** The consequence is the most useful
result in this document:

> **A 24-hour mesoscale sequence is 1,440 real frames = 48 seconds at 30 fps with
> `k = 1`.** A smooth, watchable, entirely un-synthesized timelapse. Zero interpolation,
> zero fabrication, nothing to disclose.

Caveats, both real:

- **Coverage is ~1,000 × 1,000 km**, not a disk. This is a storm-zoom source, not a
  planet source.
- **The sectors move.** NOAA repositions M1 and M2 to follow active weather, so the
  footprint is not fixed. Geolocation must be read per granule, and a 24-hour
  sequence may not be spatially continuous. Detecting and cutting at repositioning
  events is required work, not an edge case.

This makes mesoscale the natural source for the daily summary's sector callouts and
for any close-up segment in the orbital-camera track — and it means those segments
can be honest in a way the full-disk segments cannot.

## The terminator is the clock

At 1,440×, the subsolar point sweeps 180° of longitude — 12 hours, 43,200 s — in
**30 seconds of screen time**. Usable disk (inside ~75° viewing zenith) is nearer
150°, so a terminator crossing occupies roughly **25–30 seconds** of a 60-second clip.

That is why the daily-summary format works. Half the video is one clean
light-to-dark transition, which reads as a day passing rather than as an artifact.
Slow the playback much below 1,440× and the terminator stops being legible as a
single event; speed it up much past 4,500× and the whole day flickers by before the
eye locks onto anything.

**Earth's own rotation sets the natural pace of this product.** That is a pleasing
constraint rather than an annoying one.

## Regimes per track

| Track | Motion comes from | Natural speedup | `k` needed |
|---|---|---|---|
| **A — Orbital camera** | Camera, not time | **1×–10×** | 1 for camera motion; texture refresh is the only interpolation question |
| **B — Daily summary** | Time compression | 720×–4,500× | 4–25 |
| **C — Polar swath** | Satellite along-track | 60×–600× | depends on granule stitching |

Track A is the interesting case. Because the camera supplies the motion, playback
can sit near 1× and still look fast — ground speed at 1,600 km is 5.65 km/s. At 1×
a hemisphere crossing takes ~39 minutes and the texture refreshes about four times,
so clouds visibly evolve and `k = 1` works. Accelerate to 10× and the refreshes land
one screen-minute apart and become visible steps; only then does interpolation
matter, and only as a **morph between two co-registered grids** — a far easier
problem than full-frame motion synthesis.

## Decision

1. **Treat playback rate as an explicit, configured, documented parameter.** Not an
   accident of the encode command. Put it in `config.yaml` and print it in the output.
2. **Report `k` alongside speedup in every output's description.** `k` is the honest
   measure of how much of what the viewer sees was fabricated. "1,440× speedup" sounds
   like a fact about time; "12.5× interpolated" is a fact about provenance.
3. **Prefer raising speedup over raising `k`** when the two trade off. Under-sampled
   real motion is more honest than over-smoothed synthetic motion.
4. **Use mesoscale wherever the framing allows it**, because `k = 1` is available there.

## Honesty notes

- Any `k > 1` means most frames the viewer sees were never observed. State `k`.
- Speedup factors should be stated as such — a viewer has no way to infer 1,440×.
- Mesoscale sectors move; a sequence spanning a reposition is not one continuous view
  and must not be presented as one.
- Full-disk imagery is built by a scanning radiometer over ~10 minutes, so the top and
  bottom of a "single frame" differ in time by nearly that much. At high speedup this
  rolling-shutter skew is visible, and it is in the data, not introduced by us.

## Open questions

- Where does the terminator stop reading as an event? Worth rendering 360×, 720×,
  1,440×, 4,500× from the same day and just looking.
- Does mesoscale reposition frequently enough to break 24-hour continuity in practice?
  Measure over a week before designing around it.
- For Track A, is a texture-grid morph between 10-minute refreshes actually needed, or
  is a hard cut invisible at 1×? Cheapest possible experiment; run it first.

## Revisions

- **2026-08-04** — Created. Mesoscale cadence and sizes measured; see
  `logs/2026-08-04T153908Z-environment-probe.md` and the session record.
- **2026-08-04 (rev. 2)** — Full-disk C02 comparison figure updated to the measured
  318–435 MB range (was 376–406 MB). The mesoscale advantage is unaffected — it gets
  slightly larger at the low end of the range.
