from unittest.mock import patch

from mrv.pipeline.recon_sar import day_gap_stats, format_distribution, main
from mrv.utils.config import Config


def _config(**overrides):
    base = dict(
        aoi_path="data/external/aoi/bac_ninh_pilot.geojson",
        gee_project_id="p",
        gee_service_account_key_path="/secrets/key.json",
        date_start="2025-07-01",
        date_end="2025-08-15",
        max_cloud_cover_pct=100.0,
        min_clear_fraction=0.5,
        feature_indices=("ndvi",),
    )
    base.update(overrides)
    return Config(**base)


def test_day_gap_stats_uses_real_day_deltas():
    scenes = [
        {"sensing_date": "2026-01-01"},
        {"sensing_date": "2026-01-07"},  # +6
        {"sensing_date": "2026-01-19"},  # +12
    ]

    assert day_gap_stats(scenes) == {"min": 6, "median": 9, "max": 12}


def test_day_gap_stats_none_for_under_two_scenes():
    assert day_gap_stats([{"sensing_date": "2026-01-01"}]) is None
    assert day_gap_stats([]) is None


def test_format_distribution_lists_each_group():
    text = format_distribution(
        [{"orbit_pass": "DESCENDING", "relative_orbit": 18, "count": 5}]
    )
    assert "DESCENDING" in text and "18" in text and "5" in text


@patch("mrv.pipeline.recon_sar.write_backscatter_table")
@patch("mrv.pipeline.recon_sar.compute_backscatter")
@patch("mrv.pipeline.recon_sar.build_manifest")
@patch("mrv.pipeline.recon_sar.get_filtered_collection")
@patch("mrv.pipeline.recon_sar.load_aoi_geometry")
@patch("mrv.pipeline.recon_sar.init_ee")
@patch("mrv.pipeline.recon_sar.load_config")
def test_main_locks_orbit_and_runs_backscatter(
    mock_config, mock_init, mock_aoi, mock_getcol, mock_build, mock_compute, mock_write
):
    mock_config.return_value = _config(s1_orbit_pass="DESCENDING", s1_relative_orbit=18)
    mock_build.return_value = [
        {"image_id": "a", "sensing_date": "2026-01-01", "orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"image_id": "b", "sensing_date": "2026-01-13", "orbit_pass": "ASCENDING", "relative_orbit": 26},
    ]
    mock_compute.return_value = [{"image_id": "a", "vv_db": -12.0, "vh_db": -18.0}]

    rc = main()

    assert rc == 0
    # Only the locked (DESCENDING/18) scene is handed to compute — the other
    # orbit is filtered out before backscatter (R2).
    locked = mock_compute.call_args[0][1]
    assert [s["image_id"] for s in locked] == ["a"]
    mock_write.assert_called_once()


@patch("mrv.pipeline.recon_sar.write_backscatter_table")
@patch("mrv.pipeline.recon_sar.compute_backscatter")
@patch("mrv.pipeline.recon_sar.build_manifest")
@patch("mrv.pipeline.recon_sar.get_filtered_collection")
@patch("mrv.pipeline.recon_sar.load_aoi_geometry")
@patch("mrv.pipeline.recon_sar.init_ee")
@patch("mrv.pipeline.recon_sar.load_config")
def test_main_prints_distribution_and_stops_when_orbit_unset(
    mock_config, mock_init, mock_aoi, mock_getcol, mock_build, mock_compute, mock_write
):
    mock_config.return_value = _config(s1_orbit_pass=None, s1_relative_orbit=None)
    mock_build.return_value = [
        {"image_id": "a", "sensing_date": "2026-01-01", "orbit_pass": "DESCENDING", "relative_orbit": 18}
    ]

    rc = main()

    assert rc == 1  # reports the distribution, then asks the operator to lock
    mock_compute.assert_not_called()
    mock_write.assert_not_called()
