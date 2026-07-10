from __future__ import annotations

import json
from pathlib import Path

import ee

_VALID_GEOMETRY_TYPES = ("Polygon", "MultiPolygon")


def load_aoi_geometry(path: str | Path) -> ee.Geometry:
    aoi_path = Path(path)
    if not aoi_path.exists():
        raise FileNotFoundError(f"AOI file not found: {aoi_path}")

    with aoi_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    geometry = _extract_geometry(data)
    geom_type = geometry.get("type")
    if geom_type not in _VALID_GEOMETRY_TYPES:
        raise ValueError(
            f"AOI geometry must be one of {_VALID_GEOMETRY_TYPES}, got: {geom_type}"
        )

    return ee.Geometry(geometry)


def _extract_geometry(data: dict) -> dict:
    doc_type = data.get("type")
    if doc_type == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("AOI FeatureCollection has no features")
        return features[0]["geometry"]
    if doc_type == "Feature":
        return data["geometry"]
    return data
