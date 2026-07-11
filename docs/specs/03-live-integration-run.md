# 03 — Live integration run readiness (cross-module)

Depends on [00-project-overview.md](00-project-overview.md),
[01-data-collection.md](01-data-collection.md), and
[02-features.md](02-features.md); follows the workflow/testing rules in
[CLAUDE.md](../../CLAUDE.md).

## What this is (and is not)

This is a **cross-module readiness and hardening task**, not a new module. It
does not add a roadmap feature (`baseline`/API/dashboard are untouched). It
prepares the two existing modules — `data_collection` and `features` — for one
real Google Earth Engine (GEE) run, by making their cross-module contract
explicit and test-locked, and by making real-satellite-data failure modes fail
loudly and actionably instead of silently.

**The live GEE run itself is executed by the project owner** with their own
credentials and finalized AOI — it is out of scope here and is not performed as
part of this task. No credentials are needed, requested, printed, or committed
by this work.

## Problem / goal

Milestone 1 delivered `data_collection` and `features` with passing unit tests,
but **every `ee.*` call is mocked** — so no real-data behavior has ever run.
Three classes of real-data problem are invisible to the current mocked tests:

1. **The empty/sparse-data path.** A real AOI + date window + cloud threshold
   can return zero scenes, or a set where every scene is too cloudy to use.
   Today these paths produce a silent empty manifest / empty CSV (or an opaque
   GEE error), with no signal telling the operator which knob to turn.
2. **The `image_id` cross-module contract.** `data_collection` writes each
   scene's `image_id` and `features` re-fetches by it. The contract (what is
   stored vs. what is expected) is currently asserted only by prose comments,
   and the existing test fixtures are mutually inconsistent about its shape — a
   latent break that would only surface on the first real run.
3. **No way to judge data density before committing to the full run.** There is
   no entry point that reports how many scenes came back and how many survive
   the clear-fraction threshold, so the operator cannot tell whether the AOI /
   window / thresholds are viable.

Goal: close all three gaps so the owner's first live run is diagnosable and
its cross-module handoff is verified.

## Scope

- **Reconnaissance / live-run entry point** (`src/mrv/pipeline/recon.py`, per
  CLAUDE.md's reserved `pipeline/` orchestration role): runs the existing
  `collect → compute` chain end to end and prints a data-density summary
  covering **both filter tiers**:
  - **Tier 1 — post-`MAX_CLOUD_COVER_PCT`**: how many scenes the GEE query
    filter returned at all (the manifest `scene_count`).
  - **Tier 2 — `MIN_CLEAR_FRACTION` survival**: the distribution of
    `aoi_clear_fraction` and how many scenes survive across a small threshold
    sweep, so the owner can choose `MIN_CLEAR_FRACTION` from evidence.
- **Harden empty-result paths** in both modules to fail fast with an actionable
  message (see FR2/FR3), never a silent empty artifact or an opaque crash.
- **Lock the `image_id` contract**: one shared source of truth for
  suffix→full-asset-id reconstruction, a round-trip test, and fixtures that
  reflect the real runtime shape.
- **Integration tests** exercising the real `collect → manifest → compute →
  CSV` handoff with `ee.*` mocked (no credentials, CI-runnable).
- **Truthful docs update** (README) reflecting the hardening and the recon
  entry point — without claiming a live run has been executed.

## Out of scope

- Executing the live GEE run (owner-run, gated on their credentials + AOI).
- Sentinel-1 / SAR fusion (a later-stage idea in
  [00-project-overview.md](00-project-overview.md)).
- The `baseline`, API, and dashboard modules.
- Any AWS / cloud spend or infrastructure.
- New dependencies (this task uses only the standard library and the already
  approved stack; no `geopandas`/GIS additions).
- Per-parcel granularity, image/raster exports (unchanged from
  [02-features.md](02-features.md)).

## The `image_id` contract (verified)

- `data_collection` stores, per scene, `image_id = image.get("system:index")`
  — the **bare Sentinel-2 granule suffix**, not the full asset id.
- `features` re-fetches each scene as
  `ee.Image(f"{SENTINEL2_COLLECTION_ID}/{image_id}")`.

These are **consistent at runtime** for `COPERNICUS/S2_SR_HARMONIZED` (prefixing
the collection id onto the `system:index` yields a valid asset id). The risk is
drift, because the contract lives only in comments and the test fixtures
disagree about the shape. This task turns the contract into a single shared
helper plus a round-trip test, and aligns the fixtures to the real shape — the
runtime behavior is unchanged, only made drift-proof.

## Functional requirements

- **FR1 (recon)**: given the configured AOI, date window, and thresholds, an
  entry point runs `collect → compute` and prints a summary with: tier-1
  `scene_count`; `aoi_clear_fraction` min/max/mean/median + a small histogram;
  and tier-2 survival counts across a threshold sweep including the configured
  `MIN_CLEAR_FRACTION`.
- **FR2 (empty collection)**: when `data_collection` returns zero scenes, the
  module entry point raises a clear error naming the AOI, the date window, and
  `MAX_CLOUD_COVER_PCT`, and pointing at the knobs to widen — never a silent
  empty manifest. `collect_manifest()` itself stays non-raising so recon can
  still summarize an empty result.
- **FR3 (all filtered out)**: when no manifest scene meets `MIN_CLEAR_FRACTION`,
  `features` raises a clear error that names `MIN_CLEAR_FRACTION`, reports the
  best available `aoi_clear_fraction`, and distinguishes "manifest is empty →
  run data_collection first" from "manifest has scenes but none clear enough".
- **FR4 (both knobs in guidance)**: recon's low/zero-survivor guidance names
  **both** tuning knobs — widen `MAX_CLOUD_COVER_PCT` / the date window (tier 1)
  *and* lower `MIN_CLEAR_FRACTION` (tier 2) — since a thin result can come from
  either tier.
- **FR5 (contract lock)**: suffix→full-asset-id reconstruction has one shared
  source of truth, used by `features`; a round-trip test pins it; fixtures use
  the real bare-suffix shape.
- **FR6 (config knob)**: `MIN_CLEAR_FRACTION` (and `MAX_CLOUD_COVER_PCT`)
  continue to load from `.env`/config, not hardcoded, and are the exact names
  referenced in the messages above.

## Non-functional requirements

- **NFR1**: recon's summary computation (`aoi_clear_fraction` stats, histogram,
  survival sweep) is pure Python over the manifest — no `ee.*` — and
  independently unit-testable.
- **NFR2**: all tests (unit + integration) run locally with `ee.*` mocked, no
  network and no real credentials, per CLAUDE.md testing rules.
- **NFR3**: no credential or key material is ever printed, logged, or committed.
- **NFR4**: no new dependencies.

## Acceptance criteria

- Running the recon entry point on a manifest prints both filter tiers as in
  FR1, and prints both-knob guidance (FR4) when few/zero scenes survive.
- The empty-collection and all-filtered paths raise the actionable errors of
  FR2/FR3, verified by tests.
- The `image_id` contract has a single shared reconstruction helper and a
  round-trip test; the previously inconsistent fixtures use realistic bare
  `system:index` suffixes (FR5).
- New integration tests under `tests/integration/` cover `collect → manifest →
  compute → CSV` (happy path) plus the empty-collection and all-filtered
  failure paths, all with `ee.*` mocked.
- Per the CLAUDE.md workflow rule, this task is not "done" until its tests are
  written **and actually run and passing**.
- README reflects the hardening + recon entry point and still states plainly
  that no live GEE run has been executed by the author.

## Verification approach

- `pytest tests/unit/ -v` and `pytest tests/integration/ -v` — all green, no
  network / no credentials (every `ee.*` mocked). Record the real totals and
  use them in README (split unit vs integration).
- Import + dry-run the pure recon summary on a canned manifest to confirm both
  tiers and the survival sweep render.
- The live `python -m mrv.pipeline.recon` against real GEE is the **owner's**
  step, performed with their credentials and finalized AOI — explicitly not run
  as part of this task.

## Risks / open questions

- **Recon runs the full `collect → compute` chain**, so a live invocation still
  spends GEE quota; that trade-off is accepted — the summary is printed before
  the compute stage so a thin result is visible early.
- **Threshold sweep values** for the survival report (e.g. `0.5..0.9`) are a
  presentation choice, not a contract; adjustable without breaking anything.
- **Deferred report**: `docs/reports/02-live-run-readiness.*` is intentionally
  **not** written now — it is authored after the owner's first real recon run,
  when actual scene counts and clear-fraction numbers exist to report honestly.
