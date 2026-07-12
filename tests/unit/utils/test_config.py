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
    # Optional S1 vars: clear unless a test sets them, so a developer's real
    # environment can't leak into the required-fields assertions.
    for key in ("S1_ORBIT_PASS", "S1_RELATIVE_ORBIT"):
        if key not in env:
            monkeypatch.delenv(key, raising=False)
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


def test_load_config_reads_optional_s1_orbit_lock(monkeypatch, tmp_path):
    _set_env(
        monkeypatch,
        overrides={"S1_ORBIT_PASS": "DESCENDING", "S1_RELATIVE_ORBIT": "18"},
    )

    config = load_config(env_path=tmp_path / "does-not-exist.env")

    assert config.s1_orbit_pass == "DESCENDING"
    assert config.s1_relative_orbit == 18  # parsed to int


def test_load_config_defaults_s1_to_none_when_unset(monkeypatch, tmp_path):
    # Optical-only runs don't set the S1 vars; they must default to None, not
    # raise (so an S2 run keeps working unchanged).
    _set_env(monkeypatch)

    config = load_config(env_path=tmp_path / "does-not-exist.env")

    assert config.s1_orbit_pass is None
    assert config.s1_relative_orbit is None


@pytest.mark.parametrize("missing_key", list(REQUIRED_ENV.keys()))
def test_load_config_raises_on_missing_env(monkeypatch, tmp_path, missing_key):
    _set_env(monkeypatch, overrides={missing_key: None})

    with pytest.raises(RuntimeError, match=missing_key):
        load_config(env_path=tmp_path / "does-not-exist.env")
