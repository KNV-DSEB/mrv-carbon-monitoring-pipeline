import json
from unittest.mock import patch

import pytest

from mrv.data_collection.collect import collect_manifest, main, write_manifest
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

# image_id holds the bare Sentinel-2 system:index suffix that build_manifest
# stores (not a full asset path) — features re-expands it via scene_asset_id().
CANNED_SCENES = [
    {
        "image_id": "20260701T033539_20260701T034339_T48QWH",
        "sensing_date": "2026-07-01",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 10.0,
        "aoi_clear_fraction": 0.9,
    },
    {
        "image_id": "20260711T033539_20260711T034339_T48QWH",
        "sensing_date": "2026-07-11",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 20.0,
        "aoi_clear_fraction": 0.8,
    },
]


@patch("mrv.data_collection.collect.build_manifest")
@patch("mrv.data_collection.collect.get_filtered_collection")
@patch("mrv.data_collection.collect.load_aoi_geometry")
@patch("mrv.data_collection.collect.init_ee")
def test_collect_manifest_orchestrates_calls_in_order(
    mock_init_ee, mock_load_aoi, mock_get_collection, mock_build_manifest
):
    aoi_mock = mock_load_aoi.return_value
    collection_mock = mock_get_collection.return_value
    mock_build_manifest.return_value = CANNED_SCENES

    manifest = collect_manifest(CONFIG)

    mock_init_ee.assert_called_once_with(CONFIG)
    mock_load_aoi.assert_called_once_with(CONFIG.aoi_path)
    mock_get_collection.assert_called_once_with(
        aoi_mock, CONFIG.date_start, CONFIG.date_end, CONFIG.max_cloud_cover_pct
    )
    # Regression lock (spec 05): aoi_clear_fraction must be measured on the RAW
    # collection so cloud pixels count as 0 in the denominator. Pre-masking here
    # (the old bug) collapsed the metric to ~1.0/None — so build_manifest must
    # receive the unmasked collection and NO cloud mask may be applied on this
    # path. This assertion fails on the old `collection.map(mask_clouds)` code.
    collection_mock.map.assert_not_called()
    mock_build_manifest.assert_called_once_with(collection_mock, aoi_mock)

    assert manifest["aoi_path"] == CONFIG.aoi_path
    assert manifest["date_start"] == CONFIG.date_start
    assert manifest["date_end"] == CONFIG.date_end
    assert manifest["max_cloud_cover_pct"] == CONFIG.max_cloud_cover_pct
    assert manifest["gee_project_id"] == CONFIG.gee_project_id
    assert manifest["scene_count"] == 2
    assert manifest["scenes"] == CANNED_SCENES
    assert "generated_at" in manifest


def test_write_manifest_writes_json_to_output_path(tmp_path):
    manifest = {"scene_count": 1, "scenes": CANNED_SCENES[:1]}
    output_path = tmp_path / "nested" / "manifest.json"

    result_path = write_manifest(manifest, output_path)

    assert result_path == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == manifest


@patch("mrv.data_collection.collect.write_manifest")
@patch("mrv.data_collection.collect.collect_manifest")
@patch("mrv.data_collection.collect.load_config")
def test_main_loads_config_collects_and_writes(
    mock_load_config, mock_collect_manifest, mock_write_manifest
):
    config = mock_load_config.return_value
    manifest = {"scene_count": len(CANNED_SCENES), "scenes": CANNED_SCENES}
    mock_collect_manifest.return_value = manifest

    main()

    mock_load_config.assert_called_once_with()
    mock_collect_manifest.assert_called_once_with(config)
    mock_write_manifest.assert_called_once_with(manifest)


@patch("mrv.data_collection.collect.write_manifest")
@patch("mrv.data_collection.collect.collect_manifest")
@patch("mrv.data_collection.collect.load_config")
def test_main_raises_on_empty_manifest(
    mock_load_config, mock_collect_manifest, mock_write_manifest
):
    mock_load_config.return_value = CONFIG
    mock_collect_manifest.return_value = {"scene_count": 0, "scenes": []}

    with pytest.raises(RuntimeError, match="0 Sentinel-2 scenes"):
        main()

    # Fail fast: no empty manifest is persisted.
    mock_write_manifest.assert_not_called()
