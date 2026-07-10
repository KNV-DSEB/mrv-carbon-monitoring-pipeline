from unittest.mock import MagicMock, patch

from mrv.features.zonal import DEFAULT_REDUCE_SCALE_M, zonal_mean


@patch("mrv.features.zonal.ee")
def test_zonal_mean_builds_expected_reduce_region_chain(mock_ee):
    image = MagicMock()
    aoi = MagicMock(name="aoi")
    band = image.select.return_value
    reduced = band.reduceRegion.return_value

    result = zonal_mean(image, aoi, "ndvi")

    image.select.assert_called_once_with("ndvi")
    band.reduceRegion.assert_called_once_with(
        reducer=mock_ee.Reducer.mean.return_value,
        geometry=aoi,
        scale=DEFAULT_REDUCE_SCALE_M,
        maxPixels=1e9,
    )
    reduced.get.assert_called_once_with("ndvi")
    assert result is reduced.get.return_value


@patch("mrv.features.zonal.ee")
def test_zonal_mean_respects_custom_scale(mock_ee):
    image = MagicMock()
    aoi = MagicMock(name="aoi")

    zonal_mean(image, aoi, "lswi", scale=10)

    image.select.return_value.reduceRegion.assert_called_once_with(
        reducer=mock_ee.Reducer.mean.return_value,
        geometry=aoi,
        scale=10,
        maxPixels=1e9,
    )
