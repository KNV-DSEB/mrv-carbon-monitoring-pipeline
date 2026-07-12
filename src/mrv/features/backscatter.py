"""Zonal Sentinel-1 backscatter (VV/VH) over the AOI (spec 07).

Re-fetches each S1 scene from the manifest (via the shared
``sentinel1.scene_asset_id`` contract) and computes an AOI-mean backscatter per
polarisation, handling the three SAR pitfalls the spec calls out:

- R3 (dB vs linear): S1_GRD is in dB; the mean is computed in LINEAR power and
  converted back to dB, because ``mean(dB) != dB(mean(power))``.
- R4 (speckle): a ``focal_median`` runs before the reduction. At AOI scale this
  is near-negligible (the ~20k-pixel mean already suppresses speckle ~1/sqrt(N));
  it is future-proofing for per-parcel work, not a headline step.
- R5 (coverage): an AOI outside a scene's footprint has no valid pixels, so the
  backscatter is ``None`` (not observed) — NEVER coerced to 0.0.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import ee

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.sentinel1 import scene_asset_id
from mrv.features.zonal import zonal_mean
from mrv.utils.config import Config

DEFAULT_OUTPUT_PATH = Path("data/processed/s1_backscatter.csv")

# focal_median kernel. 30 m is future-proofing for per-parcel work; at AOI scale
# the ~20k-pixel zonal mean already suppresses speckle (see module docstring, R4).
SPECKLE_KERNEL_RADIUS_M = 30
BACKSCATTER_BANDS = ("VV", "VH")

_LN10 = math.log(10.0)


def _to_linear(db_image: ee.Image) -> ee.Image:
    # dB -> linear power: 10**(dB/10) == exp((dB/10) * ln 10). Written with exp
    # (all elementwise band ops) so the zonal mean happens in linear space, not
    # in dB (mean(dB) != dB(mean(power)) — R3).
    return db_image.divide(10.0).multiply(_LN10).exp()


def _despeckle(linear_image: ee.Image) -> ee.Image:
    # R4: speckle filter before the reduction. Near-negligible at AOI scale.
    return linear_image.focal_median(
        radius=SPECKLE_KERNEL_RADIUS_M, kernelType="circle", units="meters"
    )


def _band_linear_mean(image: ee.Image, aoi: ee.Geometry, band: str):
    """AOI-mean of one polarisation in LINEAR power (server-side; None if empty)."""
    linear = _to_linear(image.select(band)).rename(band)
    despeckled = _despeckle(linear)
    return zonal_mean(despeckled, aoi, band)


def _linear_to_db(linear_mean) -> float | None:
    """Convert a linear-power AOI mean back to dB, preserving no-data.

    ``None`` (AOI outside the scene footprint) stays ``None`` — never coerced to
    0.0 (R5). A non-positive mean has no dB and is also reported as ``None``.
    """
    if linear_mean is None or linear_mean <= 0:
        return None
    return 10.0 * math.log10(linear_mean)


def _scene_feature(scene: dict, aoi: ee.Geometry) -> ee.Feature:
    image = ee.Image(scene_asset_id(scene["image_id"]))
    properties: dict[str, object] = {
        "image_id": scene["image_id"],
        "sensing_date": scene["sensing_date"],
        "orbit_pass": scene.get("orbit_pass"),
        "relative_orbit": scene.get("relative_orbit"),
    }
    for band in BACKSCATTER_BANDS:
        properties[f"{band}_linear"] = _band_linear_mean(image, aoi, band)
    return ee.Feature(None, properties)


def compute_backscatter(config: Config, scenes: list[dict]) -> list[dict]:
    """Compute AOI-mean VV/VH in dB for each (orbit-locked) manifest scene."""
    aoi = load_aoi_geometry(config.aoi_path)
    features = [_scene_feature(scene, aoi) for scene in scenes]
    raw = ee.FeatureCollection(features).getInfo()

    rows: list[dict] = []
    for feature in raw["features"]:
        p = feature["properties"]
        rows.append(
            {
                "image_id": p.get("image_id"),
                "sensing_date": p.get("sensing_date"),
                "orbit_pass": p.get("orbit_pass"),
                "relative_orbit": p.get("relative_orbit"),
                "vv_db": _linear_to_db(p.get("VV_linear")),
                "vh_db": _linear_to_db(p.get("VH_linear")),
            }
        )
    return rows


def write_backscatter_table(
    rows: list[dict], output_path: Path = DEFAULT_OUTPUT_PATH
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "image_id",
        "sensing_date",
        "orbit_pass",
        "relative_orbit",
        "vv_db",
        "vh_db",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path
