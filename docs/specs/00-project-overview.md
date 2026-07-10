# 00 — Project overview spec

This is the project-level spec: the foundation that future per-feature specs
(`docs/specs/01-...`, `02-...`, …) build on. It defines the product and its
boundaries. For operational rules (how Claude Code should work in this repo —
workflow, testing rules, dependency policy) see [CLAUDE.md](../../CLAUDE.md).

## Problem statement

Continuously-flooded rice paddies are a major source of methane emissions.
Alternate Wetting and Drying (AWD) irrigation reduces those emissions, but
smallholder rice farming in Vietnam lacks a reliable, low-cost mechanism to
measure, report, and verify (MRV) that AWD is actually being practiced and
how much emission reduction it delivers — which is what carbon-credit
issuance requires.

## Goals

Build an end-to-end AI system (data → model → API → dashboard) that
estimates methane emission reduction from AWD practice using Sentinel-2
imagery and climate data, at a quality bar suitable for a climate-tech
portfolio piece / startup pitch — not a notebook demo.

## Success criteria (pilot stage)

- Detect flood/dry irrigation cycles on the Bắc Ninh pilot AOI from
  Sentinel-2 imagery.
- Produce interpretable flood/dry cycle outputs that can be manually
  inspected on sample parcels — the practical validation bar for this
  stage, since no labeled ground truth exists yet to score against.
- Generate a pilot field/parcel-level MRV-style report through the API.
- Surface that report on the dashboard.
- The entire pipeline runs on local compute, end to end.

## Users / stakeholders

- Project owner — building this as a portfolio piece / fundraising pitch.
- Carbon-credit verifiers — assumed end users of the MRV report output
  (not yet validated with a real verifier; an assumption to revisit).

## Scope

- Pilot AOI: Bắc Ninh province, a few km².
- Imagery: Sentinel-2 via Google Earth Engine.
- Features: spectral indices (NDVI, NDWI/LSWI) for flood detection.
- Temporal cadence: time series at Sentinel-2 revisit frequency, subject to
  cloud filtering — not a guaranteed regular/evenly-spaced cadence, so
  downstream cycle detection must tolerate gaps rather than assume a fixed
  interval.
- Detection approach, pilot stage: a **rule-based baseline** — threshold
  logic over NDWI/LSWI to infer flood/dry cycles — rather than a trained ML
  model. Ground truth for AWD cycles isn't available yet, so an
  interpretable baseline is the safer MVP choice. A learned model or other
  heuristic may be introduced later, but it will be evaluated *against* this
  baseline (model/heuristic comparison), not swapped in silently.
- API: FastAPI, serving inference + MRV report generation.
- Dashboard: Streamlit, field-level monitoring and verification status.

See [CLAUDE.md](../../CLAUDE.md) for the full tech stack and architecture.

## Out of scope

See the "Boundaries / out of scope" section in
[CLAUDE.md](../../CLAUDE.md) — not duplicated here so the two documents
don't drift out of sync.

## Module roadmap

Listed in expected order, no timeline commitment (no fixed deadline is a
standing agreement). Each module gets its own spec, written immediately
before that module starts, following the workflow in CLAUDE.md:

1. `data_collection` — Sentinel-2 acquisition via GEE for the pilot AOI.
2. `features` — spectral indices + zonal statistics.
3. Rule-based flood/dry-cycle baseline (with model/heuristic comparison as
   a later, separate step once the baseline exists).
4. `api` — FastAPI inference + MRV report endpoints.
5. `dashboard` — Streamlit field-level view.

## Risks / assumptions

- **Cloud cover**: Sentinel-2 optical imagery over Bắc Ninh will have gaps
  from cloud cover, which can break the flood/dry time series and degrade
  cycle-detection accuracy.
- **No standard field boundaries**: there's no existing field-boundary
  dataset for the pilot AOI. The `data_collection` module spec will need to
  decide between manually drawing a pilot AOI or sourcing reference
  boundaries.
- **No direct methane ground truth**: there is no field-measured methane
  data. The system estimates emission reduction indirectly via a remote-
  sensing proxy (flood/dry cycles), not direct methane measurement — this
  limitation must be stated explicitly in any MRV report the system
  produces, and carried into startup-pitch risk framing.
- **Future extension — Sentinel-1 SAR**: if optical cloud cover turns out to
  be too severe for reliable flood/dry cycle detection on Sentinel-2 alone,
  fusing in Sentinel-1 SAR (cloud-penetrating, widely used in flood/paddy
  monitoring literature to cover exactly this gap) is a natural follow-up
  direction. Not in scope for the pilot — noted here so it isn't
  rediscovered later as a surprise.
