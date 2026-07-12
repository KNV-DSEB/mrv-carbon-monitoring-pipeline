"""Rule-based crop-season PHASE detection (spec 06).

Turns the AOI-level spectral series in ``data/processed/spectral_indices.csv``
into an interpretable, gap-aware sequence of crop-season phenology labels
(flood/puddling -> vegetative growth -> heading/peak -> ripening/harvest). Pure
Python over the CSV -- no ``ee.*``, no network.

IMPORTANT — this detects CROP-SEASON PHASES, not the sub-monthly AWD flood/dry
cycle. The first live run showed the usable optical cadence (7 scenes across a
season, with 45-day gaps) cannot resolve AWD events; that needs denser imagery
(Sentinel-1 SAR) and parcel-level granularity (see
``docs/reports/02-first-live-run-report.en.md`` and ``docs/specs/06-baseline.md``).
Nothing here should be read as "AWD detected".

The thresholds below are HAND-SET from one AOI over one season, with no
ground-truth validation, and most likely will not transfer unchanged to another
AOI/season. They are a starting point, not a validated classifier.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

DEFAULT_INPUT_PATH = Path("data/processed/spectral_indices.csv")
DEFAULT_OUTPUT_PATH = Path("data/processed/crop_phases.csv")

# --- Tunable constants (hand-set, unvalidated — see module docstring) ---------
# Below FLOOD_NDVI_MAX with a water-like NDWI -> bare flooded field.
FLOOD_NDVI_MAX = 0.15
FLOOD_NDWI_MIN = -0.15
# A heading/peak must clear this absolute NDVI level (a reversal alone isn't
# enough — it guards against calling a low, noisy local bump a "peak").
PEAK_NDVI_MIN = 0.5
# Per-day NDVI slope magnitude below this counts as flat (neither rising nor
# falling). Scene spacing is very uneven, so the slope is ALWAYS per day.
TREND_EPS = 0.0005
# A day-delta above this is a gap: the interval is unobserved, and trend is not
# computed across it.
MAX_GAP_DAYS = 30

# Phase labels (crop-season phenology).
FLOOD = "flood/puddling"
GROWTH = "vegetative growth"
PEAK = "heading/peak"
RIPENING = "ripening/harvest"
UNDETERMINED = "undetermined"
AMBIGUOUS = "ambiguous"

_OUTPUT_DISCLAIMER = (
    "# Crop-season phenology phases (NOT AWD flood/dry events). Rule-based; "
    "thresholds hand-set on one AOI/season and unvalidated (no ground truth)."
)


def _day_delta(earlier: str, later: str) -> int:
    """Whole days between two ``YYYY-MM-DD`` date strings."""
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def load_features_table(path: Path = DEFAULT_INPUT_PATH) -> list[dict]:
    """Read the features CSV into parsed scene rows (sorted by date)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Features table not found: {path}. Run features (mrv.features.compute) first."
        )
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [
            {
                "image_id": r.get("image_id", ""),
                "sensing_date": r["sensing_date"],
                "ndvi": float(r["ndvi_mean"]),
                "ndwi": float(r["ndwi_mean"]),
                "lswi": float(r["lswi_mean"]),
                "clear": float(r["clear_pixel_fraction"]),
            }
            for r in reader
        ]
    return sorted(rows, key=lambda r: r["sensing_date"])


def _high_unconfirmed_reason(
    slope_prev: float | None,
    slope_next: float | None,
    days_prev: int | None,
    days_next: int | None,
    gap_before: bool,
    gap_after: bool,
) -> str:
    """Machine-readable reason a high-NDVI scene can't be confirmed a peak."""
    if slope_prev is None:
        if gap_before and days_prev is not None:
            return f"rise side unobserved ({days_prev}-day gap): peak not confirmable"
        return "rise side unobserved (series start): peak not confirmable"
    if slope_next is None:
        if gap_after and days_next is not None:
            return f"fall side unobserved ({days_next}-day gap): peak not confirmable"
        return "fall side unobserved (series end): peak not confirmable"
    return "high NDVI without a rising->falling reversal: peak not confirmed"


def _classify(
    ndvi: float,
    ndwi: float,
    slope_prev: float | None,
    slope_next: float | None,
    seen_high: bool,
    days_prev: int | None,
    days_next: int | None,
    gap_before: bool,
    gap_after: bool,
) -> tuple[str, str]:
    """Label one scene, returning ``(phase, reason)``.

    ``slope_prev``/``slope_next`` are per-day NDVI slopes to the adjacent scenes,
    or ``None`` when that side is a series edge or across a flagged gap.
    ``seen_high`` is whether an earlier scene in the same observed run already
    reached the peak NDVI level (so a later decline reads as ripening, not noise).
    ``reason`` is a machine-readable string for ``undetermined``/``ambiguous``
    labels, and empty for the confident labels.
    """
    if ndvi < FLOOD_NDVI_MAX and ndwi > FLOOD_NDWI_MIN:
        return FLOOD, ""

    rising_in = slope_prev is not None and slope_prev > TREND_EPS
    falling_in = slope_prev is not None and slope_prev < -TREND_EPS
    rising_out = slope_next is not None and slope_next > TREND_EPS
    falling_out = slope_next is not None and slope_next < -TREND_EPS

    # Confirmed peak: an observed rising->falling reversal, above threshold.
    if ndvi >= PEAK_NDVI_MIN and rising_in and falling_out:
        return PEAK, ""
    # High, but the reversal can't be confirmed (a side is behind a gap/edge):
    # don't force a peak label.
    if ndvi >= PEAK_NDVI_MIN:
        return UNDETERMINED, _high_unconfirmed_reason(
            slope_prev, slope_next, days_prev, days_next, gap_before, gap_after
        )
    # No trend evidence at all (isolated scene) -> can't determine a phase.
    if slope_prev is None and slope_next is None:
        return UNDETERMINED, "isolated scene: no adjacent observations to determine trend"
    # Rising -> growth.
    if rising_in or (slope_prev is None and rising_out):
        return GROWTH, ""
    # Falling -> ripening only if we've already passed a high point this run;
    # a decline before any peak (e.g. the 12 Apr anomaly) is ambiguous.
    if falling_out or (slope_next is None and falling_in):
        if seen_high:
            return RIPENING, ""
        return AMBIGUOUS, "NDVI declining before any observed peak this run (possible anomaly/cloud contamination)"
    # Flat / unclassifiable.
    return AMBIGUOUS, "no clear NDVI trend (flat)"


def detect_phases(rows: list[dict], max_gap_days: int = MAX_GAP_DAYS) -> list[dict]:
    """Label a scene series with crop-season phases, honoring gaps.

    Gaps larger than ``max_gap_days`` are flagged (``gap_before``) and the
    interval is treated as unobserved: no phase is interpolated into it, and the
    NDVI trend is never computed across it. Returns one record per input scene
    (never more — nothing is fabricated).
    """
    rows = sorted(rows, key=lambda r: r["sensing_date"])
    n = len(rows)
    result: list[dict] = []
    seen_high = False  # reset at the start of every gap-bounded run

    for i, row in enumerate(rows):
        if i == 0:
            days_prev: int | None = None
            gap_before = False
            seen_high = False
        else:
            days_prev = _day_delta(rows[i - 1]["sensing_date"], row["sensing_date"])
            gap_before = days_prev > max_gap_days
            if gap_before:
                seen_high = False  # new observed run

        if i < n - 1:
            days_next: int | None = _day_delta(
                row["sensing_date"], rows[i + 1]["sensing_date"]
            )
            gap_after = days_next > max_gap_days
        else:
            days_next = None
            gap_after = False

        slope_prev: float | None = None
        if i > 0 and not gap_before and days_prev:
            slope_prev = (row["ndvi"] - rows[i - 1]["ndvi"]) / days_prev

        slope_next: float | None = None
        if i < n - 1 and not gap_after and days_next:
            slope_next = (rows[i + 1]["ndvi"] - row["ndvi"]) / days_next

        phase, reason = _classify(
            row["ndvi"], row["ndwi"], slope_prev, slope_next, seen_high,
            days_prev, days_next, gap_before, gap_after,
        )
        if row["ndvi"] >= PEAK_NDVI_MIN:
            seen_high = True

        result.append(
            {
                "sensing_date": row["sensing_date"],
                "image_id": row.get("image_id", ""),
                "phase": phase,
                "reason": reason,
                "ndvi": row["ndvi"],
                "ndwi": row["ndwi"],
                "lswi": row.get("lswi"),
                "clear_pixel_fraction": row.get("clear"),
                "days_since_prev": days_prev,
                "gap_before": gap_before,
            }
        )
    return result


def write_phase_table(
    labeled: list[dict], output_path: Path = DEFAULT_OUTPUT_PATH
) -> Path:
    """Write the labelled series to CSV, with an honesty note as the first line."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "sensing_date",
        "image_id",
        "phase",
        "reason",
        "ndvi",
        "ndwi",
        "lswi",
        "clear_pixel_fraction",
        "days_since_prev",
        "gap_before",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        f.write(_OUTPUT_DISCLAIMER + "\n")
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(labeled)
    return output_path


def main() -> Path:
    rows = load_features_table()
    labeled = detect_phases(rows)
    output_path = write_phase_table(labeled)

    print(_OUTPUT_DISCLAIMER)
    if not labeled:
        print(
            "No usable scenes in the features table (e.g. the rainy season "
            "returns 0 clear scenes) — nothing to phase."
        )
    else:
        for rec in labeled:
            gap = " [gap: interval unobserved]" if rec["gap_before"] else ""
            why = f"  - {rec['reason']}" if rec["reason"] else ""
            print(
                f"  {rec['sensing_date']}  {rec['phase']:<18} "
                f"NDVI={rec['ndvi']:.3f}{gap}{why}"
            )
    print(f"Wrote {len(labeled)} labelled scene(s) to {output_path}.")
    return output_path


if __name__ == "__main__":
    main()
