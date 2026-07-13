# MRV Carbon Monitoring Pipeline

Satellite MRV (Measurement, Reporting, Verification) for methane reduction in
Vietnamese rice paddies — **Sentinel-2 optical + Sentinel-1 SAR**, processed
server-side on Google Earth Engine, run end-to-end on **real data** over a pilot
AOI in **Lương Tài, Bắc Ninh**.

> **What this repository actually is:** a **technical portfolio project**, not a
> commercial product. It detects **crop-season phases**, **not** AWD irrigation
> events. There is no field ground truth, so **no accuracy figure is claimed
> anywhere.** The most valuable thing in here is [the technical story](#3-the-technical-story)
> — a silent metric bug that survived 57 tests, how it was caught, and the
> headline result it forced me to throw away.

**Live demo — no credentials needed:** `streamlit run dashboard/app.py`

---

## 1. The problem, and why now

Continuously-flooded rice is one of Vietnam's largest methane sources. **Alternate
Wetting and Drying (AWD)** irrigation cuts those emissions — but smallholder rice
farming has no low-cost, scalable way to *measure, report, and verify* that AWD
actually happened. Without verification, there are no carbon credits.

Timing makes this concrete: Vietnam's **1-million-hectare low-emission rice
programme** pushes AWD at national scale, and credible **MRV is a precondition**
for the carbon financing behind it. Satellite remote sensing is the only
measurement channel that scales to hundreds of thousands of smallholder plots.

## 2. What was built

An end-to-end pipeline, run against **live Google Earth Engine** on a real
2.03 km² paddy AOI (Lương Tài, Bắc Ninh — centroid ≈ 21.0375 N, 106.2198 E):

| Stage | Module | What it does |
|---|---|---|
| Acquisition (optical) | `src/mrv/data_collection/` | Sentinel-2 SR scenes, SCL cloud handling, scene manifest |
| Acquisition (SAR) | `src/mrv/data_collection/sentinel1.py` | Sentinel-1 GRD (IW, VV+VH), orbit-locked |
| Features | `src/mrv/features/` | NDVI/NDWI/LSWI zonal stats; SAR VV/VH backscatter (dB) |
| Baseline | `src/mrv/baseline/` | Rule-based crop-season phase detection |
| Recon | `src/mrv/pipeline/` | Data-density reconnaissance before trusting any output |
| Dashboard | `dashboard/` | Streamlit demo — runs with **no GEE credentials** |

All Earth Engine computation runs server-side; only small scalars come back.
**100 tests (96 unit + 4 integration)**, every `ee.*` call mocked — the suite runs
with no network and no credentials.

## 3. The technical story

This is the part worth reading. It's a story about a metric that lied, and about
how a test suite can be 100% green and still tell you nothing.

**① The first live run looked perfect — and that was the problem.**
8 scenes came back, and **every single one had `aoi_clear_fraction = 1.000`**. The
`MIN_CLEAR_FRACTION` survival sweep was perfectly flat from 0.5 to 0.9. A cloud
metric that never varies is not a good result; it's a broken instrument.

**② I tried to break it, and it wouldn't break.**
I stress-tested against the worst case I could construct: 45 days of **peak rainy
season**, cloud filter wide open (`MAX_CLOUD_COVER_PCT=100`). Northern Vietnam in
July is under near-continuous cloud. The metric *still* returned only `1.000` or
`None`. That settled it — the metric wasn't measuring cloud at all.

**③ Root cause: the pipeline masked the evidence before measuring it.**
`collect.py` applied the SCL cloud mask **before** computing the clear fraction.
`mask_clouds()` masks the SCL band itself, so by the time the reducer ran, the
cloudy pixels were already *gone* — excluded from the denominator instead of
counted as zeros. The metric was computing `clear / valid ≈ 1.0`, not
`clear / total`. **`MIN_CLEAR_FRACTION` was completely inert.**

**④ Why 57 passing tests never noticed.**
Every test mocked `ee.*` with bare `MagicMock`s. A MagicMock models no pixels, so
`mask → reduce` arithmetic simply doesn't exist inside it. The tests asserted that
the right *functions were called* — never that the right *number came out*. The
fix ships with a **semantics-faithful fake** that models masking, `reduceRegion`
means, and no-data, plus tests that **fail on the wrong logic**.
([spec 05](docs/specs/05-clear-fraction-measures-cloud.md))

**⑤ The fix, re-validated on real data.**
Measure the clear fraction on the **raw SCL**, so clouds count as `0` in the
denominator. Re-run the rainy-season window: values now spread across `0.0` and
intermediates, and the survival sweep is no longer flat. The instrument works.

**⑥ The honest cost: my best result was a cloud artefact.**
The original series peaked at **NDVI 0.581 on 27 Apr** — the headline number. With
a working cloud metric, that scene is **cloud-contaminated and gets dropped**. The
real peak is **27 May (0.546)**. My most quotable result was noise, and the fix
deleted it. That is what the fix was *for*.

**⑦ With a working instrument, I could finally measure optical's ceiling.**

| Season | Usable optical scenes |
|---|---|
| Vụ Mùa (rainy, 45 days) | **0 of 11** |
| Đông-Xuân (dry, 5.5 months) | **7 of 38 (~18%)** |

Optical is **completely blind in the rainy season** and thin even in the dry one —
with a 45-day gap that swallowed the transplanting stage.

**⑧ So I added SAR — because of my own numbers, not a paper.**
Sentinel-1 C-band radar penetrates cloud. Locked to a single orbit (DESCENDING/91)
so backscatter is comparable across dates:

| Season | Optical | SAR |
|---|---|---|
| Vụ Mùa (rainy) | 0 scenes | **5 scenes** |
| Đông-Xuân (dry) | 7 scenes | **14 scenes** |

**⑨ Two independent sensors, one flood event.**
SAR's lowest VV backscatter of the season is **−11.32 dB on 29 Jan** (z = −2.00) —
a flooded paddy mirrors radar away from the satellite. Optical, through completely
unrelated physics, independently labels **27 Jan** as the flood phase (NDVI at its
minimum, NDWI at its most water-like). **Two days apart, two mechanisms, one
event.** Two of the three low-VV scenes (10 Feb, 22 Feb) land **inside optical's
45-day blind gap** — SAR sees precisely where optical cannot.

A brief phone call with local farmers recalled flooding in **late January**,
consistent with both sensors. This is **anecdotal, not validation** — small n,
recall-based, no structured protocol.

📄 Full write-ups: [first live run](docs/reports/02-first-live-run-report.en.md) ·
[SAR findings](docs/reports/03-sar-findings-report.en.md) (also in Vietnamese)

## 4. Limitations — and why I stopped here

Stated plainly, because the alternative is overclaiming:

- **This detects crop-SEASON phases, not AWD events.** The seasonal flood phase
  lasts weeks; AWD dry-downs last 5–10 days. Sentinel-1's 12-day repeat (max
  observed gap 24 days) **will miss them**.
- **AWD may not be measurable at AOI scale at all.** Hundreds of parcels drain out
  of sync; in a whole-AOI mean they cancel each other out. Real AWD detection
  needs **per-parcel** analysis — a different, much harder problem.
- **No structured ground truth.** One phone call is not validation. Nothing here
  is scored against reality, so no accuracy percentage is claimed.
- **The market is already served.** Carbon Farm, Mitti Labs, and Varaha are doing
  this commercially with more mature technology, field networks, and registry
  relationships — advantages I do not have.

**Conclusion: I stopped the commercial direction and kept this as a technical
portfolio piece.** The engineering is real, the measurements are real, and the
limits are real. Pretending otherwise would undo the whole point of §3.

## 5. How to run it

### The dashboard (no credentials required)

```bash
python -m venv .venv
.venv/Scripts/pip install -e .        # macOS/Linux: .venv/bin/pip install -e .

streamlit run dashboard/app.py
```

It reads committed snapshots from `data/demo/` — the AOI map, the optical series
with its 45-day gap drawn as a **break** (never interpolated), the SAR series with
the anomalous flood scenes flagged, and the two-sensor cross-check.

### The tests (no credentials, no network)

```bash
pytest tests/unit tests/integration -q     # 100 passed (96 unit + 4 integration)
```

### The live pipeline (needs your own GEE credentials)

```bash
cp .env.example .env                  # fill in GEE_PROJECT_ID, key path, AOI, dates
                                      # see docs/setup/gee_setup.md

python -m mrv.pipeline.recon          # optical reconnaissance
python -m mrv.pipeline.recon_sar      # SAR reconnaissance (reports orbit distribution)
python -m mrv.baseline.detect         # crop-season phase labels
```

## Repository map

```
src/mrv/          data_collection · features · baseline · pipeline · utils
dashboard/        Streamlit app (app.py) + pure, tested loaders (loaders.py)
data/demo/        committed snapshots — the dashboard's credential-free inputs
docs/specs/       one spec per module (00–08)
docs/reports/     live-run reports (EN + VI)
tests/            unit + integration, all ee.* mocked
```

**Stack:** Python · Google Earth Engine · Streamlit · Altair/pydeck · pytest.
