# 08 — Dashboard (Streamlit, credential-free demo)

Depends on [00-project-overview.md](00-project-overview.md),
[06-baseline.md](06-baseline.md), [07-sentinel1-sar.md](07-sentinel1-sar.md), and
the two live-run reports
([02](../reports/02-first-live-run-report.en.md),
[03](../reports/03-sar-findings-report.en.md)); follows the workflow/testing
rules in [CLAUDE.md](../../CLAUDE.md). This is roadmap module 5 (`dashboard`).

## What this is

A **Streamlit** dashboard that presents the pipeline's results — the optical
crop-phase series, the SAR backscatter series, and the two-sensor cross-check —
as a demo-able story. It is the business-facing view of everything reports 02–03
establish.

## Hard requirement: runs with NO GEE credentials

Reviewers / recruiters have no Earth Engine key, so the dashboard **must run with
zero credentials and zero network**. It reads only from **committed demo
snapshots under `data/demo/`** (small CSVs from the owner's real runs), never
from live GEE. `data/demo/` is whitelisted in `.gitignore`.

Demo inputs (already created, tracked):
- `data/demo/spectral_indices.csv` — 7 optical Đông-Xuân scenes (NDVI/NDWI/LSWI).
- `data/demo/crop_phases.csv` — baseline crop-phase labels + `gap_before` flags.
- `data/demo/s1_backscatter.csv` — 14 SAR Đông-Xuân scenes (VV/VH dB, DESC/91).
- `data/demo/coverage_summary.csv` — optical-vs-SAR usable-scene + gap counts for
  both seasons (the report-03 coverage numbers).
- AOI polygon: the tracked `data/external/aoi/bac_ninh_pilot.geojson`.

## Contents

- **AOI map** — the pilot polygon from the GeoJSON.
- **Tab 1 — Optical**: NDVI/NDWI/LSWI over time with the crop-phase label per
  scene. The **45-day gap must render as a break, not an interpolated line**
  (driven by `gap_before` in `crop_phases.csv`) — never draw a segment across an
  unobserved interval.
- **Tab 2 — SAR**: VV/VH (dB) over time, with the **three anomalously-low VV
  points marked** (29 Jan, 10 Feb, 22 Feb — the flood window).
- **Tab 3 — Two-sensor overlay** (the headline): optical flood (27 Jan) vs SAR
  VV-min (29 Jan) on one aligned time axis — two independent sensors, one event.
- **Coverage table**: optical vs SAR usable scenes + day-gaps for both seasons,
  read from `coverage_summary.csv`.
- **Fixed honesty banner** (always visible): "Phát hiện pha mùa vụ, CHƯA phải
  phát hiện sự kiện AWD. Chưa có ground truth thực địa. Ngưỡng chưa validate."

## Architecture

- **`dashboard/app.py`** — thin Streamlit UI (layout, tabs, charts, banner).
- **`dashboard/loaders.py`** — **pure, testable** helpers: load each CSV into
  plain rows, split a series into gap-aware segments from `gap_before` (so charts
  break at gaps), parse the coverage table, load the AOI polygon coordinates. No
  Streamlit imports here.
- **Charts/map via Streamlit-bundled libraries only** — `st` native charts /
  `altair` for the series, `pydeck` for the AOI polygon. **No new dependency**
  beyond the approved `streamlit` (CLAUDE.md dependency policy). Follow the
  `dataviz` skill for palette, contrast, and legibility (light + dark).

## Non-functional requirements

- **NFR1 — no credentials/network**: reads only `data/demo/` + the AOI GeoJSON;
  no `ee.*`, no live query.
- **NFR2 — no hardcoded numbers**: every figure shown is read from a CSV; nothing
  is typed into the code.
- **NFR3 — no new dependencies**: only `streamlit` (and its bundled `altair` /
  `pydeck`) + the standard library.
- **NFR4 — honest by construction**: the banner is a fixed element, and the gap
  is shown as a break, so the UI can't imply continuous observation or AWD
  detection.

## Tests

- **`tests/unit/dashboard/`** on the pure `loaders.py`: the gap-break split
  (a `gap_before=True` row starts a new segment; no segment spans a gap), the
  coverage-table parse (optical vs SAR both seasons), and the series parse. The
  Streamlit UI itself is verified by **running** it, not unit-tested.

## Acceptance criteria

- `streamlit run dashboard/app.py` renders the map, all three tabs, the coverage
  table, and the banner **with no GEE credentials and no network**.
- The optical chart shows the 45-day gap as a **break**, not an interpolated line.
- Every number on screen traces to a `data/demo/` CSV (nothing hardcoded).
- `pytest tests/unit/dashboard` is written and passes.
- The optical/SAR pipelines are untouched.

## Out of scope

- AWD-event detection or any claim of it; per-parcel views; live GEE queries;
  new dependencies; AWS/hosting; Power BI (a possible later business view, per
  CLAUDE.md — not now).

## Risks / open questions

- **`pydeck` polygon rendering** is the one uncertain piece; if it proves awkward
  offline, fall back to a simpler static map of the AOI bounds (still no new dep).
- The demo snapshots are a **point-in-time copy** of the owner's runs; if the
  pipelines are re-run with different config, refresh `data/demo/` to match.
