# First Live-Run Report — MRV Carbon Monitoring Pipeline

**Scope**: First real Google Earth Engine run, pilot AOI, Bắc Ninh, Vietnam
**Date**: July 2026
**Version**: English ([Bản tiếng Việt](02-first-live-run-report.vi.md))

**Status**: This is the **first live run against real Sentinel-2 data**. It
validated the pipeline end to end on real imagery, uncovered and fixed a metric
bug, and produced a readable seasonal signal for one season — but **no field /
ground-truth validation has been done**, and no accuracy percentage is claimed.
All numbers below come from this run's manifests and
`data/processed/spectral_indices.csv`.

## 1. Executive Summary

The first live run did three things. (1) It **validated the `collect → features`
pipeline on real Sentinel-2 imagery** for the Bắc Ninh pilot AOI. (2) It
**exposed a metric bug** — `aoi_clear_fraction` was measuring `clear/valid`
instead of `clear/total`, silently nullifying the `MIN_CLEAR_FRACTION` filter —
which was root-caused and fixed, then re-validated on the same real data.
(3) It produced a **7-scene seasonal series for the Đông-Xuân 2025–26 crop** that
reads as a coherent phenology arc (flood/puddling → growth → heading peak →
ripening/harvest).

The headline operational finding: **optical imagery alone is sufficient to
monitor the crop-season phenology in Đông-Xuân (7 usable scenes), but is not
sufficient for year-round MRV** — the Vụ Mùa (rainy) season returned **0 usable
scenes across 45 peak-rain days**. This points to Sentinel-1 SAR as the phase-2
direction, and that conclusion is drawn from measurements on this AOI, not from
literature.

## 2. Locked Configuration

- **AOI**: `data/external/aoi/bac_ninh_pilot.geojson` — ~2.03 km², Lương Tài
  (former Bắc Ninh province), centroid ≈ 21.0375 N, 106.2198 E.
- **`MAX_CLOUD_COVER_PCT` = 100**, **`MIN_CLEAR_FRACTION` = 0.5**.

**Why `MAX_CLOUD_COVER_PCT = 100`.** The scene-level `CLOUDY_PIXEL_PERCENTAGE`
filter is computed over the **whole ~110×110 km Sentinel-2 tile**, not over our
~2 km² AOI. A tile can be flagged as heavily clouded while our small AOI is
clear — so a scene-level threshold **discards scenes that are actually clear over
the AOI**. The fix is to stop filtering at the tile level and filter at the
**AOI level** instead, via `aoi_clear_fraction` + `MIN_CLEAR_FRACTION` — the
correct tier for a small AOI. Setting `MAX_CLOUD_COVER_PCT = 100` disables the
wrong-tier filter so nothing is thrown away before the AOI-level measurement.

## 3. The Metric Bug (the most important result of this run)

**Symptom.** The first run (`MAX_CLOUD_COVER_PCT = 70`) returned 8 scenes with
**every `aoi_clear_fraction` = 1.000** and a **flat survival sweep** — impossible
for a rice AOI across a season. A rainy-season stress test
(`MAX_CLOUD_COVER_PCT = 100`, 45 peak-rain days) still returned only **1.000 or
None**, which is direct evidence that the metric was broken, not just a
lucky-clear set.

**Root cause.** `collect.py` applied `collection.map(mask_clouds)` **before**
measuring. `mask_clouds` masks the SCL band's non-clear pixels, so
`reduceRegion(mean)` averaged over the surviving (clear) pixels only — the metric
measured **clear / valid ≈ 1.0**, not **clear / total**. `MIN_CLEAR_FRACTION` was
therefore completely nullified: every observed scene read as perfectly clear.

**Fix.** Measure `aoi_clear_fraction` on the **raw SCL**, so cloud pixels count
as 0 in the denominator (`clear / total-in-footprint`). A fully cloudy AOI now
yields **0.0**; `None` means only that the AOI is outside the scene footprint.
(`features` keeps its own separate cloud mask for index computation — unchanged.)

**Re-validation on real data.** After the fix, the rainy-season window now
returns **0.0 and intermediate** values, and the survival sweep is **no longer
flat** — see Sections 4–5.

**Data consequence at the locked config.** Two scenes from the earlier
(pre-fix) series are now correctly dropped as cloud-contaminated: **16 Feb** and
**27 Apr**. Honesty note: **27 Apr was the old series' "NDVI peak" (0.581) — that
peak was a cloud artefact**, not a real vegetation maximum. The true NDVI peak in
this series is **27 May (0.546)**. In compensation, lowering the threshold to 0.5
brings in **27 Jan**, the flood/puddling scene — the most valuable point in the
series (Section 6).

**Why it slipped through.** The bug passed all 57 pre-existing unit tests because
those tests use `MagicMock`s that model no pixels at all — the mask-vs-reducer
arithmetic that caused the bug was simply not represented. It could only surface
on real Earth Engine data.

## 4. Results A — Vụ Mùa 2025 (rainy season)

Window `2025-07-01 .. 2025-08-15` (45 days), `MAX_CLOUD_COVER_PCT = 100`.

- **Tier 1**: 11 scenes returned, 11 with a clear-fraction, 0 no-data.
- **`aoi_clear_fraction`**: min = 0.000, median = 0.000, mean = 0.023,
  max = 0.185.
- **Histogram**: `<0.5` = 11; all other buckets = 0.
- **Survival**: **0 scenes at every threshold 0.5 → 0.9.**

**Conclusion: optical is completely blind in the rainy season.** Across 45 days
of the Vụ Mùa peak, **0 scenes are usable**. This is the single hardest
constraint on an optical-only MRV approach for this region.

## 5. Results B — Đông-Xuân 2025–26 (dry season)

Window `2026-01-15 .. 2026-06-30`, `MAX_CLOUD_COVER_PCT = 100`.

- **Tier 1**: 38 scenes returned, 38 with a clear-fraction, 0 no-data.
- **`aoi_clear_fraction`**: min = 0.000, median = 0.000, mean = 0.163,
  max = 1.000.
- **Histogram**: `<0.5` = 31 · `0.5–0.7` = 2 · `0.7–0.8` = 0 · `0.8–0.9` = 1 ·
  `>=0.9` = 4.
- **Survival sweep**: `0.5 → 7` · `0.6 → 6` · `0.7 → 5` · `0.8 → 5` · `0.9 → 4`.
- At **`MIN_CLEAR_FRACTION = 0.5`: 7 of 38 scenes are usable (~18%).**

The non-flat survival sweep is exactly the behaviour the metric fix was meant to
restore: `MIN_CLEAR_FRACTION` now meaningfully separates clear scenes from
cloudy ones.

## 6. The 7-Scene Seasonal Series

The seven surviving scenes (from `data/processed/spectral_indices.csv`; values
rounded, full precision in the file):

| Date | clear | NDVI | NDWI | LSWI | Phase |
|---|---|---|---|---|---|
| 27 Jan | 0.608 | 0.049 | −0.005 | 0.194 | flood / puddling (đổ ải) |
| 13 Mar | 0.999 | 0.313 | −0.265 | 0.294 | early growth |
| 07 Apr | 1.000 | 0.445 | −0.392 | 0.224 | growth |
| 12 Apr | 1.000 | 0.307 | −0.247 | 0.234 | anomaly — see §7 |
| 27 May | 0.566 | 0.546 | −0.496 | 0.170 | NDVI peak (heading) |
| 01 Jun | 0.851 | 0.490 | −0.457 | 0.121 | post-peak |
| 21 Jun | 0.964 | 0.274 | −0.289 | 0.154 | ripening / harvest |

Read as a sequence, the series traces a plausible crop-season arc:
flood/puddling → growth → heading peak → ripening/harvest. **Cross-confirmation
of the flood phase**: the highest NDWI (−0.005, most water-like) falls on exactly
the same date as the lowest NDVI (27 Jan) — two independent indices agree that
27 Jan is the flooded, low-vegetation stage.

## 7. Limitations (stated explicitly, not hidden)

1. **A 45-day gap (27 Jan → 13 Mar)** swallows the **transplanting** period
   (February). That stage is simply not observed in this series.
2. **The 12 Apr anomaly**: NDVI drops from 0.445 (7 Apr) to 0.307 (12 Apr) in
   five days, although **both scenes have `clear` = 1.000**. This is
   **unexplained — an open question.** It must **not** be called an AWD drain
   event; there is no basis for that here.
3. **27 May (`clear` 0.566) and 1 Jun (`clear` 0.851)** rest on fewer clear
   pixels than the ≈1.0 scenes, so they are **less spatially representative**.
4. **Partial-footprint limitation** (documented in
   [spec 05](../specs/05-clear-fraction-measures-cloud.md)): an AOI the footprint
   covers only partially yields a fraction over the covered portion only, which
   can read high even though part of the AOI was unobserved.
5. **This is a crop-SEASON (phenology) cycle, not the AWD flood/dry cycle.** AWD
   oscillates on a sub-monthly cadence; resolving it would need far denser
   imagery **and** parcel-level granularity. Nothing here should be read as
   "AWD detected."
6. **No field ground truth.** No accuracy percentage is claimed for any signal.

## 8. Strategic Conclusion

On the evidence of this AOI's own measurements:

- **Optical-only is sufficient for crop-season phenology monitoring in
  Đông-Xuân** — 7 usable scenes trace a readable seasonal arc.
- **Optical-only is not sufficient for year-round MRV** — Vụ Mùa returned
  **0 usable scenes in 45 days** — **nor for detecting AWD flood/dry events**,
  which are sub-monthly.

Therefore **Sentinel-1 SAR (cloud-penetrating) is the phase-2 direction** for
year-round coverage and AWD-event sensitivity. This is a conclusion drawn from
the numbers measured on this pilot AOI, not a citation from the literature.
