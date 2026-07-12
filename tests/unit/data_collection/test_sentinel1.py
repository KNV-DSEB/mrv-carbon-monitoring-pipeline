from unittest.mock import MagicMock, patch

import pytest

from mrv.data_collection.sentinel1 import (
    S1_COLLECTION_ID,
    assert_single_orbit,
    build_manifest,
    filter_to_orbit,
    get_filtered_collection,
    orbit_distribution,
    scene_asset_id,
)


def test_scene_asset_id_round_trips():
    idx = "S1A_IW_GRDH_1SDV_20250703T224900_20250703T224925_054321_069ABC_1234"
    assert scene_asset_id(idx) == f"{S1_COLLECTION_ID}/{idx}"
    assert scene_asset_id(idx).startswith(S1_COLLECTION_ID + "/")


@patch("mrv.data_collection.sentinel1.ee")
def test_get_filtered_collection_filters_iw_vv_and_vh(mock_ee):
    aoi = MagicMock(name="aoi")
    collection = mock_ee.ImageCollection.return_value
    bounds = collection.filterBounds.return_value
    dated = bounds.filterDate.return_value

    get_filtered_collection(aoi, "2025-07-01", "2025-08-15")

    mock_ee.ImageCollection.assert_called_once_with(S1_COLLECTION_ID)
    collection.filterBounds.assert_called_once_with(aoi)
    bounds.filterDate.assert_called_once_with("2025-07-01", "2025-08-15")
    # IW mode + BOTH polarisations required (R1). No cloud filter anywhere.
    mock_ee.Filter.eq.assert_called_once_with("instrumentMode", "IW")
    listcontains = [c.args for c in mock_ee.Filter.listContains.call_args_list]
    assert ("transmitterReceiverPolarisation", "VV") in listcontains
    assert ("transmitterReceiverPolarisation", "VH") in listcontains


@patch("mrv.data_collection.sentinel1.ee")
def test_build_manifest_unwraps_orbit_metadata(mock_ee):
    collection = MagicMock()
    canned = [
        {
            "image_id": "s_a",
            "sensing_date": "2025-07-03",
            "orbit_pass": "DESCENDING",
            "relative_orbit": 18,
        }
    ]
    mock_ee.FeatureCollection.return_value.getInfo.return_value = {
        "features": [{"type": "Feature", "properties": p} for p in canned]
    }

    result = build_manifest(collection)

    assert result == canned
    assert collection.map.call_count == 1


def test_orbit_distribution_counts_per_pass_and_relative_orbit():
    scenes = [
        {"orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"orbit_pass": "ASCENDING", "relative_orbit": 26},
        {"orbit_pass": "DESCENDING", "relative_orbit": 91},
    ]

    dist = orbit_distribution(scenes)

    # Largest group first.
    assert dist[0] == {"orbit_pass": "DESCENDING", "relative_orbit": 18, "count": 2}
    counts = {(d["orbit_pass"], d["relative_orbit"]): d["count"] for d in dist}
    assert counts[("ASCENDING", 26)] == 1
    assert counts[("DESCENDING", 91)] == 1


def test_filter_to_orbit_keeps_only_one_group():
    scenes = [
        {"image_id": "a", "orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"image_id": "b", "orbit_pass": "ASCENDING", "relative_orbit": 18},
        {"image_id": "c", "orbit_pass": "DESCENDING", "relative_orbit": 91},
        {"image_id": "d", "orbit_pass": "DESCENDING", "relative_orbit": 18},
    ]

    kept = filter_to_orbit(scenes, "DESCENDING", 18)

    assert [s["image_id"] for s in kept] == ["a", "d"]


def test_assert_single_orbit_raises_on_mixed_orbits():
    # R2 fail-fast guard: this is the test that must FAIL if the guard is removed.
    scenes = [
        {"orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"orbit_pass": "ASCENDING", "relative_orbit": 26},
    ]

    with pytest.raises(RuntimeError, match="multiple orbit groups"):
        assert_single_orbit(scenes)


def test_assert_single_orbit_passes_on_a_single_group():
    scenes = [
        {"orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"orbit_pass": "DESCENDING", "relative_orbit": 18},
    ]

    assert_single_orbit(scenes)  # no raise
