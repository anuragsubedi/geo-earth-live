# Synthetic orbital camera over live geostationary imagery

**Created:** 2026-08-04 · **Status:** proposed concept, not yet built · **Supersedes:** nothing

---

## Problem

The reference aesthetic is Seán Doran's *ORBIT — A Journey Around Earth in Real
Time*: the ground streaming past beneath a low-orbit camera, limb curved against
black, terminator crossings, city lights at night. The stated goal is "a quasi-live
feed of Earth" with that feel.

Two facts are in tension:

1. That look is a **low-Earth-orbit artifact.** It comes from being 400 km up and
   moving at 7.7 km/s. A geostationary satellite is motionless over one spot; its
   view is a slowly breathing disk. No amount of processing turns a GEO feed into
   a flyover.
2. **Only GEO gives us the cadence to be "live"** — 10-minute full disks at 4–8
   minutes latency (`docs/DATA_SOURCES.md`). LEO sources revisit a given point
   about every 12 hours.

The inherited plan resolved this by abandoning the flyover and building a sped-up
daily summary. That is a good product, but it is not the stated goal.

## The idea

**Separate the two things that move.** In any orbital video, the frame changes for
two independent reasons: the camera moves, and the scene evolves. GEO imagery is
poor at the first and excellent at the second. So supply the camera motion
ourselves.

Texture a 3D Earth with live GEO composites, place a virtual camera on a
Keplerian orbit, and render. The clouds are real and 4–8 minutes old. The camera
is a mathematical fiction, exact and continuous at any frame rate.

```
GEO granules ──► composite ──► globe texture (updates every 10 min)
                                      │
orbit ephemeris ──► camera pose ──────┼──► ray-cast render ──► frames @ 60 fps
   (continuous, exact)                │
                              vendored base map + coastlines
```

### Why this is better than it sounds

The dominant motion in the output — the ground sweeping past — becomes **exact
rather than interpolated.** The inherited plan's hardest honesty problem was that
30 fps motion between 10-minute frames is entirely synthesized. Here, the
synthesized part is the camera path, which is *declared* rather than disguised,
and the observed part (cloud evolution) is left at its true 10-minute cadence.

Frame interpolation drops out of v1 entirely. That is a large simplification.

---

## Constraints, with numbers

### Resolution sets the honest camera altitude

For a camera at altitude `h` with horizontal field of view `θ`, the ground width in
frame is approximately `2·h·tan(θ/2)` (flat approximation — adequate as a design
guide, pessimistic near the limb). Dividing by output width gives the source
resolution you must have to avoid upscaling:

| Camera altitude | Ground width @ 60° FOV | Source GSD needed @ 4K | @ 1080p |
|---|---|---|---|
| 400 km (ISS) | 462 km | **120 m** | 241 m |
| 800 km | 924 km | 241 m | **481 m** |
| 1,600 km | 1,848 km | **481 m** | 963 m |
| 3,300 km | 3,811 km | 992 m | 1.98 km |
| 6,600 km | 7,621 km | 1.98 km | 3.97 km |

Against what we actually have — GOES C02 at **0.5 km**, C01/C03 at **1 km**, IR at
**2 km**, Himawari B03 at **0.5 km**:

> **You cannot honestly render an ISS-altitude view at 4K from GEO data.** It would
> be a 4× upscale. Two honest configurations exist:
>
> - **4K at ~1,600 km** camera altitude, from 0.5 km pan-sharpened colour.
> - **1080p at ~800 km**, same source. Closest to the ORBIT altitude.

Doran's original upscaled aggressively too, so upscaling is within genre — but it
gets disclosed, not hidden.

At 1,600 km, Earth's angular radius is `asin(6371/7971) = 53°`, so the limb sits
just outside a 60° frame: curvature visible at the edges, ground filling the view.
That is the ORBIT composition. By ~6,600 km the whole disk fits inside the frame
and it becomes the Apollo/DSCOVR look instead.

**0.5 km colour requires pan-sharpening.** ABI has no 0.5 km colour — only C02
(red) is 0.5 km. Standard practice is to pan-sharpen C01/C03 up to C02's grid.
ABI also has no green band at all; true colour needs a synthetic green,
conventionally `0.45·C02 + 0.10·C03 + 0.45·C01`. **Himawari's AHI has a real green
band (B02) and needs no such fabrication** — a genuine argument for making
Himawari the primary colour source.

### Orbital mechanics of the virtual camera

Circular orbit, `μ = 398,600 km³/s²`, `Rₑ = 6,371 km`:

| Altitude | Orbital velocity | Period | Ground-track speed |
|---|---|---|---|
| 400 km | 7.67 km/s | 92.4 min | 7.22 km/s |
| 800 km | 7.45 km/s | 100.7 min | 6.62 km/s |
| 1,600 km | 7.07 km/s | 118.0 min | 5.65 km/s |
| 6,600 km | 5.54 km/s | 4.08 h | 2.72 km/s |

A single GEO satellite gives usable geometry over roughly ±60° of longitude,
about 13,300 km at the equator. At 1,600 km altitude the camera crosses that in
**~39 minutes**, during which the texture refreshes about **four times**. So clouds
genuinely evolve during a pass at real-time playback — they are not frozen.

If playback is accelerated (say 10×), those refreshes land ~1 minute apart on
screen and become visible steps. Interpolation then matters again — but only as a
**morph between two co-registered texture grids**, which is a far easier and better-
conditioned problem than synthesizing full-frame motion. Defer it; measure first.

### Coverage decides the flight path

Reachable GEO covers roughly 10°E westward to 170°E — the Americas, the Atlantic,
and the Pacific — with a hole over Africa, Europe, and India (`docs/DATA_SOURCES.md`).

A camera flying a full 360° orbit would sail into unlit, untextured territory. Three
responses, in increasing cost:

1. **Fly only covered arcs.** A Pacific-to-Atlantic pass is ~40 minutes of gorgeous
   footage and needs nothing we don't already have. Start here.
2. **Vendor a static base map** (Blue Marble) under the live clouds, so the gap
   degrades to "real land, no live weather" instead of a black hole. Cheap, but the
   seam between live and static must be disclosed.
3. **Unlock EUMETSAT** for Meteosat/MTG. Free but requires registration, and the
   host is blocked from the container. This is the highest-value unlock available.

### Sampling and seams

Render by **direct inverse sampling**, not by pre-resampling to equirectangular:
for each output pixel, cast a ray, intersect the WGS-84 ellipsoid, convert to
geodetic lat/lon, forward-project into each source's `+proj=geos` grid, and sample
bilinearly. One resampling instead of two, so no compounded blur.

Where two GEO satellites both see a point, blend weighted by **satellite viewing
zenith angle** — each pixel prefers the satellite looking most steeply down at it.
Feather across the overlap. Beyond ~65–70° zenith, foreshortening stretches a 2 km
pixel past 6 km; cut the source off there rather than smear the limb.

### Night is a feature, not a defect

Roughly half of any low orbit is in darkness, and night passes with city lights
are among the most striking shots in the genre. We have **VIIRS DNB**, which
observes city lights, moonlit cloud and aurora *live* — unlike GeoColor's static
city-lights reference layer. Night side from live DNB plus IR cloud structure
would be more honest than the standard off-the-shelf composite, not less.

Caveat: DNB revisit is ~12 h and its measured publication latency was anomalously
long (200 min on 2026-08-04). Night side is a Phase-2 concern; v1 can fly daylit
arcs, which is also what makes the resolution budget work.

---

## Options considered

| Option | Verdict |
|---|---|
| **Synthetic camera over live GEO texture** | **Chosen.** Matches the goal, exact motion, no frame interpolation in v1, uses the cadence GEO is good at. |
| Real LEO imagery (VIIRS swaths) stitched into motion | Genuinely observed motion and 375 m detail, but push-broom strips are not a flyover, revisit is 12 h, and latency ~36 min. Keep as a separate track — it is a different, also-beautiful product. |
| GEO daily summary, sped up | The inherited plan. Good product, well-scoped, but explicitly not the flyover. Retained as a parallel track; shares most infrastructure. |
| Frame-interpolate GEO to 30 fps in place | Produces a smooth *static* disk. Solves the wrong problem — smoothness was never what made ORBIT compelling. |
| Wait for / build a real LEO video satellite | $10–80M and years. Out of scope, documented in `featuredocs/2026-08-04-orbit-selection.md`. |

---

## Honesty notes

Everything below must appear in the README and in the description of any published
output. This is the price of admission for synthesizing imagery.

1. **The camera does not exist.** No satellite took these frames from this vantage.
   The viewpoint is a rendered fiction over real imagery.
2. **Clouds update every 10 minutes**, not continuously. Any smoothness between
   texture refreshes is synthesized.
3. **GOES true colour uses a synthetic green channel.** ABI has no green band.
   Himawari-derived colour does not carry this caveat.
4. **Pan-sharpening infers colour detail** at 0.5 km from 1 km measurements.
5. **Any vendored base map is a static reference layer**, not live observation, and
   the boundary between live and static regions must be visible or stated.
6. **Limb regions are heavily resampled** and less trustworthy than nadir.
7. If output resolution exceeds source resolution, **say the upscale factor.**

## Open questions

- Does `h5py` + `fsspec` byte-range reading of C02 actually deliver a camera-sector
  crop cheaply enough? **This is the load-bearing assumption.** Prototype first.
- Colour balance across a GOES↔Himawari seam, given synthetic vs. real green.
- What renderer? A dependency-light option (numpy ray-cast, CPU) is portable and
  probably fast enough at 1080p; a GL/moderngl path is faster but adds an
  environment-sensitive dependency. Measure before choosing.
- Real orbital elements (vendored TLE + `sgp4`) or a clean analytic orbit? Analytic
  is simpler and, since the satellite is fictional anyway, arguably more honest.

## Revisions

- **2026-08-04** — Created.
