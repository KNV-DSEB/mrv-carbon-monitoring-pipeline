"""Sentinel-1 SAR scene acquisition (spec 07).

Parallels ``sentinel2.py`` but for ``COPERNICUS/S1_GRD``: no cloud mask (SAR sees
through cloud), and the manifest carries orbit metadata so the series can be
locked to ONE orbit pass + ONE relative orbit before any backscatter is compared
across dates (see :func:`assert_single_orbit` and spec 07 R2).

Metadata only here — the VV/VH backscatter values live in
``mrv.features.backscatter`` (data_collection = manifest/metadata, features =
values), re-fetching each scene via :func:`scene_asset_id` (the spec-03 id
contract).
"""

from __future__ import annotations

import ee

S1_COLLECTION_ID = "COPERNICUS/S1_GRD"


def scene_asset_id(system_index: str) -> str:
    """Reconstruct the full S1 asset id from a bare ``system:index``.

    Single source of truth for suffix -> loadable asset id, imported by the
    features module so the two can't drift (the spec-03 pattern).
    """
    return f"{S1_COLLECTION_ID}/{system_index}"


def get_filtered_collection(
    aoi: ee.Geometry, date_start: str, date_end: str
) -> ee.ImageCollection:
    """S1 GRD, IW mode, scenes carrying BOTH VV and VH. No cloud filter (R1)."""
    return (
        ee.ImageCollection(S1_COLLECTION_ID)
        .filterBounds(aoi)
        .filterDate(date_start, date_end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )


def _build_scene_feature(image: ee.Image) -> ee.Feature:
    return ee.Feature(
        None,
        {
            # Bare system:index suffix; features re-expands it via scene_asset_id().
            "image_id": image.get("system:index"),
            "sensing_date": image.date().format("YYYY-MM-dd"),
            "orbit_pass": image.get("orbitProperties_pass"),
            "relative_orbit": image.get("relativeOrbitNumber_start"),
        },
    )


def build_manifest(collection: ee.ImageCollection) -> list[dict]:
    """Per-scene metadata (image_id, date, orbit pass + relative orbit).

    Built over the UNLOCKED collection so recon can report the full orbit
    distribution before the operator chooses a lock. No AOI reduction here — the
    backscatter (which does need the AOI) lives in the features module.
    """
    mapped = collection.map(_build_scene_feature)
    raw = ee.FeatureCollection(mapped).getInfo()
    return [feature["properties"] for feature in raw["features"]]


def orbit_distribution(scenes: list[dict]) -> list[dict]:
    """Pure: scene count per (orbit_pass, relative_orbit), before any lock (R2).

    Reported so the operator can pick ONE pass + ONE relative orbit — ascending
    vs descending (and different relative orbits) image the AOI at different
    incidence angles, so their backscatter is not comparable across dates.
    """
    counts: dict[tuple[str, int], int] = {}
    for scene in scenes:
        key = (scene["orbit_pass"], int(scene["relative_orbit"]))
        counts[key] = counts.get(key, 0) + 1
    return [
        {"orbit_pass": p, "relative_orbit": r, "count": c}
        for (p, r), c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
    ]


def filter_to_orbit(
    scenes: list[dict], orbit_pass: str, relative_orbit: int
) -> list[dict]:
    """Pure: keep only scenes on ONE pass + ONE relative orbit (the R2 lock)."""
    return [
        scene
        for scene in scenes
        if scene["orbit_pass"] == orbit_pass
        and int(scene["relative_orbit"]) == int(relative_orbit)
    ]


def assert_single_orbit(scenes: list[dict]) -> None:
    """Fail fast if a scene set spans more than one (pass, relative_orbit) (R2).

    Guards the silent trap where a forgotten orbit lock lets ascending and
    descending scenes (different incidence angles) into one time series, whose
    backscatter is then not comparable across dates.
    """
    groups = {(scene["orbit_pass"], int(scene["relative_orbit"])) for scene in scenes}
    if len(groups) > 1:
        rendered = ", ".join(f"{p}/{r}" for p, r in sorted(groups))
        raise RuntimeError(
            f"SAR series spans multiple orbit groups ({rendered}); backscatter is "
            "not comparable across incidence angles. Lock S1_ORBIT_PASS + "
            "S1_RELATIVE_ORBIT in .env to a single group (see recon_sar's orbit "
            "distribution)."
        )
