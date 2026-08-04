# Data sources

Living catalog of satellite imagery we can build from. Every number marked
**[measured]** came from a probe in `logs/`; everything else is documentation or
estimate and is labelled as such.

**Reachability is environment-specific.** Every "blocked" verdict below means
*blocked in the cloud container* (`logs/2026-08-04T153908Z-environment-probe.md`).
**On a local machine none of them are blocked** — a probe on 2026-08-04 returned 200
for all 23 hosts, including every host the container denies
(`logs/2026-08-04T163938Z-environment-probe.md`). Re-run
`python3 scripts/probe_env.py` before relying on this file. See
`docs/ENVIRONMENTS.md`.

> **This does not promote blocked sources to the required path.** Production may run
> in the container, so S3 + PyPI remains the only guaranteed substrate. What local
> reachability buys is the ability to *evaluate* those sources now (D2, D7).

> **Two figures in earlier revisions of this file were wrong**, both from probe
> defects rather than from the data. VIIRS DNB was never "anomalously stale"
> (`logs/2026-08-04T164009Z-experiment-viirs-latency.md`), and a local report once
> claimed every host was blocked when a CA bundle was missing. Both are fixed.
> **Age of the newest object is not publication latency** — for a polar orbiter it is
> latency *plus* revisit gap. Use `scripts/viirs_latency.py` for the former.

---

## Tier 1 — Geostationary (the backbone)

Three of the five operational GEO weather slots are reachable anonymously on AWS.
This is the highest-cadence, lowest-latency imagery available to us by a wide margin.

| Satellite | Slot | Instrument | Full-disk cadence | Bucket | Reachable |
|---|---|---|---|---|---|
| **GOES-19** (GOES-East) | 75.2°W | ABI, 16 bands | 10 min (Mode 6) | `noaa-goes19` | **yes** |
| **GOES-18** (GOES-West) | 137.0°W | ABI, 16 bands | 10 min | `noaa-goes18` | **yes** |
| **Himawari-9** | 140.7°E | AHI, 16 bands | 10 min | `noaa-himawari9` | **yes** |
| Meteosat-12 / MTG-I1 | 0° | FCI | 10 min | EUMETSAT Data Store | **no** (needs account; host blocked in container, open locally) |
| FY-4B | 105°E | AGRI | 15 min | NSMC (China) | **no** |

### Coverage and the gap that matters

GOES-19 covers the Americas and Atlantic. GOES-18 covers the eastern Pacific and
western North America. Himawari-9 covers Asia-Pacific and Australia. Between
them they see roughly from 10°E westward across the Pacific to 170°E — call it
**60% of longitudes with usable viewing geometry.**

The hole runs roughly **20°W to 100°E: Africa, Europe, the Middle East, India,
and the western Indian Ocean.** That is Meteosat and FY-4 territory, and neither
is reachable today. This is the single most consequential fact in this document,
because it decides what "a view of Earth" can actually mean for us:

- A **full-globe** product needs the gap filled (EUMETSAT account, or a polar-orbiter
  mosaic, or a static base layer under live clouds).
- A **Pacific-and-Americas** product needs nothing extra and can start immediately.

See `docs/ROADMAP.md` — this shapes the track ordering.

### Measured sizes and latency

**[measured]** 2026-08-04, GOES-19 `ABI-L2-CMIPF` (Cloud & Moisture Imagery, full disk),
one 10-minute frame:

| Band | Wavelength | Native res | Size/frame |
|---|---|---|---|
| C01 (blue) | 0.47 µm | 1 km | 73.6 MB |
| **C02 (red)** | 0.64 µm | **0.5 km** | **318–435 MB** |
| C03 (veggie NIR) | 0.86 µm | 1 km | 83.8 MB |
| C07 (shortwave IR) | 3.9 µm | 2 km | 25.2 MB |
| C13 (clean longwave IR) | 10.3 µm | 2 km | 22.7 MB |
| C15 (dirty longwave IR) | 12.3 µm | 2 km | 22.4 MB |
| `MCMIPF` (**all 16 bands, all at 2 km, one file**) | — | 2 km | 332 MB |
| `FDCF` (fire/hotspot L2) | — | 2 km | 1.7 MB |

Full-disk fixed grid: 5424² at 2 km, 10848² at 1 km, 21696² at 0.5 km.

**C02 size varies with the scene, so treat it as a range, not a constant.** Across
probes on 2026-08-04 the observed span was **318–435 MB** — GOES-19 413.7 and
414.6 MB, GOES-18 318.1 and 323.5 MB. These files are internally compressed, so a
cloudier or higher-contrast disk costs more bytes, and GOES-18's Pacific disk is
consistently cheaper than GOES-19's. **Any budget or threshold expressed in absolute
bytes will drift; express it as a fraction of the actual file** (as gate G1 does).

**Publication latency [measured]:** a scan starting 14:00:20Z ended 14:09:51Z and its
objects appeared in S3 at **14:10:08Z — about 17 seconds after scan end**, ~10 minutes
after scan start. Substantially better than the 30–90 s the inherited draft assumed.

### Sub-disk sectors — the cadence that changes the design

ABI does not only scan full disks. **[measured]** for
`noaa-goes19/ABI-L2-CMIPM/2026/216/14/` and `ABI-L2-CMIPC/`:

| Product | Coverage | Cadence | Frames/hour | C13 size | C02 size |
|---|---|---|---|---|---|
| `CMIPF` full disk | hemisphere | 600 s | 6 | 22.7 MB | 318–435 MB |
| `CMIPC` CONUS | ~5000×3000 km | **300 s** | 12 | ~11.6 MB | — |
| **`CMIPM1` / `CMIPM2` mesoscale** | ~1000×1000 km each | **60 s** | **60 each** | **0.31 MB** | **4.4 MB** |

**Two independent mesoscale sectors, 60-second cadence, all 16 bands, at roughly
1/70th the bytes of the full-disk equivalent.**

This matters more than its size suggests. At 60 s cadence a 24-hour sequence is 1,440
real frames — **48 seconds at 30 fps with no interpolation at all**
(`featuredocs/2026-08-04-time-compression.md`). It is the only reachable source that
yields smooth, watchable, entirely un-synthesized motion.

Caveats: coverage is a small box, not a disk; and **NOAA repositions the sectors to
follow active weather**, so the footprint is not fixed and geolocation must be read
per granule. A 24-hour sequence may span a reposition and will not be spatially
continuous across it.

### Pre-rendered composites — cheap pixels, environment-dependent

NOAA/CIRA publish **GeoColor** as finished JPEG (true colour by day; bands 7+13 at
night over a static VIIRS city-lights layer) at `cdn.star.nesdis.noaa.gov`, in sizes
from 339² to 21696². At ~2–4 MB for 5424², a full day is ~430 MB — an order of
magnitude cheaper than compositing from netCDF, and operational quality.

**Blocked in the cloud container; confirmed reachable (200) on a local machine
2026-08-04.** It remains a legitimate and fast route to a presentable product, and it
is the inherited plan's choice. Treated as one of four open night-side options in
`featuredocs/2026-08-04-night-side-compositing.md`. Its cost is the disclosure that
the city lights are a static database rather than observation.

Because the host answers locally, **the night-side four-way experiment is runnable
today** — it was the one experiment gated on a local machine. It cannot become a
required-path dependency while production may run in the container.

**Himawari-9 is the efficiency winner [measured]:** AHI L1b full disk is delivered as
**10 bzip2-compressed segments** per band. Newest-frame age across three probes:
**4.6, 3.6 and 5.1 minutes** — consistent with a 10-minute scan plus a few minutes of
publication, and the best latency of any source here.

| Band | Res | Size/segment | Size/frame (×10) |
|---|---|---|---|
| B03 (red, 0.64 µm) | 0.5 km | 8.40 MB | ~84 MB |
| B13 (10.4 µm) | 2 km | 1.13 MB | ~11 MB |
| B16 (13.3 µm) | 2 km | 0.92 MB | ~9 MB |

Himawari's IR is roughly **half the bytes of the GOES equivalent** thanks to bz2, and
segmentation means you can fetch only the latitude bands you actually need.

### Two real advantages of Himawari over GOES

1. **AHI has a true green band** (B02, 0.51 µm). ABI does not — GOES true colour
   requires a *synthesized* green, conventionally `0.45·C02 + 0.10·C03 + 0.45·C01`
   (CIRA). That synthetic green is a fabrication and must be disclosed. Himawari
   needs no such caveat.
2. **Lower latency and lower volume**, as measured above.

Its disadvantage: HSD is a bespoke binary format (`.DAT.bz2`), not netCDF. `satpy`'s
`ahi_hsd` reader handles it; hand-rolling is not advisable.

---

## Tier 2 — Polar-orbiting LEO (real motion, real resolution)

Sun-synchronous orbit at ~824 km, ~98.7° inclination, LTAN ~13:25. Three VIIRS
instruments fly the same plane phased about 50 minutes apart.

| Satellite | Launched | Bucket | Reachable |
|---|---|---|---|
| NOAA-21 (JPSS-2) | 2022 | `noaa-nesdis-n21-pds` | **yes** |
| NOAA-20 (JPSS-1) | 2017 | `noaa-nesdis-n20-pds` | **yes** |
| Suomi-NPP | 2011 | `noaa-nesdis-snpp-pds` | **yes** |

**VIIRS characteristics:** 3060 km swath, ~85 s per granule, all 22 bands published
as separate per-band SDR products (`VIIRS-M1-SDR` … `VIIRS-M16-SDR`, `VIIRS-I1-SDR` …
`VIIRS-I5-SDR`, `VIIRS-DNB-SDR`), each with matching geolocation
(`VIIRS-MOD-GEO-TC` for M-bands, `VIIRS-IMG-GEO-TC` for I-bands).

- **I-bands: 375 m** — the highest-resolution imagery reachable to us at useful cadence.
- **M-bands: 750 m** — the multispectral workhorse.
- **DNB (day-night band): 750 m** — near-constant contrast, sensitive enough to image
  **city lights, moonlit cloud, aurora, and fires at night.**

**[measured]** `logs/2026-08-04T164009Z-experiment-viirs-latency.md`, NOAA-21,
UTC day 2026-08-04, from granule filename timestamps (no downloads):

| Product | Granules/day | **Publication latency (median)** | min–max | Coverage gaps > 5 min |
|---|---|---|---|---|
| `VIIRS-DNB-SDR` | 691 | **26.8 min** | 10.9 – 57.0 | none |
| `VIIRS-M5-SDR` | 666 | **30.3 min** | 11.1 – 57.0 | none |

Granule sizes are variable: M5 observed at 3.93–9.76 MB, DNB at 8.61–9.15 MB.

> **Correction.** Earlier revisions of this file said the newest DNB object was
> **200 minutes** old and called it "anomalously stale… re-measure before designing
> around DNB latency." That was a defect in `probe_env.py`, which listed only the
> first 1000 keys of a flat daily prefix and so never saw the newest granule. **DNB
> is marginally *faster* than M5 and publishes continuously.** The re-measure
> instruction is discharged.
>
> The general lesson is worth carrying: **age of the newest object ≠ publication
> latency.** For a polar orbiter, age is latency *plus* the revisit gap. Use
> `scripts/viirs_latency.py` when you need latency alone.

### Why DNB is strategically important

CIRA GeoColor's city lights are a **static multi-year VIIRS composite, not live
observation** — a disclosure burden the inherited plan correctly flagged. VIIRS DNB
is an actual observation of *this* night, so it captures outages, fires and shipping
that a static layer cannot.

It **reduces** the disclosure rather than removing it. VIIRS's night pass is near
01:25 local, so a GEO night frame can be **up to ~7 hours away in time** from the DNB
observation lighting it, from a different sensor and viewing geometry. And DNB images
cloud by reflected *moonlight*, so its cloud detail varies over the lunar cycle and
largely vanishes near new moon.

**Latency is not among its problems** — ~27 min, measured. Note that *continuous
publication* is not *continuous coverage of a given place*: granules appear all day,
but revisit at any single point is still ~12 h per satellite. The binding constraints
on live city lights are **temporal offset and lunar phase**, not freshness.

Better, not caveat-free. Fully worked through, alongside the other three night-side
options, in `featuredocs/2026-08-04-night-side-compositing.md`.

### Why LEO is not a drop-in replacement for GEO

Revisit at any given point is ~12 hours per satellite. You get strips, not a
persistent view. LEO gives you *resolution and genuine motion*; GEO gives you
*cadence and persistence*. The interesting designs use both.

---

## Tier 3 — Not reachable now, worth knowing

| Source | What it uniquely offers | Blocker |
|---|---|---|
| **DSCOVR / EPIC** (Sun–Earth L1) | The **always-fully-lit** full disk. Zero night side, zero eclipse, ever — the only geometry that fully dissolves the darkness problem. 10 narrowband channels, 2048². | `epic.gsfc.nasa.gov` blocked. ~13–22 images/day and 12–36 h latency make it archival, not live. Also available via `api.nasa.gov`. |
| **Meteosat-12 / MTG-I1** (0°) | Fills the Africa/Europe/India gap. FCI, 10-min full disk, 500 m VIS. | EUMETSAT Data Store: free but requires registration. Host blocked in container, **reachable locally [measured]** — so registration, not egress, is now the only barrier. **Highest-value unlock in this table.** |
| **Arktika-M1 / M2** | Molniya orbit (12 h, i=63.4°, apogee ~40,000 km). GEO-class full-hemisphere imaging **of the Arctic**, which no GEO satellite can see. Range varies from perigee to apogee, so Earth naturally zooms. | Roshydromet distribution; not on AWS; practical access unclear. |
| **FY-4B** (105°E) | Also fills part of the gap. AGRI, 15 min. | NSMC portal, registration, blocked. |
| **Sentinel-3 OLCI** | 300 m, 1270 km swath, 10:00 LTAN — better-lit than VIIRS's 13:25. | Copernicus/EUMETSAT; blocked. |
| **Sentinel-2 MSI** | 10 m. | `sentinel-s2-l1c` reachable but **requester-pays** (needs AWS credentials); 5-day revisit makes it useless for live. |
| **Sen (SpaceTV-1, ISS)** | Actual 4K video from space, ~60 m/px. The commercial proof the concept works. | Proprietary. Reference, not a source. |

---

## Ancillary data

Status column is **container** reachability; all four hosts answer locally
[measured]. The fallbacks stand regardless — see the note below.

| Need | Preferred source | Status (container) | Fallback |
|---|---|---|---|
| Coastlines / borders / graticule | Natural Earth vectors | **blocked** | **Vendor into `assets/`** — small, static, versioned. Do this regardless; it removes a network dependency from rendering. |
| Global base map (land/ocean under clouds) | NASA GIBS Blue Marble | **blocked** | Vendor a single downsampled BMNG tile set into `assets/`. Static by nature, so vendoring costs nothing in freshness. |
| Tropical cyclone positions | `nhc.noaa.gov/CurrentStorms.json` | **blocked** | Derive from ABI C13 brightness-temperature minima ourselves, or find an S3-hosted best-track mirror. Open question. |
| Orbital elements (TLE) | celestrak.org | **blocked** | Not needed for a *synthetic* camera — we define the orbit. If real TLEs are ever wanted, vendor a snapshot and propagate offline with `sgp4` (PyPI, reachable). |
| Solar geometry (terminator, phase) | computed | n/a | `pyorbital` or direct ephemeris math. No network needed. |

**Note on vendored assets:** anything static and small (coastlines, base maps, colour
tables, a TLE snapshot) belongs in `assets/` committed to the repo. It makes the
pipeline reproducible offline and identical across environments, which is worth far
more than the few MB.

**Local reachability does not retire vendoring — it enables it.** These hosts being
open locally is precisely how the assets get *into* `assets/`: fetch once here, commit
the result, and the render path stays offline and identical in the container. Fetching
them at runtime would reintroduce the dependency that vendoring exists to remove.

---

## Access mechanics

**Anonymous S3 — no AWS account needed** for every NOAA bucket above:

```python
# plain HTTPS, stdlib
urllib.request.urlopen("https://noaa-goes19.s3.amazonaws.com/<key>")

# or, with s3fs
import s3fs; fs = s3fs.S3FileSystem(anon=True)
fs.ls("noaa-goes19/ABI-L2-CMIPF/2026/216/15/")
```

Path conventions differ and this bites people:

- GOES: `<product>/YYYY/DDD/HH/` — **day-of-year**, not month/day.
- Himawari: `AHI-L1b-FLDK/YYYY/MM/DD/HHMM/` — calendar date, and the minute
  directory is the scan start.
- VIIRS: `<product>/YYYY/MM/DD/` — flat within a day, ~1000 granules.

Both partition schemes sort lexicographically in chronological order, which is why
`scripts/probe_env.py` can find the newest granule by walking last-prefix repeatedly.

**Byte-range reads are the key optimization, and they work [measured]** —
`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`. netCDF4 *is* HDF5, chunked and
internally compressed, so with `h5py` over `fsspec` a spatial region can be read
without downloading the file. Measured on a 435.38 MB C02 granule: a 2048² sector in
**15.7% of the bytes, 15.39 s** from outside AWS, pixels bit-identical to a full read.
This was gate G1 and it **passed**; it is now a measurement, not an assumption.

**But the geometry is not what you would guess.** `CMI` is chunked **(6, 21696)** —
full-width 6-row strips — so **byte cost tracks sector height and ignores width
entirely**. A 2048-row band costs **54.05 MB whether it is 2048 or 21696 px wide, the
same figure to the byte**; cost is **26.4 kB/row**, linear, with ~4096 rows the
practical ceiling. Read **row bands, not square tiles**, and set `cache_type`
explicitly — fsspec's common `"bytes"` default over-fetches to 27.1% and would fail
a 25% budget, where `"readahead"` at a 4 MiB block lands at 15.7%.

**Colocate with the data.** All NOAA Open Data buckets live in `us-east-1`. Compute
in that region gets near-line-rate transfer and zero egress cost. This matters more
than any amount of parallelism — see `docs/ROADMAP.md` on compute.

---

## Quick selection guide

| If you want… | Use |
|---|---|
| Highest cadence, persistent view, lowest latency | GOES-19 / GOES-18 / Himawari-9 full disk |
| **Smooth motion with zero interpolation** | **ABI mesoscale `CMIPM1`/`CMIPM2` — 60 s cadence** |
| Fastest route to a presentable product | GeoColor JPEG from NOAA STAR CDN (local machine only) |
| Cheapest usable frames | ABI mesoscale C13 (0.31 MB), then Himawari-9 B13 (~11 MB) |
| True colour without fabricating a channel | Himawari-9 B01/B02/B03 |
| 0.5 km detail for a low-altitude camera | GOES C02 pan-sharpening C01/C03, via byte-range reads |
| Genuine observed motion (no interpolation) | VIIRS swaths, or a synthetic camera (see featuredocs) |
| Honest live night side | VIIRS DNB — ~27 min latency [measured], no obstacle |
| Never-dark full disk | DSCOVR/EPIC — reachable locally; ~13–22 images/day and 12–36 h latency keep it archival |
| Africa / Europe / India | Nothing on the required path. Unlock EUMETSAT (needs an account; host is reachable locally). |

---

## Revisions

- **2026-08-04** — Created. Reachability and all sizes/latencies measured in the
  cloud container; see `logs/2026-08-04T153908Z-environment-probe.md`.
- **2026-08-04 (rev. 2)** — First local probe
  (`logs/2026-08-04T163938Z-environment-probe.md`): all 23 hosts open, so every
  "blocked" verdict here is container-specific. Two corrections, both from probe
  defects rather than the data:
  - **VIIRS DNB was never "anomalously stale."** Measured at 26.8 min median
    publication latency, marginally faster than M5
    (`logs/2026-08-04T164009Z-experiment-viirs-latency.md`). The 200-minute figure
    came from an unpaginated S3 listing. Added the latency-vs-revisit distinction.
  - **C02 is 318–435 MB, not 376–406.** Scene-dependent; thresholds must be
    fractions of the actual file.
  Also: Himawari latency across three probes (4.6 / 3.6 / 5.1 min), Meteosat and
  GeoColor reachability clarified, byte-range reads relabelled as an unproven
  assumption pending G1.
- **2026-08-04 (rev. 3)** — **G1 ran and passed**
  (`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`). Byte-range reads move from
  assumption to measurement: 15.7% of bytes, pixel-exact. Added the chunk-geometry
  result — `CMI` is chunked (6, 21696), so cost scales with sector **height** and
  ignores width; read row bands, not tiles; set `cache_type` explicitly. C02's
  observed range widened again to **318–435 MB** on two granules measuring 435.4 MB,
  which is the second time a fraction-based threshold has absorbed a drift an
  absolute one would not have.
