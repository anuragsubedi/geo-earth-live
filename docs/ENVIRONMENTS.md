# Environments

This project is developed from more than one place, and the places differ in ways
that change the design rather than just the setup. **Do not assume the environment
you are in is the only one.**

## Known environments

| | Cloud container | Local machine (VS Code / Cursor) |
|---|---|---|
| Trigger | Claude Code on the web / a Routine | Owner works locally with an IDE agent |
| Platform | Linux x86-64 | macOS 26.2 ARM64 **[measured]** |
| Egress | **Policy-filtered proxy** — allowlist | **Unfiltered — all 23 probed hosts OPEN [measured]** |
| Persistence | **Ephemeral.** Container reclaimed after inactivity | Persistent |
| Compute | 4 cores, ~15 GB RAM, ~30 GB free disk | 8 cores, 16 GB RAM, **13.3 GB free disk [measured]** |
| ffmpeg | Not installed by default | **8.1, installed [measured]** |

Local figures **[measured]** on 2026-08-04 —
[`logs/2026-08-04T162813Z-environment-probe.md`](../logs/2026-08-04T162813Z-environment-probe.md).

> **Disk is the surprise: local is tighter, not roomier.** 13.3 GB free against the
> container's ~30 GB. Every streaming and cache-budget rule below is *more* binding
> here, not less. Do not treat "run it locally" as an escape from the disk budget.

### The rule that follows

> **Anything not committed and pushed does not exist.** The container is reclaimed.
> Data files, renders and scratch work are disposable by design; documentation,
> scripts, assets and logs are the deliverable.

## Egress differences are a design constraint, not a nuisance

Measured in the container on 2026-08-04
(`logs/2026-08-04T153908Z-environment-probe.md`):

**Open:** `*.s3.amazonaws.com` (all NOAA Open Data buckets), `pypi.org`,
`files.pythonhosted.org`, `api.github.com`.

**Blocked (org egress policy, 403 at CONNECT):** `cdn.star.nesdis.noaa.gov`,
`www.star.nesdis.noaa.gov`, `rammb-slider.cira.colostate.edu`, `www.nhc.noaa.gov`,
`celestrak.org`, `gibs.earthdata.nasa.gov`, `epic.gsfc.nasa.gov`,
`naturalearthdata.com`, `data.eumetsat.int`, `youtube.com`.

**Confirmed on the local machine 2026-08-04** — every one of those ten hosts is
**OPEN** here, along with all thirteen that were already open in the container
(`logs/2026-08-04T162813Z-environment-probe.md`). The asymmetry is real and total:
the container's blocklist is exactly the set of things a local run unlocks.

That directly affects two open decisions: **D2** (EUMETSAT for Meteosat/MTG — the
20°W–100°E coverage gap) and **D7** (the night-side four-way, whose GeoColor arm
needs `cdn.star.nesdis.noaa.gov`). Both are runnable here *today*. Neither becomes
a required-path dependency because of it — see consequence 1 below.

That asymmetry has three consequences, and they are the reason this file exists:

1. **The pipeline's required path must use only S3 + PyPI.** Anything else is an
   optional enhancement with a reachable fallback. This is what killed the
   inherited plan's design, which depended on the NOAA STAR CDN for its pixels.
2. **Vendor static assets into the repo.** Coastlines, base maps, colour tables, any
   TLE snapshot. They are small, they never change, and vendoring makes rendering
   identical and offline-capable everywhere. `assets/`.
3. **Never route around a block.** A 403 at CONNECT is an organization policy
   decision. Record it in `logs/` and design for what is open.

### Distinguishing a block from a mistake

- **`403` at CONNECT** → egress policy denial.
- **`404` from `*.s3.amazonaws.com`** → the host answered; the bucket name is wrong.
- **TLS verification failure** → **not a block.** A broken or missing CA bundle, and
  it says nothing about reachability.
  - *In the container:* the tool is not reading `/root/.ccr/ca-bundle.crt`. Point it there.
  - *Locally:* a python.org framework build ships **no** CA bundle at its configured
    `openssl_cafile` path, so every TLS connection fails. Use `certifi`,
    `/etc/ssl/cert.pem`, or run `Install Certificates.command`.
  - **Never disable verification**, never unset `HTTPS_PROXY`. Disabling verification
    would turn a genuine MITM-proxy denial into a false **OPEN** — a worse error than
    the one being fixed.

> **This bit us.** Until 2026-08-04 `scripts/probe_env.py` classified *any* connection
> failure as **BLOCKED**. On the local machine the missing CA bundle therefore produced
> a report claiming all 23 hosts were blocked — including PyPI and S3, which is never
> true anywhere. The probe now resolves a working trust store, classifies TLS-trust,
> DNS, timeout and refusal separately from policy denial, and stamps a warning banner
> across any report containing a TLS-trust failure. **A probe report is evidence only
> if its `tls_trust_store` machine fact resolved.**

## First thing to do in any environment

```bash
python3 scripts/probe_env.py --json
```

Stdlib only, so it runs before anything is installed. It writes a timestamped
report to `logs/` covering machine facts, host reachability, and live data
freshness. **Commit the report** — the accumulating series is how we know when
something changed.

Then read `PROJECT_STATE.md`.

## Portability rules for code

1. **No hardcoded absolute paths.** Resolve from the repo root
   (`Path(__file__).resolve().parent.parent`).
2. **No assumption that a host is reachable.** Fetching code fails with a message
   naming the host and pointing at this file, rather than a bare traceback.
3. **No assumption about core count, RAM, or disk.** Read them; scale batch sizes
   from them. The container has ~30 GB free and the local machine **13.3 GB
   [measured]** — a day of GOES C02 at full rate fits in neither, so streaming and
   discarding is mandatory, not an optimization. Scale from the *measured* figure;
   never from the larger of the two.
4. **UTC everywhere.** Satellite timestamps, S3 partitions and scan schedules are
   all UTC. Never format a local time into a path.
5. **`ffmpeg` may be absent.** Detect it, and if the project needs it, prefer the
   `imageio-ffmpeg` wheel from PyPI (reachable everywhere) over a system package.
6. **Pin dependencies** so a local run and a container run resolve the same versions.

## Working with parallel agents

The repo is the only shared memory between agents and between environments.

- **`PROJECT_STATE.md` is the single source of truth.** Read it first; update it in
  the same commit as any change that alters status or a decision.
- **Claim work in `PROJECT_STATE.md`** before starting, so two agents don't build
  the same module.
- **Write the doc with the change, not after.** A featuredoc landing three commits
  later has already lost the reasoning it was meant to capture.
- **Prefer many small commits** on the designated branch over one large one, so a
  parallel agent can rebase cheaply.

## Revisions

- **2026-08-04** — Created, from the container probe.
- **2026-08-04 (rev. 2)** — First local-machine probe. All 23 hosts OPEN, confirming
  the container blocklist is purely local policy. Recorded local compute and the
  13.3 GB disk figure. Corrected the block-vs-mistake guidance after
  `scripts/probe_env.py` misreported a missing local CA bundle as a total egress block.
