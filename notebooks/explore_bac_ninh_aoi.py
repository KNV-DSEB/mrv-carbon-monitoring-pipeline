"""One-off helper to pick the pilot AOI for Bắc Ninh — NOT production code.

Not part of the src/mrv/ pipeline and not covered by tests/unit/, per the
`notebooks/` convention in CLAUDE.md ("exploratory analysis only").

Usage (run manually, once, after registering GEE per docs/setup/gee_setup.md):

1. Download the GADM Vietnam administrative level-3 (commune) boundaries
   as GeoJSON from https://gadm.org/download_country.html (select
   Vietnam). This script does not download it automatically, to avoid
   adding an HTTP dependency for a one-time step.

2. List candidate communes in Bắc Ninh, sorted by area:

       python notebooks/explore_bac_ninh_aoi.py list <path-to-gadm-level3.geojson>

3. Review the printed list, pick 1-3 adjacent communes whose combined
   area is on the order of a few km² (per docs/specs/01-data-collection.md
   — district-level boundaries are explicitly out of scope), then export
   the pilot AOI:

       python notebooks/explore_bac_ninh_aoi.py export <path-to-gadm-level3.geojson> \\
           <commune-name-1> [<commune-name-2> ...] \\
           --output data/external/aoi/bac_ninh_pilot.geojson

GADM field names (NAME_1 = province, NAME_2 = district, NAME_3 = commune)
are assumed based on the standard GADM schema; verify against the actual
downloaded file and adjust PROVINCE_FIELD/COMMUNE_FIELD/DISTRICT_FIELD
below if the real file uses different field names or diacritics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

PROVINCE_FIELD = "NAME_1"
DISTRICT_FIELD = "NAME_2"
COMMUNE_FIELD = "NAME_3"
TARGET_PROVINCE = "Bắc Ninh"


def _load_features(gadm_path: str | Path) -> list[dict]:
    with Path(gadm_path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("features", [])


def _province_communes(gadm_path: str | Path, province: str = TARGET_PROVINCE) -> list[dict]:
    features = _load_features(gadm_path)
    matches = [f for f in features if f["properties"].get(PROVINCE_FIELD) == province]
    if not matches:
        available = sorted({f["properties"].get(PROVINCE_FIELD) for f in features})
        raise ValueError(
            f"No features matched province {province!r} on field {PROVINCE_FIELD!r}. "
            f"Available values include: {available[:10]}... "
            "Check diacritics/field names in the actual GADM file."
        )
    return matches


def list_communes(gadm_path: str | Path, province: str = TARGET_PROVINCE) -> None:
    communes = _province_communes(gadm_path, province)
    rows = []
    for feature in communes:
        geom = ee.Geometry(feature["geometry"])
        area_km2 = geom.area().getInfo() / 1_000_000
        rows.append(
            (
                feature["properties"].get(COMMUNE_FIELD, "?"),
                feature["properties"].get(DISTRICT_FIELD, "?"),
                area_km2,
            )
        )

    rows.sort(key=lambda r: r[2])
    print(f"{'Commune (xã)':30} {'District (huyện)':25} {'Area (km2)':>10}")
    for name, district, area_km2 in rows:
        print(f"{name:30} {district:25} {area_km2:10.2f}")


def export_selected_communes(
    gadm_path: str | Path,
    commune_names: list[str],
    output_path: str | Path,
    province: str = TARGET_PROVINCE,
) -> Path:
    communes = _province_communes(gadm_path, province)
    selected = [f for f in communes if f["properties"].get(COMMUNE_FIELD) in commune_names]

    found_names = {f["properties"].get(COMMUNE_FIELD) for f in selected}
    missing = set(commune_names) - found_names
    if missing:
        raise ValueError(f"Commune(s) not found in {province}: {sorted(missing)}")

    feature_collection = {
        "type": "FeatureCollection",
        "features": selected,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(feature_collection, f, indent=2, ensure_ascii=False)

    total_area_km2 = sum(
        ee.Geometry(f["geometry"]).area().getInfo() / 1_000_000 for f in selected
    )
    print(f"Wrote {len(selected)} commune(s) to {output_path} (~{total_area_km2:.2f} km2 total)")
    return output_path


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List Bắc Ninh communes by area")
    list_parser.add_argument("gadm_path", help="Path to GADM Vietnam level-3 GeoJSON")

    export_parser = subparsers.add_parser("export", help="Export selected communes as pilot AOI")
    export_parser.add_argument("gadm_path", help="Path to GADM Vietnam level-3 GeoJSON")
    export_parser.add_argument("commune_names", nargs="+", help="Commune (xã) name(s) to include")
    export_parser.add_argument(
        "--output",
        default="data/external/aoi/bac_ninh_pilot.geojson",
        help="Output GeoJSON path",
    )

    args = parser.parse_args()

    if args.command == "list":
        list_communes(args.gadm_path)
    elif args.command == "export":
        export_selected_communes(args.gadm_path, args.commune_names, args.output)


if __name__ == "__main__":
    sys.exit(_main())
