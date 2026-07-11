# MRV Carbon Monitoring Pipeline

AI system for measuring, reporting, and verifying (MRV) methane emission
reductions from Alternate Wetting and Drying (AWD) irrigation in Vietnamese
rice paddies, using Sentinel-2 satellite imagery and climate data.

Pilot region: Bắc Ninh province, Red River Delta.

## Status (as of July 2026)

Milestone 1 complete — a local technical MVP — and now **hardened for a live
integration run**. The `data_collection` and `features` modules have working
code with **51 tests passing (48 unit + 3 integration), all Google Earth Engine
calls mocked** (no network or credentials needed to run the suite).

Readiness work completed for the first real run:

- A reconnaissance entry point — `python -m mrv.pipeline.recon` — runs the full
  `collect → compute` chain and prints a data-density summary: scenes returned
  after the `MAX_CLOUD_COVER_PCT` filter (tier 1), the `aoi_clear_fraction`
  distribution, and how many scenes survive across a `MIN_CLEAR_FRACTION` sweep
  (tier 2) — so the AOI / date window / thresholds can be judged before
  trusting the output.
- Real-data failure modes now fail fast with actionable messages: an empty
  collection, or a manifest where every scene is too cloudy, names the exact
  `.env` knob to adjust (widen the date window / raise `MAX_CLOUD_COVER_PCT`, or
  lower `MIN_CLEAR_FRACTION`) instead of crashing opaquely or writing a silent
  empty artifact.
- The cross-module `image_id` contract (the manifest stores the bare Sentinel-2
  `system:index`; `features` re-expands it to the full asset id) is locked
  behind a single shared helper plus a round-trip test.

As of this snapshot:

- **No live Google Earth Engine integration run has been executed by the author
  yet** — the recon run above is the operator's step, performed with their own
  credentials and a finalized Bắc Ninh AOI.
- No field / ground-truth validation has been completed yet.
- No production deployment exists — local-only.

This is a point-in-time snapshot and will need updating as Milestone 2
work (the real integration run, `baseline` module, field validation)
progresses. The Milestone 1 reports remain the historical snapshot:
[English](docs/reports/01-milestone-one-report.en.md) ·
[Vietnamese](docs/reports/01-milestone-one-report.vi.md).

See [CLAUDE.md](CLAUDE.md) for the target architecture, tech stack, and
working agreements this project follows.

## Project structure

See the "Repository structure" section in [CLAUDE.md](CLAUDE.md).

## Setup

Environment and credential setup guides live under
[docs/setup/](docs/setup/) (starting with Google Earth Engine access).

## Contact

Open to collaboration, pilot partnerships, or technical feedback — reach
out via this GitHub repository.
