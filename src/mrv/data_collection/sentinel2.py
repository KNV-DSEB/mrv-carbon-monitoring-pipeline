from __future__ import annotations

import ee

SENTINEL2_COLLECTION_ID = "COPERNICUS/S2_SR_HARMONIZED"

# SCL classes considered clear/valid in the conservative baseline mask:
# 4 = vegetation, 5 = bare soil, 6 = water, 11 = snow/ice.
#
# Class 7 (Unclassified) is deliberately EXCLUDED from the baseline. SCL
# does not guarantee class 7 is a clean pixel — it can mark classifier
# boundaries/artifacts — so treating it as valid by default would silently
# loosen the cloud filter. Re-including it is an explicit opt-in via
# `include_unclassified`, never the default.
BASELINE_CLEAR_SCL_CLASSES = [4, 5, 6, 11]
UNCLASSIFIED_SCL_CLASS = 7

MANIFEST_REDUCE_SCALE_M = 20


def get_filtered_collection(
    aoi: ee.Geometry,
    date_start: str,
    date_end: str,
    max_cloud_cover_pct: float,
) -> ee.ImageCollection:
    return (
        ee.ImageCollection(SENTINEL2_COLLECTION_ID)
        .filterBounds(aoi)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_cloud_cover_pct))
    )


def _clear_scl_classes(include_unclassified: bool = False) -> list[int]:
    classes = list(BASELINE_CLEAR_SCL_CLASSES)
    if include_unclassified:
        classes.append(UNCLASSIFIED_SCL_CLASS)
    return classes


def mask_clouds(image: ee.Image, include_unclassified: bool = False) -> ee.Image:
    classes = _clear_scl_classes(include_unclassified)
    scl = image.select("SCL")
    clear_mask = scl.remap(classes, [1] * len(classes), 0)
    return image.updateMask(clear_mask.eq(1))


def _build_scene_feature(image: ee.Image, aoi: ee.Geometry) -> ee.Feature:
    classes = _clear_scl_classes()
    clear_fraction = (
        image.select("SCL")
        .remap(classes, [1] * len(classes), 0)
        .rename("clear")
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=MANIFEST_REDUCE_SCALE_M,
            maxPixels=1e9,
        )
        .get("clear")
    )
    return ee.Feature(
        None,
        {
            "image_id": image.get("system:index"),
            "sensing_date": image.date().format("YYYY-MM-dd"),
            "mgrs_tile": image.get("MGRS_TILE"),
            "cloudy_pixel_percentage": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            "aoi_clear_fraction": clear_fraction,
        },
    )


def build_manifest(collection: ee.ImageCollection, aoi: ee.Geometry) -> list[dict]:
    mapped = collection.map(lambda image: _build_scene_feature(image, aoi))
    raw = ee.FeatureCollection(mapped).getInfo()
    return [feature["properties"] for feature in raw["features"]]
