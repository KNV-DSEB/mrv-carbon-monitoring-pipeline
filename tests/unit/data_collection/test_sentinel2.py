from unittest.mock import MagicMock, patch

from mrv.data_collection.sentinel2 import (
    SENTINEL2_COLLECTION_ID,
    _build_scene_feature,
    build_manifest,
    get_filtered_collection,
    mask_clouds,
    scene_asset_id,
)


def test_scene_asset_id_reconstructs_full_asset_id():
    # Round-trip lock: the bare system:index suffix that build_manifest stores,
    # re-prefixed by scene_asset_id, is exactly the full asset id features loads.
    system_index = "20260701T033539_20260701T034339_T48QWH"
    assert scene_asset_id(system_index) == f"{SENTINEL2_COLLECTION_ID}/{system_index}"
    assert scene_asset_id(system_index).startswith(SENTINEL2_COLLECTION_ID + "/")


@patch("mrv.data_collection.sentinel2.ee")
def test_get_filtered_collection_builds_expected_chain(mock_ee):
    aoi = MagicMock(name="aoi")
    collection_mock = mock_ee.ImageCollection.return_value
    bounds_mock = collection_mock.filterBounds.return_value
    date_mock = bounds_mock.filterDate.return_value
    filter_mock = date_mock.filter.return_value

    result = get_filtered_collection(aoi, "2026-06-15", "2026-11-15", 70.0)

    mock_ee.ImageCollection.assert_called_once_with(SENTINEL2_COLLECTION_ID)
    collection_mock.filterBounds.assert_called_once_with(aoi)
    bounds_mock.filterDate.assert_called_once_with("2026-06-15", "2026-11-15")
    mock_ee.Filter.lte.assert_called_once_with("CLOUDY_PIXEL_PERCENTAGE", 70.0)
    date_mock.filter.assert_called_once_with(mock_ee.Filter.lte.return_value)
    assert result is filter_mock


def test_mask_clouds_baseline_excludes_unclassified():
    image = MagicMock()
    scl = image.select.return_value
    remapped = scl.remap.return_value

    result = mask_clouds(image)

    image.select.assert_called_once_with("SCL")
    # Class 7 (Unclassified) must NOT appear in the baseline mask.
    scl.remap.assert_called_once_with([4, 5, 6, 11], [1, 1, 1, 1], 0)
    remapped.eq.assert_called_once_with(1)
    image.updateMask.assert_called_once_with(remapped.eq.return_value)
    assert result is image.updateMask.return_value


def test_mask_clouds_can_include_unclassified_explicitly():
    image = MagicMock()
    scl = image.select.return_value

    mask_clouds(image, include_unclassified=True)

    scl.remap.assert_called_once_with([4, 5, 6, 11, 7], [1, 1, 1, 1, 1], 0)


@patch("mrv.data_collection.sentinel2.ee")
def test_build_scene_feature_maps_expected_fields(mock_ee):
    image = MagicMock()
    aoi = MagicMock()
    reduced = (
        image.select.return_value.remap.return_value.rename.return_value.reduceRegion.return_value
    )

    _build_scene_feature(image, aoi)

    image.select.assert_called_with("SCL")
    image.select.return_value.remap.assert_called_once_with([4, 5, 6, 11], [1, 1, 1, 1], 0)
    image.select.return_value.remap.return_value.rename.assert_called_once_with("clear")
    image.select.return_value.remap.return_value.rename.return_value.reduceRegion.assert_called_once_with(
        reducer=mock_ee.Reducer.mean.return_value,
        geometry=aoi,
        scale=20,
        maxPixels=1e9,
    )
    reduced.get.assert_called_once_with("clear")

    image.get.assert_any_call("system:index")
    image.get.assert_any_call("MGRS_TILE")
    image.get.assert_any_call("CLOUDY_PIXEL_PERCENTAGE")
    image.date.return_value.format.assert_called_once_with("YYYY-MM-dd")

    assert mock_ee.Feature.call_count == 1
    args, _ = mock_ee.Feature.call_args
    assert args[0] is None
    assert set(args[1].keys()) == {
        "image_id",
        "sensing_date",
        "mgrs_tile",
        "cloudy_pixel_percentage",
        "aoi_clear_fraction",
    }


@patch("mrv.data_collection.sentinel2.ee")
def test_build_manifest_unwraps_feature_properties(mock_ee):
    collection = MagicMock()
    aoi = MagicMock()
    canned_scenes = [
        {
            "image_id": "20260701T033539_20260701T034339_T48QWH",
            "sensing_date": "2026-07-01",
            "mgrs_tile": "48QWH",
            "cloudy_pixel_percentage": 12.4,
            "aoi_clear_fraction": 0.91,
        },
        {
            "image_id": "20260711T033539_20260711T034339_T48QWH",
            "sensing_date": "2026-07-11",
            "mgrs_tile": "48QWH",
            "cloudy_pixel_percentage": 30.0,
            "aoi_clear_fraction": 0.6,
        },
    ]
    mock_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": props} for props in canned_scenes]
    }

    result = build_manifest(collection, aoi)

    assert collection.map.call_count == 1
    assert callable(collection.map.call_args[0][0])
    mock_ee.FeatureCollection.assert_called_once_with(collection.map.return_value)
    assert result == canned_scenes
