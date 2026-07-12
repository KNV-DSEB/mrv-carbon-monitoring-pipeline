# 07 — Sentinel-1 SAR: acquisition + recon (measure first)

Depends on [00-project-overview.md](00-project-overview.md),
[01-data-collection.md](01-data-collection.md),
[05-clear-fraction-measures-cloud.md](05-clear-fraction-measures-cloud.md), and
the first live-run report
([02-first-live-run-report.en.md](../reports/02-first-live-run-report.en.md));
follows the workflow/testing rules in [CLAUDE.md](../../CLAUDE.md). This adds the
Sentinel-1 branch flagged as the phase-2 direction in report 02 §8.

## Why SAR (from this project's own live run, not a literature citation)

- **Vụ Mùa 2025** (45 days, `MAX_CLOUD=100`): **0 of 11 scenes usable**, max
  `aoi_clear_fraction` 0.185 — optical is **blind** in the rainy season.
- **Đông-Xuân 2025–26**: only **7 of 38 scenes usable (~18%)**, and a 45-day gap
  swallowed both the transplanting stage and the rising side of the true NDVI
  peak (the baseline must return `undetermined` at the real peak — spec 06).

Optical alone is therefore insufficient for year-round MRV or for AWD-event
sensitivity. Sentinel-1 C-band SAR sees through cloud, so it is the candidate fix.

## What this is (and is NOT)

**Acquisition + reconnaissance ONLY.** This measures the real Sentinel-1 scene
density and builds a VV/VH backscatter time series on the pilot AOI. It does
**not** build S1+S2 fusion, an AWD detector, ML, or per-parcel outputs.

Rationale — the "measure first, build second" discipline that has already saved
this project twice (specs 04 and 05): **we do not yet know the real S1 scene
density on this 2.03 km² AOI**, especially after the mandatory single-orbit lock
(below). Measure it, then decide the next step from evidence.

## Physical basis (state precisely; claim nothing beyond it)

A flooded paddy is a smooth water surface → **specular** reflection bounces the
radar pulse away from the satellite → **low VV backscatter**. A drained field
with a standing canopy scatters more energy back → **higher VV**. This is the
physical basis a later flood/dry detector would rest on. **This task only
measures and builds the series — it must NOT claim AWD has been detected, and
with no ground truth it must NOT report any "% accuracy".**

## Mandatory technical requirements (each guards a SILENT failure)

### R1 — Collection & polarisations
- `COPERNICUS/S1_GRD`, filtered to `instrumentMode == 'IW'`, carrying **both**
  `VV` and `VH` (`ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')`
  and likewise `'VH'`).
- **No cloud mask, and the `clear-fraction` concept is dropped entirely** — SAR's
  cloud penetration is the whole point. There is no `MAX_CLOUD_COVER_PCT` /
  `MIN_CLEAR_FRACTION` on this branch.

### R2 — Orbit consistency (silent trap #1: kills a time series with no error)
`ASCENDING` and `DESCENDING` passes — and different relative orbits — image the
AOI at **different incidence angles**, so their backscatter values are **not
comparable across dates**. Mixing them silently corrupts the series.
- **Recon reports the scene distribution by `orbitProperties_pass` AND
  `relativeOrbitNumber_start` (count per group) BEFORE any orbit filtering**, so
  the operator can choose.
- The series pipeline then **locks to exactly ONE pass + ONE relative orbit**,
  configured in `.env` (`S1_ORBIT_PASS`, `S1_RELATIVE_ORBIT`) — **never
  hardcoded**.
- A **fail-fast guard** rejects a manifest that still spans more than one
  (pass, relative-orbit) group, so a forgotten lock cannot pass silently.

### R3 — dB vs linear (silent trap #2: wrong number, no crash)
`S1_GRD` in GEE is in **dB** (log scale), and `mean(dB) ≠ dB(mean(power))`. A
zonal mean MUST convert out of log first:

```
linear      = 10 ** (dB / 10)          # per pixel
aoi_linear  = reduceRegion(mean, linear-image, AOI)
aoi_db      = 10 * log10(aoi_linear)   # back to dB for reporting
```

Averaging in dB directly understates the mean and is a **silent methodological
error**. The formula and its reason are pinned by a test that proves the two
paths differ (see Testing).

### R4 — Speckle (implement it, but be honest about its scale)
SAR carries multiplicative speckle noise. Apply `focal_median` with a **30 m**
kernel on the **linear** image **before** the zonal reduction. Order:
`dB → linear → focal_median (speckle) → reduceRegion(mean) → dB`.

**Quantitative honesty — do NOT oversell this step.** The AOI is ~2.03 km²; at
Sentinel-1's ~10 m pixel spacing that is ≈ **20,300 pixels**. Averaging ~20k
pixels in the zonal mean **already** suppresses speckle (variance falls ~1/N, i.e.
noise ~1/√N), so an explicit focal filter at the **AOI level is nearly
negligible** on the reported mean. It is kept as **future-proofing for per-parcel
work** — where N per field is small and speckle actually bites — and must **not**
be presented as an important methodological step here. Trade-off: smoothing blurs
field-boundary detail (irrelevant at AOI scale, relevant per-parcel). Unlike R2/R3/
R5, this is not a silent-bug guard.

### R5 — Coverage semantics (inherited from specs 04/05)
When the AOI lies outside a scene's footprint there are no valid pixels, so
`reduceRegion(mean)` returns `null` → the backscatter is **`None` (not
observed)**. **`None` must never be coerced to `0`.** A backscatter of `0.0` is a
legitimate value categorically different from "no data" — do not repeat the
spec-04/05 mistake. Recon counts and reports the `None` (out-of-footprint) scenes
separately.

## Architecture (respect the declared module map — no new packages)

- **`src/mrv/data_collection/sentinel1.py`** — S1 collection filtering (R1),
  orbit-distribution reporting (R2), single-orbit lock + the single-orbit
  fail-fast guard, and manifest build (per scene: bare `system:index`,
  `sensing_date`, `orbit_pass`, `relative_orbit`) with a shared
  `scene_asset_id()` id-reconstruction helper (the spec-03 pattern). Reuses
  `init_ee` and `load_aoi_geometry`.
- **`src/mrv/features/backscatter.py`** — per-scene zonal VV & VH in dB
  (R3 + R4 + R5), returning `None` for an out-of-footprint AOI. Reuses
  `zonal.zonal_mean` on the **linearised** band, then converts the mean back to
  dB (it cannot be reused on the raw dB band — that would be the R3 bug).
- **`src/mrv/pipeline/recon_sar.py`** — the SAR recon entry point (own entry
  point; the optical `recon.py` is untouched). Prints the R2 distribution, and
  after the orbit lock the density summary + `None` count, and writes the VV/VH
  table.
- **Config**: add `S1_ORBIT_PASS`, `S1_RELATIVE_ORBIT` to `Config`/`.env.example`,
  loaded **non-strictly** (absent → `None`) so existing optical runs, which do
  not set them, keep working unchanged. `recon_sar` fails fast with a clear
  message if they are needed but unset. `DATE_START`/`DATE_END` are reused.
- **Do not touch the optical code** — `data_collection.collect`/`sentinel2`,
  `features.compute`, `pipeline.recon` must run exactly as before.

## Recon output (must print / write)

1. **Total scenes** returned in the date window (pre-orbit-filter).
2. **Distribution by `orbit_pass` + `relative_orbit`** (count per group) — for the
   operator to choose the lock.
3. **After the orbit lock**: remaining scene count, and inter-scene day-gaps
   (**min / median / max**) — so the operator can see whether the SAR series is
   genuinely **denser** than optical.
4. **Count of scenes with the AOI outside the footprint** (`None` backscatter).
5. **VV/VH mean (dB) by date → CSV** (e.g. `data/processed/s1_backscatter.csv`,
   gitignored).

## Testing (the hard lesson: the spec-05 bug slipped past 57 MagicMock tests)

- **No empty MagicMocks for the computation.** Use a **semantics-faithful fake**
  (as in spec 05) that models: `reduceRegion(mean)` over the **unmasked** pixels,
  the **dB↔linear** conversion, and **`None`** when the AOI has no valid pixel.
- **Tests must FAIL on the wrong logic:**
  - one proving **mean-over-dB ≠ mean-over-linear** (e.g. pixels −20 dB & −10 dB →
    correct ≈ **−12.6 dB**, not the −15 dB a naive dB-mean gives) — this locks R3;
  - one proving a **mixed-orbit** manifest is **blocked** by the R2 guard.
- **`None` is preserved, never coerced to 0** (R5), asserted with the fake.
- **Mock only establishes the contract.** **Real acceptance is the operator**
  running `python -m mrv.pipeline.recon_sar` live with their own credentials over
  **BOTH** windows — **Vụ Mùa `2025-07-01..2025-08-15`** and **Đông-Xuân
  `2026-01-15..2026-06-30`** — and seeing the SAR series come back **clearly
  denser than optical, with the Vụ Mùa window in particular returning scenes
  (optical returned 0)**. Real S1 orbit geometry and speckle are what a fake only
  approximates.

## Prediction to falsify (a self-check for the live run)

SAR penetrates cloud, so there is **no physical reason for it to be blank in the
rainy season**. Concrete falsifiable prediction: the live `recon_sar` over the
**Vụ Mùa window `2025-07-01..2025-08-15`** — where optical returned **0 usable
scenes** — **MUST return Sentinel-1 scenes**. If the rainy-season recon also comes
back with 0 scenes, treat that as a **BUG in the R1 filter / R2 orbit lock, NOT a
property of SAR** — do not accept it as "SAR is blind too". This gives the live
run a built-in way to catch its own configuration errors instead of quietly
trusting a wrong result.

## Acceptance criteria

- Recon prints items 1–5 above; the orbit distribution appears **before** any
  orbit filtering; the single-orbit lock is read from `.env`, not hardcoded.
- The R3 formula, the R2 mixed-orbit guard, and the R5 `None`-not-`0` behaviour
  are each pinned by a test that fails on the wrong logic, all with `ee.*` faked
  (no network/credentials).
- The optical suite still passes unchanged (S2 untouched).
- Tests are written **and actually run and pass** (CLAUDE.md workflow).

## Out of scope (do not build, do not bundle)

S1+S2 fusion; an AWD flood/dry detector; ML; per-parcel granularity;
API/dashboard; AWS/cloud; new dependencies; executing the live GEE run (the
operator's step).

## Risks / open questions

- **Single-orbit lock may thin the series.** After R2 the usable S1 series could
  be sparser than hoped — which is exactly why this is measure-only: the density
  numbers decide whether a flood/dry detector is even feasible next.
- **Backscatter is a proxy**, like the optical indices — it does not measure
  methane or water level directly; any later claim needs ground truth this
  project does not yet have.
- **Speckle filtering blurs boundaries** — fine at AOI scale, revisit before any
  per-parcel work.
