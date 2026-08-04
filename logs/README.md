# logs/

Durable run records. **These are committed** — they are the project's memory across
environments and across agents. A claim like "Himawari-9 publishes at ~4 minutes
latency" is only trustworthy because a dated probe in here measured it.

## Naming

```
YYYY-MM-DDTHHMMSSZ-<kind>.md      # human-readable report
YYYY-MM-DDTHHMMSSZ-<kind>.json    # optional machine-readable sidecar
```

UTC always. This project lives in UTC — satellite timestamps, S3 partitions, and
scan schedules are all UTC, and mixing in local time is how you lose an hour of
frames without noticing.

## Kinds

| Kind | Produced by | Why it matters |
|---|---|---|
| `environment-probe` | `scripts/probe_env.py` | Which hosts are reachable *here*. Regenerate in every new environment before trusting `docs/DATA_SOURCES.md`. |
| `ingest-run` | ingest CLI (not yet built) | What was fetched, what was missing, bytes moved, elapsed. |
| `render-run` | render CLI (not yet built) | Frame counts, gaps, encode settings, output checksums. |
| `decision` | written by hand | A choice made and why, when it doesn't warrant a full featuredoc. |

## Rules

1. **Append, never rewrite.** A probe from three months ago that shows a host was
   open is evidence, not clutter. If it is stale, a newer file supersedes it by date.
2. **Raw noise goes in `logs/raw/`**, which is gitignored. Curated reports go here.
3. Anything asserting a *measurement* in `docs/` should be traceable to a file here.
4. Prune only when a file is superseded *and* wrong. Keep the record honest.
