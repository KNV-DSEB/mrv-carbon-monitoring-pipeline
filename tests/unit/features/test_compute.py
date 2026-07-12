from unittest.mock import MagicMock, patch

import pytest

from mrv.data_collection.sentinel2 import scene_asset_id
from mrv.features.compute import (
    _compute_scene_row,
    _fetch_masked_image,
    _included_scenes,
    compute_features,
    main,
    write_features_table,
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


def test_included_scenes_filters_by_min_clear_fraction():
    manifest = {
        "scenes": [
            {"image_id": "a", "aoi_clear_fraction": 0.9},
            {"image_id": "b", "aoi_clear_fraction": 0.5},
            {"image_id": "c", "aoi_clear_fraction": 0.8},
        ]
    }

    result = _included_scenes(manifest, min_clear_fraction=0.8)

    assert [scene["image_id"] for scene in result] == ["a", "c"]


def test_included_scenes_excludes_none_fraction():
    # A None aoi_clear_fraction (no-data) is excluded without raising on the
    # `None >= x` comparison.
    manifest = {
        "scenes": [
            {"image_id": "a", "aoi_clear_fraction": 0.9},
            {"image_id": "b", "aoi_clear_fraction": None},
            {"image_id": "c", "aoi_clear_fraction": 0.85},
        ]
    }

    result = _included_scenes(manifest, min_clear_fraction=0.8)

    assert [scene["image_id"] for scene in result] == ["a", "c"]


def test_compute_features_raises_on_all_none_manifest():
    # All scenes no-data: must raise the actionable MIN_CLEAR_FRACTION error,
    # not a TypeError from max() over None.
    manifest = {
        "scenes": [
            {"image_id": "a", "sensing_date": "2026-07-01", "aoi_clear_fraction": None},
            {"image_id": "b", "sensing_date": "2026-07-11", "aoi_clear_fraction": None},
        ]
    }

    with pytest.raises(RuntimeError, match="MIN_CLEAR_FRACTION"):
        compute_features(CONFIG, manifest, ["ndvi"], min_clear_fraction=0.8)


@patch("mrv.features.compute.mask_clouds")
@patch("mrv.features.compute.ee")
def test_fetch_masked_image_builds_full_asset_id_and_masks(mock_ee, mock_mask_clouds):
    image_id = "20260710T030529_20260710T031310_T48QWH"

    _fetch_masked_image(image_id)

    mock_ee.Image.assert_called_once_with(scene_asset_id(image_id))
    mock_mask_clouds.assert_called_once_with(mock_ee.Image.return_value)


@patch("mrv.features.compute.zonal_mean")
@patch("mrv.features.compute._fetch_masked_image")
@patch("mrv.features.compute.ee")
def test_compute_scene_row_reuses_clear_fraction_from_manifest(
    mock_ee, mock_fetch_masked_image, mock_zonal_mean
):
    scene = {
        "image_id": "scene_a",
        "sensing_date": "2026-07-01",
        "aoi_clear_fraction": 0.777,
    }
    aoi = MagicMock(name="aoi")

    _compute_scene_row(scene, aoi, index_names=[])

    args, _ = mock_ee.Feature.call_args
    assert args[0] is None
    properties = args[1]
    assert properties["clear_pixel_fraction"] == 0.777
    assert properties["image_id"] == "scene_a"
    assert properties["sensing_date"] == "2026-07-01"
    # Not recomputed: zonal_mean is never asked for a "clear" band here.
    mock_zonal_mean.assert_not_called()


@patch("mrv.features.compute.load_aoi_geometry")
@patch("mrv.features.compute.ee")
@patch("mrv.features.zonal.ee")
def test_compute_features_filters_and_returns_manifest_properties(
    mock_zonal_ee, mock_ee, mock_load_aoi
):
    manifest = {
        "scenes": [
            {"image_id": "scene_a", "sensing_date": "2026-07-01", "aoi_clear_fraction": 0.9},
            {"image_id": "scene_b", "sensing_date": "2026-07-11", "aoi_clear_fraction": 0.3},
        ]
    }
    canned_row = {
        "image_id": "scene_a",
        "sensing_date": "2026-07-01",
        "clear_pixel_fraction": 0.9,
        "ndvi_mean": 0.6,
    }
    mock_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": canned_row}]
    }

    result = compute_features(CONFIG, manifest, ["ndvi"], min_clear_fraction=0.8)

    mock_load_aoi.assert_called_once_with(CONFIG.aoi_path)
    features_arg = mock_ee.FeatureCollection.call_args[0][0]
    assert len(features_arg) == 1  # only scene_a passes the 0.8 threshold
    assert result == [canned_row]


def test_compute_features_raises_when_all_scenes_filtered_out():
    manifest = {
        "scenes": [
            {"image_id": "a", "sensing_date": "2026-07-01", "aoi_clear_fraction": 0.4},
            {"image_id": "b", "sensing_date": "2026-07-11", "aoi_clear_fraction": 0.6},
        ]
    }

    # Actionable error names the exact knob and the best available fraction.
    with pytest.raises(RuntimeError, match="MIN_CLEAR_FRACTION"):
        compute_features(CONFIG, manifest, ["ndvi"], min_clear_fraction=0.8)


def test_compute_features_raises_when_manifest_empty():
    with pytest.raises(RuntimeError, match="0 scenes"):
        compute_features(CONFIG, {"scenes": []}, ["ndvi"], min_clear_fraction=0.8)


def test_write_features_table_writes_expected_csv(tmp_path):
    rows = [
        {
            "image_id": "scene_a",
            "sensing_date": "2026-07-01",
            "clear_pixel_fraction": 0.91,
            "ndvi_mean": 0.62,
            "ndwi_mean": -0.18,
            "lswi_mean": 0.05,
        }
    ]
    output_path = tmp_path / "spectral_indices.csv"

    result_path = write_features_table(rows, ["ndvi", "ndwi", "lswi"], output_path)

    assert result_path == output_path
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "image_id,sensing_date,clear_pixel_fraction,ndvi_mean,ndwi_mean,lswi_mean"
    assert lines[1] == "scene_a,2026-07-01,0.91,0.62,-0.18,0.05"


@patch("mrv.features.compute.write_features_table")
@patch("mrv.features.compute.compute_features")
@patch("mrv.features.compute.load_manifest")
@patch("mrv.features.compute.init_ee")
@patch("mrv.features.compute.load_config")
def test_main_orchestrates_calls_in_order(
    mock_load_config, mock_init_ee, mock_load_manifest, mock_compute_features, mock_write_table
):
    mock_load_config.return_value = CONFIG
    manifest = mock_load_manifest.return_value
    rows = mock_compute_features.return_value

    main()

    mock_load_config.assert_called_once_with()
    mock_init_ee.assert_called_once_with(CONFIG)
    mock_load_manifest.assert_called_once_with()
    mock_compute_features.assert_called_once_with(
        CONFIG, manifest, ["ndvi", "ndwi", "lswi"], 0.8
    )
    mock_write_table.assert_called_once_with(rows, ["ndvi", "ndwi", "lswi"])
