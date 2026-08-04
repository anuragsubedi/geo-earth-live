# <Feature or module name>

**Created:** YYYY-MM-DD · **Status:** proposed | building | built | superseded · **Supersedes:** <link or "nothing">

---

## Problem

What is actually hard here, in a few sentences. Not "we need a fetcher" — *why*
fetching is non-trivial in this case. If a reader finishes this section thinking
"that sounds easy," either the section is wrong or the feature doesn't need a doc.

## Constraints, with numbers

Physics, geometry, bandwidth, memory, latency. **Numbers, with units, and where
they came from.** Mark measurements `[measured]` and cite the `logs/` file; mark
everything else as documentation or estimate.

## Options considered

| Option | Verdict |
|---|---|
| … | Chosen / rejected, and why in one line |

Include the options that were rejected. A future agent will re-propose them
otherwise, and the reason for rejection is the expensive part.

## Decision

What we're doing, stated so someone could implement it without asking follow-ups.

## Honesty notes

**Not optional.** This project synthesizes imagery. Name every element a viewer
would reasonably assume was observed but isn't:

- interpolated or otherwise synthesized frames
- synthetic channels (e.g. ABI has no green band)
- virtual cameras and viewpoints
- static reference layers presented alongside live observation
- upscaling beyond source resolution — state the factor
- heavily resampled regions (limb, swath edges)

If none apply, write "None — every pixel and every motion in this feature is
observed." That should be rare, and it is worth saying when true.

Whatever lands here propagates to `README.md` and to the description of any
published output.

## Open questions

Things genuinely unresolved. Better here than pretended-away in the Decision.

## Revisions

- **YYYY-MM-DD** — Created.
