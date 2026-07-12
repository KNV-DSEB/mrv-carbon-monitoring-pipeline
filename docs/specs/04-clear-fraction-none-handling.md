# 04 — Handling `aoi_clear_fraction = None` scenes (no-data vs cloudy)

Depends on [01-data-collection.md](01-data-collection.md),
[02-features.md](02-features.md), and
[03-live-integration-run.md](03-live-integration-run.md); follows the
workflow/testing rules in [CLAUDE.md](../../CLAUDE.md).

> **Semantics corrected by [spec 05](05-clear-fraction-measures-cloud.md).**
> This spec assumed `None` could mean "AOI fully cloud/masked". Spec 05 fixed the
> upstream bug where the manifest was measured on a pre-masked collection: a
> cloudy-but-observed AOI now yields `0.0`, and `None` means **only** that the AOI
> is entirely outside the scene footprint. The `None`-handling below is still
> correct; only the *reason* wording ("fully cloud/masked → None") is superseded.

## What this is

A **bug fix + semantics hardening**, not a new module. It makes the manifest
consumers (`pipeline/recon.py` and `features/compute.py`) correctly handle
scenes whose `aoi_clear_fraction` is `None`, instead of crashing on them.

## Problem (from a live run)

When `MAX_CLOUD_COVER_PCT` is relaxed, the GEE query returns more scenes — and
some of them enter the manifest with `aoi_clear_fraction = None`.

Root cause: `_build_scene_feature`
([sentinel2.py:63-74](../../src/mrv/data_collection/sentinel2.py#L63-L74))
derives the fraction from `reduceRegion(mean).get("clear")`. When the AOI has
**no valid (unmasked) pixels** for that scene — the scene only partially covers
the AOI, or the whole AOI is cloud/masked-out — `reduceRegion` returns `null`,
which serializes to `None` in the manifest JSON.

`None` here means **"no data / AOI not observed"**, which is categorically
different from `0.0` ("observed, but densely clouded"). Both consumers assume a
numeric fraction and break on `None`:

1. **`summarize_manifest`**
   ([recon.py:60](../../src/mrv/pipeline/recon.py#L60)) —
   `float(scene["aoi_clear_fraction"])` → `float(None)` → `TypeError`.
2. **`_included_scenes`**
   ([compute.py:34](../../src/mrv/features/compute.py#L34)) —
   `scene["aoi_clear_fraction"] >= min_clear_fraction` → `None >= 0.8` →
   `TypeError` (unorderable types in Python 3).
3. **`_assert_scenes_to_process`**
   ([compute.py:57](../../src/mrv/features/compute.py#L57)) —
   `max(scene["aoi_clear_fraction"] for scene in all_scenes)` also raises
   `TypeError` once any scene's fraction is `None` (only reached on the
   all-filtered path, but a latent crash all the same).

## Goal

Consume `None`-fraction scenes without crashing, while **keeping "no data"
distinct from "densely cloudy"** — never coerce `None` to `0.0`.

## Non-goals / out of scope

- Changing how `data_collection` produces the manifest (the `None` is a
  legitimate, informative value — this task consumes it, it does not suppress
  it at the source).
- Reprojecting/repairing partial-coverage scenes or clipping the AOI.
- Any change to the `image_id` contract, indices, zonal stats, or thresholds.
- New dependencies; AWS/cloud; API/dashboard/`baseline` modules.

## Functional requirements

- **FR1 (partition, don't coerce)**: `summarize_manifest` splits scenes into
  those with a **valid numeric** `aoi_clear_fraction` and those with `None`.
  All tier-2 numeric outputs — `clear_fraction_stats`, `histogram`, and the
  `survival` sweep — are computed **only over the valid group**. `None` scenes
  are never mapped to `0.0` and never enter those numbers.
- **FR2 (report no-data separately)**: `summarize_manifest` adds a distinct
  count of `None`-fraction scenes (e.g. `no_data_count`), and `format_summary`
  prints it with a **one-line reason** ("AOI only partially covered by the
  scene, or fully cloud/masked — no clear-fraction could be computed"), visibly
  separate from the cloudy/low-fraction scenes. `scene_count` (tier 1) stays the
  full manifest count.
- **FR3 (filter excludes None, no crash)**: in `features/compute.py`, a scene
  with `aoi_clear_fraction = None` is treated as **not meeting**
  `MIN_CLEAR_FRACTION` (excluded from compute), via an explicit `None` check —
  not by comparing `None >= x`.
- **FR4 ("best available" over valid only)**: `_assert_scenes_to_process`
  computes the reported best `aoi_clear_fraction` over valid fractions only,
  and its all-filtered message still makes sense when **every** scene is `None`
  (e.g. states that no scene had a computable clear-fraction).
- **FR5 (no coercion anywhere)**: no code path substitutes `0.0` (or any
  sentinel number) for a `None` fraction; "no data" and "cloudy" stay separable
  end to end.

## Non-functional requirements

- **NFR1**: `summarize_manifest`/`format_summary` stay pure Python over the
  manifest — no `ee.*` — and independently unit-testable (per
  [03](03-live-integration-run.md) NFR1).
- **NFR2**: all tests run locally, `ee.*` mocked, no network/credentials.
- **NFR3**: no new dependencies.
- **NFR4**: existing behavior for all-numeric manifests is unchanged (the
  current recon/compute tests keep passing without edits).

## Tests (unit)

- **recon**: a manifest containing one `None`-fraction scene alongside valid
  scenes → `summarize_manifest` does not raise; the `None` scene is counted in
  the new no-data count; `clear_fraction_stats`/`histogram`/`survival` match the
  valid-only scenes (identical to dropping the `None` scene). `format_summary`
  output includes the no-data line.
- **compute**: a manifest with one `None`-fraction scene → `_included_scenes`
  excludes it without raising; a mixed manifest → included set is exactly the
  valid scenes at/above the threshold. An all-`None` manifest → raises the
  actionable `MIN_CLEAR_FRACTION` error (FR4) rather than a `TypeError` from
  `max()`.

## Acceptance criteria

- Running recon on a manifest with `None`-fraction scenes prints both tiers plus
  a separate no-data count with its reason, and never raises `float(None)`.
- `compute_features` excludes `None`-fraction scenes and never raises on a
  `None` comparison; the all-`None` case raises the FR4 error.
- No code path coerces `None` → `0.0`.
- New/updated unit tests are written **and actually run and pass**, alongside
  the existing recon/compute suites (unchanged).

## Risks / open questions

- **Field name** for the no-data count (`no_data_count` vs alternatives) is a
  presentation choice, not an external contract — adjustable.
- This task assumes `None` is the only non-numeric shape GEE emits for an
  unobservable AOI; if a future GEE change emits `NaN` instead, the valid/None
  partition predicate (`value is None`) would need to also reject `NaN`.
