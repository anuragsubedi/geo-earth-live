# implementation_plans/

One file per plan. A plan is a *commitment to build a specific thing*, with a
definition of done. It is not a roadmap (see `docs/ROADMAP.md`) and not a design
rationale (see `featuredocs/`).

## Naming

```
YYYY-MM-DD-<slug>.md           # active or completed
archive/YYYY-MM-DD-<slug>.md   # superseded — kept, never deleted
```

## Lifecycle

Every plan carries a status header:

| Status | Meaning |
|---|---|
| `DRAFT` | Being written. Do not build from it. |
| `PROPOSED` | Complete, awaiting sign-off from the repo owner. |
| `ACTIVE` | Approved. This is what is being built right now. |
| `DONE` | Delivered. Definition-of-done met. |
| `SUPERSEDED` | Replaced. Moved to `archive/`, with a pointer to the successor. |

**At most one plan is `ACTIVE` at a time.** If you think a second one should be,
you actually want to split the work or revise the active plan.

## Rules

1. **Never edit a `SUPERSEDED` plan.** It is a record of what was believed then.
   Correct the record by writing a new plan that says what changed and why.
2. A plan that turns out to rest on a wrong assumption gets superseded, not patched.
   The archived version plus the successor's "what changed" section is the audit trail.
3. Plans state *measured* numbers where numbers matter, and cite the `logs/` file
   they came from. Estimates must be labelled as estimates.
4. When a plan goes `ACTIVE` or `DONE`, update `PROJECT_STATE.md` in the same commit.

## Index

| Date | Plan | Status |
|---|---|---|
| 2026-08-04 | [`2026-08-04-shared-core.md`](2026-08-04-shared-core.md) | `PROPOSED` |
| 2026-08-03 | [`archive/2026-08-03-geo-daily-summary.md`](archive/2026-08-03-geo-daily-summary.md) | `SUPERSEDED` |
