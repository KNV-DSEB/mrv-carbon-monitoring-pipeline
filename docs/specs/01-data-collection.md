# 01 — Data collection module spec

Depends on [00-project-overview.md](00-project-overview.md) and the
workflow/testing rules in [CLAUDE.md](../../CLAUDE.md).

## Problem / goal

Acquire a cloud-filtered Sentinel-2 imagery time series for the Bắc Ninh
pilot AOI, covering one rice growing cycle, as input to the next module
(`features` — index computation). This module owns querying GEE and
producing a reliable scene manifest; it does not compute NDVI/NDWI/LSWI
itself — that's the `features` module.

## Scope

- **AOI**: a public GADM **commune-level (xã)** administrative boundary
  within Bắc Ninh province, optionally 1–3 adjacent communes if a larger
  area is needed — but still on the order of a few km², consistent with
  the pilot AOI size committed to in
  [00-project-overview.md](00-project-overview.md). The exact commune(s)
  are finalized during implementation, chosen for visible rice-paddy
  coverage in sample imagery — not guessed at spec time. Stored as
  GeoJSON at `data/external/aoi/bac_ninh_pilot.geojson`, referenced via
  `AOI_PATH` in `.env` (per existing `.env.example`).
  **District-level (huyện) boundaries are out of scope for the pilot** —
  a district is typically tens to 100+ km², well beyond the committed
  pilot AOI size, so it must not be used even as a convenience shortcut.
- **Date range**: the current/most recent Vụ Mùa season in the Red River
  Delta — approximately June/July to October/November. Exact start/end
  dates finalized at implementation time and parameterized via `.env`,
  not hardcoded, per CLAUDE.md conventions.
- **Data source**: Sentinel-2 Surface Reflectance
  (`COPERNICUS/S2_SR_HARMONIZED`) via Google Earth Engine.
- **Cloud filtering**: server-side filter on scene-level cloud cover %,
  plus a per-pixel cloud mask (QA60 or Scene Classification Layer /
  Cloud Score+) applied server-side in GEE — a cloud-masked
  imagery/metadata pipeline, not a guarantee of zero residual cloud
  contamination (Sentinel-2 cloud masking is rarely perfect).
- **Output**: a scene manifest (image IDs, acquisition dates, cloud %,
  post-filtering) written under `data/raw/` as small JSON/CSV —
  consistent with the "computation runs server-side on GEE" principle in
  CLAUDE.md's tech stack notes; not multi-GB raster exports. Whether to
  also export composite images is an implementation-time decision, not
  required for this module to be "done."
- **Auth**: GEE service-account authentication per
  `docs/setup/gee_setup.md`, credentials via `.env`.

## Out of scope for this module

- Spectral index computation (NDVI/NDWI/LSWI) — `features` module, next.
- Zonal statistics per field/parcel — `features` module, next.
- Rule-based flood/dry-cycle baseline — later module.
- Any AWS/cloud storage — local-only, per CLAUDE.md boundaries.

## Acceptance criteria

- Given the AOI GeoJSON and a date-range config, a function/script under
  `src/mrv/data_collection/` returns/exports a filtered, cloud-masked
  Sentinel-2 scene manifest for the pilot AOI.
- **Manifest metadata contract**: each manifest entry contains, at
  minimum — image ID, sensing date, tile/MGRS tile identifier (if
  available), a cloud metric (e.g. scene cloud cover %), and a
  geometry/reference back to the AOI it was queried against.
- Unit tests under `tests/unit/` cover this logic with `ee.*` calls
  mocked (per CLAUDE.md Testing rules) — no live network or real
  credentials required to run the tests.
- Per the workflow rule in CLAUDE.md, this module isn't "done" until its
  tests are written **and actually run and passing** — not merely
  written.

## Expected dependencies (not yet installed)

Per CLAUDE.md's "no unapproved dependencies" rule, these are proposed
here but require explicit approval at plan/implementation time, not
installed as part of this spec:
- `earthengine-api` — core GEE Python client.
- `python-dotenv` — load `.env` config.
- `geopandas`/`shapely` — **optional**, for AOI GeoJSON handling. Default
  assumption is to defer these and work with raw GeoJSON dicts +
  `ee.Geometry` directly; do not default to installing the full GIS stack
  in the implementation step without confirming it's actually needed.

## Open questions to resolve when the implementation plan is proposed

- Exact GADM commune(s) within Bắc Ninh to use.
- Exact start/end dates for the current Vụ Mùa season.
- Whether module output includes exported image composites or a scene
  manifest only (leaning: manifest-only for this module).
- Whether **parcel-level** output is even achievable without a parcel
  boundary dataset — per the "No standard field boundaries" risk in
  [00-project-overview.md](00-project-overview.md), this module may only
  be able to produce AOI/tile-level manifests, with true parcel-level
  granularity deferred until a boundary source is chosen.
