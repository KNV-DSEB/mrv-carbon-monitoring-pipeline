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


def scene_asset_id(system_index: str) -> str:
    """Reconstruct the full Sentinel-2 asset id from a bare ``system:index``.

    ``_build_scene_feature`` stores ``image_id = image.get("system:index")`` —
    the bare granule suffix, not the full asset path. This is the single source
    of truth for turning that suffix back into an ``ee.Image``-loadable asset
    id; the features module imports it so the two modules can't drift on the id
    format.
    """
    return f"{SENTINEL2_COLLECTION_ID}/{system_index}"


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
    # `image` MUST be the RAW (unmasked) scene, not a cloud-masked one. The
    # remap below maps clear SCL classes to 1 and everything else (cloud,
    # shadow, cirrus, ...) to 0 via the default; the mean over the AOI is then
    # clear_pixels / (total AOI pixels within the scene footprint). If the SCL
    # were pre-masked, non-clear pixels would be masked away rather than counted
    # as 0, collapsing the metric to clear/valid ~ 1.0 (spec 05).
    #
    # aoi_clear_fraction is therefore 0.0 for an AOI the footprint covers but is
    # fully cloudy, and None ONLY when the AOI lies entirely outside the scene
    # footprint (no valid pixels for the mean -> reduceRegion returns null).
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
            # Bare system:index suffix; features re-expands it via
            # sentinel2.scene_asset_id() before ee.Image(...).
            "image_id": image.get("system:index"),
            "sensing_date": image.date().format("YYYY-MM-dd"),
            "mgrs_tile": image.get("MGRS_TILE"),
            "cloudy_pixel_percentage": image.get("CLOUDY_PIXEL_PERCENTAGE"),
            "aoi_clear_fraction": clear_fraction,
        },
    )


def build_manifest(collection: ee.ImageCollection, aoi: ee.Geometry) -> list[dict]:
    """Build per-scene manifest rows from an UNMASKED image collection.

    The collection must NOT be cloud-masked: aoi_clear_fraction is measured on
    the raw SCL so cloud pixels count as 0 in the denominator (see
    :func:`_build_scene_feature` and spec 05).
    """
    mapped = collection.map(lambda image: _build_scene_feature(image, aoi))
    raw = ee.FeatureCollection(mapped).getInfo()
    return [feature["properties"] for feature in raw["features"]]
