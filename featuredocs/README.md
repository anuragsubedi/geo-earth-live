# featuredocs/

One timestamped document per feature or module. This is where *reasoning* lives —
the physics, the tradeoffs, the numbers, the things that were considered and
rejected. Code says what; featuredocs say why.

## Naming

```
YYYY-MM-DD-<feature-slug>.md
```

The date is when the document was **created**, and it does not change. If the
thinking evolves substantially, write a new dated document and mark the old one
superseded with a link. Small corrections can be edited in place, with a line in
the Revisions section at the bottom.

## When to write one

Write a featuredoc when **any** of these is true:

- The design involves a physical or geometric constraint someone could get wrong
  (orbital mechanics, projections, radiometry, sampling).
- You evaluated more than one approach and picked one.
- A future agent reading only the code would reasonably ask "why on earth is it
  done this way?"

Do **not** write one for routine plumbing. A CLI flag is not a feature doc.

## Structure

Use `TEMPLATE.md`. The non-negotiable sections are **Problem**, **Constraints
(with numbers)**, **Options considered**, **Decision**, and **Honesty notes**.

"Honesty notes" is specific to this project and is not optional. We synthesize
imagery: interpolated frames, synthetic green channels, virtual cameras, static
reference layers presented alongside live observation. Every one of those is
fine to do and *not* fine to leave undisclosed. If a feature fabricates anything
a viewer would reasonably assume was observed, the featuredoc names it, and that
disclosure propagates to the README and to any published output.

## Index

| Date | Document | Subject |
|---|---|---|
| 2026-08-04 | [`2026-08-04-orbital-camera.md`](2026-08-04-orbital-camera.md) | Synthetic orbital camera over live GEO imagery — Track A's core idea |
| 2026-08-04 | [`2026-08-04-orbit-selection.md`](2026-08-04-orbit-selection.md) | Which orbit dissolves the darkness problem, and what that implies for source selection |
| 2026-08-04 | [`2026-08-04-time-compression.md`](2026-08-04-time-compression.md) | Playback rate, the speedup/interpolation invariant, and the 60-second mesoscale finding |
| 2026-08-04 | [`2026-08-04-interpolation-and-upscaling.md`](2026-08-04-interpolation-and-upscaling.md) | Temporal and spatial synthesis methods, and the hold-out experiment that scores them |
| 2026-08-04 | [`2026-08-04-night-side-compositing.md`](2026-08-04-night-side-compositing.md) | Four open options for the night side, with selection criteria |
