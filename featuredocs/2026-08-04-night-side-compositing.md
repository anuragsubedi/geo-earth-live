# Night-side compositing

**Created:** 2026-08-04 · **Status:** proposed experiment — four options open · **Supersedes:** nothing

---

## Problem

A geostationary satellite watches Earth cycle through phases like the Moon. At the
subsatellite point's local midnight, illuminated fraction runs from 0% at equinox to
~4% at solstice. **The whole visible scene goes dark every night, year-round.**

Every product this project might build has to decide what to show then. There are
four defensible answers and this document keeps all of them open, with criteria for
choosing between them.

## The four options

### Option 1 — Consume CIRA GeoColor

NOAA/CIRA's operational composite: true colour by day, bands 7 and 13 at night
rendered so liquid-water cloud reads blue and ice cloud white, over a **static VIIRS
city-lights layer**. Served as pre-rendered JPEG from the NOAA STAR CDN.

- **Cost:** near zero. ~2–4 MB per 5424² frame; no compositing, no calibration.
- **Quality:** operational-grade. Better than a first attempt will be.
- **Honesty burden:** the city lights are a **multi-year static reference database,
  not observation**. A viewer sees a lit city on a night it may have been dark.
- **Environment:** `cdn.star.nesdis.noaa.gov` is **blocked in the cloud container**
  and expected to work on a local machine. This option is explorable locally only.

This was the inherited plan's choice, and it was a good one. It remains the fastest
route to a presentable product.

### Option 2 — Self-composited IR night, no lights

Band 13 (10.3 µm) alone, or the standard night-microphysics RGB
(12.3−10.3 / 10.3−3.9 / 10.3). Cloud-top temperature and structure, identically at
noon and midnight.

- **Cost:** low. Band 13 is 22.7 MB/frame on GOES, ~11 MB on Himawari **[measured]**.
- **Honesty burden:** **none.** Every pixel is a measurement.
- **Look:** no city lights, no "civilization glowing in the dark" shot. Meteorologically
  richer, aesthetically colder.

### Option 3 — Self-composited IR + live VIIRS DNB city lights

IR for cloud structure, VIIRS day-night band for lights. The apparent best of both.

**I previously described this as making the disclosure "disappear entirely." That was
wrong, and the correction matters:**

- VIIRS is sun-synchronous with a ~13:25 ascending node, so the **night pass is near
  01:25 local**. Night runs roughly 18:00–06:00 local, so a GEO night frame can sit
  **up to ~7 hours away in time** from the DNB observation used to light it. Three
  satellites (S-NPP, NOAA-20, NOAA-21) are phased ~50 min apart in the same plane, so
  the passes cluster around 00:35–02:15 local rather than spreading across the night.
- Different sensor, different orbit, different viewing geometry, different resolution.

So the caveat changes from *"static multi-year database"* to *"real observation from a
different sensor, up to ~7 hours off."* **Genuinely better — this night's outages,
fires and ship lights appear — but not co-temporal, and it must not be described as
live.**

There is a second limitation that is easy to miss: **DNB's cloud sensitivity depends
on moonlight.** It images cloud tops by reflected lunar illumination, so near new moon
the cloud signal largely vanishes and only artificial lights remain. **Night imagery
quality varies over the lunar cycle** — which is exactly why GeoColor uses IR for
cloud and reserves DNB-derived lights for the lights.

- **Cost:** high. Second ingest path, swath-to-fixed-grid reprojection, temporal
  alignment policy, lunar-phase handling.

### Option 4 — Let it go dark

Show the night side as it is: black, with the terminator sweeping.

- **Cost:** zero. **Honesty burden:** zero.
- For **Track A** this is arguably correct — the reference video's night passes are
  dark, and the darkness is part of the drama.
- For **Track B** it wastes half the frame.

---

## Selection criteria

| | Cost | Honesty burden | Look | Works in container |
|---|---|---|---|---|
| 1 — GeoColor | **lowest** | static lights | **best** | **no** (local only) |
| 2 — IR only | low | **none** | cold, informative | yes |
| 3 — IR + live DNB | **highest** | ~7 h offset; lunar-dependent | warm, most informative | yes |
| 4 — Dark | **zero** | **none** | dramatic / wasteful | yes |

**No single option wins.** The right answer is track-dependent, which is why this
stays open:

- Track A (orbital camera) → probably **4**, possibly **3** for a night pass set piece.
- Track B (daily summary) → **1** to get moving, **2** or **3** once the pipeline exists.
- Track C (polar swath) → **3** is native; VIIRS is already the sensor.

## The experiment

Render the same GEO night scene four ways and look at them side by side. Cheap,
and it settles an argument that is otherwise aesthetic and unresolvable in the abstract.

1. Pick one night with interesting cloud structure over a well-lit landmass.
2. Produce all four renderings of the same timestamp.
3. Record in `logs/` as an `experiment`: the frames, the cost in bytes and wall-clock
   for each, and the disclosure each would require.
4. **Repeat near full moon and near new moon** — otherwise Option 3 gets judged on
   whichever lunar phase happened to be up.

Option 1 requires a local machine. That is fine, and it is a good first task for a
local IDE agent — it is the clearest case of environment-dependent work in the project.

## Decision

**Deferred, deliberately.** All four remain live. Build the shared core so that the
night-side treatment is a swappable stage rather than a baked-in assumption, then run
the comparison.

The one commitment: **whichever is chosen, the disclosure that goes with it ships
with the output.** Option 1 says the lights are static. Option 3 says how far off in
time they are and that cloud detail depends on moonlight.

## Honesty notes

- GeoColor's city lights are a **static multi-year VIIRS composite**, not observation.
- Live DNB lights are real but **up to ~7 hours offset** from the GEO frame they are
  composited into, from a different sensor and viewing geometry. Not "live."
- **DNB cloud detail depends on lunar phase.** Near new moon it is largely absent.
  A product whose night appearance changes over a month should say why.
- Night-microphysics RGB is a **false-colour rendering** of brightness-temperature
  differences. The colours are informative, not what anything looks like.

## Open questions

- Is a ~7 hour offset visible in practice for city lights? Cities do not move; the
  offset matters for outages, fires and shipping. Possibly a small effect worth
  measuring before paying Option 3's cost.
- Can Option 3's temporal offset be reduced by using the **most recent** of the three
  VIIRS platforms per location, and is ~50 minutes of improvement worth the complexity?
- Does GeoColor's day/night transition blend well enough to imitate, or should a
  self-built version use a different terminator treatment?

## Revisions

- **2026-08-04** — Created. Corrects an overstatement made earlier in session — live
  DNB reduces but does not eliminate the night-side disclosure.
- **2026-08-04 (rev. 2)** — **The four-way experiment is unblocked.** A local probe
  reaches every arm, including GeoColor's `cdn.star.nesdis.noaa.gov`
  (`logs/2026-08-04T163938Z-environment-probe.md`). Separately, DNB publication
  latency is measured at **26.8 min**, marginally faster than the M-bands
  (`logs/2026-08-04T164009Z-experiment-viirs-latency.md`), so **freshness is not a
  discriminator between the options** — the ~7 h temporal offset and lunar-phase
  dependence recorded above are, and both are unchanged. Option 1 remains
  container-unreachable and therefore off the required path.
