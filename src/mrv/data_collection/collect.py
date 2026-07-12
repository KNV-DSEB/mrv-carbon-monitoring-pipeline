from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.gee_client import init_ee
from mrv.data_collection.sentinel2 import (
    build_manifest,
    get_filtered_collection,
)
from mrv.utils.config import Config, load_config

DEFAULT_OUTPUT_PATH = Path("data/raw/sentinel2_manifest.json")


def collect_manifest(config: Config) -> dict:
    init_ee(config)
    aoi = load_aoi_geometry(config.aoi_path)
    collection = get_filtered_collection(
        aoi, config.date_start, config.date_end, config.max_cloud_cover_pct
    )
    # Measure aoi_clear_fraction on the RAW collection, not a cloud-masked one:
    # build_manifest's SCL.remap([clear]->1, default 0).mean needs the cloud
    # pixels present so they count as 0 in the denominator (clear / total AOI
    # pixels in footprint). Pre-masking here would strip the SCL of non-clear
    # pixels, collapsing the metric to clear/valid ~ 1.0 (see spec 05). The
    # features module applies its own mask separately for index computation.
    scenes = build_manifest(collection, aoi)

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


def _assert_nonempty_manifest(manifest: dict, config: Config) -> None:
    """Fail fast when a real query returns nothing.

    ``collect_manifest()`` itself stays non-raising so the reconnaissance path
    (``mrv.pipeline.recon``) can still summarize/persist an empty result; the
    fail-fast guard lives here in the CLI entrypoint instead. No credentials
    are referenced in the message.
    """
    if manifest["scene_count"] > 0:
        return
    raise RuntimeError(
        "data_collection returned 0 Sentinel-2 scenes for AOI "
        f"{config.aoi_path!r} over {config.date_start}..{config.date_end} "
        f"with MAX_CLOUD_COVER_PCT={config.max_cloud_cover_pct}. "
        "Nothing was written. Widen DATE_START/DATE_END or raise "
        "MAX_CLOUD_COVER_PCT in .env, then re-run."
    )


def main() -> Path:
    config = load_config()
    manifest = collect_manifest(config)
    _assert_nonempty_manifest(manifest, config)
    return write_manifest(manifest)


if __name__ == "__main__":
    main()
