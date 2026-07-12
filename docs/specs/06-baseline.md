# 06 — Baseline: rule-based crop-season phase detection

Depends on [00-project-overview.md](00-project-overview.md),
[02-features.md](02-features.md), and the first live-run report
([02-first-live-run-report.en.md](../reports/02-first-live-run-report.en.md));
follows the workflow/testing rules in [CLAUDE.md](../../CLAUDE.md). This is
roadmap module 3 (`baseline`).

## Honest reframe (read first)

The roadmap ([00](00-project-overview.md) §Module roadmap) named module 3 a
"rule-based flood/dry-cycle baseline". The first live run
([report 02](../reports/02-first-live-run-report.en.md)) shows that framing
over-promises for the data we actually have: the usable optical series is
**7 scenes across one dry season, unevenly spaced, with a 45-day gap**. That
cadence can resolve **crop-season phenology** (flood/puddling → growth → heading
peak → ripening/harvest), but **cannot** resolve the **sub-monthly AWD flood/dry
cycle**. So this module detects **crop-season phases**, and explicitly **does not
claim AWD-event detection**. Detecting AWD needs far denser observations
(Sentinel-1 SAR for year-round coverage — report 02 §8) and parcel-level
granularity; that is a later phase, not this one.

## What this is

A **rule-based** (threshold-logic, no ML) labeller that turns the AOI-level
spectral series in `data/processed/spectral_indices.csv` into an interpretable,
gap-aware sequence of crop-season phase labels. Pure Python, no `ee.*`, no
network. It lives at **`src/mrv/baseline/`** (the name the roadmap already gives
module 3 — no new `models/` package is introduced). It is the interpretability
layer over `features`, and the foundation the later API/report step consumes.

Rule-based, not ML, is deliberate: there is **no labelled ground truth** for
phases on this AOI yet, so a transparent, inspectable threshold model is the
honest MVP (per [00](00-project-overview.md) §Scope). A learned model may be
compared *against* this baseline later, never swapped in silently.

## Phase taxonomy (crop-season phenology)

Grounded in the 7-scene Đông-Xuân series (report 02 §6):

- **flood / puddling** — canopy absent, standing water: NDVI below an absolute
  low threshold with a water-like NDWI (e.g. 27 Jan: NDVI 0.049, NDWI −0.005).
- **vegetative growth** — NDVI rising (positive per-day trend), mid-range.
- **heading / peak** — a **local NDVI trend reversal (rising → falling)**
  confirmed on both observed sides, with NDVI above an absolute high threshold.
  Detected from the trend, **not** from "the series maximum" (see FR2 — a
  max-based rule is circular).
- **ripening / harvest** — NDVI declining (negative per-day trend) after an
  observed high point in the same observed run.
- **undetermined** — NDVI is high but a reversal cannot be confirmed because one
  side is hidden by a gap or series edge (e.g. the rise into 27 May is behind a
  45-day gap). The module returns `undetermined` rather than force-assigning
  `heading/peak`.
- **ambiguous** — a scene that fits none of the above (e.g. the unexplained
  12 Apr NDVI regression, report 02 §7). Labelled explicitly, never force-fit and
  never dropped silently.

## Hard constraints (from the real data — must be honored)

- **Sparse series**: ~7 usable scenes in a season; the logic must work on few
  points, not assume a dense curve.
- **Uneven spacing**: scenes are days-to-weeks apart (5 days vs 45 days), so the
  trend must be **ΔNDVI per day** (normalised by the actual day-delta), never a
  raw scene-to-scene difference (FR3).
- **A 45-day gap (27 Jan → 13 Mar)** hides the **transplanting** stage. The
  module **must flag large gaps and mark the interval unobserved — it must NOT
  interpolate a phase across a gap** or fabricate the missing stage, and trend
  must never be computed across a flagged gap.
- **AOI-level only** — no parcel granularity.
- **Rainy season = no data**: Vụ Mùa returned 0 usable scenes (report 02 §4), so
  the module may legitimately receive an empty/all-cloudy series; it must degrade
  gracefully, not crash or invent phases.

## Functional requirements

- **FR1 (read + classify)**: read the `features` output
  (`spectral_indices.csv`: `sensing_date`, `ndvi_mean`, `ndwi_mean`, `lswi_mean`,
  `clear_pixel_fraction`) and classify each scene into exactly one taxonomy label
  via documented thresholds over NDVI / NDWI (LSWI a secondary signal).
- **FR2 (non-circular peak)**: `heading/peak` is a **local trend reversal
  (rising→falling) above an absolute NDVI threshold**, NOT the series maximum. A
  max rule is circular — the label would depend on which scene happened to be
  cloud-free, would not run mid-season, and would not transfer to another AOI (it
  would also have enshrined the old 27 Apr cloud-artefact peak, report 02 §3).
  When the reversal cannot be confirmed, return `undetermined`, never a forced
  peak.
- **FR3 (per-day trend)**: trend is **ΔNDVI / day**, normalised by the real
  day-delta; never a raw difference, given the very uneven spacing.
- **FR4 (crop-season naming)**: labels are **crop-season phenology**, named as
  such in code and any output; nothing is labelled or described as an AWD event.
- **FR5 (gap annotation, no fill)**: emit a labelled series (per-scene: date,
  indices, phase) plus **inter-scene gap annotation** — day-delta to the previous
  scene, with gaps above a configured cutoff flagged (`gap_before`) and the
  interval treated as `unobserved`. **No interpolation**; trend never spans a
  flagged gap.
- **FR6 (explicit non-fits)**: an ambiguous scene gets the `ambiguous` label
  (raw indices retained); a high-but-unconfirmable scene gets `undetermined`.
  Never a forced phase, never a crash.
- **FR7 (documented constants)**: thresholds and the gap cutoff are **named,
  documented constants** in one place, not magic numbers scattered through the
  logic.

## Threshold honesty (must be stated in the module + any output)

The thresholds are **hand-set from ONE AOI over ONE season, with no ground-truth
validation**. They encode a plausible reading of this pilot's Đông-Xuân series,
nothing more, and **most likely will not transfer** unchanged to another AOI,
another season, or the rainy season. They are a starting point to be revisited as
more data arrives — not a validated classifier.

## Testing approach (contract, NOT validation)

- **The 7-scene run is a CONTRACT test, not validation.** It asserts structural
  invariants: the module does not crash, honors both ~45-day gaps (flags them,
  marks the interval unobserved), interpolates nothing (output rows = input
  scenes), keeps the robust 27 Jan = flood label, and does not force-fit the
  12 Apr anomaly (→ `ambiguous`) or the gap-isolated 27 May high (→
  `undetermined`). **It does not prove the thresholds are *correct*** — if they
  are tuned on these same 7 points, the test passes by construction and proves
  nothing about accuracy. This limitation is stated in the test itself.
- **Synthetic cases give the discriminating power** the 7-point test cannot:
  - a **monotonic rising** series → all `growth`, no peak fired;
  - a clean **rise-then-fall above threshold** → `heading/peak` at the reversal
    (proves peak detection *does* fire when the data genuinely supports it);
  - a **flat** series → no false peak (`ambiguous`/no-peak);
  - a **single-point** series → no trend, no crash (`undetermined`);
  - an **empty** series (the Vụ Mùa case) → empty output, no crash.
- All tests: standard library only, no `ee.*`, no network, real 7-scene values as
  **inline fixtures** (the CSV under `data/processed/` is gitignored).

## Acceptance criteria

- On the 7-scene Đông-Xuân series: 27 Jan = `flood/puddling`; the rising scenes =
  `growth`; the 12 Apr anomaly = `ambiguous`; the gap-isolated 27 May high =
  `undetermined` (peak not force-claimed); the post-high decline (1 Jun, 21 Jun)
  = `ripening/harvest`. Both ~45-day gaps flagged; nothing interpolated.
- The synthetic rise-then-fall case yields `heading/peak` at the reversal, and the
  monotonic/flat/single/empty cases behave as above — demonstrating the peak rule
  discriminates rather than always firing (or never firing).
- Tests are written **and actually run and pass** (CLAUDE.md workflow).

## Out of scope

- **AWD flood/dry-event detection** — sub-monthly, needs SAR + parcel-level
  (report 02 §8); this module must not claim it.
- ML / trained models; interpolation or gap-filling; parcel-level granularity.
- Methane / carbon-number estimation; API/report/dashboard wiring (later modules
  consume this module's output).
- New dependencies; AWS/cloud; Sentinel-1 fusion.

## Risks / open questions

- **Thresholds are hand-set on one season/one AOI, unvalidated** (see Threshold
  honesty) — labels are interpretive, not verified; they will need revisiting
  with more seasons/AOIs, and any later model must be scored against real ground
  truth, not against these labels.
- **The 12 Apr anomaly is unexplained** (report 02 §7); the baseline flags it, it
  does not explain it.
- **The season's true peak may land in a gap** (as 27 May does), so
  `undetermined` is an expected, honest output — not a bug.
