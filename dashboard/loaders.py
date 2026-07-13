"""Pure data loaders for the dashboard (spec 08).

No Streamlit, no ``ee``, no network: this reads only the committed demo snapshots
under ``data/demo/``, so the dashboard runs with **no Google Earth Engine
credentials**. Kept free of UI imports so every rule here is unit-testable.

Two honesty rules are enforced *here*, in data, rather than left to the UI:

- **Gaps are never bridged.** :func:`assign_segments` starts a new line segment at
  every scene flagged ``gap_before``, so a chart physically cannot draw a line
  across the 45-day unobserved interval (spec 06).
- **Nothing is hardcoded.** The flood date, the SAR VV minimum, and the
  anomalously-low VV scenes are all *derived* from the CSVs at read time.
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = _REPO_ROOT / "data" / "demo"
AOI_PATH = _REPO_ROOT / "data" / "external" / "aoi" / "bac_ninh_pilot.geojson"

# A VV z-score at or below this marks an anomalously low backscatter (a flood
# candidate). The threshold is a rule; the dates it selects come from the data.
LOW_VV_Z = -1.0


def _to_float(value) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV, skipping ``#`` comment lines (crop_phases.csv opens with one)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Demo data not found: {path}. The dashboard reads committed snapshots "
            "from data/demo/ (no GEE credentials needed)."
        )
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = [line for line in f if not line.lstrip().startswith("#")]
    return list(csv.DictReader(rows))


def load_optical_series(demo_dir: Path = DEMO_DIR) -> list[dict]:
    """Raw features table (spectral_indices.csv) — the upstream optical series."""
    rows = _read_csv(Path(demo_dir) / "spectral_indices.csv")
    series = [
        {
            "sensing_date": r["sensing_date"],
            "ndvi": _to_float(r["ndvi_mean"]),
            "ndwi": _to_float(r["ndwi_mean"]),
            "lswi": _to_float(r["lswi_mean"]),
            "clear": _to_float(r["clear_pixel_fraction"]),
        }
        for r in rows
    ]
    return sorted(series, key=lambda r: r["sensing_date"])


def load_phases(demo_dir: Path = DEMO_DIR) -> list[dict]:
    """Labelled optical series (crop_phases.csv): indices + phase + gap flags."""
    rows = _read_csv(Path(demo_dir) / "crop_phases.csv")
    series = [
        {
            "sensing_date": r["sensing_date"],
            "phase": r["phase"],
            "reason": r.get("reason", "") or "",
            "ndvi": _to_float(r.get("ndvi")),
            "ndwi": _to_float(r.get("ndwi")),
            "lswi": _to_float(r.get("lswi")),
            "days_since_prev": _to_float(r.get("days_since_prev")),
            "gap_before": str(r.get("gap_before", "")).strip().lower() == "true",
        }
        for r in rows
    ]
    return sorted(series, key=lambda r: r["sensing_date"])


def load_sar_series(demo_dir: Path = DEMO_DIR) -> list[dict]:
    """SAR backscatter series (s1_backscatter.csv), VV/VH in dB."""
    rows = _read_csv(Path(demo_dir) / "s1_backscatter.csv")
    series = [
        {
            "sensing_date": r["sensing_date"],
            "orbit_pass": r.get("orbit_pass", ""),
            "relative_orbit": r.get("relative_orbit", ""),
            "vv_db": _to_float(r.get("vv_db")),
            "vh_db": _to_float(r.get("vh_db")),
        }
        for r in rows
    ]
    return sorted(series, key=lambda r: r["sensing_date"])


def load_coverage(demo_dir: Path = DEMO_DIR) -> list[dict]:
    """Optical-vs-SAR coverage comparison for both seasons."""
    rows = _read_csv(Path(demo_dir) / "coverage_summary.csv")
    return [
        {
            "season": r["season"],
            "window": r["window"],
            "sensor": r["sensor"],
            "usable_scenes": int(r["usable_scenes"]),
            "gap_min": _to_float(r.get("gap_min")),
            "gap_median": _to_float(r.get("gap_median")),
            "gap_max": _to_float(r.get("gap_max")),
        }
        for r in rows
    ]


def assign_segments(rows: list[dict]) -> list[dict]:
    """Tag each row with a ``segment`` id that increments at every flagged gap.

    Charts draw one line per segment, so **no line can span an unobserved
    interval** — the 45-day optical gap renders as a break, never an interpolation.
    """
    out: list[dict] = []
    segment = 0
    for i, row in enumerate(rows):
        if i > 0 and row.get("gap_before"):
            segment += 1
        out.append({**row, "segment": segment})
    return out


def mark_low_vv(rows: list[dict], z_threshold: float = LOW_VV_Z) -> list[dict]:
    """Attach a VV z-score and flag anomalously low scenes (flood candidates).

    The z-score uses the sample standard deviation over the series' own VV values —
    so the flagged dates are derived from the data, never hardcoded.
    """
    values = [r["vv_db"] for r in rows if r["vv_db"] is not None]
    if len(values) < 2:
        return [{**r, "vv_z": None, "low_vv": False} for r in rows]

    mean = statistics.fmean(values)
    sd = statistics.stdev(values)  # sample sd (n-1)
    out: list[dict] = []
    for row in rows:
        vv = row["vv_db"]
        if vv is None or sd == 0:
            out.append({**row, "vv_z": None, "low_vv": False})
            continue
        z = (vv - mean) / sd
        out.append({**row, "vv_z": z, "low_vv": z <= z_threshold})
    return out


def optical_flood_date(phases: list[dict]) -> str | None:
    """The date the baseline labelled as the flood phase (derived, not hardcoded)."""
    for row in phases:
        if row["phase"].startswith("flood"):
            return row["sensing_date"]
    return None


def sar_vv_min_date(sar_rows: list[dict]) -> str | None:
    """The date of the series' lowest VV backscatter (derived, not hardcoded)."""
    valid = [r for r in sar_rows if r["vv_db"] is not None]
    if not valid:
        return None
    return min(valid, key=lambda r: r["vv_db"])["sensing_date"]


def load_aoi_polygon(path: Path = AOI_PATH) -> list[list[float]]:
    """Exterior ring of the pilot AOI as ``[[lon, lat], ...]``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("type") == "FeatureCollection":
        geometry = data["features"][0]["geometry"]
    elif data.get("type") == "Feature":
        geometry = data["geometry"]
    else:
        geometry = data
    ring = geometry["coordinates"][0]
    return [[float(lon), float(lat)] for lon, lat in ring]


def polygon_centroid(ring: list[list[float]]) -> list[float]:
    """Mean-vertex centroid ``[lon, lat]`` — good enough to centre the map view."""
    lons = [c[0] for c in ring]
    lats = [c[1] for c in ring]
    return [sum(lons) / len(lons), sum(lats) / len(lats)]
