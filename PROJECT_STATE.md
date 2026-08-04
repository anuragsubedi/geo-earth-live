# Project state

**Single source of truth.** Read this first. Update it in the same commit as any
change that alters status, a decision, or who is working on what.

**Last updated:** 2026-08-04 (rev. 4) · **Phase:** P0 (documentation & environment) ·
**Active plan:** none — [`2026-08-04-shared-core.md`](implementation_plans/2026-08-04-shared-core.md) is `PROPOSED`, awaiting sign-off

---

## What this project is

A **feed of Earth built from real satellite data**, aiming for the feel of Seán
Doran's *ORBIT — A Journey Around Earth in Real Time*: motion, curvature,
terminator crossings, night passes.

**"Quasi-live" is rhetorical, not literal.** A real-time feed would be unwatchable —
one frame per 600 s, and weather barely moves at 1×. A sped-up animation is a
legitimate expression of the goal, not a fallback from it. Latency still matters and
is good (3.6–5.1 min Himawari-9, ~8 min GOES-19), but it is a secondary quality.

**All three tracks are in scope** and pursued in parallel (`docs/ROADMAP.md`). The
open question is sequencing, not selection. The near-term plan builds what all three
share.

---

## Where we are

| | |
|---|---|
| **Code written** | `scripts/probe_env.py`, `scripts/viirs_latency.py`, `scripts/g1_byte_range.py`. No pipeline yet. |
| **Docs written** | Complete scaffold — this file, handover, roadmap, data sources, environments, two featuredocs, one plan, one archived plan. |
| **Next gate** | **G1 passed** (`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`). The shared-core plan's remaining blocker is owner sign-off, not a technical unknown. |
| **Blocked on** | Owner's decision D1 — which track leads. Not blocking P1, which is track-agnostic. |
| **Branch** | `claude/satellite-orbit-setup-fl5q39` |

### Recent history

- **2026-08-03** — Prior session: feasibility analysis; established that a GEO
  visible-light livestream fails on daily illumination phase, not eclipse seasons.
  Produced the founding plan (a sped-up daily summary).
- **2026-08-04** — This repo created. Environment probed, inherited plan superseded
  (its data source is blocked here), documentation scaffold built.
- **2026-08-04 (rev. 2)** — Scope broadened on owner's direction: "quasi-live"
  clarified as rhetorical, all three tracks moved in scope, the inherited plan's
  alternatives (GeoColor, upscaling, interpolation) restored as things to *evaluate*
  rather than discard. Mesoscale 60-second cadence measured. Three featuredocs added
  (time compression, interpolation/upscaling, night-side compositing).
- **2026-08-04 (rev. 3)** — **First local-machine probe**, plus two defect fixes in
  `scripts/probe_env.py` and a documentation pass aligning every doc to the result.
  - Reported a broken local CA bundle as a total egress block (TLS failure ≠ policy
    denial). Fixed; all 23 hosts are OPEN locally, unblocking the D2 and D7
    experiments.
  - Never paginated S3 listings, so VIIRS freshness was read off the *oldest* 1000
    keys of a flat daily prefix. Fixed; this retracts the "DNB is anomalously stale"
    finding entirely.
  - Local disk is **13.3 GB free — tighter than the container's ~30 GB.**
  - C02 measured at **318–415 MB**, wider than the 376–406 MB on record.
- **2026-08-04 (rev. 4)** — **G1 ran and passed**
  (`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`). 0.5 km is affordable, so
  the 2 km fallback and the ~6,600 km camera cap are not taken. The sweep produced a
  larger result than the gate itself: **C02 chunks are full-width 6-row strips, so
  byte cost depends on sector height alone and is indifferent to width.**

---

## Key facts

Container figures trace to `logs/2026-08-04T153908Z-environment-probe.md`; local
figures to `logs/2026-08-04T162813Z-environment-probe.md`.

### Data

- **Reachable GEO:** GOES-19 (75.2°W), GOES-18 (137°W), Himawari-9 (140.7°E) —
  all anonymous on AWS S3, 10-minute full disk.
- **Reachable LEO:** VIIRS on NOAA-21, NOAA-20, Suomi-NPP — 375 m I-bands,
  750 m M-bands, plus the day-night band for live city lights.
- **Latency [measured]:** Himawari-9 **3.6–5.1 min** across three probes; GOES-19
  **~8 min** from scan start (~17 s after scan end); VIIRS **~27–30 min** publication
  latency. All are observation → available in S3; for the polar orbiters that is
  distinct from the ~12 h revisit gap.
- **VIIRS latency, resolved [measured]** —
  `logs/2026-08-04T164009Z-experiment-viirs-latency.md`. Publication latency is
  **DNB 26.8 min, M5 30.3 min** (medians), neither with a coverage gap over 5 min.
  **DNB is marginally faster than M5**, so freshness is no obstacle to D7's live
  city lights. The binding constraints there remain temporal offset (~7 h) and lunar
  phase.
  - The earlier "200 / 249 min stale" figures were **a defect in our own probe**,
    which listed only the first 1000 keys of a flat daily prefix. Corrected, and the
    lesson generalizes: **age of the newest object ≠ publication latency**, and two
    runs of the same buggy tool are not corroboration.
- **The coverage gap:** nothing reachable between roughly **20°W and 100°E** —
  Africa, Europe, the Middle East, India. That is Meteosat/FY-4 territory. It is
  the single most consequential constraint in the project (decision D2).
- **Mesoscale changes the calculus [measured]:** ABI `CMIPM1`/`CMIPM2` publish two
  independent ~1000 km sectors at **60-second cadence**, all 16 bands, at **0.31 MB
  (C13) / 4.4 MB (C02)** per frame — 10× the cadence at ~1/70th the bytes. A 24-hour
  mesoscale sequence is 48 s at 30 fps **with zero interpolation.** Sectors move to
  follow weather, so geolocation must be read per granule.
- **Cheapest usable frames:** mesoscale C13 (0.31 MB), then Himawari-9 B13 (~11 MB,
  bz2, 10 segments). **Most expensive:** GOES C02 — the observed range widens to
  **318–415 MB** [measured] (GOES-19 413.7/414.6, GOES-18 318.1/323.5), against the
  376–406 MB previously recorded. Two G1 granules then measured **435.4 MB**, so the
  observed range is now **318–435 MB**. Size is scene-dependent, so absolute byte
  thresholds drift — which is exactly why G1's criterion was a fraction of the actual
  file, and why it held.
- **Byte-range reads work, and cost scales with sector *height* only [measured]** —
  `logs/2026-08-04T171354Z-experiment-g1-byte-range.md`. `CMI` is chunked
  **(6, 21696)**: full-width 6-row strips, gzip-5 + shuffle. A 2048-row band costs
  **54.05 MB whether it is 2048 or 21696 px wide — the same figure to the byte.**
  Cost is **26.4 kB per row**, linear. Consequences: the fetch primitive is a
  **row band, not a square tile**; a camera pans cheaply east–west and expensively
  north–south; **~4096 rows is the ceiling** under the 25% criterion (24.8%).

### Environment

- **Egress is filtered in the cloud container.** `*.s3.amazonaws.com`, PyPI and
  GitHub are open. NOAA STAR CDN, NHC, EUMETSAT, NASA GIBS, DSCOVR/EPIC, Celestrak
  and Natural Earth are **blocked by org policy**.
- **Locally, nothing is blocked [measured].** All 23 probed hosts return 200,
  including every host the container denies. The container blocklist is purely local
  policy, not upstream availability. **This does not change the required path** —
  production may run in the container, so S3 + PyPI remains the only guaranteed
  substrate. It does mean the D2 and D7 experiments are runnable here today.
- **The required path uses only S3 + PyPI.** Anything else is optional with a fallback.
- Container: 4 cores, ~15 GB RAM, ~30 GB free disk, no ffmpeg, ephemeral.
- Local **[measured]**: macOS 26.2 ARM64, 8 cores, 16 GB RAM, **13.3 GB free disk**,
  ffmpeg 8.1 present, Python 3.14.2. **Local disk is tighter than the container's** —
  scale cache budgets from the measured figure, never the larger of the two.
- **A probe report is evidence only if its `tls_trust_store` fact resolved.** A TLS
  verification failure is a broken CA bundle, not a block; the probe now says so
  rather than reporting **BLOCKED**. Never disable verification to "fix" it — that
  converts a real proxy denial into a false **OPEN**.

### Design

- **Motion and imagery are separable.** GEO has cadence but no motion; LEO has
  motion but no cadence. A synthetic camera over live GEO texture supplies exact
  motion and leaves cloud evolution at its true rate — no frame interpolation in v1.
  (`featuredocs/2026-08-04-orbital-camera.md`)
- **Playback is one-dimensional:** `speedup × k = cadence × fps`. For 10-min full
  disk at 30 fps that constant is **18,000**; for 60-s mesoscale, **1,800**. You
  cannot independently choose slow, smooth, and un-synthesized — pick two.
  (`featuredocs/2026-08-04-time-compression.md`)
- **Cloud displacement is 1–30 px per 600 s at 2 km**, not the 0.3–5 px the inherited
  plan assumed — and convective growth is not motion at all, so no flow-based method
  can predict it. Interpolation quality will be worst exactly where the weather is
  most interesting. (`featuredocs/2026-08-04-interpolation-and-upscaling.md`)
- **Resolution sets the honest camera altitude.** 4K at ~1,600 km or 1080p at
  ~800 km, from 0.5 km pan-sharpened colour. An ISS-altitude 4K view would be a
  4× upscale and cannot be claimed honestly.
- **Himawari needs no synthetic green** (AHI has a real green band); GOES does.
- **Compute: colocate, don't distribute.** The job is I/O-bound. Running in
  `us-east-1` beats any cluster elsewhere. (`docs/ROADMAP.md`)

---

## Decisions

### Settled

| # | Decision | Date | Where |
|---|---|---|---|
| — | Inherited daily-summary plan superseded **as a plan**; its data source is unreachable here. Its *ideas* stay in scope as Track B | 2026-08-04 | `implementation_plans/archive/` |
| — | "Quasi-live" is rhetorical — sped-up animation is a legitimate expression of the goal | 2026-08-04 | `docs/ROADMAP.md` |
| — | All three tracks explored in parallel; open question is sequencing, not selection | 2026-08-04 | `docs/ROADMAP.md` |
| — | Exploration must end in a reviewable `logs/` **experiment record**, not an opinion | 2026-08-04 | `logs/README.md` |
| — | Build the shared core before committing effort to any one track | 2026-08-04 | `implementation_plans/2026-08-04-shared-core.md` |
| — | Static assets vendored into `assets/`, not fetched at runtime | 2026-08-04 | `docs/ENVIRONMENTS.md` |
| — | No distributed compute until a measurement demands it | 2026-08-04 | `docs/ROADMAP.md` |
| — | Every synthesized element gets disclosed in output | 2026-08-04 | `featuredocs/` |
| G1 | **Byte-range reads adopted.** 0.5 km is affordable — 15.7% of bytes, 15.39 s from outside AWS, pixel-exact. The 2 km `MCMIPF` fallback and ~6,600 km camera cap are **not** taken | 2026-08-04 | `logs/…-experiment-g1-byte-range.md` |

### Open

| # | Question | Gates | Owner |
|---|---|---|---|
| D1 | Track **sequencing** — what order, how much parallelism? Proposal: B → A → C | P2 | repo owner |
| D2 | Unlock EUMETSAT for Meteosat/MTG? Only way to cover Africa/Europe/India | P3 | repo owner |
| D3 | Production compute: GitHub Actions, AWS `us-east-1`, or local? | P6 | repo owner |
| D4 | Repo public? Output published? | P6 | repo owner |
| D5 | Live/rolling stream or batch renders? | P6 | repo owner |
| D6 | Colour source of record: GOES or Himawari? | P3 | technical |
| D7 | Night side: GeoColor / IR-only / IR+live DNB / dark. Likely differs per track | P3 | technical |

### Experiments specified, awaiting a run

Each ends in a `logs/` experiment record. See `docs/ROADMAP.md` § Evaluation discipline.

| Experiment | Specified in | Decides |
|---|---|---|
| **Hold-out interpolation** | `featuredocs/…-interpolation-and-upscaling.md` | Which method ships, and its measured cost. **Highest-value single result available.** |
| **Night-side four-way** | `featuredocs/…-night-side-compositing.md` | D7. **Now runnable** — GeoColor's host is OPEN on this local machine. |
| **Playback rate ladder** | `featuredocs/…-time-compression.md` | Where the terminator stops reading as an event |
| **Mesoscale continuity** | `featuredocs/…-time-compression.md` | Whether sector repositioning breaks 24 h sequences |

**Completed:**

- *VIIRS latency vs. revisit* — `logs/2026-08-04T164009Z-experiment-viirs-latency.md`.
  Verdict **adopt**: DNB latency 26.8 min, removing a false constraint on D7.
- *G1 byte-range reads* — `logs/2026-08-04T171354Z-experiment-g1-byte-range.md`.
  Verdict **adopt**: 15.7% of bytes in 15.39 s, corroborated by an independent
  `urllib`+`zlib` path agreeing to 0.06% with 0 pixel mismatches.

---

## Work claims

Claim before you start. Release when done. This is how parallel agents avoid
colliding.

| Module / task | Claimed by | Since | Status |
|---|---|---|---|
| `scripts/probe_env.py` | — | 2026-08-04 | **done** — TLS-classification and pagination fixes landed rev. 3 |
| `scripts/viirs_latency.py` | — | 2026-08-04 | **done** |
| Documentation scaffold | — | 2026-08-04 | **done** |
| Doc alignment to rev. 3 measurements | — | 2026-08-04 | **done** |
| DNB latency vs. revisit | — | 2026-08-04 | **done** — see `logs/…-experiment-viirs-latency.md` |
| G1 byte-range prototype | — | 2026-08-04 | **done** — `scripts/g1_byte_range.py`, verdict PASS |
| `src/geoearth/*` | *unclaimed* | — | **unblocked** — G1 answered; awaiting shared-core sign-off |
| Night-side four-way experiment | *unclaimed* | — | **unblocked** — this local machine reaches every arm |
| Hold-out interpolation experiment | *unclaimed* | — | blocked on P2 (needs frames) |

---

## Orientation

1. `AGENT_HANDOVER.md` — if you are an agent joining this project, start there.
2. `python3 scripts/probe_env.py` — always, in any new environment, before trusting
   `docs/DATA_SOURCES.md`.
3. `docs/ROADMAP.md` — the three tracks and why the choice is still open.
4. `implementation_plans/` — what is actually being built.
5. `featuredocs/` — why anything is the way it is.

---

## Update protocol

- **Same commit.** A status change and its `PROJECT_STATE.md` edit land together.
- **Measurements cite `logs/`.** If a number here has no traceable source, it is a
  guess and must be labelled one.
- **Decisions move, they don't vanish.** Open → Settled, with a date and a link.
- **Keep this file short enough to be read.** Detail belongs in `docs/`,
  `featuredocs/` and `implementation_plans/`; this file points at them.
