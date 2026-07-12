"""Tests for the rule-based crop-season phase detector (spec 06).

Two kinds of test, deliberately kept distinct (spec 06 §Testing approach):

* The 7-scene run below is a **CONTRACT test, not validation** — it pins
  structural invariants (no crash, gaps honored, nothing interpolated, anomalies
  not force-fit). Because the thresholds in ``detect.py`` were hand-set looking
  at these very points, the phase labels here pass *by construction* and prove
  nothing about real-world accuracy. Real validation needs ground truth we do
  not have.
* The **synthetic** cases are what actually exercise the rules' discriminating
  power: they show the peak rule fires on a genuine reversal, stays silent on a
  flat/rising/gap-isolated series, and that everything degrades gracefully.
"""

from mrv.baseline.detect import (
    AMBIGUOUS,
    FLOOD,
    GROWTH,
    PEAK,
    RIPENING,
    UNDETERMINED,
    detect_phases,
    load_features_table,
    write_phase_table,
)

# The real 7 usable Đông-Xuân scenes, values straight from
# data/processed/spectral_indices.csv (report 02 §6).
SEVEN_SCENES = [
    {"image_id": "s1", "sensing_date": "2026-01-27", "ndvi": 0.04858462154479304, "ndwi": -0.00474211848061936, "lswi": 0.19375993718045015, "clear": 0.6079929267501663},
    {"image_id": "s2", "sensing_date": "2026-03-13", "ndvi": 0.31344815407609, "ndwi": -0.2651931449736379, "lswi": 0.2941548494367712, "clear": 0.9994092755324242},
    {"image_id": "s3", "sensing_date": "2026-04-07", "ndvi": 0.4449545772064142, "ndwi": -0.39247412749202626, "lswi": 0.22383909872413088, "clear": 1.0},
    {"image_id": "s4", "sensing_date": "2026-04-12", "ndvi": 0.30700277658851377, "ndwi": -0.24731604432490842, "lswi": 0.23377615029948906, "clear": 1.0},
    {"image_id": "s5", "sensing_date": "2026-05-27", "ndvi": 0.5462459562570279, "ndwi": -0.4962940423667713, "lswi": 0.169621063942014, "clear": 0.5655982146993869},
    {"image_id": "s6", "sensing_date": "2026-06-01", "ndvi": 0.48992201003341157, "ndwi": -0.4567466744726722, "lswi": 0.12061227369017405, "clear": 0.8511050022393478},
    {"image_id": "s7", "sensing_date": "2026-06-21", "ndvi": 0.2744436926233821, "ndwi": -0.288842216647034, "lswi": 0.1535756678792117, "clear": 0.9637349230127719},
]


def _row(sensing_date, ndvi, ndwi=-0.3, lswi=0.2, clear=1.0):
    return {"image_id": sensing_date, "sensing_date": sensing_date, "ndvi": ndvi, "ndwi": ndwi, "lswi": lswi, "clear": clear}


# --- Contract test on the real series (NOT validation) ------------------------

def test_seven_scene_series_contract():
    result = detect_phases(SEVEN_SCENES)
    phases = {rec["sensing_date"]: rec["phase"] for rec in result}

    # No interpolation: exactly one record per input scene, nothing fabricated.
    assert len(result) == len(SEVEN_SCENES)

    # Robust label: a bare flooded field (very low NDVI + water-like NDWI).
    assert phases["2026-01-27"] == FLOOD
    # Anomalies are not force-fit: the unexplained 12 Apr dip is ambiguous, and
    # the true seasonal high (27 May) is undetermined because its rise is hidden
    # behind a 45-day gap — the detector refuses to claim a peak it can't confirm.
    assert phases["2026-04-12"] == AMBIGUOUS
    assert phases["2026-05-27"] == UNDETERMINED
    # Rising region and post-high decline.
    assert phases["2026-03-13"] == GROWTH
    assert phases["2026-04-07"] == GROWTH
    assert phases["2026-06-01"] == RIPENING
    assert phases["2026-06-21"] == RIPENING


def test_reason_is_machine_readable_for_undetermined_and_ambiguous():
    by_date = {rec["sensing_date"]: rec for rec in detect_phases(SEVEN_SCENES)}

    # 27 May is undetermined because its rise is behind the 45-day gap — the
    # reason must say so, machine-readably (and cite the gap length).
    assert by_date["2026-05-27"]["reason"] == (
        "rise side unobserved (45-day gap): peak not confirmable"
    )
    # The 12 Apr anomaly carries a reason too.
    assert by_date["2026-04-12"]["reason"] != ""
    # Confident labels carry no reason.
    assert by_date["2026-01-27"]["reason"] == ""  # flood
    assert by_date["2026-04-07"]["reason"] == ""  # growth
    assert by_date["2026-06-21"]["reason"] == ""  # ripening


def test_isolated_point_reason_names_the_missing_trend():
    (rec,) = detect_phases([_row("2026-01-01", 0.4)])
    assert rec["phase"] == UNDETERMINED
    assert "isolated" in rec["reason"]


def test_seven_scene_series_flags_both_45_day_gaps():
    by_date = {rec["sensing_date"]: rec for rec in detect_phases(SEVEN_SCENES)}

    # 27 Jan -> 13 Mar (45d) and 12 Apr -> 27 May (45d) are the two gaps.
    assert by_date["2026-03-13"]["gap_before"] is True
    assert by_date["2026-03-13"]["days_since_prev"] == 45
    assert by_date["2026-05-27"]["gap_before"] is True
    assert by_date["2026-05-27"]["days_since_prev"] == 45
    # A 25-day spacing is NOT a gap.
    assert by_date["2026-04-07"]["gap_before"] is False
    assert by_date["2026-04-07"]["days_since_prev"] == 25
    # First scene has no previous.
    assert by_date["2026-01-27"]["days_since_prev"] is None


# --- Synthetic cases: the actual discriminating power -------------------------

def test_peak_fires_on_a_genuine_reversal_above_threshold():
    rows = [
        _row("2026-01-01", 0.2),
        _row("2026-01-11", 0.4),
        _row("2026-01-21", 0.6),  # rising in, falling out, >= 0.5 -> peak
        _row("2026-01-31", 0.4),
        _row("2026-02-10", 0.2),
    ]
    phases = [rec["phase"] for rec in detect_phases(rows)]

    assert phases == [GROWTH, GROWTH, PEAK, RIPENING, RIPENING]


def test_gap_before_a_high_point_suppresses_the_peak_label():
    # A high, falling scene whose RISE is hidden behind a gap must not be called
    # a peak (the non-circular rule) — it is undetermined instead.
    rows = [
        _row("2026-01-01", 0.2),
        _row("2026-01-11", 0.4),  # 10d rising
        _row("2026-03-01", 0.6),  # 49d gap before -> rise unobserved
        _row("2026-03-11", 0.4),  # falling out
    ]
    phases = {rec["sensing_date"]: rec["phase"] for rec in detect_phases(rows)}

    assert phases["2026-03-01"] == UNDETERMINED


def test_monotonic_rising_is_all_growth_no_false_peak():
    rows = [
        _row("2026-01-01", 0.2),
        _row("2026-01-11", 0.3),
        _row("2026-01-21", 0.4),
    ]
    phases = [rec["phase"] for rec in detect_phases(rows)]

    assert phases == [GROWTH, GROWTH, GROWTH]
    assert PEAK not in phases


def test_flat_series_has_no_false_peak():
    rows = [_row(f"2026-01-{d:02d}", 0.4) for d in (1, 11, 21)]
    phases = [rec["phase"] for rec in detect_phases(rows)]

    assert PEAK not in phases
    assert all(p == AMBIGUOUS for p in phases)


def test_single_point_is_undetermined_not_a_crash():
    result = detect_phases([_row("2026-01-01", 0.4)])
    assert [rec["phase"] for rec in result] == [UNDETERMINED]


def test_empty_series_returns_empty_no_crash():
    # The Vụ Mùa (rainy season) case: 0 usable scenes.
    assert detect_phases([]) == []


# --- I/O ----------------------------------------------------------------------

def test_write_phase_table_writes_disclaimer_and_rows(tmp_path):
    labeled = detect_phases(SEVEN_SCENES)
    out = tmp_path / "crop_phases.csv"

    write_phase_table(labeled, out)

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    # First line is the honesty disclaimer (crop-season phases, not AWD).
    assert lines[0].startswith("#")
    assert "NOT AWD" in lines[0]
    assert lines[1].split(",")[:4] == ["sensing_date", "image_id", "phase", "reason"]
    assert len(lines) == 2 + len(labeled)  # disclaimer + header + rows


def test_load_features_table_round_trips_written_features(tmp_path):
    # load_features_table reads the FEATURES csv shape (image_id, sensing_date,
    # clear_pixel_fraction, *_mean), not the phases output.
    csv_path = tmp_path / "spectral_indices.csv"
    csv_path.write_text(
        "image_id,sensing_date,clear_pixel_fraction,ndvi_mean,ndwi_mean,lswi_mean\n"
        "s_b,2026-02-01,0.9,0.2,-0.1,0.3\n"
        "s_a,2026-01-01,0.8,0.1,-0.2,0.25\n",
        encoding="utf-8",
    )

    rows = load_features_table(csv_path)

    # Parsed to floats and sorted by date.
    assert [r["sensing_date"] for r in rows] == ["2026-01-01", "2026-02-01"]
    assert rows[0]["ndvi"] == 0.1 and rows[0]["clear"] == 0.8
