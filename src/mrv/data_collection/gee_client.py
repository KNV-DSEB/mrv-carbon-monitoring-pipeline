from __future__ import annotations

import ee

from mrv.utils.config import Config


def init_ee(config: Config) -> None:
    credentials = ee.ServiceAccountCredentials(
        email=None,
        key_file=config.gee_service_account_key_path,
    )
    ee.Initialize(credentials, project=config.gee_project_id)
