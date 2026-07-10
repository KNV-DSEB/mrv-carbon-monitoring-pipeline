from unittest.mock import MagicMock

import pytest

from mrv.features.indices import (
    INDEX_FUNCTIONS,
    compute_lswi,
    compute_ndvi,
    compute_ndwi,
    get_index_function,
)


def test_compute_ndvi_uses_expected_band_pair():
    image = MagicMock()

    result = compute_ndvi(image)

    image.normalizedDifference.assert_called_once_with(["B8", "B4"])
    image.normalizedDifference.return_value.rename.assert_called_once_with("ndvi")
    assert result is image.normalizedDifference.return_value.rename.return_value


def test_compute_ndwi_uses_expected_band_pair():
    image = MagicMock()

    compute_ndwi(image)

    image.normalizedDifference.assert_called_once_with(["B3", "B8"])
    image.normalizedDifference.return_value.rename.assert_called_once_with("ndwi")


def test_compute_lswi_uses_expected_band_pair():
    image = MagicMock()

    compute_lswi(image)

    image.normalizedDifference.assert_called_once_with(["B8", "B11"])
    image.normalizedDifference.return_value.rename.assert_called_once_with("lswi")


def test_index_functions_registry_matches_supported_names():
    assert set(INDEX_FUNCTIONS) == {"ndvi", "ndwi", "lswi"}


def test_get_index_function_returns_registered_function():
    assert get_index_function("ndvi") is compute_ndvi


def test_get_index_function_raises_on_unsupported_name():
    with pytest.raises(ValueError, match="evi"):
        get_index_function("evi")
