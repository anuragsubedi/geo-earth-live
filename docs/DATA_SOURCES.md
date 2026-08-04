# Data sources

Living catalog of satellite imagery we can build from. Every number marked
**[measured]** came from a probe in `logs/`; everything else is documentation or
estimate and is labelled as such.

**Reachability is environment-specific.** The verdicts below are from
`logs/2026-08-04T153908Z-environment-probe.md`, taken in the cloud container.
On a local machine most "blocked" entries are expected to be open. Re-run
`python3 scripts/probe_env.py` before relying on this file. See
`docs/ENVIRONMENTS.md`.

---

## Tier 1 — Geostationary (the backbone)

Three of the five operational GEO weather slots are reachable anonymously on AWS.
This is the highest-cadence, lowest-latency imagery available to us by a wide margin.

| Satellite | Slot | Instrument | Full-disk cadence | Bucket | Reachable |
|---|---|---|---|---|---|
| **GOES-19** (GOES-East) | 75.2°W | ABI, 16 bands | 10 min (Mode 6) | `noaa-goes19` | **yes** |
| **GOES-18** (GOES-West) | 137.0°W | ABI, 16 bands | 10 min | `noaa-goes18` | **yes** |
| **Himawari-9** | 140.7°E | AHI, 16 bands | 10 min | `noaa-himawari9` | **yes** |
| Meteosat-12 / MTG-I1 | 0° | FCI | 10 min | EUMETSAT Data Store | **no** (blocked; needs account) |
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
| **C02 (red)** | 0.64 µm | **0.5 km** | **376–406 MB** |
| C03 (veggie NIR) | 0.86 µm | 1 km | 83.8 MB |
| C07 (shortwave IR) | 3.9 µm | 2 km | 25.2 MB |
| C13 (clean longwave IR) | 10.3 µm | 2 km | 22.7 MB |
| C15 (dirty longwave IR) | 12.3 µm | 2 km | 22.4 MB |
| `MCMIPF` (**all 16 bands, all at 2 km, one file**) | — | 2 km | 332 MB |
| `FDCF` (fire/hotspot L2) | — | 2 km | 1.7 MB |

Full-disk fixed grid: 5424² at 2 km, 10848² at 1 km, 21696² at 0.5 km.

**Publication latency [measured]:** a scan starting 14:00:20Z ended 14:09:51Z and its
objects appeared in S3 at **14:10:08Z — about 17 seconds after scan end**, ~10 minutes
after scan start. Substantially better than the 30–90 s the inherited draft assumed.

**Himawari-9 is the efficiency winner [measured]:** AHI L1b full disk is delivered as
**10 bzip2-compressed segments** per band, and the newest frame was **4.6 minutes** old.

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

**[measured]** NOAA-21 M5 granule: 9.16–9.76 MB, newest **36 minutes** old. DNB granule:
9.15 MB, but the newest was **200 minutes** old on this probe — anomalously stale
compared to M-bands. Re-measure before designing around DNB latency.

### Why DNB is strategically important

The inherited plan's night-side solution was CIRA GeoColor, whose city lights are a
**static VIIRS reference layer, not live observation** — a disclosure burden the plan
correctly flagged. VIIRS DNB is the *actual observation*. If we composite our own
night side from live DNB, the caveat disappears entirely and the product becomes
more honest than the off-the-shelf one. That is a rare case where doing more work
buys integrity rather than just polish.

### Why LEO is not a drop-in replacement for GEO

Revisit at any given point is ~12 hours per satellite. You get strips, not a
persistent view. LEO gives you *resolution and genuine motion*; GEO gives you
*cadence and persistence*. The interesting designs use both.

---

## Tier 3 — Not reachable now, worth knowing

| Source | What it uniquely offers | Blocker |
|---|---|---|
| **DSCOVR / EPIC** (Sun–Earth L1) | The **always-fully-lit** full disk. Zero night side, zero eclipse, ever — the only geometry that fully dissolves the darkness problem. 10 narrowband channels, 2048². | `epic.gsfc.nasa.gov` blocked. ~13–22 images/day and 12–36 h latency make it archival, not live. Also available via `api.nasa.gov`. |
| **Meteosat-12 / MTG-I1** (0°) | Fills the Africa/Europe/India gap. FCI, 10-min full disk, 500 m VIS. | EUMETSAT Data Store: free but requires registration; host blocked in container. **Highest-value unlock in this table.** |
| **Arktika-M1 / M2** | Molniya orbit (12 h, i=63.4°, apogee ~40,000 km). GEO-class full-hemisphere imaging **of the Arctic**, which no GEO satellite can see. Range varies from perigee to apogee, so Earth naturally zooms. | Roshydromet distribution; not on AWS; practical access unclear. |
| **FY-4B** (105°E) | Also fills part of the gap. AGRI, 15 min. | NSMC portal, registration, blocked. |
| **Sentinel-3 OLCI** | 300 m, 1270 km swath, 10:00 LTAN — better-lit than VIIRS's 13:25. | Copernicus/EUMETSAT; blocked. |
| **Sentinel-2 MSI** | 10 m. | `sentinel-s2-l1c` reachable but **requester-pays** (needs AWS credentials); 5-day revisit makes it useless for live. |
| **Sen (SpaceTV-1, ISS)** | Actual 4K video from space, ~60 m/px. The commercial proof the concept works. | Proprietary. Reference, not a source. |

---

## Ancillary data

| Need | Preferred source | Status | Fallback |
|---|---|---|---|
| Coastlines / borders / graticule | Natural Earth vectors | host **blocked** | **Vendor into `assets/`** — small, static, versioned. Do this regardless; it removes a network dependency from rendering. |
| Global base map (land/ocean under clouds) | NASA GIBS Blue Marble | **blocked** | Vendor a single downsampled BMNG tile set into `assets/`. Static by nature, so vendoring costs nothing in freshness. |
| Tropical cyclone positions | `nhc.noaa.gov/CurrentStorms.json` | **blocked** | Derive from ABI C13 brightness-temperature minima ourselves, or find an S3-hosted best-track mirror. Open question. |
| Orbital elements (TLE) | celestrak.org | **blocked** | Not needed for a *synthetic* camera — we define the orbit. If real TLEs are ever wanted, vendor a snapshot and propagate offline with `sgp4` (PyPI, reachable). |
| Solar geometry (terminator, phase) | computed | n/a | `pyorbital` or direct ephemeris math. No network needed. |

**Note on vendored assets:** anything static and small (coastlines, base maps, colour
tables, a TLE snapshot) belongs in `assets/` committed to the repo. It makes the
pipeline reproducible offline and identical across environments, which is worth far
more than the few MB.

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

**Byte-range reads are the key optimization.** netCDF4 *is* HDF5, chunked and
internally compressed. With `h5py` over `fsspec`, a single variable — or a single
spatial chunk region — can be read without downloading the file. For C02 at 376 MB
this is the difference between a feasible pipeline and an infeasible one. Prototype
this early; it is the load-bearing assumption of any plan that touches 0.5 km data.

**Colocate with the data.** All NOAA Open Data buckets live in `us-east-1`. Compute
in that region gets near-line-rate transfer and zero egress cost. This matters more
than any amount of parallelism — see `docs/ROADMAP.md` on compute.

---

## Quick selection guide

| If you want… | Use |
|---|---|
| Highest cadence, persistent view, lowest latency | GOES-19 / GOES-18 / Himawari-9 full disk |
| Cheapest usable frames | Himawari-9 B13 (~11 MB/frame) |
| True colour without fabricating a channel | Himawari-9 B01/B02/B03 |
| 0.5 km detail for a low-altitude camera | GOES C02 pan-sharpening C01/C03, via byte-range reads |
| Genuine observed motion (no interpolation) | VIIRS swaths, or a synthetic camera (see featuredocs) |
| Honest live night side | VIIRS DNB |
| Never-dark full disk | DSCOVR/EPIC — when reachable |
| Africa / Europe / India | Nothing today. Unlock EUMETSAT. |

---

## Revisions

- **2026-08-04** — Created. Reachability and all sizes/latencies measured in the
  cloud container; see `logs/2026-08-04T153908Z-environment-probe.md`.
