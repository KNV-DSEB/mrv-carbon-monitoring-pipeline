import pytest

from mrv.utils.config import Config, load_config

REQUIRED_ENV = {
    "AOI_PATH": "data/external/aoi/bac_ninh_pilot.geojson",
    "GEE_PROJECT_ID": "test-project",
    "GEE_SERVICE_ACCOUNT_KEY_PATH": "/secrets/key.json",
    "DATE_START": "2026-06-15",
    "DATE_END": "2026-11-15",
    "MAX_CLOUD_COVER_PCT": "70",
    "MIN_CLEAR_FRACTION": "0.8",
    "FEATURE_INDICES": "ndvi,ndwi,lswi",
}


def _set_env(monkeypatch, overrides=None):
    env = dict(REQUIRED_ENV)
    if overrides:
        env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_load_config_reads_all_fields(monkeypatch, tmp_path):
    _set_env(monkeypatch)

    config = load_config(env_path=tmp_path / "does-not-exist.env")

    assert config == Config(
        aoi_path="data/external/aoi/bac_ninh_pilot.geojson",
        gee_project_id="test-project",
        gee_service_account_key_path="/secrets/key.json",
        date_start="2026-06-15",
        date_end="2026-11-15",
        max_cloud_cover_pct=70.0,
        min_clear_fraction=0.8,
        feature_indices=("ndvi", "ndwi", "lswi"),
    )


@pytest.mark.parametrize("missing_key", list(REQUIRED_ENV.keys()))
def test_load_config_raises_on_missing_env(monkeypatch, tmp_path, missing_key):
    _set_env(monkeypatch, overrides={missing_key: None})

    with pytest.raises(RuntimeError, match=missing_key):
        load_config(env_path=tmp_path / "does-not-exist.env")
