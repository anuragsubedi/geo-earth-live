# Environments

This project is developed from more than one place, and the places differ in ways
that change the design rather than just the setup. **Do not assume the environment
you are in is the only one.**

## Known environments

| | Cloud container | Local machine (VS Code / Cursor) |
|---|---|---|
| Trigger | Claude Code on the web / a Routine | Owner works locally with an IDE agent |
| Platform | Linux x86-64 | macOS ARM (16 GB) expected |
| Egress | **Policy-filtered proxy** — allowlist | Normal internet |
| Persistence | **Ephemeral.** Container reclaimed after inactivity | Persistent |
| Compute | 4 cores, ~15 GB RAM, ~30 GB free disk | Owner's machine |
| ffmpeg | Not installed by default | Homebrew |

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

Most of these are expected to work fine on a local machine. That asymmetry has
three consequences, and they are the reason this file exists:

1. **The pipeline's required path must use only S3 + PyPI.** Anything else is an
   optional enhancement with a reachable fallback. This is what killed the
   inherited plan's design, which depended on the NOAA STAR CDN for its pixels.
2. **Vendor static assets into the repo.** Coastlines, base maps, colour tables, any
   TLE snapshot. They are small, they never change, and vendoring makes rendering
   identical and offline-capable everywhere. `assets/`.
3. **Never route around a block.** A 403 at CONNECT is an organization policy
   decision. Record it in `logs/` and design for what is open.

### Distinguishing a block from a mistake

- **`403` at CONNECT / no status at all** → egress policy denial.
- **`404` from `*.s3.amazonaws.com`** → the host answered; the bucket name is wrong.
- **TLS verification failure** → the tool is not reading the container's CA bundle
  at `/root/.ccr/ca-bundle.crt`. Point it there. Never disable verification, never
  unset `HTTPS_PROXY`.

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
   from them. The container has ~30 GB free — a day of GOES C02 at full rate would
   not fit, so streaming and discarding is mandatory, not an optimization.
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
