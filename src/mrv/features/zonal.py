from __future__ import annotations

import ee

# 20m: LSWI depends on B11, a native-20m band, so one consistent
# reduceRegion scale is used across all indices for the pilot rather than
# mixing scales per band.
DEFAULT_REDUCE_SCALE_M = 20


def zonal_mean(
    image: ee.Image,
    aoi: ee.Geometry,
    band_name: str,
    scale: int = DEFAULT_REDUCE_SCALE_M,
) -> ee.ComputedObject:
    return (
        image.select(band_name)
        .reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=scale,
            maxPixels=1e9,
        )
        .get(band_name)
    )
