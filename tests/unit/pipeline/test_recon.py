from unittest.mock import patch

from mrv.pipeline.recon import (
    format_summary,
    main,
    summarize_manifest,
)
from mrv.utils.config import Config

CONFIG = Config(
    aoi_path="data/external/aoi/bac_ninh_pilot.geojson",
    gee_project_id="test-project",
    gee_service_account_key_path="/secrets/key.json",
    date_start="2026-06-15",
    date_end="2026-11-15",
    max_cloud_cover_pct=70.0,
    min_clear_fraction=0.8,
    feature_indices=("ndvi", "ndwi", "lswi"),
)

MANIFEST = {
    "max_cloud_cover_pct": 70.0,
    "date_start": "2026-06-15",
    "date_end": "2026-11-15",
    "scene_count": 3,
    "scenes": [
        {"image_id": "s_a", "sensing_date": "2026-07-01", "aoi_clear_fraction": 0.95},
        {"image_id": "s_b", "sensing_date": "2026-07-11", "aoi_clear_fraction": 0.85},
        {"image_id": "s_c", "sensing_date": "2026-07-21", "aoi_clear_fraction": 0.40},
    ],
}


def test_summarize_manifest_reports_both_tiers():
    summary = summarize_manifest(MANIFEST, min_clear_fraction=0.8)

    # Tier 1: scenes returned after the MAX_CLOUD_COVER_PCT query filter.
    assert summary["scene_count"] == 3
    # Tier 2: survival sweep + distribution.
    assert summary["survivors_at_config"] == 2
    assert summary["survival"][0.8] == 2
    assert summary["survival"][0.9] == 1
    assert summary["survival"][0.5] == 2  # 0.40 excluded
    assert summary["clear_fraction_stats"]["max"] == 0.95
    assert summary["clear_fraction_stats"]["min"] == 0.40
    assert summary["histogram"][">=0.9"] == 1  # 0.95
    assert summary["histogram"]["0.8-0.9"] == 1  # 0.85
    assert summary["histogram"]["<0.5"] == 1  # 0.40


def test_summarize_manifest_injects_configured_threshold_into_sweep():
    summary = summarize_manifest(MANIFEST, min_clear_fraction=0.83)

    assert 0.83 in summary["survival"]
    assert summary["survival"][0.83] == 2  # 0.95, 0.85 >= 0.83
    assert summary["survivors_at_config"] == summary["survival"][0.83]


def test_summarize_manifest_handles_empty():
    summary = summarize_manifest({"scenes": []}, min_clear_fraction=0.8)

    assert summary["scene_count"] == 0
    assert summary["clear_fraction_stats"] is None
    assert summary["survivors_at_config"] == 0
    assert all(count == 0 for count in summary["survival"].values())


def test_summarize_manifest_counts_none_fraction_separately():
    # A no-data scene (aoi_clear_fraction=None) must be counted apart from the
    # valid scenes and must not corrupt the numeric tier-2 outputs.
    manifest_with_none = {
        **MANIFEST,
        "scene_count": 4,
        "scenes": MANIFEST["scenes"]
        + [{"image_id": "s_none", "sensing_date": "2026-07-31", "aoi_clear_fraction": None}],
    }

    summary = summarize_manifest(manifest_with_none, min_clear_fraction=0.8)

    # Tier 1 counts every returned scene; the no-data one is a distinct bucket.
    assert summary["scene_count"] == 4
    assert summary["no_data_count"] == 1
    # Tier 2 numbers are identical to the valid-only manifest: None is excluded,
    # never coerced to 0.0.
    baseline = summarize_manifest(MANIFEST, min_clear_fraction=0.8)
    assert summary["clear_fraction_stats"] == baseline["clear_fraction_stats"]
    assert summary["histogram"] == baseline["histogram"]
    assert summary["survival"] == baseline["survival"]
    assert summary["survivors_at_config"] == baseline["survivors_at_config"]


def test_summarize_manifest_all_none_does_not_crash():
    manifest = {
        "max_cloud_cover_pct": 90.0,
        "scene_count": 1,
        "scenes": [
            {"image_id": "s_none", "sensing_date": "2026-07-31", "aoi_clear_fraction": None}
        ],
    }

    summary = summarize_manifest(manifest, min_clear_fraction=0.8)

    assert summary["scene_count"] == 1
    assert summary["no_data_count"] == 1
    assert summary["clear_fraction_stats"] is None
    assert summary["survivors_at_config"] == 0


def test_format_summary_surfaces_no_data_count_at_tier1():
    manifest_with_none = {
        **MANIFEST,
        "scene_count": 4,
        "scenes": MANIFEST["scenes"]
        + [{"image_id": "s_none", "sensing_date": "2026-07-31", "aoi_clear_fraction": None}],
    }

    text = format_summary(summarize_manifest(manifest_with_none, min_clear_fraction=0.8))

    tier1_line = next(line for line in text.splitlines() if line.startswith("Tier 1"))
    assert "1 no-data" in tier1_line
    assert "3 with clear-fraction" in tier1_line


def test_format_summary_labels_both_tiers_and_knobs():
    text = format_summary(summarize_manifest(MANIFEST, min_clear_fraction=0.8))

    assert "Tier 1" in text
    assert "MAX_CLOUD_COVER_PCT" in text
    assert "Tier 2" in text
    assert "MIN_CLEAR_FRACTION" in text


@patch("mrv.pipeline.recon.write_features_table")
@patch("mrv.pipeline.recon.compute_features")
@patch("mrv.pipeline.recon.write_manifest")
@patch("mrv.pipeline.recon.collect_manifest")
@patch("mrv.pipeline.recon.load_config")
def test_main_runs_full_chain_when_scenes_survive(
    mock_load_config, mock_collect, mock_write_manifest, mock_compute, mock_write_table
):
    mock_load_config.return_value = CONFIG
    mock_collect.return_value = MANIFEST
    mock_compute.return_value = [{"image_id": "s_a"}, {"image_id": "s_b"}]

    rc = main()

    assert rc == 0
    mock_collect.assert_called_once_with(CONFIG)
    mock_write_manifest.assert_called_once_with(MANIFEST)
    mock_compute.assert_called_once_with(CONFIG, MANIFEST, ["ndvi", "ndwi", "lswi"], 0.8)
    mock_write_table.assert_called_once_with(
        mock_compute.return_value, ["ndvi", "ndwi", "lswi"]
    )


@patch("mrv.pipeline.recon.write_features_table")
@patch("mrv.pipeline.recon.compute_features")
@patch("mrv.pipeline.recon.write_manifest")
@patch("mrv.pipeline.recon.collect_manifest")
@patch("mrv.pipeline.recon.load_config")
def test_main_skips_compute_when_no_survivors(
    mock_load_config, mock_collect, mock_write_manifest, mock_compute, mock_write_table
):
    mock_load_config.return_value = CONFIG
    mock_collect.return_value = {
        "max_cloud_cover_pct": 70.0,
        "date_start": "2026-06-15",
        "date_end": "2026-11-15",
        "scene_count": 1,
        "scenes": [
            {"image_id": "x", "sensing_date": "2026-07-01", "aoi_clear_fraction": 0.4}
        ],
    }

    rc = main()

    assert rc == 1
    # Manifest still persisted for the record; compute chain is skipped.
    mock_write_manifest.assert_called_once()
    mock_compute.assert_not_called()
    mock_write_table.assert_not_called()
