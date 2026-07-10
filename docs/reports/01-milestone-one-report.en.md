# Milestone 1 Report — MRV Carbon Monitoring Pipeline

**Scope**: Pilot stage, Red River Delta (Bắc Ninh), Vietnam
**Date**: July 2026
**Version**: English ([Bản tiếng Việt](01-milestone-one-report.vi.md))

**Status as of July 2026**: no live Google Earth Engine integration run
has been completed; no field/ground-truth validation has been
completed; the project is at Milestone 1 / local technical MVP stage.

## 1. Executive Summary

Continuously-flooded rice cultivation is a major source of methane
emissions in Vietnam. Alternate Wetting and Drying (AWD) irrigation
reduces those emissions, but smallholder rice farming lacks a
low-cost, scalable measurement, reporting, and verification (MRV)
mechanism to confirm the practice is happening. The MRV Carbon
Monitoring Pipeline is a system built on Sentinel-2 satellite imagery
and Google Earth Engine that estimates AWD adoption through spectral
indices tracking a field's flood/dry state. As of this report, the
first two pipeline modules (`data_collection`, `features`) have
working code, fully unit-tested with all Google Earth Engine calls
mocked, passing 38 unit tests, with a proper packaging setup
(`pyproject.toml` + editable install).

The project is at a pre-traction stage with a working local technical
MVP; the next required step is a real integration run against live
Google Earth Engine credentials and a finalized pilot AOI in Bắc Ninh.

## 2. The Problem

Measuring flood/dry cycles at the scale of individual small rice
fields is difficult for three main reasons. First, in-field soil
moisture or water-level sensors are essentially absent at Vietnam's
smallholder scale — installing and maintaining them across many fields
is not economically viable. Second, field boundaries are typically
small, irregular, and not covered by a standardized, publicly
available parcel-boundary dataset with sufficient detail. Third,
manual field verification across growing seasons and wide areas is
costly and does not scale.

This matters directly for MRV and carbon accounting: issuing carbon
credits for AWD-driven emission reductions requires reproducible,
independently verifiable measurement evidence — not just self-reported
practice from farmers or project developers. The current gap is a
low-cost, scalable remote-sensing method suited to Vietnam's specific
conditions: small field parcels, high cloud cover during the rainy
season, and limited field-measurement infrastructure.

## 3. Approach

The pipeline uses Sentinel-2 Surface Reflectance imagery, queried and
processed through Google Earth Engine (GEE) — all computation (cloud
filtering, spectral index calculation, zonal statistics) runs
server-side on GEE, avoiding the need to download and process
large-volume raster data locally. Three spectral indices serve as
proxy signals for a field's water/vegetation state: NDVI (vegetation),
NDWI using the McFeeters formula (surface water), and LSWI (surface
moisture/water, sensitive via the SWIR band). These are indirect proxy
signals — they do not measure methane or soil moisture directly.

At the current stage, the pipeline computes time-series zonal
statistics (per-index mean value) over the whole pilot AOI for each
satellite scene — a foundational step ahead of building the flood/dry
cycle detection module planned next. This approach fits a developing
market context: it relies entirely on open satellite data
(Sentinel-2, free), an open-source stack, and GEE's free compute quota
for research use — with no dependency on proprietary satellite
infrastructure or heavy cloud spend to get started.

## 4. System Architecture / Pipeline Overview

The pipeline is designed around four sequential modules:

- **`data_collection`** — complete: queries Sentinel-2 via GEE for a
  given AOI and date range, filters cloud cover, exports a scene
  manifest.
- **`features`** — complete: computes spectral indices and zonal
  statistics from the manifest, exports a tabular dataset.
- **`baseline`** — planned: rule-based flood/dry-cycle detection
  (thresholds over NDWI/LSWI); no code written yet.
- **`reporting`** (API + dashboard) — planned: generates field/parcel-
  level MRV-style reports and surfaces them via FastAPI + Streamlit;
  no code written yet.

The actual data flow, as implemented: an AOI GeoJSON file (prepared
outside the system, stored under `data/external/aoi/`) → a scene
manifest JSON at `data/raw/sentinel2_manifest.json` (produced by
`data_collection`) → a spectral-index table at
`data/processed/spectral_indices.csv` (produced by `features`) → the
`baseline` and `reporting` modules (not yet built, intended to consume
the artifacts above).

Three design principles run through the system: (1) all pixel-level
computation happens server-side on GEE, pulling back only small scalar
values via `getInfo()`; (2) every intermediate artifact is small and
tabular/JSON (no raster image exports); (3) all logic is fully
testable locally by mocking `ee.*` calls, requiring no network access
or real credentials to run tests. The whole pipeline follows a
spec-driven workflow: short spec → proposed plan → explicit approval →
implementation → tests → verification, as documented in `CLAUDE.md`.

## 5. What Was Completed in Milestone 1

**`data_collection`** (`src/mrv/data_collection/`): queries the
Sentinel-2 Surface Reflectance collection (`COPERNICUS/S2_SR_HARMONIZED`)
on GEE for a configured AOI and date range (via `.env`); applies a
Scene Classification Layer (SCL)-based cloud mask with a deliberately
conservative baseline (class 7/Unclassified is excluded from the clear-
pixel set by default, not assumed clean); produces a scene manifest in
JSON with `image_id`, `sensing_date`, `mgrs_tile`,
`cloudy_pixel_percentage`, `aoi_clear_fraction`, and `scene_count`.

**`features`** (`src/mrv/features/`): reads the scene manifest,
re-fetches each scene by `image_id`, computes NDVI/NDWI/LSWI
server-side via `ee.Image.normalizedDifference()`, computes a zonal
mean (20 m scale) over the whole AOI per index, filters out scenes
below a configured clear-fraction threshold (`min_clear_fraction`),
and writes the result to `data/processed/spectral_indices.csv`.

**Packaging**: the project is packaged with `pyproject.toml`
(setuptools, src-layout) and installed via `pip install -e .` —
verified to run `python -m mrv.data_collection.collect` from the repo
root without manually setting `PYTHONPATH`.

**Documentation**: `CLAUDE.md` documents the target architecture and
working process; three module specs
(`docs/specs/00-project-overview.md`, `01-data-collection.md`,
`02-features.md`); one decision note on the packaging approach
(`docs/decisions/01-packaging-approach.md`).

**Testing**: **38 unit tests pass** under `tests/unit/`, all mocking
`ee.*` calls, runnable entirely locally with no network access or real
credentials. What this number means: it confirms the query, filtering,
cloud-masking, and index-computation logic behaves as designed — it
does **not** yet confirm the pipeline runs correctly against real
satellite data, since no integration run against live GEE has happened
yet.

Worth stating plainly: the repository is currently a **local-only
technical MVP** — no production deployment, no hosted service, and no
run yet against real satellite data.

## 6. Key Technical Decisions and Rationale

**Why Sentinel-2**: free data, roughly 5-day revisit frequency, and
spatial resolution adequate for observing rice fields — compared to
commercial imagery options that carry meaningfully higher cost for a
pilot-stage project.

**Why Google Earth Engine**: avoids downloading and processing
large-volume raster data locally; leverages GEE's free server-side
compute for research use, matching the project's current local-compute
constraint.

**Why prioritize cloud masking + scene filtering over cloud-free-only
imagery**: the rainy season in Northern Vietnam brings heavy cloud
cover; keeping only fully cloud-free scenes would discard most of the
time series, leaving too little data to track flood/dry cycles. The
decision was to accept partially cloudy scenes, combining scene-level
filtering (cloud-percentage threshold) with pixel-level masking (SCL)
to retain more observation points while still controlling for quality.

**Why AOI-level before parcel-level**: no reliable parcel-boundary
dataset currently exists for the pilot area. This decision is stated
explicitly in both `01-data-collection.md` and `02-features.md`, to
avoid overclaiming the granularity of current results in the absence
of suitable boundary data.

**Why a spec-driven workflow and unit tests before an integration
run**: running against live GEE costs time and compute quota; mocking
all `ee.*` calls allows logic to be verified quickly, at no cost, and
repeatably before spending a real run — reducing the risk of debugging
logic errors against real data that could have been caught earlier.

## 7. Current Limitations and Risks

- **No parcel boundaries yet**: current output is AOI-level only, not
  yet reportable at the level of individual real field parcels.
- **No live GEE run yet**: all 38 tests rely on mocks; the pipeline has
  not been verified against real satellite data.
- **No ground-truth/field validation yet**: there is no field data to
  confirm whether NDVI/NDWI/LSWI actually track real AWD cycles on the
  ground.
- **Spectral indices are indirect proxies**: they do not measure
  methane or soil moisture directly — a methodological limitation, not
  an implementation gap.
- **Dependent on public data and cloud-mask quality**: the pipeline
  relies on Sentinel-2 and (planned) public administrative boundary
  data (GADM); the SCL band used for cloud filtering is not perfectly
  accurate, as already documented in `docs/specs/01-data-collection.md`.

## 8. Next Steps / Milestone 2 Roadmap

1. Run a real integration run: complete Google Earth Engine
   registration, finalize a specific AOI in Bắc Ninh via
   `notebooks/explore_bac_ninh_aoi.py`, then run `data_collection` and
   `features` against real data.
2. Build the `baseline` module — rule-based flood/dry-cycle detection
   over NDWI/LSWI, per the roadmap in
   `docs/specs/00-project-overview.md`.
3. Extend to parcel-level once a reliable field-boundary data source is
   identified.
4. Validate against field data or higher-resolution imagery to test
   the proxy signals.
5. API (FastAPI) and dashboard (Streamlit): stretch goals with no
   committed timeline — the project prioritizes technical correctness
   over speed.

## 9. How to Run This Project (for Technical Reviewers)

```bash
python -m venv .venv
.venv/Scripts/pip install -e .        # macOS/Linux: .venv/bin/pip install -e .

cp .env.example .env
# Fill in GEE_PROJECT_ID, GEE_SERVICE_ACCOUNT_KEY_PATH, AOI_PATH, and
# the remaining variables — see docs/setup/gee_setup.md for GEE setup.

python -m mrv.data_collection.collect  # → data/raw/sentinel2_manifest.json
python -m mrv.features.compute         # → data/processed/spectral_indices.csv

pytest tests/unit/ -v                  # 38 passed
```

The two commands that run the real pipeline (`mrv.data_collection.collect`
and `mrv.features.compute`) require Google Earth Engine credentials and
a configured AOI. This is how to run them once those prerequisites are
in place — it does **not** describe a run that has already been
executed successfully during development as of this report.

## 10. Project Status / Team

The project is currently developed by a single contributor. Status:
pre-traction — a local technical MVP is complete at the level described
in Section 5, with a real integration run and the `baseline` module
still pending. Geographic focus: Vietnam, piloting in Bắc Ninh, Red
River Delta. The project is open to collaboration, pilot partnerships,
or technical feedback — reach out via the project's GitHub repository.
