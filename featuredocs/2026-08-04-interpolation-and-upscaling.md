# Interpolation and upscaling

**Created:** 2026-08-04 · **Status:** proposed experiment · **Supersedes:** nothing

---

## Problem

Two different kinds of invention, often conflated:

- **Temporal** — inventing frames between observations. Needed whenever `k > 1`
  (see `featuredocs/2026-08-04-time-compression.md`).
- **Spatial** — inventing detail finer than the sensor resolved. Needed whenever
  output resolution exceeds source GSD.

Both are legitimate and both are used in the reference video, which interpolated and
upscaled ISS stills heavily. The question is not whether to do it but **how much it
costs in fidelity, and how to find out.**

This document specifies the experiment rather than asserting an answer.

---

## How far do clouds actually move?

The number that governs temporal interpolation difficulty. Typical advection speeds
and the resulting displacement over a 600-second full-disk interval:

| Cloud regime | Speed | Displacement / 600 s | px @ 2 km | px @ 0.5 km |
|---|---|---|---|---|
| Low stratus / cumulus | 5–15 m/s | 3–9 km | 1.5–4.5 | 6–18 |
| Mid-level | 15–30 m/s | 9–18 km | 4.5–9 | 18–36 |
| Cirrus at jet level | 30–70 m/s | 18–42 km | 9–21 | 36–84 |
| Jet core | up to 100 m/s | 60 km | 30 | 120 |

**This corrects a figure carried in from the inherited plan**, which put displacement
at 0.3–5 px and concluded interpolation was comfortably easy. At 2 km the real range
is roughly **1–30 px**, and the upper end is well outside where naive optical flow
stays reliable. That is precisely why large-motion methods exist.

At 60-second mesoscale cadence, divide everything by ten: **0.15–3 px**. Trivially
easy — another argument for mesoscale.

**Advection is not the hard part.** Convective towers *grow*: a cumulonimbus top can
appear and expand where nothing was 10 minutes earlier. No flow-based method can
predict that, because it is not motion. Expect interpolation quality to collapse over
active convection specifically, and design the evaluation to catch it rather than
average it away.

---

## Methods to compare

### Temporal

| Method | Cost | Notes |
|---|---|---|
| **Hold-frame** | free | The honest floor. Judders, invents nothing. |
| **Cross-fade** | free | The real baseline. Anything that cannot beat it perceptually is not earning its dependency. |
| **ffmpeg `minterpolate`** | zero deps | `mi_mode=mci:mc_mode=aobmc:vsbmc=1`. Block-based; blocks tear on large motion. The inherited plan's v1 choice, and a sound one. |
| **RIFE** | PyTorch + weights | Fast, real-time class, well-behaved to moderate displacement. |
| **FILM** | PyTorch + weights | Built for *large* motion — the regime the table above says we are actually in at 0.5 km and in jet-level cirrus. |

### Spatial

| Method | Invents? | Notes |
|---|---|---|
| **Pan-sharpening** (C01/C03 → C02's 0.5 km grid) | **No** — real measurement | Uses genuine 0.5 km luminance. Preferred wherever available. |
| **Lanczos / bicubic** | No | Honest blur. The floor. |
| **Learned SR** (Real-ESRGAN, SwinIR) | **Yes — hallucinates texture** | The single most dangerous technique in this project. It will confidently invent cloud structure that was never observed. |

**Position on learned SR:** acceptable for purely aesthetic output, with the upscale
factor and the method named in the description. **Never** on frames used for
detection, measurement, or anything captioned as showing a specific weather feature.
If a viewer might screenshot it and point at a cloud, it must not be hallucinated.

---

## The experiment

The mechanism for "explore it separately, review the results, decide if it's relevant."

**Protocol — hold-out interpolation.** From a real sequence at cadence `C`, discard
every other frame. Interpolate across the resulting `2C` gap. Score the reconstruction
against the frame that was withheld. Repeat across many gaps.

This is the inherited plan's idea and it remains the most valuable single result the
project can produce. Three refinements:

**1. Three metrics, always reported together.**

| Metric | Measures | Failure mode |
|---|---|---|
| PSNR | pixel error | **Rewards blur.** A cross-fade often wins on PSNR while looking obviously wrong. |
| SSIM | local structure | Better, still forgiving of smearing. |
| **LPIPS** | perceptual similarity | Closest to "does it look right." Where learned methods should earn their keep. |

They will disagree. **The disagreement is the finding** — if a method wins PSNR and
loses LPIPS, it is blurring, and reporting only PSNR would have hidden that.

**2. Stratify, don't average.** A single mean number across a full disk is nearly
meaningless. Break results down by:

- **Cloud regime** — clear / stratiform / convective. Convective is where methods
  break, and it is what a weather product most wants to show.
- **Viewing zenith** — nadir vs. limb. Limb pixels are heavily foreshortened.
- **Day vs. night** — different bands, different noise.
- **Measured displacement** — bin by actual flow magnitude, so results transfer to
  other cadences and resolutions.

**3. Include the free baselines.** Hold-frame and cross-fade go in every table. A
method that cannot beat cross-fade on LPIPS does not justify a PyTorch dependency.

**Spatial analogue:** downsample a real 0.5 km frame to 2 km, upscale back by each
method, score against the true 0.5 km original. Pan-sharpening should win outright;
the interesting question is how much learned SR *appears* to win on LPIPS while
inventing.

### Deliverable

A `logs/` experiment record with the full stratified table, plus a side-by-side
frame grid over an active convective scene. That result decides which method ships
and gets cited wherever `k > 1` output is published.

---

## Decision

1. **Start with `k = 1` wherever possible** — mesoscale at 60 s, or higher speedup.
   No interpolation is always better than good interpolation.
2. **Default to ffmpeg `minterpolate`** for `k > 1` in early work. Zero dependencies,
   memory-light, good enough to ship.
3. **Run the hold-out experiment before adopting any learned method.** RIFE or FILM
   enters the pipeline only with a measured LPIPS win over cross-fade, stratified by
   cloud regime.
4. **Pan-sharpen for spatial detail; never learned SR on analysis frames.**
5. **Report `k`, the method, and the upscale factor** in every output description.

## Honesty notes

- Interpolated frames are **synthesized, not observed**. State `k` and the method.
- Interpolation quality is **not uniform** — it is worst exactly over active
  convection, which is usually the most visually interesting part of the frame. If
  quality varies materially across a published frame, say so.
- Learned super-resolution **hallucinates**. If used, name it and the factor.
- Pan-sharpening is inference from real 0.5 km luminance — much weaker fabrication
  than SR, but still inference, and colour at 0.5 km is not measured.
- The displacement table above is from published typical advection speeds, **not
  measured by us.** Measuring true displacement distributions from real frame pairs
  is part of the experiment.

## Open questions

- Does FILM's large-motion advantage actually show up at 0.5 km, where displacement
  reaches 100+ px? That is its design regime and our worst case.
- Can convective regions be detected cheaply enough (band 13 brightness temperature)
  to route them to a different method, or to fall back to hold-frame?
- Is there a defensible way to blend hold-frame over convection with interpolation
  elsewhere, without the seam being worse than either?

## Revisions

- **2026-08-04** — Created. Corrects the inherited plan's 0.3–5 px displacement figure.
