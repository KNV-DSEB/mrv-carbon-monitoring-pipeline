"""Tests for zonal Sentinel-1 backscatter (spec 07 R3/R4/R5).

Per the spec-05 lesson (a bug slipped past 57 empty-MagicMock tests), the
computation is exercised with a **semantics-faithful fake** that models the three
things that matter: elementwise band math (so dB->linear is real), a
``reduceRegion(mean)`` over the UNMASKED pixels, and ``None`` when the AOI has no
valid pixel. The dB test is genuinely discriminating: mean-over-dB and
mean-over-linear give different numbers, and only one is correct.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from mrv.data_collection.sentinel1 import scene_asset_id
from mrv.features.backscatter import (
    _band_linear_mean,
    _despeckle,
    _linear_to_db,
    compute_backscatter,
)
from mrv.utils.config import Config

CONFIG = Config(
    aoi_path="data/external/aoi/bac_ninh_pilot.geojson",
    gee_project_id="p",
    gee_service_account_key_path="/secrets/key.json",
    date_start="2025-07-01",
    date_end="2025-08-15",
    max_cloud_cover_pct=100.0,
    min_clear_fraction=0.5,
    feature_indices=("ndvi",),
    s1_orbit_pass="DESCENDING",
    s1_relative_orbit=18,
)


# --- Semantics-faithful fake (pixel value None == masked / outside footprint) --

class _FakeReduce:
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values.get(key)


class _FakeBand:
    def __init__(self, pixels, name):
        self.pixels = pixels
        self.name = name

    def select(self, name):
        return self

    def divide(self, scalar):
        return _FakeBand([None if p is None else p / scalar for p in self.pixels], self.name)

    def multiply(self, scalar):
        return _FakeBand([None if p is None else p * scalar for p in self.pixels], self.name)

    def exp(self):
        return _FakeBand([None if p is None else math.exp(p) for p in self.pixels], self.name)

    def rename(self, name):
        return _FakeBand(self.pixels, name)

    def focal_median(self, **kwargs):
        return self  # identity: negligible at AOI scale (R4)

    def reduceRegion(self, reducer=None, geometry=None, scale=None, maxPixels=None):
        valid = [p for p in self.pixels if p is not None]
        mean = None if not valid else sum(valid) / len(valid)
        return _FakeReduce({self.name: mean})


class _FakeS1Image:
    def __init__(self, bands):
        self._bands = bands

    def select(self, band):
        return _FakeBand(list(self._bands[band]), band)


class _FakeFeature:
    def __init__(self, props):
        self.props = props


class _FakeFeatureCollection:
    def __init__(self, features):
        self._features = features

    def getInfo(self):
        return {"features": [{"properties": f.props} for f in self._features]}


class _FakeReducerNS:
    @staticmethod
    def mean():
        return "mean"


class _FakeEE:
    Reducer = _FakeReducerNS
    _registry: dict = {}

    @staticmethod
    def Image(asset_id):
        return _FakeEE._registry[asset_id]

    @staticmethod
    def Feature(geometry, props):
        return _FakeFeature(props)

    @staticmethod
    def FeatureCollection(features):
        return _FakeFeatureCollection(features)


# --- R3: the mean must be taken in LINEAR power, not in dB --------------------

@patch("mrv.features.zonal.ee", _FakeEE)
def test_mean_is_computed_in_linear_power_not_in_db():
    # Two pixels at -20 dB and -10 dB.
    image = _FakeS1Image({"VV": [-20.0, -10.0]})

    linear_mean = _band_linear_mean(image, aoi=object(), band="VV")
    result_db = _linear_to_db(linear_mean)

    # Correct: dB(mean(power)) = 10*log10((0.01 + 0.1)/2) = -12.596 dB.
    assert result_db == pytest.approx(-12.596, abs=0.01)
    # The WRONG logic (plain mean of dB) would give (-20 + -10)/2 = -15.0 dB.
    # This assertion is what fails if _to_linear is skipped.
    assert abs(result_db - (-15.0)) > 1.0


# --- R5: AOI outside the footprint is None, never 0.0 -------------------------

@patch("mrv.features.zonal.ee", _FakeEE)
def test_out_of_footprint_aoi_is_none_not_zero():
    image = _FakeS1Image({"VV": [None, None]})  # all masked -> not observed

    linear_mean = _band_linear_mean(image, aoi=object(), band="VV")

    assert linear_mean is None
    assert _linear_to_db(linear_mean) is None  # NOT 0.0


def test_linear_to_db_preserves_none_and_rejects_nonpositive():
    assert _linear_to_db(None) is None      # no-data stays no-data (R5)
    assert _linear_to_db(0.0) is None        # no dB for zero/neg power
    assert _linear_to_db(-1.0) is None
    assert _linear_to_db(0.055) == pytest.approx(-12.596, abs=0.01)


# --- R4: speckle filter is applied with the documented kernel -----------------

def test_despeckle_applies_focal_median_with_30m_kernel():
    image = MagicMock()

    _despeckle(image)

    image.focal_median.assert_called_once_with(
        radius=30, kernelType="circle", units="meters"
    )


# --- Full chain: dB values + None passthrough via the manifest re-fetch -------

@patch("mrv.features.backscatter.load_aoi_geometry")
@patch("mrv.features.zonal.ee", _FakeEE)
@patch("mrv.features.backscatter.ee", _FakeEE)
def test_compute_backscatter_emits_db_and_preserves_none(mock_load_aoi):
    _FakeEE._registry = {
        scene_asset_id("scene_ok"): _FakeS1Image(
            {"VV": [-20.0, -10.0], "VH": [-25.0, -15.0]}
        ),
        scene_asset_id("scene_out"): _FakeS1Image({"VV": [None, None], "VH": [None, None]}),
    }
    scenes = [
        {"image_id": "scene_ok", "sensing_date": "2026-01-01", "orbit_pass": "DESCENDING", "relative_orbit": 18},
        {"image_id": "scene_out", "sensing_date": "2026-01-13", "orbit_pass": "DESCENDING", "relative_orbit": 18},
    ]

    rows = compute_backscatter(CONFIG, scenes)
    by_id = {r["image_id"]: r for r in rows}

    assert by_id["scene_ok"]["vv_db"] == pytest.approx(-12.596, abs=0.01)
    assert by_id["scene_ok"]["vh_db"] == pytest.approx(-17.596, abs=0.01)
    # Out-of-footprint scene: None, never coerced to 0.0.
    assert by_id["scene_out"]["vv_db"] is None
    assert by_id["scene_out"]["vh_db"] is None
    mock_load_aoi.assert_called_once_with(CONFIG.aoi_path)
