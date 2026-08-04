# Experiment — VIIRS publication latency vs. revisit gap

**Date:** 2026-08-04 16:40 UTC · **Kind:** `experiment` · **Environment:** local
(macOS ARM64) · **Produced by:** `scripts/viirs_latency.py`

**Decides:** whether VIIRS DNB is fresh enough for D7's "live city lights" option.
**Verdict: adopt — DNB latency is a non-issue. The prior "anomalously stale" figure
was our own measurement bug.**

---

## Why this ran

`docs/DATA_SOURCES.md` recorded the newest DNB object as **200 minutes** old and
called it *"anomalously stale compared to M-bands. Re-measure before designing
around DNB latency."* A second probe 49 minutes later reported **249 minutes**.

That delta is the tell. Age had grown by **exactly** the wall-clock elapsed
(49.1 min vs 49.1 min) and both probes named the **identical granule**
`SVDNB_j02_d20260804_t1151103_e1152331_b19340_c20260804121727884000_oeac_ops.h5`.
No new DNB object had appeared in 49 minutes, while M5 published several. Either
DNB publishing had stalled for hours, or we were not looking at the newest object.

## Root cause — a defect in our probe, not a property of the satellite

`scripts/probe_env.py::latest_granule` listed with `max-keys=1000` and **never
paginated**.

VIIRS partitions an entire UTC day into one flat prefix (`<product>/YYYY/MM/DD/`)
holding thousands of objects, and S3 ListObjectsV2 returns keys in **lexicographic**
order — which for VIIRS filenames is **observation order**. So the probe was ranking
"newest by LastModified" across only the **earliest ~1000 keys of the day**.

DNB publishes ~690 granules/day plus a `.sha384` sidecar each, so the first 1000
objects run out at roughly the 11:51Z granule — precisely the granule both probes
reported. The figure was an artifact of the listing, start to finish.

GOES and Himawari were unaffected: their prefixes are hourly or per-scan-minute and
hold far fewer than 1000 objects, so page one is the whole partition. **The bug was
invisible on the sources we look at most.**

Fixed in the same commit as this record: `s3_list_all()` paginates via
`NextContinuationToken` (40-page cap), checksum sidecars are excluded from freshness
ranking, and a truncated listing is now flagged in the report.

## What was compared

Held constant: bucket `noaa-nesdis-n21-pds`, UTC day 2026-08-04, NOAA-21, timestamps
parsed from granule filenames only — **no files downloaded**.

The two quantities the old number conflated:

| Quantity | Definition | What it depends on |
|---|---|---|
| **Publication latency** | observation end → object in S3 | ground processing pipeline |
| **Revisit / coverage gap** | spacing between consecutive observations | orbit |
| *"Age of newest object"* | *the sum of both* | *neither, usefully* |

A VIIRS SDR filename carries all of it —
`…_d20260804_t1611293_e1612521_b19343_c20260804163441643000_…` gives observation
date, start, end, orbit, and creation time.

## Results [measured]

| Product | Granules/day | **Publication latency (median)** | min–max | Coverage gaps > 5 min |
|---|---|---|---|---|
| `VIIRS-DNB-SDR` | 691 | **26.8 min** | 10.9 – 57.0 | none |
| `VIIRS-M5-SDR` | 666 | **30.3 min** | 11.1 – 57.0 | none |

**DNB is marginally *faster* than M5, not 7× slower.** Both publish continuously
across the day with no gap over 5 minutes. Re-running `probe_env.py` after the
pagination fix reported DNB at **1.1 min** and M5 at **0.9 min** old.

## Cost

Negligible. Two paginated `ListObjectsV2` walks, no object bodies fetched, a few
seconds wall-clock, no new dependencies (stdlib only).

## Disclosure required

None from this measurement itself. It **removes** a false constraint rather than
adding a capability.

The pre-existing DNB disclosures in
`featuredocs/2026-08-04-night-side-compositing.md` are untouched and still apply —
latency was never the binding constraint on live city lights:

- VIIRS's night pass is near 01:25 local, so a GEO night frame can be **up to ~7
  hours** from the DNB observation lighting it, from a different sensor and viewing
  geometry.
- DNB images cloud by reflected **moonlight**, so cloud detail varies over the lunar
  cycle and largely vanishes near new moon.
- Continuous *publication* is not continuous *coverage of a given place*: revisit at
  any point is still ~12 h per satellite.

## Verdict

**Adopt.** DNB publication latency (~27 min) is comparable to the M-bands and poses
no obstacle to D7's live-city-lights option. The `docs/DATA_SOURCES.md` instruction
to "re-measure before designing around DNB latency" is discharged by this record.

The constraint that actually governs D7 remains **temporal offset and lunar phase**,
not freshness.

## Lesson worth keeping

**"Age of newest object" is not latency for a polar orbiter**, and a paginated
listing is not optional on a flat daily prefix. Two independent probes agreed on a
wrong number because they shared a bug — agreement between runs of the same tool is
not corroboration. The filename-derived measurement is the trustworthy one because it
does not depend on our listing being complete.

---

**Reproduce:**

```bash
python3 scripts/viirs_latency.py --date 2026-08-04
```
