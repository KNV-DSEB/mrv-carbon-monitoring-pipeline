# MRV Carbon Monitoring Pipeline

AI system for measuring, reporting, and verifying (MRV) methane emission
reductions from Alternate Wetting and Drying (AWD) irrigation in Vietnamese
rice paddies, using Sentinel-2 satellite imagery and climate data.

Pilot region: Bắc Ninh province, Red River Delta.

## Status (as of July 2026)

Milestone 1 complete — a local technical MVP. The `data_collection` and
`features` modules have working, unit-tested code (38 tests passing, all
Google Earth Engine calls mocked). As of this snapshot:

- No live Google Earth Engine integration run has been completed yet.
- No field / ground-truth validation has been completed yet.
- No production deployment exists — local-only.

This is a point-in-time snapshot and will need updating as Milestone 2
work (real integration run, `baseline` module, field validation)
progresses. See the full reports for details:
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
