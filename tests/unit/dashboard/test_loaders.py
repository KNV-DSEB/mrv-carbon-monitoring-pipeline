"""Tests for the dashboard's pure loaders (spec 08).

Two classes of test:
* **Rule tests** on synthetic rows — the gap-break and low-VV rules, which are the
  dashboard's honesty guarantees.
* **Smoke tests against the real committed `data/demo/` snapshots** — these are
  what the dashboard actually ships and reads with no credentials, so they must
  parse (including the `#` disclaimer line that opens crop_phases.csv).
"""

import pytest

from dashboard.loaders import (
    assign_segments,
    load_aoi_polygon,
    load_coverage,
    load_optical_series,
    load_phases,
    load_sar_series,
    mark_low_vv,
    optical_flood_date,
    polygon_centroid,
    sar_vv_min_date,
)


# --- Rule: a line may never span an unobserved gap -----------------------------

def test_assign_segments_starts_a_new_segment_at_every_gap():
    rows = [
        {"sensing_date": "2026-01-27", "gap_before": False},
        {"sensing_date": "2026-03-13", "gap_before": True},   # 45-day gap
        {"sensing_date": "2026-04-07", "gap_before": False},
        {"sensing_date": "2026-05-27", "gap_before": True},   # second gap
    ]

    segments = [r["segment"] for r in assign_segments(rows)]

    # A new segment id at each gap => a chart cannot draw a line across the gap.
    assert segments == [0, 1, 1, 2]


def test_assign_segments_single_segment_when_no_gaps():
    rows = [{"sensing_date": f"2026-01-0{i}", "gap_before": False} for i in (1, 2, 3)]
    assert [r["segment"] for r in assign_segments(rows)] == [0, 0, 0]


# --- Rule: low-VV scenes are derived from the data, not hardcoded --------------

def test_mark_low_vv_flags_only_scenes_at_or_below_the_z_threshold():
    rows = [
        {"sensing_date": "d1", "vv_db": -8.0},
        {"sensing_date": "d2", "vv_db": -8.0},
        {"sensing_date": "d3", "vv_db": -12.0},  # far below the mean
        {"sensing_date": "d4", "vv_db": -8.0},
    ]

    marked = {r["sensing_date"]: r for r in mark_low_vv(rows, z_threshold=-1.0)}

    assert marked["d3"]["low_vv"] is True
    assert marked["d3"]["vv_z"] < -1.0
    assert all(marked[d]["low_vv"] is False for d in ("d1", "d2", "d4"))


def test_mark_low_vv_handles_none_and_too_short_series():
    assert mark_low_vv([])== []
    single = mark_low_vv([{"sensing_date": "d1", "vv_db": -8.0}])
    assert single[0]["low_vv"] is False and single[0]["vv_z"] is None

    with_none = mark_low_vv(
        [
            {"sensing_date": "d1", "vv_db": -8.0},
            {"sensing_date": "d2", "vv_db": None},  # no-data scene
            {"sensing_date": "d3", "vv_db": -9.0},
        ]
    )
    assert with_none[1]["low_vv"] is False and with_none[1]["vv_z"] is None


# --- Smoke tests on the real committed demo snapshots --------------------------

def test_load_phases_parses_the_commented_csv_and_gap_flags():
    phases = load_phases()

    # crop_phases.csv opens with a '#' disclaimer line — it must not be read as
    # the header row.
    assert {"sensing_date", "phase", "gap_before"} <= set(phases[0])
    assert len(phases) == 7
    # The 45-day optical gap is flagged (and the first scene never is).
    assert phases[0]["gap_before"] is False
    assert any(p["gap_before"] for p in phases)


def test_load_sar_series_and_derived_headline_dates():
    sar = load_sar_series()
    phases = load_phases()

    assert len(sar) == 14
    # The two headline dates are derived from the CSVs, not typed in.
    assert sar_vv_min_date(sar) == "2026-01-29"
    assert optical_flood_date(phases) == "2026-01-27"
    # Exactly the three anomalously-low VV scenes fall out of the z rule.
    low = [r["sensing_date"] for r in mark_low_vv(sar) if r["low_vv"]]
    assert low == ["2026-01-29", "2026-02-10", "2026-02-22"]


def test_load_optical_series_and_coverage():
    optical = load_optical_series()
    coverage = load_coverage()

    assert len(optical) == 7
    assert optical[0]["sensing_date"] == "2026-01-27"

    by_key = {(c["season"], c["sensor"]): c for c in coverage}
    # The headline of the whole project: optical is blind in the rainy season.
    assert by_key[("Vụ Mùa", "optical")]["usable_scenes"] == 0
    assert by_key[("Vụ Mùa", "SAR")]["usable_scenes"] == 5
    assert by_key[("Đông-Xuân", "optical")]["usable_scenes"] == 7
    assert by_key[("Đông-Xuân", "SAR")]["usable_scenes"] == 14


def test_load_aoi_polygon_and_centroid():
    ring = load_aoi_polygon()

    assert len(ring) >= 4
    lon, lat = polygon_centroid(ring)
    # Lương Tài, Bắc Ninh.
    assert 106.0 < lon < 106.5
    assert 20.8 < lat < 21.3


def test_missing_demo_file_raises_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="data/demo"):
        load_phases(demo_dir=tmp_path)
