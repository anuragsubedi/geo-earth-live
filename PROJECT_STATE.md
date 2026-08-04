# Project state

**Single source of truth.** Read this first. Update it in the same commit as any
change that alters status, a decision, or who is working on what.

**Last updated:** 2026-08-04 (rev. 3) · **Phase:** P0 (documentation & environment) ·
**Active plan:** none — [`2026-08-04-shared-core.md`](implementation_plans/2026-08-04-shared-core.md) is `PROPOSED`, awaiting sign-off

---

## What this project is

A **feed of Earth built from real satellite data**, aiming for the feel of Seán
Doran's *ORBIT — A Journey Around Earth in Real Time*: motion, curvature,
terminator crossings, night passes.

**"Quasi-live" is rhetorical, not literal.** A real-time feed would be unwatchable —
one frame per 600 s, and weather barely moves at 1×. A sped-up animation is a
legitimate expression of the goal, not a fallback from it. Latency still matters and
is good (~4.6 min Himawari-9, ~8 min GOES-19), but it is a secondary quality.

**All three tracks are in scope** and pursued in parallel (`docs/ROADMAP.md`). The
open question is sequencing, not selection. The near-term plan builds what all three
share.

---

## Where we are

| | |
|---|---|
| **Code written** | `scripts/probe_env.py` only. No pipeline yet. |
| **Docs written** | Complete scaffold — this file, handover, roadmap, data sources, environments, two featuredocs, one plan, one archived plan. |
| **Next gate** | **G1: byte-range read prototype** (see the active plan). Load-bearing for anything at 0.5 km. |
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
- **2026-08-04 (rev. 3)** — **First local-machine probe.** Fixed a defect in
  `scripts/probe_env.py` that reported a broken local CA bundle as a total egress
  block. All 23 hosts are OPEN locally, unblocking the D2 and D7 experiments. Local
  disk is **13.3 GB free — tighter than the container's ~30 GB.**

---

## Key facts

Container figures trace to `logs/2026-08-04T153908Z-environment-probe.md`; local
figures to `logs/2026-08-04T162813Z-environment-probe.md`.

### Data

- **Reachable GEO:** GOES-19 (75.2°W), GOES-18 (137°W), Himawari-9 (140.7°E) —
  all anonymous on AWS S3, 10-minute full disk.
- **Reachable LEO:** VIIRS on NOAA-21, NOAA-20, Suomi-NPP — 375 m I-bands,
  750 m M-bands, plus the day-night band for live city lights.
- **Latency [measured]:** Himawari-9 **4.6 min** (**3.6 min** on the local re-probe);
  GOES-19 **~8 min** from scan start (~17 s after scan end); VIIRS M-band **~36 min**.
- **VIIRS DNB newest object was 249 min old [measured, local probe].** That number is
  *not* established as publication latency — for a polar orbiter it may just be
  orbital revisit, since DNB granules only exist over the night side. It matters
  because D7's "live city lights" option depends on which it is. **Measure before
  relying on it:** compare a granule's `c`-timestamp to its `d`/`t` observation time,
  which separates the two. Until then, treat "live DNB" as unquantified.
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
  **318–414 MB** with the local probe (GOES-19 **413.74 MB**, GOES-18 **318.13 MB**
  [measured]), above the 376–406 MB the shared-core plan quotes. Size varies with
  scene compressibility, so **G1's pass threshold must be a fraction of the actual
  file, not a fixed byte count.**

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
| — | Build the shared core before committing effort to any one track | 2026-08-04 | active plan |
| — | Static assets vendored into `assets/`, not fetched at runtime | 2026-08-04 | `docs/ENVIRONMENTS.md` |
| — | No distributed compute until a measurement demands it | 2026-08-04 | `docs/ROADMAP.md` |
| — | Every synthesized element gets disclosed in output | 2026-08-04 | `featuredocs/` |

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
| G1 | Do byte-range reads make 0.5 km affordable? | P1 | technical — **prototype next** |

### Experiments specified, awaiting a run

Each ends in a `logs/` experiment record. See `docs/ROADMAP.md` § Evaluation discipline.

| Experiment | Specified in | Decides |
|---|---|---|
| **G1** — byte-range reads of C02 | active plan | Whether 0.5 km is affordable; honest camera altitude |
| **Hold-out interpolation** | `featuredocs/…-interpolation-and-upscaling.md` | Which method ships, and its measured cost. **Highest-value single result available.** |
| **Night-side four-way** | `featuredocs/…-night-side-compositing.md` | D7. **Now runnable** — GeoColor's host is OPEN on this local machine. |
| **Playback rate ladder** | `featuredocs/…-time-compression.md` | Where the terminator stops reading as an event |
| **Mesoscale continuity** | `featuredocs/…-time-compression.md` | Whether sector repositioning breaks 24 h sequences |
| **DNB latency vs. revisit** | this file, § Data | Whether "live city lights" is viable for D7. Cheap; a prerequisite for the four-way's DNB arm |

---

## Work claims

Claim before you start. Release when done. This is how parallel agents avoid
colliding.

| Module / task | Claimed by | Since | Status |
|---|---|---|---|
| `scripts/probe_env.py` | — | 2026-08-04 | **done** — TLS-classification fix landed rev. 3 |
| Documentation scaffold | — | 2026-08-04 | **done** |
| G1 byte-range prototype | *unclaimed* | — | next up |
| `src/geoearth/*` | *unclaimed* | — | blocked on G1 |
| Night-side four-way experiment | *unclaimed* | — | **unblocked** — this local machine reaches every arm |
| DNB latency vs. revisit | *unclaimed* | — | ready; cheap, gates the four-way's DNB arm |
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
