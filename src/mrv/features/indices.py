from __future__ import annotations

from typing import Callable

import ee

# ee.Image.normalizedDifference() is GEE's standard API for (b1-b2)/(b1+b2)
# — used here instead of a hand-rolled expression so tests can assert the
# exact band pair passed in. Note: it can mask negative/invalid input
# values per GEE's default behavior; accepted for the pilot unless a real
# run surfaces a problem worth revisiting.


def compute_ndvi(image: ee.Image) -> ee.Image:
    return image.normalizedDifference(["B8", "B4"]).rename("ndvi")


def compute_ndwi(image: ee.Image) -> ee.Image:
    return image.normalizedDifference(["B3", "B8"]).rename("ndwi")


def compute_lswi(image: ee.Image) -> ee.Image:
    return image.normalizedDifference(["B8", "B11"]).rename("lswi")


INDEX_FUNCTIONS: dict[str, Callable[[ee.Image], ee.Image]] = {
    "ndvi": compute_ndvi,
    "ndwi": compute_ndwi,
    "lswi": compute_lswi,
}


def get_index_function(name: str) -> Callable[[ee.Image], ee.Image]:
    try:
        return INDEX_FUNCTIONS[name]
    except KeyError:
        raise ValueError(
            f"Unsupported index: {name!r}. Supported: {sorted(INDEX_FUNCTIONS)}"
        ) from None
