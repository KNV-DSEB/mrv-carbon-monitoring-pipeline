import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mrv.data_collection.aoi import load_aoi_geometry

FIXTURES_DIR = Path(__file__).parent / "fixtures"

POLYGON_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[0.0, 0.0], [0.0, 0.01], [0.01, 0.01], [0.01, 0.0], [0.0, 0.0]]],
}


@patch("mrv.data_collection.aoi.ee")
def test_load_aoi_geometry_from_feature_collection(mock_ee):
    load_aoi_geometry(FIXTURES_DIR / "sample_aoi.geojson")

    mock_ee.Geometry.assert_called_once_with(POLYGON_GEOMETRY)


@patch("mrv.data_collection.aoi.ee")
def test_load_aoi_geometry_from_bare_geometry(mock_ee, tmp_path):
    path = tmp_path / "bare_geometry.geojson"
    path.write_text(json.dumps(POLYGON_GEOMETRY), encoding="utf-8")

    load_aoi_geometry(path)

    mock_ee.Geometry.assert_called_once_with(POLYGON_GEOMETRY)


@patch("mrv.data_collection.aoi.ee")
def test_load_aoi_geometry_from_feature(mock_ee, tmp_path):
    feature = {"type": "Feature", "properties": {}, "geometry": POLYGON_GEOMETRY}
    path = tmp_path / "feature.geojson"
    path.write_text(json.dumps(feature), encoding="utf-8")

    load_aoi_geometry(path)

    mock_ee.Geometry.assert_called_once_with(POLYGON_GEOMETRY)


def test_load_aoi_geometry_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_aoi_geometry(tmp_path / "does-not-exist.geojson")


def test_load_aoi_geometry_rejects_non_polygon(tmp_path):
    point_feature = {
        "type": "Feature",
        "properties": {},
        "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
    }
    path = tmp_path / "point.geojson"
    path.write_text(json.dumps(point_feature), encoding="utf-8")

    with pytest.raises(ValueError, match="Polygon"):
        load_aoi_geometry(path)


def test_load_aoi_geometry_rejects_empty_feature_collection(tmp_path):
    empty_fc = {"type": "FeatureCollection", "features": []}
    path = tmp_path / "empty.geojson"
    path.write_text(json.dumps(empty_fc), encoding="utf-8")

    with pytest.raises(ValueError, match="no features"):
        load_aoi_geometry(path)
