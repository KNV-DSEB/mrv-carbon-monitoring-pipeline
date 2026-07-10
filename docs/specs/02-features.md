# 02 — Features module spec

Depends on [00-project-overview.md](00-project-overview.md) and
[01-data-collection.md](01-data-collection.md); follows the
workflow/testing rules in [CLAUDE.md](../../CLAUDE.md).

## Problem / goal

Turn the raw Sentinel-2 scene manifest produced by `data_collection`
(`data/raw/sentinel2_manifest.json`) into a time series of spectral
indices (NDVI, NDWI, LSWI) summarized over the pilot AOI — the direct
input the next module (rule-based flood/dry-cycle baseline) needs. This
module owns index computation and zonal aggregation; it does not
interpret the resulting values into flood/dry cycles itself.

## Scope (pilot stage)

- **Input scenes**: exactly the scenes already identified in
  `data/raw/sentinel2_manifest.json`. This module issues **no new
  Sentinel-2 collection search/filter queries** (no new
  `ee.ImageCollection(...).filterBounds/.filterDate/.filter` calls) — it
  fetches each scene server-side by its exact `image_id`
  (`ee.Image(image_id)`) and computes on it. Fetching an image directly
  by ID is expected and allowed; only re-searching the Sentinel-2
  collection is out of scope. The manifest fully determines *which*
  scenes get processed; this module doesn't re-search for imagery.
- **Cloud masking**: the manifest only carries metadata, not masked pixel
  data, so this module reapplies the same conservative SCL baseline mask
  used in `data_collection` (clear classes `{4, 5, 6, 11}`, class 7
  Unclassified excluded by default) — reused via a cross-module import
  of `mrv.data_collection.sentinel2.mask_clouds`, not redefined
  differently. Importing across the `data_collection`/`features`
  boundary for this one shared function is acceptable for the pilot —
  it avoids two divergent definitions of "clear pixel" — even though it
  may later be hoisted into a shared location (see Risks below).
- **Indices**: NDVI, NDWI (McFeeters), LSWI — standard Sentinel-2 SR band
  formulas:
  - NDVI = (B8 − B4) / (B8 + B4)
  - NDWI = (B3 − B8) / (B3 + B8)
  - LSWI = (B8 − B11) / (B8 + B11)
- **Zonal statistics**: computed over the **whole pilot AOI as one zone**
  (mean per index per scene) — not per-parcel. There is still no parcel
  boundary dataset (open question carried over from
  [01-data-collection.md](01-data-collection.md)), so parcel-level
  breakdown remains out of reach at this stage.
- **Output granularity**: scalar zonal summaries only (one row per
  scene). Per-scene index raster/image exports are out of scope for the
  pilot — consistent with the "computation runs server-side on GEE, pull
  small summaries not rasters" principle already established in
  `data_collection`.
- Only scenes meeting a configurable minimum `aoi_clear_fraction`
  (from the manifest) are processed — very cloudy scenes are skipped
  rather than producing noisy zonal stats.

## Inputs

- `data/raw/sentinel2_manifest.json` — from `data_collection`.
- `data/external/aoi/bac_ninh_pilot.geojson` — same AOI file, loaded via
  the existing `mrv.data_collection.aoi.load_aoi_geometry` (reused, not
  reimplemented).
- Config: which indices to compute (default: NDVI, NDWI, LSWI — list, not
  hardcoded), minimum clear-fraction threshold to include a scene.

## Outputs

A tabular artifact under `data/processed/` — one row per included scene,
columns: `image_id`, `sensing_date`, `ndvi_mean`, `ndwi_mean`,
`lswi_mean`, `clear_pixel_fraction`. Exact filename/format (CSV vs JSON)
is an open question below (leaning CSV — simple time series, easiest to
hand to the next module and to plot).

`clear_pixel_fraction` is **reused directly from the manifest's
`aoi_clear_fraction`** for the corresponding scene, not recomputed in
this module. It's already the correct "fraction of AOI pixels passing
the same SCL clear-pixel definition" value, computed the same way this
module would compute it again — recomputing it would be redundant GEE
work with no accuracy benefit, and risks silently diverging from the
manifest's value if the two computations were ever implemented
slightly differently.

## Out of scope

- Flood/dry-cycle baseline logic (rule-based detection) — next module in
  the roadmap.
- Any ML/heuristic model training or comparison.
- Per-parcel zonal statistics (no parcel boundary dataset yet).
- New Sentinel-2 collection search/filter queries beyond what
  `data_collection`'s manifest already selected (fetching individual
  scenes by `image_id` is in scope; searching for new ones is not).
- Raster/image exports of index maps.
- Surfacing these features via API or dashboard (later modules).

## Functional requirements

- FR1: Given the manifest + AOI, compute NDVI/NDWI/LSWI zonal mean per
  scene, for scenes meeting the configured minimum clear-fraction.
- FR2: Reapply the same SCL cloud mask as `data_collection` (reused via
  cross-module import, not a second definition).
- FR3: Write results to a defined tabular artifact under
  `data/processed/`.
- FR4: No new Sentinel-2 collection search/filter queries — only fetch
  images by the exact `image_id`s already present in the manifest.
- FR5: Index list and clear-fraction threshold are configurable
  (env/config), not hardcoded, per CLAUDE.md conventions.

## Non-functional requirements

- NFR1: All pixel computation stays server-side on GEE; only small
  scalar summaries are pulled client-side via `getInfo()`.
- NFR2: Deterministic given the same manifest + AOI + config.
- NFR3: Testable without live GEE — `ee.*` mocked, same approach as
  `data_collection`'s tests.
- NFR4: Reuses `data_collection.aoi.load_aoi_geometry` and
  `data_collection.sentinel2.mask_clouds` rather than duplicating them.

## Acceptance criteria

- Given a manifest with N scenes and the pilot AOI, running the module
  produces a tabular artifact with one row per included scene (after
  clear-fraction filtering) and one column per configured index's zonal
  mean, plus `clear_pixel_fraction` carried over from the manifest.
- Unit tests under `tests/unit/features/` (mirroring the existing
  `tests/unit/data_collection/` and `tests/unit/utils/` convention) mock
  `ee.*` calls — no live network or real credentials required.
- Per the CLAUDE.md workflow rule, this module isn't "done" until its
  tests are written **and actually run and passing**.

## Verification approach

- `pytest tests/unit/features/ -v` — mocked `ee`, asserting: correct
  index formulas requested (band pairs per index), correct manifest
  parsing/filtering by clear-fraction, correct output schema/rows
  written, and that `clear_pixel_fraction` passes through from the
  manifest unchanged rather than being recomputed.
- A real run against live GEE is deferred until the pilot AOI is
  finalized and GEE credentials are configured — same caveat already
  documented for `data_collection`.

## Risks / open questions

- **Output format**: CSV vs JSON for the processed artifact — leaning
  CSV (simple tabular time series), not finalized; to confirm at
  implementation-plan time.
- **Zonal stat richness**: mean-only per index for the pilot, or also
  stddev/min/max — leaning mean-only for simplicity, can extend later
  without breaking the schema (additive columns).
- **Shared mask logic**: reusing `data_collection.sentinel2.mask_clouds`
  via a cross-module import is **accepted as fine for the pilot** — it's
  a small, stable function and duplicating it would be worse than one
  cross-module import. Whether it should later be hoisted into a shared
  `utils/` location (to avoid `features/` reaching into
  `data_collection/` internals as the codebase grows) is an
  implementation-time / future-cleanup question, not a blocker now.
- **LSWI SWIR band choice**: B11 vs B12 — B11 is the more commonly used
  choice for LSWI in flood/paddy literature and is proposed here, but
  worth confirming at implementation time.
- Cloud-cover risk (carried from
  [00-project-overview.md](00-project-overview.md)) still applies: even
  with a clear-fraction threshold, partially-masked scenes can produce
  noisier zonal means than fully clear ones — not eliminated, only
  mitigated.
