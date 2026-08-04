# Agent handover

Paste this to any agent joining the project — a Claude Code session on the web, a
local IDE agent (VS Code / Cursor), or a subagent taking one module. It is written
to be read cold, with no prior context.

---

## You are working on: geo-earth-live

A **quasi-live feed of Earth built from real satellite data**, inspired by the feel
of Seán Doran's *ORBIT — A Journey Around Earth in Real Time*: motion, curvature,
terminator crossings, night passes.

The repo is the **only shared memory** between agents and between environments.
Anything not committed does not exist — the cloud container is ephemeral and gets
reclaimed.

## Do these four things first

1. **`python3 scripts/probe_env.py --json`** — stdlib only, runs before any install.
   Writes a timestamped capability report to `logs/`. **Commit it.** Reachability
   differs between environments and every doc here depends on knowing yours.
2. **Read `PROJECT_STATE.md`** — status, measured facts, settled and open decisions,
   and who is working on what.
3. **Read the active plan** in `implementation_plans/` (exactly one is `ACTIVE`, or
   none if work is awaiting sign-off).
4. **Claim your work** in the `PROJECT_STATE.md` work-claims table before starting.

## Where things live

| Path                      | Contains                                                                     |
| ------------------------- | ---------------------------------------------------------------------------- |
| `PROJECT_STATE.md`      | Single source of truth. Status, facts, decisions, claims.                    |
| `docs/DATA_SOURCES.md`  | Every satellite source: reachability, cadence, measured sizes and latency.   |
| `docs/ROADMAP.md`       | Three candidate tracks, phases, decision points, compute strategy.           |
| `docs/ENVIRONMENTS.md`  | Cloud vs. local differences, egress policy, portability rules.               |
| `featuredocs/`          | Dated design rationale. Why, not what.`TEMPLATE.md` for new ones.          |
| `implementation_plans/` | What is being built, with definitions of done.`archive/` for superseded.   |
| `logs/`                 | Probe reports and run records.**Committed** — this is project memory. |
| `assets/`               | Vendored static data (coastlines, base maps). Committed on purpose.          |
| `scripts/`              | Standalone utilities:`probe_env.py`, `viirs_latency.py`, `g1_byte_range.py`. |
| `src/geoearth/`         | The pipeline. Does not exist yet.                                            |

`probe_env.py` is **stdlib only and must stay that way** — it has to run before any
install, in an environment you do not yet trust. `g1_byte_range.py` is the exception
and needs `h5py fsspec s3fs numpy`; there is no `pyproject.toml` until M1, so until
then: `python3 -m venv .venv && .venv/bin/pip install h5py fsspec s3fs numpy`
(`.venv/` is gitignored).

## The eight things that will trip you up

1. **Egress is filtered in the cloud container — and only there.** `*.s3.amazonaws.com`,
   PyPI and GitHub are open. NOAA STAR CDN, NHC, EUMETSAT, NASA GIBS, DSCOVR/EPIC,
   Celestrak and Natural Earth are **blocked by organization policy**. A `403` at
   CONNECT is a policy decision — **record it, never route around it.** A `404` from
   an S3 host is not a block; the bucket name is wrong. **A TLS verification failure
   is not a block either** — it is a broken CA bundle, and reporting it as BLOCKED is
   a mistake this project has already made once. On a local machine nothing is
   blocked, which does **not** promote those hosts to the required path (see 2).
   Trust `scripts/probe_env.py` only when its `tls_trust_store` line resolved.
2. **The required path must use only S3 + PyPI.** Anything else is an optional
   enhancement with a reachable fallback. This is exactly what killed the inherited
   plan, whose pixels came from a blocked CDN.
3. **UTC everywhere, and the path conventions differ.** GOES partitions by
   **day-of-year** (`ABI-L2-CMIPF/YYYY/DDD/HH/`); Himawari by calendar date and scan
   minute (`AHI-L1b-FLDK/YYYY/MM/DD/HHMM/`). Unit-test the conversions. This is
   where silent off-by-one-hour bugs live.
4. **Never hold the frame set in memory.** One decoded 5424² RGB frame is 88 MB; a
   float32 band array is 118 MB. Fine alone, fatal in bulk. Process one, write it,
   release it. Target peak RSS under 1.5 GB.
5. **Disk is not free.** The container has ~30 GB. A day of GOES C02 at 10-minute
   cadence is ~55 GB and **will not fit**. Stream and discard; enforce a cache budget.
6. **Gaps are normal, not exceptional.** Build the expected timestamp list, fetch
   what exists, log what is missing. Outages cluster around local midnight near the
   equinoxes (solar keep-out) and during calibration. Never crash on a gap.
7. **Colocate with the data.** All NOAA buckets are in `us-east-1`. That single fact
   is worth more than any amount of parallelism. The job is I/O-bound; do not reach
   for a cluster. It is also why **every wall-clock number in `logs/` measured from a
   laptop is an upper bound** — those runs are latency-bound, hundreds of serialized
   ~85 ms round trips. Byte counts port between environments; seconds do not.
8. **Sector cost depends on height, not area** [measured, `logs/…-experiment-g1-byte-range.md`].
   ABI `CMI` is chunked **(6, 21696)** — full-width 6-row strips. A 2048-row band costs
   **54.05 MB whether it is 2048 or 21696 px wide, the same figure to the byte.** So:
   fetch **row bands, never square tiles**; a horizontal tiling scheme multiplies cost
   and buys nothing; panning east–west is free and north–south is not. Also set
   `cache_type` explicitly when opening over fsspec — the common default `"bytes"`
   over-fetches enough to **fail** the 25% budget (27.1%), while `"readahead"` with a
   4 MiB block passes at 15.7%.

## The honesty requirement

This project synthesizes imagery, and that is fine — **as long as it is disclosed.**
Every featuredoc has a mandatory "Honesty notes" section, and whatever lands there
propagates to the README and to any published output.

Name anything a viewer would reasonably assume was observed but isn't:

- interpolated or synthesized frames
- synthetic channels — **ABI has no green band**; GOES true colour fabricates one
- virtual cameras and viewpoints
- static reference layers shown alongside live observation (e.g. GeoColor's
  city lights are a **static VIIRS database, not live observation**)
- upscaling beyond source resolution — state the factor
- heavily resampled regions (limb, swath edges)

If you build something that fabricates and you don't document it, you have
introduced a defect, not a feature.

## Working conventions

- **Branch:** `claude/satellite-orbit-setup-fl5q39`. Push with `git push -u origin <branch>`.
  Never push elsewhere without explicit permission. Do not open a PR unless asked.
- **Commit small and often.** The container can be reclaimed at any point, and
  parallel agents need to rebase cheaply.
- **Write the doc with the change, not after.** A featuredoc landing three commits
  later has already lost the reasoning it was meant to capture.
- **Numbers get sourced.** Mark measurements `[measured]` and cite the `logs/` file.
  An unlabelled number is assumed to be a guess.
- **Plans are superseded, not patched.** If a plan rests on a wrong assumption,
  write a successor that says what changed, and move the old one to
  `implementation_plans/archive/` unedited.
- **No hardcoded absolute paths.** Resolve from the repo root.

## What is true right now

Rather than trusting this paragraph, read `PROJECT_STATE.md` — it is maintained;
this section is a snapshot.

As of **2026-08-04 (rev. 4)**: documentation scaffold complete; the only code is
`scripts/probe_env.py`, `scripts/viirs_latency.py` and `scripts/g1_byte_range.py`.
**No pipeline exists — `src/geoearth/` is still empty.**

**G1 has been answered, and it passed.** Byte-range reads of GOES C02 cost **15.7% of
a 435 MB granule in 15.39 s** from outside AWS, pixel-exact
(`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`). 0.5 km is affordable, so the
2 km `MCMIPF` fallback and the ~6,600 km camera-altitude cap are **not** taken, and
the honest camera can assume native 0.5 km. What that experiment mainly bought,
though, was the chunk-geometry fact in trip-up 8 — read it before writing any fetch
code.

**The next concrete task is a decision, not a measurement.** The shared-core plan is
still `PROPOSED` and unsigned, and its one technical unknown is now closed. Building
`src/geoearth/` needs the repo owner's sign-off (and ideally D1, track sequencing).
If you want measurement work instead, four experiments remain specified and unclaimed
in `PROJECT_STATE.md`.

**Three published numbers have turned out to be defects in our own tools**, not
properties of the data — a missing CA bundle read as a total egress block, an
unpaginated S3 listing that made VIIRS DNB look 7× staler than it is, and a G1 run
that reported `FAIL` because the script picked the fewest-*bytes* configuration
rather than a *passing* one. All three are fixed and recorded. The habit worth
inheriting: **cross-check any load-bearing number by a second method that shares no
code with the first.** Two runs of the same tool agreeing is not corroboration —
G1's headline figure is trustworthy because an independent `urllib`+`zlib` path
reproduced it to 0.06% with zero pixel mismatches, not because it ran twice.

**Long runs must report progress and checkpoint their output.** `g1_byte_range.py` is
the reference: live status on stderr, and its JSON report rewritten after every phase
so an interrupted run still leaves evidence in `logs/`. A tool that goes silent for
four minutes is indistinguishable from one that has hung.

**All three tracks are in scope and explored in parallel** (`docs/ROADMAP.md`); the
open question is sequencing, not selection. "Quasi-live" is rhetorical — a sped-up
animation is a legitimate expression of the goal, not a fallback.

**Exploration must produce reviewable results, not opinions.** Every exploratory
branch ends in a `logs/` experiment record: what was compared, cost, quality
(measured where measurable), the disclosure each option would require, and a verdict.
"Defer" is a valid verdict. Four experiments remain specified and unclaimed — see
`PROJECT_STATE.md`. The night-side four-way used to need a local machine for its
GeoColor arm; **on a local machine every arm is now reachable [measured]**, so it is
runnable today. Two experiments are complete: VIIRS latency
(`logs/2026-08-04T164009Z-experiment-viirs-latency.md`) and G1 byte-range reads
(`logs/2026-08-04T171354Z-experiment-g1-byte-range.md`) — read the latter as the
worked example of the format, including its "incidental findings" section, which is
where the load-bearing chunk-geometry result actually surfaced.
