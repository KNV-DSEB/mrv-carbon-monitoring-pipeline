# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Early implementation. `data_collection` and `features` are implemented and
unit-tested (all `ee.*` mocked), a reconnaissance/live-run entry point
(`src/mrv/pipeline/recon.py`) exists, and the **first live Google Earth Engine
run has been completed** on the Bắc Ninh pilot AOI (see
`docs/reports/02-first-live-run-report.en.md`). The `baseline` module
(rule-based crop-season phase detection) is the current module. The `api` and
`dashboard` layers are not built yet — those parts of the sections below still
describe the **target architecture** that implementation should converge on.
Update this file as each module lands so it stays a true description of the
codebase, not just an aspiration.

## What this project is

MRV Carbon Monitoring Pipeline: an end-to-end AI system that monitors and
verifies methane emission reductions from **Alternate Wetting and Drying
(AWD)** irrigation in Vietnamese rice paddies, using Sentinel-2 satellite
imagery and climate data. MRV = Measurement, Reporting, Verification — the
standard framework carbon-credit issuers require.

Pilot region: **Bắc Ninh** province — start with a small AOI (a few km²) to
prove the pipeline end-to-end before scaling to district/province coverage.

This is built as a **portfolio-grade system**, not a notebook demo: the bar is
a working data → model → API → dashboard → monitoring chain, deployable and
demoable, structured so it could plausibly become a climate-tech
startup/competition pitch.

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Data acquisition | Google Earth Engine (GEE) Python API | Primary source for Sentinel-2. Chosen over Copernicus Data Space Ecosystem direct download because computation (cloud masking, indices, zonal stats) runs server-side on GEE — no need to store/process multi-GB tiles locally. |
| Language | Python >=3.9 | 3.9 is EOL as of 2025; consider bumping to >=3.10 in the future if earthengine-api and other deps allow. |
| Modeling / experiment tracking | MLflow (local tracking store) | Runs locally under `mlruns/`; no remote tracking server until there's a reason for one. |
| API | FastAPI | Serves inference + MRV report endpoints. |
| Dashboard | Streamlit | Default choice: free, local, code-first, fits local-only compute. Power BI may be added later as a business-facing view — not started until there's a concrete need. |
| Containerization | Docker | For API/dashboard packaging; introduced once a service is stable enough to containerize. |
| Cloud (S3 / SageMaker) | AWS — **phase 2** | Explicitly deferred: current compute budget is local-only. Do not introduce AWS resources, IaC, or SDK calls until the user confirms a cloud budget. |

**Dependency policy**: do not add a dependency outside this table's scope
without asking first — this was an explicit working agreement with the user,
not a default assumption to relax later.

## Architecture (target data flow)

```
Google Earth Engine (Sentinel-2 SR + cloud mask)
        │  AOI-scoped queries, server-side compositing
        ▼
src/mrv/data_collection/   → raw scene metadata + exported composites → data/raw/
        │
        ▼
src/mrv/features/          → spectral indices + zonal stats (AOI-level, pilot) →
        │                     data/processed/ (data/interim/ reserved for later
        │                     per-scene/parcel-level raster artifacts, once parcel
        │                     boundaries are available)
        ▼
src/mrv/models/            → AWD-cycle detection / methane-reduction estimation
        │                     (experiments tracked in MLflow under mlruns/)
        ▼
api/app/                   → FastAPI endpoints: inference, MRV report generation
        │
        ▼
dashboard/                 → Streamlit app: field-level monitoring, verification status
```

`src/mrv/pipeline/` orchestrates the above stages as a runnable sequence
(module-by-module scripts first; only introduce a scheduler/orchestrator like
Prefect or Airflow if the manual sequence becomes a real bottleneck).

## Repository structure

```
data/
  raw/            # unmodified GEE exports / downloads — gitignored, never hand-edited
  interim/        # intermediate processing output — gitignored
  processed/      # model-ready datasets — gitignored unless small reference samples
  external/       # ground-truth / reference data (AWD field boundaries, weather) — gitignored unless small reference samples
src/mrv/
  data_collection/  # GEE queries, AOI definitions, export logic
  features/         # index computation, zonal stats, feature engineering
  models/           # training, inference, evaluation
  pipeline/         # module orchestration / entrypoints
  utils/            # config loading, logging, geo helpers shared across modules
api/app/            # FastAPI application (routers/, schemas/)
dashboard/          # Streamlit app
notebooks/          # exploratory analysis only — nothing here is production code;
                     # logic that proves out should be migrated into src/mrv/
tests/
  unit/             # one test module per src/mrv submodule
  integration/       # cross-module / pipeline-level tests
infra/
  docker/           # Dockerfiles, compose files
  aws/              # IaC — empty until phase 2 (cloud budget confirmed)
docs/setup/          # environment & credential setup guides (e.g. GEE registration)
mlruns/              # local MLflow tracking store — gitignored
```

## Working agreements & feature workflow

Every feature/module goes through the same sequence — do not skip or
collapse steps, and do not start implementing until step 3 is done:

1. **Spec**: write a short spec at `docs/specs/NN-feature-name.md` —
   problem, scope, acceptance criteria. Number sequentially from the
   existing specs in that folder.
2. **Plan**: propose an implementation plan (Claude Code Plan Mode).
3. **Approve**: stop and wait for explicit user approval before writing any
   code. Do not infer approval from silence or from the spec alone.
4. **Implement**: build exactly what was approved. No drive-by refactors or
   "while I'm in here" changes outside the approved scope — if you spot
   something else worth fixing, mention it, don't just do it.
5. **Test**: write tests for the code just implemented.
6. **Verify**: actually run the tests (and, where applicable, exercise the
   behavior) — writing tests without running them does not count as done.
7. **Report**: summarize the step using the format below.

Additional standing rules:
- **Module-by-module with a review gate**: one module at a time; don't
  chain multiple modules/features into a single pass.
- **No unapproved dependencies**: the tech stack table above is the agreed
  scope. If a task needs something outside it (a new PyPI package, a cloud
  resource, a paid API tier), ask before installing/provisioning it.
- **No fixed deadline**: this is an iterative portfolio project — prioritize
  correctness and clarity of each module over speed.
- **Local-only compute for now**: no AWS spend, no SageMaker, no cloud
  infrastructure until the user explicitly confirms a budget.
- Credentials (GEE service account, future AWS keys) are configured via `.env`
  (see `.env.example`) — never hardcoded, never committed.

## Report format

After finishing any step (implementation, tests, or a docs-only change),
report back in exactly this shape:
- **Đã làm gì** — what was done.
- **File nào thay đổi** — which files changed (created/edited/deleted).
- **Cách kiểm tra** — how the user can verify it (commands to run, what to
  look at).
- **Rủi ro còn lại** — remaining risks, gaps, or open questions.

## Testing rules

- Every module under `src/mrv/` gets a corresponding test module under
  `tests/unit/` before it's considered done.
- Tests must run locally without live network access or real credentials —
  mock `ee.*` (Earth Engine) calls and any other external API.
- `tests/integration/` is for cross-module/pipeline-level flows; these may
  be slower and are kept separate from unit tests.
- A step is not "done" until its tests have actually been run and pass —
  not merely written.

## Boundaries / out of scope

- No AWS/cloud spend until the user explicitly confirms a budget.
- No production deployment at this stage — local/demo only.
- No integration with real carbon-credit issuance or trading (registries,
  marketplaces) — scope is MRV estimation only.
- No mobile app or frontend beyond Streamlit.
- No expansion beyond the Bắc Ninh pilot AOI until the pipeline runs
  end-to-end on the pilot region.
- No orchestrator (Airflow/Prefect) until the manual script sequence is an
  actual bottleneck.
- No refactoring outside the current task's approved scope.

## Conventions

- Python: type hints on function signatures in `src/mrv/`; keep GEE-specific
  code (server-side `ee.*` objects) isolated in `data_collection/` and
  `features/` rather than leaking `ee` API calls into `models/` or `api/`.
- AOI (area of interest) definitions are data, not code — store them as
  GeoJSON under `data/external/aoi/` rather than inlining coordinates in
  Python modules, so the pilot region can change without touching logic.
- Config (AOI paths, GEE project id, date ranges) loads from environment
  variables / `.env`, not from hardcoded constants, so the same code runs
  against different pilot regions later.
- See "Testing rules" above for test requirements.
