from __future__ import annotations

import csv
import json
from pathlib import Path

import ee

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.gee_client import init_ee
from mrv.data_collection.sentinel2 import mask_clouds, scene_asset_id
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


def _assert_scenes_to_process(
    manifest: dict, included: list[dict], min_clear_fraction: float
) -> None:
    """Fail fast with an actionable message when there's nothing to compute.

    Distinguishes an empty manifest (run data_collection first) from a manifest
    whose scenes all fall below MIN_CLEAR_FRACTION (lower the threshold or
    collect a denser series). Raised before touching GEE, so the operator sees
    guidance instead of an opaque empty-FeatureCollection error.
    """
    if included:
        return
    all_scenes = manifest["scenes"]
    if not all_scenes:
        raise RuntimeError(
            "Manifest contains 0 scenes; nothing to compute. Run "
            "data_collection first (python -m mrv.data_collection.collect) with "
            "a wider DATE_START/DATE_END or a higher MAX_CLOUD_COVER_PCT."
        )
    best = max(scene["aoi_clear_fraction"] for scene in all_scenes)
    raise RuntimeError(
        f"None of the {len(all_scenes)} manifest scene(s) meet "
        f"MIN_CLEAR_FRACTION={min_clear_fraction} (best available "
        f"aoi_clear_fraction={best}). Lower MIN_CLEAR_FRACTION in .env or "
        "collect a denser/clearer time series."
    )


def _fetch_masked_image(image_id: str) -> ee.Image:
    # The manifest stores the bare Sentinel-2 system:index suffix, not the
    # full asset id. scene_asset_id() (the single source of truth in
    # data_collection.sentinel2) reconstructs the loadable asset id, so the
    # two modules can't drift on the id format.
    return mask_clouds(ee.Image(scene_asset_id(image_id)))


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
    scenes = _included_scenes(manifest, min_clear_fraction)
    _assert_scenes_to_process(manifest, scenes, min_clear_fraction)
    aoi = load_aoi_geometry(config.aoi_path)

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
