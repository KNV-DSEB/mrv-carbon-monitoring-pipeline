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


# --- Semantics-faithful fake for the clear-fraction contract (spec 05) --------
#
# The prior tests use opaque MagicMocks, which model no pixel arithmetic — which
# is exactly why the "measures clear/valid, not clear/total" bug slipped past 57
# tests. This fake models the THREE Earth Engine behaviours the contract turns
# on, and nothing more:
#   * updateMask(m): pixels where m != 1 become masked (no-data).
#   * remap(from, to, default): a MASKED pixel stays masked (the default only
#     applies to VALID pixels not in `from`).
#   * reduceRegion(mean).get(band): mean over the UNMASKED pixels, or None when
#     there are none.
# A pixel value of None represents "masked / outside footprint".
#
# It is a MODEL, not real EE — hence spec 05's real acceptance is the owner's
# live rainy-season recon, not this test.


class _FakeReduce:
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values.get(key)


class _FakeBand:
    def __init__(self, pixels, name="SCL"):
        self.pixels = pixels
        self.name = name

    def remap(self, frm, to, default):
        mapping = dict(zip(frm, to))
        return _FakeBand(
            [None if p is None else mapping.get(p, default) for p in self.pixels],
            self.name,
        )

    def rename(self, name):
        return _FakeBand(self.pixels, name)

    def eq(self, value):
        return _FakeBand(
            [None if p is None else int(p == value) for p in self.pixels], self.name
        )

    def reduceRegion(self, reducer=None, geometry=None, scale=None, maxPixels=None):
        valid = [p for p in self.pixels if p is not None]
        mean = None if not valid else sum(valid) / len(valid)
        return _FakeReduce({self.name: mean})


class _FakeDate:
    def format(self, fmt):
        return "2025-07-15"


class _FakeImage:
    """Raw Sentinel-2 scene double carrying only the SCL pixels under test."""

    def __init__(self, scl_pixels, image_id="scene_x"):
        self._scl = scl_pixels
        self._id = image_id

    def select(self, band):
        assert band == "SCL"
        return _FakeBand(list(self._scl), "SCL")

    def updateMask(self, mask_band):
        kept = [
            scl if m == 1 else None for scl, m in zip(self._scl, mask_band.pixels)
        ]
        return _FakeImage(kept, self._id)

    def get(self, key):
        return {
            "system:index": self._id,
            "MGRS_TILE": "48QWH",
            "CLOUDY_PIXEL_PERCENTAGE": 42.0,
        }[key]

    def date(self):
        return _FakeDate()


class _FakeFeature:
    def __init__(self, props):
        self.props = props


class _FakeCollection:
    def __init__(self, images):
        self._images = images

    def map(self, fn):
        return _FakeCollection([fn(img) for img in self._images])


class _FakeFeatureCollection:
    def __init__(self, collection):
        self._collection = collection

    def getInfo(self):
        return {
            "features": [
                {"type": "Feature", "properties": f.props}
                for f in self._collection._images
            ]
        }


class _FakeReducerNS:
    @staticmethod
    def mean():
        return "mean"


class _FakeEE:
    Reducer = _FakeReducerNS

    @staticmethod
    def Feature(geometry, props):
        return _FakeFeature(props)

    @staticmethod
    def FeatureCollection(collection):
        return _FakeFeatureCollection(collection)


@patch("mrv.data_collection.sentinel2.ee", _FakeEE)
def test_build_manifest_measures_clear_over_total_in_footprint():
    aoi = object()
    scenes = _FakeCollection(
        [
            _FakeImage([8, 8, 8, 8], "all_cloud"),  # observed, fully clouded
            _FakeImage([4, 5, 6, 8], "mixed"),  # 3 clear + 1 cloud
            _FakeImage([None, None], "outside"),  # AOI outside footprint
        ]
    )

    rows = build_manifest(scenes, aoi)
    frac = {r["image_id"]: r["aoi_clear_fraction"] for r in rows}

    # Contract: clear / total-in-footprint. Clouds count 0 in the denominator.
    assert frac["all_cloud"] == 0.0  # fully cloudy AOI -> 0.0, NOT None
    assert frac["mixed"] == 0.75  # 3 of 4 pixels clear
    assert frac["outside"] is None  # no-data ONLY when outside the footprint


@patch("mrv.data_collection.sentinel2.ee", _FakeEE)
def test_old_premask_path_collapses_clear_fraction():
    # Documents WHY the old pipeline was wrong: measuring on the cloud-masked
    # collection removes non-clear pixels before the reducer, so a fully cloudy
    # AOI reads as None and a partly cloudy one reads as 1.0. This is the exact
    # behaviour spec 05 removes; the new path (test above) yields 0.0 / 0.75.
    aoi = object()
    scenes = _FakeCollection(
        [
            _FakeImage([8, 8, 8, 8], "all_cloud"),
            _FakeImage([4, 5, 6, 8], "mixed"),
        ]
    )

    old_rows = build_manifest(scenes.map(mask_clouds), aoi)
    frac = {r["image_id"]: r["aoi_clear_fraction"] for r in old_rows}

    assert frac["all_cloud"] is None  # every pixel masked -> no valid -> None
    assert frac["mixed"] == 1.0  # only the 3 clear pixels survive the mask
