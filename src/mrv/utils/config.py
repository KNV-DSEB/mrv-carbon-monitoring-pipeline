from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    aoi_path: str
    gee_project_id: str
    gee_service_account_key_path: str
    date_start: str
    date_end: str
    max_cloud_cover_pct: float
    min_clear_fraction: float
    feature_indices: tuple[str, ...]
    # Sentinel-1 SAR orbit lock (spec 07). Optional: the optical pipeline does
    # not set these, so they default to None and never break an S2-only run.
    # recon_sar validates their presence when it actually needs them.
    s1_orbit_pass: str | None = None
    s1_relative_orbit: int | None = None


def load_config(env_path: str | Path | None = None) -> Config:
    load_dotenv(dotenv_path=env_path)
    return Config(
        aoi_path=_require_env("AOI_PATH"),
        gee_project_id=_require_env("GEE_PROJECT_ID"),
        gee_service_account_key_path=_require_env("GEE_SERVICE_ACCOUNT_KEY_PATH"),
        date_start=_require_env("DATE_START"),
        date_end=_require_env("DATE_END"),
        max_cloud_cover_pct=float(_require_env("MAX_CLOUD_COVER_PCT")),
        min_clear_fraction=float(_require_env("MIN_CLEAR_FRACTION")),
        feature_indices=tuple(
            name.strip() for name in _require_env("FEATURE_INDICES").split(",")
        ),
        s1_orbit_pass=_optional_env("S1_ORBIT_PASS"),
        s1_relative_orbit=_optional_int_env("S1_RELATIVE_ORBIT"),
    )


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _optional_env(key: str) -> str | None:
    value = os.environ.get(key)
    return value or None


def _optional_int_env(key: str) -> int | None:
    value = os.environ.get(key)
    return int(value) if value else None
