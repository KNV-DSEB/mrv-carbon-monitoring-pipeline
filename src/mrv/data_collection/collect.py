from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.gee_client import init_ee
from mrv.data_collection.sentinel2 import (
    build_manifest,
    get_filtered_collection,
    mask_clouds,
)
from mrv.utils.config import Config, load_config

DEFAULT_OUTPUT_PATH = Path("data/raw/sentinel2_manifest.json")


def collect_manifest(config: Config) -> dict:
    init_ee(config)
    aoi = load_aoi_geometry(config.aoi_path)
    collection = get_filtered_collection(
        aoi, config.date_start, config.date_end, config.max_cloud_cover_pct
    )
    masked_collection = collection.map(mask_clouds)
    scenes = build_manifest(masked_collection, aoi)

    return {
        "aoi_path": config.aoi_path,
        "date_start": config.date_start,
        "date_end": config.date_end,
        "max_cloud_cover_pct": config.max_cloud_cover_pct,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gee_project_id": config.gee_project_id,
        "scene_count": len(scenes),
        "scenes": scenes,
    }


def write_manifest(manifest: dict, output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return output_path


def main() -> Path:
    config = load_config()
    manifest = collect_manifest(config)
    return write_manifest(manifest)


if __name__ == "__main__":
    main()
