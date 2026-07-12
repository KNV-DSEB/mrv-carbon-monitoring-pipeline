"""Cross-module flow: collect -> manifest (on disk) -> compute -> CSV.

All ``ee.*`` is mocked at the module boundary, so these run in CI with no
network and no credentials. Unlike the unit tests (which check each module in
isolation), these pin the *handoff*: the manifest data_collection writes is
readable by features, the bare ``image_id`` reconstructs to the full asset id
via the shared ``scene_asset_id`` contract, and the CSV schema lines up. The
empty / all-filtered paths assert the fail-fast messages surface.
"""

from unittest.mock import patch

import pytest

from mrv.data_collection.collect import collect_manifest, write_manifest
from mrv.data_collection.collect import main as collect_main
from mrv.data_collection.sentinel2 import SENTINEL2_COLLECTION_ID
from mrv.features.compute import compute_features, load_manifest, write_features_table
from mrv.pipeline.recon import summarize_manifest
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

# Bare system:index suffixes — exactly what build_manifest stores on real data.
SCENES = [
    {
        "image_id": "20260701T033539_20260701T034339_T48QWH",
        "sensing_date": "2026-07-01",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 8.0,
        "aoi_clear_fraction": 0.95,
    },
    {
        "image_id": "20260711T033539_20260711T034339_T48QWH",
        "sensing_date": "2026-07-11",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 15.0,
        "aoi_clear_fraction": 0.82,
    },
    {
        "image_id": "20260721T033539_20260721T034339_T48QWH",
        "sensing_date": "2026-07-21",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 60.0,
        "aoi_clear_fraction": 0.40,
    },
]


@patch("mrv.features.compute.load_aoi_geometry")
@patch("mrv.features.compute.zonal_mean")
@patch("mrv.features.compute.ee")
@patch("mrv.data_collection.collect.load_aoi_geometry")
@patch("mrv.data_collection.collect.init_ee")
@patch("mrv.data_collection.sentinel2.ee")
def test_collect_to_compute_happy_path(
    mock_s2_ee,
    mock_init_ee,
    mock_collect_aoi,
    mock_compute_ee,
    mock_zonal_mean,
    mock_compute_aoi,
    tmp_path,
):
    # --- collect: build_manifest's getInfo yields bare-suffix scenes ---
    mock_s2_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": scene} for scene in SCENES]
    }

    manifest = collect_manifest(CONFIG)
    manifest_path = tmp_path / "sentinel2_manifest.json"
    write_manifest(manifest, manifest_path)

    on_disk = load_manifest(manifest_path)
    assert on_disk["scene_count"] == 3
    # The persisted ids are bare suffixes, not full asset paths.
    for scene in on_disk["scenes"]:
        assert not scene["image_id"].startswith(SENTINEL2_COLLECTION_ID)

    # --- compute: getInfo yields canned rows for the surviving scenes ---
    surviving = [
        scene
        for scene in SCENES
        if scene["aoi_clear_fraction"] >= CONFIG.min_clear_fraction
    ]
    canned_rows = [
        {
            "image_id": scene["image_id"],
            "sensing_date": scene["sensing_date"],
            "clear_pixel_fraction": scene["aoi_clear_fraction"],
            "ndvi_mean": 0.6,
        }
        for scene in surviving
    ]
    mock_compute_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": row} for row in canned_rows]
    }

    rows = compute_features(CONFIG, on_disk, ["ndvi"], CONFIG.min_clear_fraction)
    csv_path = tmp_path / "spectral_indices.csv"
    write_features_table(rows, ["ndvi"], csv_path)

    # Cross-module contract: each surviving bare id was reconstructed to the
    # full asset id before ee.Image(...).
    requested = [call.args[0] for call in mock_compute_ee.Image.call_args_list]
    assert requested == [
        f"{SENTINEL2_COLLECTION_ID}/{scene['image_id']}" for scene in surviving
    ]

    # CSV schema + one row per surviving scene.
    lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "image_id,sensing_date,clear_pixel_fraction,ndvi_mean"
    assert len(lines) == 1 + len(surviving)
    assert lines[1].startswith(surviving[0]["image_id"])


@patch("mrv.features.compute.load_aoi_geometry")
@patch("mrv.features.compute.zonal_mean")
@patch("mrv.features.compute.ee")
@patch("mrv.data_collection.collect.load_aoi_geometry")
@patch("mrv.data_collection.collect.init_ee")
@patch("mrv.data_collection.sentinel2.ee")
def test_none_fraction_scene_flows_through_without_a_csv_row(
    mock_s2_ee,
    mock_init_ee,
    mock_collect_aoi,
    mock_compute_ee,
    mock_zonal_mean,
    mock_compute_aoi,
    tmp_path,
):
    # A no-data scene (aoi_clear_fraction=None) interleaved among valid ones:
    # summarize -> compute -> CSV must not crash, and the None scene must not
    # produce a CSV row.
    none_scene = {
        "image_id": "20260716T033539_20260716T034339_T48QWH",
        "sensing_date": "2026-07-16",
        "mgrs_tile": "48QWH",
        "cloudy_pixel_percentage": 45.0,
        "aoi_clear_fraction": None,
    }
    interleaved = [SCENES[0], none_scene, SCENES[1], SCENES[2]]  # 0.95, None, 0.82, 0.40

    mock_s2_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": scene} for scene in interleaved]
    }

    manifest = collect_manifest(CONFIG)
    manifest_path = tmp_path / "sentinel2_manifest.json"
    write_manifest(manifest, manifest_path)
    on_disk = load_manifest(manifest_path)

    # summarize does not crash on the None and counts it as no-data.
    summary = summarize_manifest(on_disk, CONFIG.min_clear_fraction)
    assert summary["scene_count"] == 4
    assert summary["no_data_count"] == 1

    # compute: only the two valid scenes at/above 0.8 survive (None and 0.40 out).
    surviving = [SCENES[0], SCENES[1]]
    canned_rows = [
        {
            "image_id": scene["image_id"],
            "sensing_date": scene["sensing_date"],
            "clear_pixel_fraction": scene["aoi_clear_fraction"],
            "ndvi_mean": 0.6,
        }
        for scene in surviving
    ]
    mock_compute_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": row} for row in canned_rows]
    }

    rows = compute_features(CONFIG, on_disk, ["ndvi"], CONFIG.min_clear_fraction)
    csv_path = tmp_path / "spectral_indices.csv"
    write_features_table(rows, ["ndvi"], csv_path)

    # The None scene was never fetched from GEE...
    requested = [call.args[0] for call in mock_compute_ee.Image.call_args_list]
    assert f"{SENTINEL2_COLLECTION_ID}/{none_scene['image_id']}" not in requested
    # ...and it has no CSV row: header + exactly the two surviving scenes.
    text = csv_path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert len(lines) == 1 + len(surviving)
    assert none_scene["image_id"] not in text


@patch("mrv.data_collection.collect.write_manifest")
@patch("mrv.data_collection.collect.load_aoi_geometry")
@patch("mrv.data_collection.collect.init_ee")
@patch("mrv.data_collection.collect.load_config")
@patch("mrv.data_collection.sentinel2.ee")
def test_empty_collection_fails_fast(
    mock_s2_ee, mock_load_config, mock_init_ee, mock_collect_aoi, mock_write_manifest
):
    mock_load_config.return_value = CONFIG
    mock_s2_ee.FeatureCollection.return_value.getInfo.return_value = {"features": []}

    with pytest.raises(RuntimeError, match="0 Sentinel-2 scenes"):
        collect_main()

    mock_write_manifest.assert_not_called()


def test_all_filtered_fails_fast():
    manifest = {
        "scenes": [
            {"image_id": "x", "sensing_date": "2026-07-01", "aoi_clear_fraction": 0.4},
        ]
    }

    with pytest.raises(RuntimeError, match="MIN_CLEAR_FRACTION"):
        compute_features(CONFIG, manifest, ["ndvi"], min_clear_fraction=0.8)
