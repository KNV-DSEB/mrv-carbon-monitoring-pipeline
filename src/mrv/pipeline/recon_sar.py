"""Sentinel-1 SAR reconnaissance entry point (spec 07).

Runs ``get_filtered_collection -> manifest`` and reports the orbit distribution
BEFORE any lock, so the operator can choose ONE pass + ONE relative orbit
(``S1_ORBIT_PASS`` / ``S1_RELATIVE_ORBIT`` in ``.env``). Once locked, it reports
the surviving scene count, the inter-scene day-gaps, the out-of-footprint (None)
count, and writes the VV/VH backscatter table.

The optical ``recon.py`` is deliberately untouched; this is a separate SAR entry
point. Run via ``python -m mrv.pipeline.recon_sar`` (the live GEE call is the
operator's, with their own credentials).

Prediction to falsify (spec 07): the Vụ Mùa window, where optical returned 0
usable scenes, MUST return S1 scenes here — 0 would mean a filter/orbit-lock bug,
not "SAR is blind too".
"""

from __future__ import annotations

import statistics
from datetime import date

from mrv.data_collection.aoi import load_aoi_geometry
from mrv.data_collection.gee_client import init_ee
from mrv.data_collection.sentinel1 import (
    assert_single_orbit,
    build_manifest,
    filter_to_orbit,
    get_filtered_collection,
    orbit_distribution,
)
from mrv.features.backscatter import compute_backscatter, write_backscatter_table
from mrv.utils.config import load_config


def day_gap_stats(scenes: list[dict]) -> dict | None:
    """Pure: min/median/max day-gap between consecutive date-sorted scenes.

    Returns None for fewer than 2 scenes (no gap defined). Lets the operator see
    whether the locked SAR series is genuinely denser than the optical one.
    """
    dates = sorted(scene["sensing_date"] for scene in scenes)
    if len(dates) < 2:
        return None
    gaps = [
        (date.fromisoformat(b) - date.fromisoformat(a)).days
        for a, b in zip(dates, dates[1:])
    ]
    return {"min": min(gaps), "median": statistics.median(gaps), "max": max(gaps)}


def format_distribution(distribution: list[dict]) -> str:
    """Render the pre-lock orbit distribution for the operator to choose from."""
    lines = ["Orbit distribution (pass / relative_orbit -> scenes):"]
    if not distribution:
        lines.append("  (no scenes)")
    for d in distribution:
        lines.append(
            f"  {d['orbit_pass']:<11} / {d['relative_orbit']:>3} -> {d['count']}"
        )
    return "\n".join(lines)


def main() -> int:
    config = load_config()
    init_ee(config)
    aoi = load_aoi_geometry(config.aoi_path)
    collection = get_filtered_collection(aoi, config.date_start, config.date_end)
    scenes = build_manifest(collection)

    print(f"=== SAR reconnaissance ({config.date_start}..{config.date_end}) ===")
    print(f"Tier 1: {len(scenes)} S1 GRD IW (VV+VH) scene(s) returned.")
    print(format_distribution(orbit_distribution(scenes)))

    if config.s1_orbit_pass is None or config.s1_relative_orbit is None:
        print(
            "\nOrbit not locked. Pick ONE pass + ONE relative orbit from the "
            "distribution above, set S1_ORBIT_PASS and S1_RELATIVE_ORBIT in .env, "
            "then re-run — backscatter across mixed orbits is not comparable (R2)."
        )
        return 1

    locked = filter_to_orbit(scenes, config.s1_orbit_pass, config.s1_relative_orbit)
    assert_single_orbit(locked)
    print(
        f"\nLocked to {config.s1_orbit_pass}/{config.s1_relative_orbit}: "
        f"{len(locked)} scene(s)."
    )
    if not locked:
        print(
            "No scenes on the chosen orbit — pick another (pass, relative_orbit) "
            "from the distribution above and re-run."
        )
        return 1

    gaps = day_gap_stats(locked)
    if gaps is not None:
        print(
            f"  day-gaps between scenes: min={gaps['min']} "
            f"median={gaps['median']} max={gaps['max']}"
        )

    rows = compute_backscatter(config, locked)
    no_data = sum(1 for r in rows if r["vv_db"] is None and r["vh_db"] is None)
    print(f"  scenes with AOI outside footprint (None backscatter): {no_data}")

    output_path = write_backscatter_table(rows)
    print(f"Wrote {len(rows)} VV/VH row(s) to {output_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
