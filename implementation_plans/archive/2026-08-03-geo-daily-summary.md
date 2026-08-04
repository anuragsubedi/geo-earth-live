> **ARCHIVED — `SUPERSEDED` on 2026-08-04.**
>
> **Superseded by:** [`../2026-08-04-shared-core.md`](../2026-08-04-shared-core.md)
>
> **Provenance:** written in a prior Claude Code session (transcript exported as
> `session_transcript.md`) and inherited into this repo as its founding plan.
> Preserved verbatim below the rule. **Do not edit it** — it is a record of what was
> believed on 2026-08-03, not a live document.
>
> **Why it was superseded:** its render tier depended on `cdn.star.nesdis.noaa.gov`
> (pre-rendered GeoColor JPEGs), which is blocked by egress policy in this project's
> cloud environment — measured in `logs/2026-08-04T153908Z-environment-probe.md`.
> `nhc.noaa.gov` is likewise blocked, removing its cyclone-position source. The
> successor plan records the full delta.
>
> **What remains valid and worth rereading:** the memory strategy (one frame in
> flight, never hold the stack), the hold-out PSNR/SSIM interpolation metric, the
> insistence on reusing NOAA L2 products instead of re-deriving them, the day-of-year
> path warning, and the honesty requirements around interpolated frames and
> GeoColor's static city-lights layer. All of those carried forward.

---

# GEO Earth Daily — Implementation Plan

## Context

The starting question was whether a near-live view of Earth from geostationary orbit could be broadcast like the linked ISS "ORBIT" video. Research in this conversation established:

- A **live** GEO stream is a $10–80M satellite program, and the killer isn't bandwidth — it's that the entire visible disk goes dark every night, year-round (phase angle at local midnight yields 0–4% illumination), not just during eclipse seasons.
- The **sped-up daily summary** dissolves that problem: at ~1440× speedup the day/night terminator sweep becomes the clock that makes the video readable, and IR bands provide illumination-independent observation.

This project builds the second thing: a reproducible daily job that turns 24 hours of GOES-19 full-disk imagery into a short annotated video plus a text recap of the day's notable weather.

**Constraints:** standalone project (not DSCI 411 — no Hadoop/Spark/Kafka/Zeppelin), must run on a 16 GB MacBook.

**Assumption flagged:** "after the rendering pipeline" is read as *the plan should also cover what happens downstream of rendering* — the analysis/annotation layer and publishing. Milestones M2–M5 cover that. Correct me if you meant something narrower.

---

## Key design decision: two tiers with different data sources

The single most important choice, and it's what makes this fit in 16 GB.

| Tier | Purpose | Source | Volume/day |
|---|---|---|---|
| **Render** | The pixels you see | Pre-rendered GeoColor JPEGs from NOAA STAR CDN | **~430 MB** |
| **Analysis** | What to annotate | GOES-19 L2 netCDF from `noaa-goes19` S3 | **~1–2 GB** |

**Why not build the composite ourselves:** `ABI-L2-MCMIPF` (all 16 bands, 2 km) is ~300–450 MB *per frame* — 43–65 GB/day. Off the table on a laptop. And [GeoColor](https://rammb.cira.colostate.edu/research/goes-r/proving_ground/cira_product_list/geocolor_imagery_detailed.asp) already solves the day/night blend (true color by day; bands 7+13 at night over a static VIIRS city-lights layer) better than a first attempt would.

Verified CDN endpoint and naming:

```
https://cdn.star.nesdis.noaa.gov/GOES19/ABI/FD/GEOCOLOR/
  20262061630_GOES19-ABI-FD-GEOCOLOR-5424x5424.jpg
  └─ YYYYDDDHHMM (year, day-of-year, UTC hour, minute) = scan start
```

Resolutions available: 339, 678, 1808, 5424, 10848, 21696 (square). **Use 5424×5424** (~2–4 MB each): downsampling 5424 → 3840 for 4K output is a 0.71× supersample, which is the right quality/size point. 21696 runs 28–56 MB per frame and buys nothing at 4K.

**Consequence — no satpy needed for v1.** GeoColor JPEGs sit on the standard ABI fixed grid, so annotation placement only needs `pyproj` with a `+proj=geos` CRS. This avoids satpy/pyresample, which are the two dependencies most likely to fight you on macOS ARM without conda. satpy becomes an optional Phase-2 dependency only if custom composites are wanted.

---

## Repository

New standalone repo, **created private** (flip to public later — say the word if you want it public from the start).

Local path: `~/Projects/geo-earth-daily` (outside `Desktop/DSCI 411/`, since this is unrelated to the coursework there).

```
geo-earth-daily/
├── README.md
├── pyproject.toml
├── .gitignore                 # data/, out/, *.mp4, .venv/
├── config.yaml                # satellite, resolution, thresholds, output specs
├── src/geoearth/
│   ├── config.py              # load/validate config.yaml
│   ├── fetch_frames.py        # CDN GeoColor JPEG fetch + gap handling
│   ├── fetch_science.py       # anon S3: band 13 CMIPF, FDCF fire product
│   ├── geo.py                 # ABI fixed-grid <-> lat/lon (pyproj)
│   ├── detect.py              # convection, fires, storm sectors
│   ├── compose.py             # annotate frames, build sector crops
│   ├── render.py              # ffmpeg: interpolation + encode + concat
│   ├── summarize.py           # text recap generation
│   └── cli.py                 # `geoearth daily --date YYYY-MM-DD`
├── tests/
│   ├── test_geo.py            # projection round-trip
│   └── test_detect.py         # threshold logic on fixture arrays
├── data/                      # gitignored working dir
└── out/                       # gitignored render output
```

**Dependencies (deliberately small):** `httpx`, `pillow`, `numpy`, `pyproj`, `xarray`, `netCDF4`, `s3fs`, `typer`, `pyyaml`. Plus `ffmpeg` via Homebrew. Standard `venv` + `pip` — no conda required.

---

## Memory strategy (the 16 GB constraint)

Non-negotiable rules, enforced in code:

1. **Never hold the frame set in RAM.** Process one frame at a time, write annotated PNG/JPEG to `data/frames/`, let ffmpeg read the file sequence. Peak RSS stays under ~1.5 GB.
   - One decoded 5424² RGB frame = 88 MB. One band-13 float32 array = 118 MB. Both fine individually; 144 of either is not.
2. **Analysis tier runs at 30-min cadence**, not 10-min (48 frames/day instead of 144). Convection and fire detection don't need 10-min sampling, and this cuts the S3 pull to ~1–2 GB/day.
3. **Tracking uses a rolling 3–5 frame window**, never the full stack.
4. **Interpolate at reduced resolution.** RIFE/FILM via PyTorch MPS at 4K wants >10 GB unified memory — too risky here. See render section.

Disk: ~1.5–2 GB/day of intermediates. `data/` is purged after each successful render.

---

## The video format

A 6-second raw timelapse is technically correct and useless as a "summary." The output is a **~60 s edit**:

| Segment | Length | Content |
|---|---|---|
| Title card | 3 s | Date, satellite, coverage |
| Full-disk day loop | 25 s | 144 frames, 4–6× interpolated, terminator sweep |
| Sector callouts | 3 × 8 s | Zoomed crops on the day's notable features |
| Summary card | 5 s | Text recap |

The sector crops (1024×1024) are cheap to interpolate. Only the full-disk segment is expensive — budget **20–60 min** of ffmpeg time for it on an M-series CPU. This is a background/overnight job, not interactive.

**Interpolation:** v1 uses ffmpeg's built-in motion compensation — zero extra dependencies, no model weights, memory-light:

```bash
ffmpeg -framerate 24 -i frames/%04d.jpg -filter:v "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1" -c:v libx264 -crf 18 out/fulldisk.mp4
```

RIFE at reduced resolution (2048², then upscale) is a documented Phase-2 upgrade, not a v1 requirement.

**Honesty requirement:** interpolated motion is *synthesized, not observed*. True cloud displacement between real frames is 0.3–5 px at 2 km, so it's plausible — but the README and video description must say frames are interpolated. Same applies to GeoColor's city lights, which are a **static VIIRS reference layer, not live observation**.

---

## Analysis layer — reuse existing L2 products, don't rebuild

This is where most of the "don't write code that already exists" savings are:

| Feature | Approach |
|---|---|
| **Tropical cyclones** | Pull `https://www.nhc.noaa.gov/CurrentStorms.json` for active storm lat/lon. Crop sectors around them. Far more reliable than detecting from scratch. |
| **Wildfires** | Use NOAA's existing `ABI-L2-FDCF` (Fire/Hot Spot Characterization, Full Disk) product. Already an operational L2 product — do not re-derive from band 7. |
| **Deep convection / overshooting tops** | The one thing worth computing: band 13 (10.3 µm) brightness temperature < ~200 K, connected-component label, area threshold. This is genuinely simple and is the project's own contribution. |
| **Dust/ash** | Optional Phase 2: split-window difference (band 15 − band 13). |

Sector ranking for the callouts: score candidates by area × (threshold − min BT) for convection, by FRP for fires, by intensity for cyclones; take the top 3.

**Geolocation (`geo.py`)** — the one fiddly bit:

```python
CRS("+proj=geos +h=35786023 +lon_0=-75.2 +sweep=x "
    "+a=6378137 +rf=298.257222096")
```

GOES-19 (GOES-East, operational since 2025-04-04) sits at 75.2°W. **Verify `longitude_of_projection_origin` from the `goes_imager_projection` variable in an actual netCDF granule once, then pin it in `config.yaml`** — older files carry −75.0 and the mismatch is ~15 km of annotation offset.

---

## Practical details that will otherwise bite

- **Missing frames are normal.** Build the expected 144-timestamp list, fetch what exists, log gaps. Outages cluster around local midnight near the equinoxes (solar keep-out) and during calibration. The renderer must hold-frame or interpolate across gaps rather than crash.
- **The CDN directory listing is HTML**, not an API. Parse it once per run and cache; don't hammer it per-frame.
- **S3 access is anonymous** — `s3fs.S3FileSystem(anon=True)`, no AWS credentials needed.
- **Timestamps are day-of-year**, not month/day. Get the `%Y%j%H%M` conversion right and unit-test it.

---

## Milestones

| | Deliverable | Definition of done |
|---|---|---|
| **M0** | Repo scaffold, private GitHub repo, venv, config | `geoearth --help` runs |
| **M1** | Fetch + plain timelapse | An MP4 of yesterday exists, no analysis. **This is the "it works" moment — get here first.** |
| **M2** | Geolocation + annotation | Coastline/graticule overlay lands correctly on the disk |
| **M3** | Detection + text summary | Top-3 features identified, sector crops generated, recap text written |
| **M4** | Interpolation + full edit | The ~60 s assembled video |
| **M5** | Daily automation | Scheduled and running unattended |

**M5 note:** a macOS `launchd` job requires the laptop awake. Because the render tier is only ~430 MB/day, **GitHub Actions is a viable free alternative** (7 GB RAM, 14 GB disk, 6 h job limit — all sufficient) and removes the laptop dependency entirely. Decide at M5.

---

## Verification

1. **Projection round-trip** (`tests/test_geo.py`): known landmark lat/lon → fixed-grid pixel → back to lat/lon. Assert < 1 px error. Visually confirm by overlaying a coastline vector on one frame.
2. **Detection sanity**: run against a date with a known major hurricane; assert it appears in the top-3 sectors.
3. **Interpolation quality — the real metric**: hold out every other real frame, interpolate across the resulting 20-min gap, score PSNR/SSIM against the withheld truth. Report as a function of cloud regime. This turns "looks smooth" into a defensible number and is the most interesting result in the project.
4. **Memory guardrail**: assert peak RSS via `resource.getrusage` in the end-to-end test; fail the build above ~2 GB.
5. **End-to-end**: `geoearth daily --date <yesterday>` produces a playable MP4 plus a text recap, from a clean `data/`.

---

## Explicitly out of scope for v1

- Global mosaic (GOES-18 / Himawari-9 / MTG-I1) — three more sensors with different formats and calibrations
- Live/rolling stream mode and RTMP push to YouTube
- Custom composites from raw netCDF via satpy
- ML-based interpolation (RIFE/FILM)
