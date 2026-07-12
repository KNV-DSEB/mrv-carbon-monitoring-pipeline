"""Reconnaissance / live-run entry point.

Runs the existing ``collect -> compute`` chain end to end and prints a
data-density summary so the operator can judge whether the AOI / date window /
thresholds are viable *before* trusting the output. It surfaces both filter
tiers:

- **Tier 1** — how many scenes the GEE query returned at all, i.e. scenes that
  already passed the ``MAX_CLOUD_COVER_PCT`` filter (the manifest scene_count).
- **Tier 2** — the ``aoi_clear_fraction`` distribution and how many scenes
  survive across a sweep of ``MIN_CLEAR_FRACTION`` thresholds.

The summary math (:func:`summarize_manifest`) is pure Python over the manifest —
no ``ee.*`` — so it is independently unit-testable. Run via
``python -m mrv.pipeline.recon`` (the live GEE call is the operator's, with
their own credentials).
"""

from __future__ import annotations

import statistics
from typing import Sequence

from mrv.data_collection.collect import collect_manifest, write_manifest
from mrv.features.compute import compute_features, write_features_table
from mrv.utils.config import load_config

# Threshold sweep for the tier-2 survival report. The configured
# MIN_CLEAR_FRACTION is always merged in so the operator sees where they stand.
DEFAULT_SURVIVAL_THRESHOLDS: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9)

# aoi_clear_fraction histogram buckets: [lo, hi). The final bucket's hi is >1 so
# a perfectly clear scene (1.0) lands in it.
_HISTOGRAM_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("<0.5", 0.0, 0.5),
    ("0.5-0.7", 0.5, 0.7),
    ("0.7-0.8", 0.7, 0.8),
    ("0.8-0.9", 0.8, 0.9),
    (">=0.9", 0.9, 1.0001),
)


def _histogram(fractions: Sequence[float]) -> dict[str, int]:
    counts = {label: 0 for label, _, _ in _HISTOGRAM_BUCKETS}
    for value in fractions:
        for label, lo, hi in _HISTOGRAM_BUCKETS:
            if lo <= value < hi:
                counts[label] += 1
                break
    return counts


def summarize_manifest(
    manifest: dict,
    min_clear_fraction: float,
    thresholds: Sequence[float] | None = None,
) -> dict:
    """Compute the two-tier data-density summary from a manifest (pure).

    Scenes whose ``aoi_clear_fraction`` is ``None`` are "no-data" — the AOI lies
    entirely outside the scene footprint, so it was not observed and no clear
    fraction could be computed. They are NOT the same as a fully cloudy scene
    (fraction ``0.0``, observed but clouded), so they are counted separately
    (``no_data_count``) and kept out of every numeric tier-2 output rather than
    coerced to a number.
    """
    scenes = manifest.get("scenes", [])
    valid_fractions = [
        float(scene["aoi_clear_fraction"])
        for scene in scenes
        if scene.get("aoi_clear_fraction") is not None
    ]
    no_data_count = sum(
        1 for scene in scenes if scene.get("aoi_clear_fraction") is None
    )

    sweep_source = DEFAULT_SURVIVAL_THRESHOLDS if thresholds is None else thresholds
    # Always include the configured threshold so survivors_at_config is defined.
    sweep = sorted(set(sweep_source) | {min_clear_fraction})
    survival = {t: sum(1 for f in valid_fractions if f >= t) for t in sweep}

    stats = None
    if valid_fractions:
        stats = {
            "min": min(valid_fractions),
            "max": max(valid_fractions),
            "mean": statistics.fmean(valid_fractions),
            "median": statistics.median(valid_fractions),
        }

    return {
        # Tier 1: scenes that passed the MAX_CLOUD_COVER_PCT query filter.
        "scene_count": len(scenes),
        # Of those, how many carried no computable clear-fraction (no-data).
        "no_data_count": no_data_count,
        "max_cloud_cover_pct": manifest.get("max_cloud_cover_pct"),
        "date_start": manifest.get("date_start"),
        "date_end": manifest.get("date_end"),
        # Tier 2: aoi_clear_fraction distribution + MIN_CLEAR_FRACTION survival,
        # computed over the valid (non-None) fractions only.
        "clear_fraction_stats": stats,
        "histogram": _histogram(valid_fractions),
        "min_clear_fraction": min_clear_fraction,
        "survival": survival,
        "survivors_at_config": survival[min_clear_fraction],
    }


def format_summary(summary: dict) -> str:
    """Render :func:`summarize_manifest` output as a readable, labelled block."""
    lines = ["=== Reconnaissance summary ==="]
    no_data = summary["no_data_count"]
    with_fraction = summary["scene_count"] - no_data
    lines.append(
        f"Tier 1 (post MAX_CLOUD_COVER_PCT={summary['max_cloud_cover_pct']}): "
        f"{summary['scene_count']} scene(s) returned over "
        f"{summary['date_start']}..{summary['date_end']} "
        f"- {with_fraction} with clear-fraction, {no_data} no-data"
        + (" (AOI outside scene footprint - not observed)" if no_data else "")
    )
    stats = summary["clear_fraction_stats"]
    if stats is None:
        lines.append("  aoi_clear_fraction: (no scenes with a computable clear-fraction)")
    else:
        lines.append(
            "  aoi_clear_fraction: "
            f"min={stats['min']:.3f} median={stats['median']:.3f} "
            f"mean={stats['mean']:.3f} max={stats['max']:.3f}"
        )
        lines.append("  histogram:")
        for label, count in summary["histogram"].items():
            lines.append(f"    {label:>7}: {count}")
    lines.append(
        "Tier 2 (survival by MIN_CLEAR_FRACTION, "
        f"configured={summary['min_clear_fraction']}):"
    )
    for threshold, count in summary["survival"].items():
        marker = "  <- configured" if threshold == summary["min_clear_fraction"] else ""
        lines.append(f"    >= {threshold:.2f}: {count} scene(s){marker}")
    return "\n".join(lines)


def _thin_result_guidance(summary: dict) -> str:
    """Actionable guidance naming BOTH knobs when nothing survives tier 2."""
    return (
        "No scenes survive MIN_CLEAR_FRACTION="
        f"{summary['min_clear_fraction']}. Two knobs widen the result:\n"
        "  - Tier 1: widen DATE_START/DATE_END or raise MAX_CLOUD_COVER_PCT in "
        ".env (more scenes returned), then re-run.\n"
        "  - Tier 2: lower MIN_CLEAR_FRACTION in .env (accept cloudier scenes)."
    )


def main() -> int:
    config = load_config()
    manifest = collect_manifest(config)

    summary = summarize_manifest(manifest, config.min_clear_fraction)
    print(format_summary(summary))

    # Persist the manifest for the record even if it's thin — this is a live
    # run, and the summary above is already printed for diagnosis.
    write_manifest(manifest)

    if summary["survivors_at_config"] == 0:
        print(_thin_result_guidance(summary))
        return 1

    rows = compute_features(
        config, manifest, list(config.feature_indices), config.min_clear_fraction
    )
    output_path = write_features_table(rows, list(config.feature_indices))
    dropped = summary["scene_count"] - len(rows)
    # Same total, split by reason: no-data scenes never had a clear-fraction to
    # compare, so they're a distinct bucket from scenes below the threshold.
    no_data = summary["no_data_count"]
    below = dropped - no_data
    print(
        f"Wrote {len(rows)} feature row(s) to {output_path} "
        f"({dropped} scene(s) dropped: {below} below MIN_CLEAR_FRACTION="
        f"{config.min_clear_fraction}, {no_data} no-data)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
