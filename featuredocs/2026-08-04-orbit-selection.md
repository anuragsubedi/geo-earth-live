# Orbit selection: which orbit dissolves the darkness problem

**Created:** 2026-08-04 · **Status:** reference analysis · **Supersedes:** nothing

---

## Problem

Prior work established that a visible-light geostationary livestream fails for a
reason that is geometric, not technical: **a GEO satellite watches Earth cycle
through phases like the Moon, once per day.** At the subsatellite point's local
midnight the phase angle is `180° − δ☉`, so the illuminated fraction
`(1 + cos θ)/2` runs from **0% at equinox to about 4% at solstice**. The entire
scene goes black every night, year-round. Satellite eclipse — up to ~70 min/night
for six weeks around each equinox — is a separate, seasonal, battery-side problem
that happens to land on top of the same hours.

The question this document answers: **which non-geostationary orbits avoid that,
and do any of them also supply natural motion?**

This is written as design-space reference. It informs source selection today and
would inform hardware if the project ever grew that far. It is not a proposal to
launch anything.

---

## The candidates

### Sun-synchronous LEO — the direct answer

~700–830 km, inclination ~98°, retrograde. Earth's oblateness (J2) regresses the
orbit plane; at that inclination the regression is tuned to **+0.9856°/day**, exactly
Earth's mean motion around the Sun. The orbit plane therefore holds a fixed angle
to the Sun, and the satellite crosses the equator at the **same local solar time
forever**.

Pick a mid-morning node — 10:00–10:30, as Landsat, Sentinel-2 and Terra do — and
the daylight track is well-lit on every pass, permanently. **There is no day/night
cycle in the imagery at all**, not because the lighting was fixed but because you
only ever image one local time.

The satellite still eclipses (a power-system concern). The pictures never do.

**And the motion comes free.** At ~98° inclination the orbit is retrograde, ground
speed is ~6.6–7.5 km/s, and there are ~14.5 orbits per day. Because Earth turns
underneath, each successive ground track shifts about **24.8° west**. Fourteen
strips a day sweeping westward around the planet *is* the accelerated view — and
critically, it is **observed motion, not interpolated**.

There is a second, underrated advantage. Push-broom imagers like VIIRS have no
full-disk scan bottleneck: along-track time *is* the scan, and a granule is ~85
seconds. The 10-minute cadence ceiling that defines GEO simply does not exist here.

*Available to us today:* VIIRS on Suomi-NPP, NOAA-20, NOAA-21 — all reachable
(`docs/DATA_SOURCES.md`). LTAN 13:25, 375 m I-bands, ~36 min latency.

### Dawn–dusk sun-synchronous — the extreme case

LTAN 06:00 or 18:00. The orbit rides the terminator and stays in near-continuous
sunlight, **eclipse-free for much of the year**. Sentinel-1, RADARSAT and Aeolus
use it, mostly for power and thermal stability.

Honest tradeoff: the ground below is always at sunrise or sunset. Very long
shadows, dramatic relief, low sun angle — striking, but dim at nadir and nothing
like the bright-Earth look of the reference video. Solves the constraint by
choosing the one lighting condition that is most atmospheric and least neutral.

### Molniya / Tundra — the most visually interesting

Highly elliptical, at the **critical inclination 63.43°** (where `4 − 5sin²i = 0`,
so apsidal precession vanishes and apogee stays put). Molniya: ~12 h period,
e ≈ 0.74, apogee ~39,800 km locked over the northern hemisphere. Tundra: 24 h.

Two properties no other orbit has:

1. **Kepler's second law gives you a free dwell.** The satellite loiters near
   apogee for roughly 6–8 hours of each 12-hour orbit, then whips through perigee.
   You get quasi-geostationary viewing of the **Arctic**, which GEO geometrically
   cannot see at all.
2. **Range varies from perigee to ~40,000 km, so Earth naturally zooms in and out
   over the orbit.** A dolly shot no other orbit produces.

*Real precedent:* Russia's **Arktika-M1 (2021) and M2 (2023)** fly exactly this,
carrying MSU-GS — a GEO-class full-hemisphere imager at 15–30 minute cadence.
*Blocker:* distribution is via Roshydromet, not AWS. Not reachable, and unlikely
to become so.

### Sun–Earth L1 — the theoretical optimum for darkness

1.5 million km sunward. From there Earth is **always a fully-lit disk**: no night
side, no eclipse, ever. It is the only geometry that eliminates the problem
outright rather than working around it.

DSCOVR sits in a Lissajous orbit about L1, deliberately offset so EPIC views Earth
at 4–15° phase angle — avoiding both exact-full specular glint and the solar RF
interference cone.

Costs: Earth subtends only ~0.5° (about a Moon's width), EPIC delivers 13–22
images/day at 12–36 h latency. **Perfect illumination, no motion, no liveness** —
the exact inverse of what the reference video is made of. And `epic.gsfc.nasa.gov`
is blocked from the container.

(Sun–Earth L2, where JWST sits, is the trap: from there Earth is permanently *new*
— a black disk against the Sun.)

### Very low Earth orbit — more motion, more problems

250–350 km. Closer means larger apparent ground motion and finer resolution for a
given aperture; period is still ~89–91 min. The cost is atmospheric drag requiring
continuous propulsion. Buys aesthetics, not availability, and does nothing for
darkness. Half of every orbit is still night.

### Inclined geosynchronous — a footnote

A geosynchronous orbit with non-zero inclination traces a figure-eight ground track;
the disk gently nods over 24 hours. Marginally more interesting than a static disk,
free (you skip inclination station-keeping), and irrelevant to darkness. Noted for
completeness.

---

## Comparison

| Orbit | Darkness solved? | Natural motion? | Live data reachable? |
|---|---|---|---|
| **Sun-sync LEO (mid-morning)** | **Yes** — always the same local time | **Yes** — 6.6 km/s, 14.5 orbits/day | **Yes** — VIIRS ×3 |
| Dawn–dusk sun-sync | Yes, but always golden-hour | Yes | Not directly |
| Molniya / Tundra | Partly — high-latitude dwell | **Yes, plus natural zoom** | No (Arktika-M) |
| Sun–Earth L1 | **Completely** | No | No (blocked; 12–36 h latency) |
| VLEO | No | Yes, strongest | No |
| GEO / inclined GSO | No | No | **Yes** — GOES ×2, Himawari |

---

## Decision

**Nothing here changes what we build from — it changes what we build.**

The orbit that solves both constraints, sun-synchronous LEO, is reachable as data
(VIIRS) but at 12-hour revisit and ~36-minute latency. It cannot carry a live feed.
The orbit with the cadence to be live, GEO, cannot escape the darkness or supply
motion.

So the resolution is not to pick an orbit. It is to **take motion from a synthetic
camera and imagery from whichever real sensor has the right cadence** — see
`featuredocs/2026-08-04-orbital-camera.md`. That approach lets us fly *any* of these
orbits as a virtual camera, including a Molniya zoom-out or an L1 full-disk hold,
without launching anything.

Two concrete follow-ons for source selection:

1. **A sun-synchronous VIIRS track is worth building** as its own product — real
   observed motion, 375 m, never dark. Slow and non-live, but authentic in a way
   the synthetic camera is not.
2. **DSCOVR/EPIC is worth revisiting on a local machine**, where `epic.gsfc.nasa.gov`
   is likely reachable. A perpetually-full Earth rotating once per day is a beautiful
   loop and needs almost no processing.

## Honesty notes

- No satellite in this project's outputs flies any of these orbits. Where a virtual
  camera imitates one, say which and say that it is virtual.
- The 0%/4% illumination figures are geometry, not measurement; they follow from
  phase angle `180° − δ☉` and are worth re-deriving rather than trusting.
- Arktika-M and FY-4 capabilities here are from published documentation, not
  measured by us — we have no access to either.

## Revisions

- **2026-08-04** — Created, from analysis in the inherited session plus this
  session's reachability probe.
