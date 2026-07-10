from unittest.mock import MagicMock, patch

from mrv.data_collection.gee_client import init_ee
from mrv.utils.config import Config

CONFIG = Config(
    aoi_path="data/external/aoi/bac_ninh_pilot.geojson",
    gee_project_id="test-project",
    gee_service_account_key_path="/secrets/key.json",
    date_start="2026-06-15",
    date_end="2026-11-15",
    max_cloud_cover_pct=70.0,
    min_clear_fraction=0.8,
    feature_indices=("ndvi", "ndwi", "lswi"),
)


@patch("mrv.data_collection.gee_client.ee")
def test_init_ee_authenticates_with_service_account(mock_ee):
    mock_credentials = MagicMock()
    mock_ee.ServiceAccountCredentials.return_value = mock_credentials

    init_ee(CONFIG)

    mock_ee.ServiceAccountCredentials.assert_called_once_with(
        email=None, key_file="/secrets/key.json"
    )
    mock_ee.Initialize.assert_called_once_with(mock_credentials, project="test-project")
