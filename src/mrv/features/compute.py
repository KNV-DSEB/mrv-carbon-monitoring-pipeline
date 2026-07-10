from __future__ import annotations

import csv
import json
from pathlib import Path

import ee

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.gee_client import init_ee
from mrv.data_collection.sentinel2 import SENTINEL2_COLLECTION_ID, mask_clouds
from mrv.features.indices import get_index_function
from mrv.features.zonal import zonal_mean
from mrv.utils.config import Config, load_config

DEFAULT_MANIFEST_PATH = Path("data/raw/sentinel2_manifest.json")
DEFAULT_OUTPUT_PATH = Path("data/processed/spectral_indices.csv")


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict:
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_path}. Run data_collection first."
        )
    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _included_scenes(manifest: dict, min_clear_fraction: float) -> list[dict]:
    return [
        scene
        for scene in manifest["scenes"]
        if scene["aoi_clear_fraction"] >= min_clear_fraction
    ]


def _fetch_masked_image(image_id: str) -> ee.Image:
    # The manifest stores the Sentinel-2 system:index suffix, not the full
    # asset ID, so it must be re-prefixed with the collection ID here.
    full_asset_id = f"{SENTINEL2_COLLECTION_ID}/{image_id}"
    return mask_clouds(ee.Image(full_asset_id))


def _compute_scene_row(scene: dict, aoi: ee.Geometry, index_names: list[str]) -> ee.Feature:
    masked_image = _fetch_masked_image(scene["image_id"])

    properties: dict[str, object] = {
        "image_id": scene["image_id"],
        "sensing_date": scene["sensing_date"],
        # Reused directly from the manifest, not recomputed: it's already
        # the fraction of AOI pixels passing the same SCL clear-pixel
        # definition this module would otherwise compute again.
        "clear_pixel_fraction": scene["aoi_clear_fraction"],
    }
    for name in index_names:
        index_image = get_index_function(name)(masked_image)
        properties[f"{name}_mean"] = zonal_mean(index_image, aoi, name)

    return ee.Feature(None, properties)


def compute_features(
    config: Config,
    manifest: dict,
    index_names: list[str],
    min_clear_fraction: float,
) -> list[dict]:
    aoi = load_aoi_geometry(config.aoi_path)
    scenes = _included_scenes(manifest, min_clear_fraction)

    # Built as a Python-side list rather than ee.ImageCollection.map():
    # per-scene metadata (sensing_date, clear_fraction) is already
    # available client-side from the manifest, so there's no need to
    # "discover" it server-side. All N features are still batched into one
    # FeatureCollection and resolved with a single getInfo() call below —
    # acceptable for the pilot's small scene count; revisit (e.g. batching)
    # if the scene count grows much larger.
    features = [_compute_scene_row(scene, aoi, index_names) for scene in scenes]
    raw = ee.FeatureCollection(features).getInfo()
    return [feature["properties"] for feature in raw["features"]]


def write_features_table(
    rows: list[dict],
    index_names: list[str],
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["image_id", "sensing_date", "clear_pixel_fraction"] + [
        f"{name}_mean" for name in index_names
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def main() -> Path:
    config = load_config()
    init_ee(config)
    manifest = load_manifest()
    rows = compute_features(
        config, manifest, list(config.feature_indices), config.min_clear_fraction
    )
    return write_features_table(rows, list(config.feature_indices))


if __name__ == "__main__":
    main()
