# assets/

Vendored static data. **Committed on purpose.**

The cloud environment blocks `naturalearthdata.com`, `gibs.earthdata.nasa.gov` and
`celestrak.org` (`docs/ENVIRONMENTS.md`). More importantly, these files never
change, so fetching them at runtime buys nothing and costs reproducibility. Vendoring
makes rendering identical, offline-capable, and version-controlled everywhere.

## What belongs here

| Asset | Purpose | Source | Status |
|---|---|---|---|
| Coastlines / borders (Natural Earth 1:50m or 1:110m) | Overlay and geolocation verification | naturalearthdata.com | **not yet vendored** |
| Blue Marble base map, downsampled | Land/ocean under live clouds; fills the Africa/Europe/India coverage gap | NASA GIBS / BMNG | **not yet vendored** |
| Colour tables / enhancement curves | IR rendering | derived | **not yet vendored** |
| TLE snapshot | Only if real orbital elements are ever wanted | celestrak.org | not needed (camera is analytic) |

## Rules

1. **Keep it small.** Downsample before committing. A 1:110m coastline set is a few
   hundred KB; the 1:10m set is tens of MB and buys nothing at 2 km pixels.
2. **Record provenance.** Every asset gets a row in the table above with its source
   and licence. Natural Earth is public domain; NASA imagery is generally
   unrestricted with attribution — confirm per asset, don't assume.
3. **Static reference layers are not observations.** A Blue Marble base under live
   clouds is a *reference layer*, and any output using it must say so — the same
   disclosure that GeoColor's static city-lights layer required. See the honesty
   notes in `featuredocs/`.
4. **No large binaries without discussion.** If something exceeds ~25 MB, raise it
   before committing.
