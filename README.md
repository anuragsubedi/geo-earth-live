# geo-earth-live

A **quasi-live feed of Earth built from real satellite data** — aiming for the feel
of Seán Doran's *ORBIT — A Journey Around Earth in Real Time*: motion, curvature,
terminator crossings, night passes.

> **Status: planning.** No pipeline yet. The documentation set is complete and the
> environment is measured; the next step is a prototype that decides whether 0.5 km
> imagery is affordable. See [`PROJECT_STATE.md`](PROJECT_STATE.md).

---

## What "quasi-live" means here

**Rhetorically, not literally.** A true real-time feed would be unwatchable —
geostationary imagery arrives one frame per 600 seconds, and weather at 1× barely
moves. The reference video's appeal comes from *orbital velocity*, not from real-time
observation. So a **sped-up animation is a legitimate expression of the goal, not a
fallback from it.**

Latency still matters and is genuinely good: **3.6–5.1 minutes** from Himawari-9,
**~8 minutes** from GOES-19 [measured]. That is what makes "today's weather" possible
rather than "last week's." It is a secondary quality, not the definition of success.

Two further constraints shape everything here:

- **A geostationary satellite watches Earth cycle through phases like the Moon.** At
  the subsatellite point's local midnight, the illuminated fraction runs from 0% at
  equinox to about 4% at solstice. The whole scene goes dark every night, year-round
  — not seasonally, and not just half the disk.
- **The flyover aesthetic is a low-orbit artifact.** It comes from being 400 km up
  and moving at 7.7 km/s. GEO gives cadence but no motion; polar orbits give motion
  but revisit any point only twice a day.

Three tracks are being explored in parallel, all in scope
([`docs/ROADMAP.md`](docs/ROADMAP.md)):

- **A — Orbital camera.** Motion and imagery are separable: take motion from a
  synthetic camera and imagery from whichever sensor has the right cadence.
- **B — Daily summary.** 24 hours compressed to ~60 s, terminator sweep as the clock,
  with automated detection of the day's notable weather. Sequenced first — shortest
  path to moving pictures.
- **C — Polar swath.** VIIRS strips at 375 m. Zero synthesis; every pixel and every
  motion observed.

One measured finding shapes all three: **ABI mesoscale sectors publish every 60
seconds** at ~1/70th the bytes of a full disk, so a 24-hour sequence is 48 seconds at
30 fps **with no interpolation at all**
([`featuredocs/2026-08-04-time-compression.md`](featuredocs/2026-08-04-time-compression.md)).

## Data

Anonymous, no credentials, no cost:

| Source | Slot / orbit | Cadence | Latency [measured] |
|---|---|---|---|
| **Himawari-9** (AHI) | 140.7°E | 10 min full disk | **3.6–5.1 min** |
| **GOES-19** (ABI) | 75.2°W | 10 min full disk | **~8 min** |
| **GOES-18** (ABI) | 137.0°W | 10 min full disk | ~8 min |
| **VIIRS** ×3 (NOAA-21/20, S-NPP) | sun-sync, ~824 km | ~12 h revisit | ~27–30 min |

Latency is **observation → available in S3**, which for the polar orbiters is
separate from the ~12 h revisit gap. Measured in `logs/`.

Together the GEO trio covers the Americas and the Pacific. **Nothing reachable
covers roughly 20°W to 100°E** — Africa, Europe, the Middle East, India. That gap is
the project's defining constraint. Full catalog:
[`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Getting oriented

```bash
python3 scripts/probe_env.py --json     # always run this first, in any environment
```

Stdlib only, so it works before anything is installed. It writes a timestamped
capability report to `logs/` — machine facts, host reachability, live data freshness.
Reachability differs sharply between the cloud container and a local machine — the
container filters egress by policy, a local machine generally doesn't — and every
other document here depends on knowing which you're in.

**Check the report's `tls_trust_store` line before believing it.** If TLS
verification fails, the run marks itself untrustworthy and must not be recorded as
evidence: a broken CA bundle is not an egress block.

Then:

| Read | For |
|---|---|
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | Single source of truth — status, facts, decisions, work claims |
| [`AGENT_HANDOVER.md`](AGENT_HANDOVER.md) | Cold-start briefing for any agent joining |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Three candidate tracks and why the choice is still open |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Every source, measured |
| [`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md) | Cloud vs. local, egress policy, portability rules |
| [`featuredocs/`](featuredocs/) | Design rationale — why, not what |
| [`implementation_plans/`](implementation_plans/) | What is being built, with definitions of done |

## Repository layout

```
PROJECT_STATE.md        single source of truth
AGENT_HANDOVER.md       onboarding prompt for any agent
docs/                   living reference: data sources, roadmap, environments
featuredocs/            dated design rationale, one per feature
implementation_plans/   plans, with archive/ for superseded ones
logs/                   probe reports and run records (committed — project memory)
assets/                 vendored static data (coastlines, base maps)
scripts/                standalone utilities
src/geoearth/           the pipeline (not yet built)
```

## Honesty policy

This project synthesizes imagery. That is legitimate, and it is disclosed rather
than hidden. Every design document carries a mandatory "Honesty notes" section, and
whatever appears there propagates to any published output.

Currently anticipated disclosures:

- **Any virtual camera viewpoint is fabricated.** No satellite occupies it.
- **GOES true colour uses a synthetic green channel** — ABI has no green band.
  (Himawari's AHI does, and carries no such caveat.)
- **Cloud imagery updates every 10 minutes.** Smoothness between updates is synthesized.
- **Pan-sharpening infers colour detail** it did not measure.
- **Static base layers are reference data, not observation** — including the
  city-lights layer in NOAA's GeoColor product.
- **Any upscaling beyond source resolution is stated with its factor.**

If something fabricates and isn't listed, that's a defect.

## Attribution

Imagery from NOAA/NESDIS (GOES ABI, JPSS VIIRS) and JMA (Himawari AHI), via the
[AWS Registry of Open Data](https://registry.opendata.aws/). Inspiration: Seán
Doran's *ORBIT*, and [Sen](https://www.sen.com/), who stream real 4K video from the ISS.
