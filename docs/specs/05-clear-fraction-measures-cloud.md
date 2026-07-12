# 05 — `aoi_clear_fraction` must measure cloud (clear / total-in-footprint)

Depends on [01-data-collection.md](01-data-collection.md),
[03-live-integration-run.md](03-live-integration-run.md), and
[04-clear-fraction-none-handling.md](04-clear-fraction-none-handling.md);
follows the workflow/testing rules in [CLAUDE.md](../../CLAUDE.md).

## What this is

A **bug fix + semantics correction**, not a new module. It makes the manifest's
`aoi_clear_fraction` actually reflect cloud cover over the AOI, instead of being
pinned at `1.0`/`None`.

## Problem (from a rainy-season stress test)

Across 13 data-bearing scenes (Đông-Xuân + the Vụ Mùa rain peak, `MAX_CLOUD=100`)
`aoi_clear_fraction` only ever returned `1.000` or `None` — never `0.0` or an
intermediate value. The `MIN_CLEAR_FRACTION` survival sweep is therefore flat
across `0.5→0.9`, i.e. the threshold is effectively a no-op: it cannot separate
clear scenes from cloudy ones because every observed scene reads as perfectly
clear.

## Root cause (verified)

`_build_scene_feature`
([sentinel2.py:61-86](../../src/mrv/data_collection/sentinel2.py#L61-L86))
computes `SCL.remap([4,5,6,11]→1, default 0).mean` over the AOI. Read alone this
is the **correct** clear/total ratio — cloud pixels (SCL 3/8/9/10/…) are not in
the clear set, so `remap`'s default maps them to `0`, counting them in the
denominator.

But `collect_manifest`
([collect.py:25-26](../../src/mrv/data_collection/collect.py#L25-L26)) feeds
`build_manifest` a **pre-masked** collection:

```python
masked_collection = collection.map(mask_clouds)   # updateMask() masks ALL bands, incl. SCL
scenes = build_manifest(masked_collection, aoi)
```

`mask_clouds` (`updateMask(clear.eq(1))`) masks the **SCL band itself**, so the
cloud pixels are already gone before `remap` runs. `remap`'s default `0` never
fires for them (a *masked* pixel stays masked — the default only applies to
*valid* pixels not in `from`), and `reduceRegion(mean)` averages over the
surviving (=clear) pixels only. The metric collapses to `clear/valid ≈ 1.0`, or
`None` when the AOI has no valid pixel left. That reproduces the "1.000 or None"
evidence exactly.

`masked_collection` exists **only** to feed `build_manifest`, and the `features`
module masks independently and correctly for index computation
([compute.py:88](../../src/mrv/features/compute.py#L88)) — so removing this
pre-mask is safe and does not affect `features`.

## Correct contract (target)

- `aoi_clear_fraction = clear_pixels / (TOTAL AOI pixels within the scene
  footprint)`. Cloud / shadow / cirrus count as **0** in the denominator.
- AOI covered by the footprint but fully cloudy ⇒ **0.0** (NOT `None`).
- `None` **only** when the AOI is entirely outside the scene footprint
  (genuinely unobserved). This narrows — but is consistent with — the
  [spec-04](04-clear-fraction-none-handling.md) no-data semantics.

## Fix

- `collect.py`: feed the **raw** `collection` to `build_manifest` (drop the
  `collection.map(mask_clouds)` pre-mask); remove the now-unused `mask_clouds`
  import; add a comment stating clear-fraction is measured on raw SCL.
- `sentinel2.py`: **no formula change** — only document that
  `build_manifest`/`_build_scene_feature` require **unmasked** imagery, that the
  denominator is all in-footprint AOI pixels, and that `None` means "AOI outside
  the footprint".
- Reword the [spec-04](04-clear-fraction-none-handling.md) `None`-reason strings
  in `recon.py`/`compute.py` from "partially covered / fully cloud-masked" to
  "AOI outside the scene footprint (not observed)", to match the narrowed
  semantics above.

## Known limitation (declared, NOT fixed here)

After this fix, an AOI that the footprint covers **only partially** yields a
clear-fraction computed over the **covered portion only** (the uncovered pixels
are masked in the source and excluded from both numerator and denominator) — it
is a number, not `None`. So a scene can report a **high** clear-fraction even
though part of the AOI was never observed by that scene.

This matters for the pilot: the Bắc Ninh AOI sits near swath edges, so recon
already shows frequent no-data — partial coverage is expected. Handling it
correctly needs a separate **coverage check** (footprint-vs-AOI overlap
fraction), which is deferred to a later phase; doing it here would widen this
fix's scope. **For now: declared transparently — read the clear-fraction with
this caveat in mind, especially for scenes near the swath edge.**

## Tests (mock `ee.*`, no network/credentials)

- **Regression lock (must fail on old logic)**: `build_manifest` is called with
  the **raw** collection and `mask_clouds` is not applied on the manifest path;
  the old `build_manifest(masked_collection, …)` fails this assertion.
- **Contract via a small semantics-faithful fake**: modelling `updateMask`,
  `remap(default)`, and `reduceRegion(mean)`, assert all-cloud AOI ⇒ `0.0` (and,
  via the old pre-mask path with the same fake, ⇒ `None`); mixed 3-clear/1-cloud
  ⇒ `0.75`; AOI outside footprint ⇒ `None`.
- **No-coercion passthrough** (ties to spec 04): the `reduceRegion` result flows
  to `aoi_clear_fraction` verbatim — `0.0` stays `0.0`, `None` stays `None`.

## Acceptance

- **Code-level (this task)**: the tests above are written **and actually run and
  pass**; the regression-lock test demonstrably fails if the pre-mask is
  restored.
- **Real acceptance (owner, NOT part of this task)**: the mock/fake tests only
  *establish the code-level contract* — the bug slipped past the prior 57 tests
  because they used opaque `MagicMock`s that model no pixel semantics, so the
  mask-defeats-reducer arithmetic was invisible. Final acceptance is the owner
  re-running `python -m mrv.pipeline.recon` on the rainy window
  `2025-07-01..2025-08-15` with `MAX_CLOUD=100` and now seeing `0.0`/intermediate
  clear-fractions and a **non-flat** survival sweep. Real EE mask/reduce
  arithmetic is the thing a test double only approximates.

## Out of scope

- Changing `mask_clouds` itself, or anything in `features`/`indices`/`zonal`.
- The partial-footprint coverage check (see Known limitation) — later phase.
- API/dashboard/`baseline`; new dependencies; AWS/cloud.
