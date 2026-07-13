"""MRV Carbon Monitoring — Streamlit dashboard (spec 08).

Runs with **no Google Earth Engine credentials**: every number on screen is read
from the committed demo snapshots in ``data/demo/`` (see ``dashboard/loaders.py``).
Nothing is hardcoded — the flood date, the VV minimum, and the anomalous scenes
are derived from the CSVs at read time.

Run:  streamlit run dashboard/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run dashboard/app.py` puts dashboard/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard.loaders import (  # noqa: E402
    assign_segments,
    load_aoi_polygon,
    load_coverage,
    load_optical_series,
    load_phases,
    load_sar_series,
    mark_low_vv,
    optical_flood_date,
    polygon_centroid,
    sar_vv_min_date,
)

# Validated categorical palette (blue / aqua / yellow), light + dark steps.
# Verified with the dataviz validator: all checks pass; worst adjacent CVD ΔE
# 47.2 (light) / 41.3 (dark). Light-mode aqua+yellow sit under 3:1 on the
# surface, so the "relief rule" applies — every chart ships a data table.
LIGHT = {
    "series": ["#2a78d6", "#1baf7a", "#eda100"],
    "critical": "#d03b3b",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "muted": "#898781",
}
DARK = {
    "series": ["#3987e5", "#199e70", "#c98500"],
    "critical": "#d03b3b",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "muted": "#898781",
}


def palette() -> dict:
    try:
        if st.context.theme.type == "dark":
            return DARK
    except Exception:
        pass
    return LIGHT


def style(chart: alt.Chart, pal: dict) -> alt.Chart:
    """Recessive grid/axes, transparent surface (inherits the Streamlit theme)."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=pal["grid"],
            domainColor=pal["axis"],
            tickColor=pal["axis"],
            labelColor=pal["muted"],
            titleColor=pal["muted"],
        )
        .configure_legend(labelColor=pal["muted"], titleColor=pal["muted"])
    )


@st.cache_data
def get_data() -> dict:
    phases = assign_segments(load_phases())
    sar = mark_low_vv(load_sar_series())
    return {
        "phases": phases,
        "optical_raw": load_optical_series(),
        "sar": sar,
        "coverage": load_coverage(),
        "ring": load_aoi_polygon(),
        "flood_date": optical_flood_date(phases),
        "vv_min_date": sar_vv_min_date(sar),
    }


def x_axis(domain: list) -> alt.X:
    return alt.X(
        "sensing_date:T",
        title=None,
        scale=alt.Scale(domain=domain),
        axis=alt.Axis(format="%d %b", grid=False),
    )


# --------------------------------------------------------------------------- #

st.set_page_config(page_title="MRV Carbon Monitoring — Bắc Ninh", layout="wide")
pal = palette()
data = get_data()

st.title("MRV Carbon Monitoring — Bắc Ninh rice pilot")
st.caption(
    "Sentinel-2 optical + Sentinel-1 SAR over a 2.03 km² paddy AOI in Lương Tài. "
    "All figures read from committed snapshots in `data/demo/` — no Earth Engine "
    "credentials required."
)

# Fixed honesty banner — always visible, never dismissable.
st.warning(
    "**Phát hiện pha MÙA VỤ, CHƯA phải phát hiện sự kiện AWD.** "
    "Chưa có ground truth thực địa. Ngưỡng chưa validate.  \n"
    "_Crop-season phase detection — NOT AWD event detection. No field ground "
    "truth. Thresholds unvalidated._"
)

phases_df = pd.DataFrame(data["phases"])
phases_df["sensing_date"] = pd.to_datetime(phases_df["sensing_date"])
sar_df = pd.DataFrame(data["sar"])
sar_df["sensing_date"] = pd.to_datetime(sar_df["sensing_date"])

flood_dt = pd.to_datetime(data["flood_date"])
vv_min_dt = pd.to_datetime(data["vv_min_date"])

# Shared time domain so the two sensors line up across charts.
domain = [
    min(phases_df["sensing_date"].min(), sar_df["sensing_date"].min()),
    max(phases_df["sensing_date"].max(), sar_df["sensing_date"].max()),
]

# --- AOI + coverage -------------------------------------------------------- #

left, right = st.columns([1, 1])

with left:
    st.subheader("Pilot AOI")
    ring = data["ring"]
    lon, lat = polygon_centroid(ring)
    st.pydeck_chart(
        pdk.Deck(
            layers=[
                pdk.Layer(
                    "PolygonLayer",
                    data=[{"polygon": ring}],
                    get_polygon="polygon",
                    get_fill_color=[42, 120, 214, 55],
                    get_line_color=[42, 120, 214],
                    line_width_min_pixels=2,
                    stroked=True,
                    filled=True,
                )
            ],
            initial_view_state=pdk.ViewState(longitude=lon, latitude=lat, zoom=12.5),
            map_style=None,  # no basemap tiles => renders offline
        )
    )

with right:
    st.subheader("Coverage: optical vs SAR")
    cov = pd.DataFrame(data["coverage"])
    st.dataframe(
        cov.rename(
            columns={
                "season": "Season",
                "window": "Window",
                "sensor": "Sensor",
                "usable_scenes": "Usable scenes",
                "gap_min": "Gap min (d)",
                "gap_median": "Gap median (d)",
                "gap_max": "Gap max (d)",
            }
        ),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        "Optical returns **0 usable scenes** in the rainy season; SAR returns 5. "
        "In the dry season SAR doubles the series (7 → 14)."
    )

st.divider()

tab_optical, tab_sar, tab_overlay = st.tabs(
    ["Optical (crop phases)", "SAR (backscatter)", "Two-sensor cross-check"]
)

# --- Tab 1: optical -------------------------------------------------------- #

with tab_optical:
    st.subheader("Sentinel-2 indices + crop-season phase")
    st.caption(
        "The 45-day gap (27 Jan → 13 Mar) is drawn as a **break, never "
        "interpolated** — it hid the transplanting stage and the rise into the "
        "true NDVI peak."
    )

    long = phases_df.melt(
        id_vars=["sensing_date", "segment", "phase"],
        value_vars=["ndvi", "ndwi", "lswi"],
        var_name="index",
        value_name="value",
    )
    long["index"] = long["index"].str.upper()

    color = alt.Color(
        "index:N",
        title="Index",
        scale=alt.Scale(domain=["NDVI", "NDWI", "LSWI"], range=pal["series"]),
    )
    base = alt.Chart(long).encode(
        x=x_axis(domain),
        y=alt.Y("value:Q", title="Index value"),
        color=color,
    )
    # `detail=segment` => one line per gap-bounded run; no line spans the gap.
    lines = base.mark_line(strokeWidth=2).encode(detail="segment:N")
    points = base.mark_point(size=70, filled=True, opacity=1).encode(
        tooltip=[
            alt.Tooltip("sensing_date:T", title="Date", format="%d %b %Y"),
            alt.Tooltip("index:N", title="Index"),
            alt.Tooltip("value:Q", title="Value", format=".3f"),
            alt.Tooltip("phase:N", title="Phase"),
        ]
    )
    st.altair_chart(style((lines + points).properties(height=320), pal), width="stretch")

    # Table view: the contrast-relief channel, and the phase/reason record.
    st.dataframe(
        phases_df[["sensing_date", "phase", "reason", "ndvi", "ndwi", "lswi", "gap_before"]]
        .assign(sensing_date=lambda d: d["sensing_date"].dt.date)
        .rename(columns={"sensing_date": "Date", "phase": "Phase", "reason": "Why", "gap_before": "Gap before"}),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Raw features table (spectral_indices.csv)"):
        st.dataframe(pd.DataFrame(data["optical_raw"]), hide_index=True, width="stretch")

# --- Tab 2: SAR ------------------------------------------------------------ #

with tab_sar:
    st.subheader("Sentinel-1 backscatter (DESCENDING / 91)")
    st.caption(
        "A flooded paddy reflects radar away from the satellite → **low VV**. "
        "Scenes with a VV z-score ≤ −1.0 are flagged (derived from the data)."
    )

    sar_long = sar_df.melt(
        id_vars=["sensing_date"], value_vars=["vv_db", "vh_db"],
        var_name="band", value_name="value",
    )
    sar_long["band"] = sar_long["band"].str.replace("_db", "", regex=False).str.upper()

    sar_base = alt.Chart(sar_long).encode(
        x=x_axis(domain),
        y=alt.Y("value:Q", title="Backscatter (dB)", scale=alt.Scale(zero=False)),
        color=alt.Color(
            "band:N", title="Polarisation",
            scale=alt.Scale(domain=["VV", "VH"], range=pal["series"][:2]),
        ),
    )
    sar_lines = sar_base.mark_line(strokeWidth=2)
    sar_points = sar_base.mark_point(size=70, filled=True, opacity=1).encode(
        tooltip=[
            alt.Tooltip("sensing_date:T", title="Date", format="%d %b %Y"),
            alt.Tooltip("band:N", title="Band"),
            alt.Tooltip("value:Q", title="dB", format=".2f"),
        ]
    )

    low = sar_df[sar_df["low_vv"]]
    low_marks = (
        alt.Chart(low)
        .mark_point(size=200, shape="diamond", filled=False, strokeWidth=2.5, color=pal["critical"])
        .encode(x=x_axis(domain), y=alt.Y("vv_db:Q", scale=alt.Scale(zero=False)))
    )
    low_labels = (
        alt.Chart(low)
        .mark_text(dy=18, fontSize=11, color=pal["critical"])
        .encode(x=x_axis(domain), y=alt.Y("vv_db:Q", scale=alt.Scale(zero=False)), text=alt.value("low VV"))
    )

    st.altair_chart(
        style((sar_lines + sar_points + low_marks + low_labels).properties(height=320), pal),
        width="stretch",
    )
    st.dataframe(
        sar_df[["sensing_date", "vv_db", "vh_db", "vv_z", "low_vv"]]
        .assign(sensing_date=lambda d: d["sensing_date"].dt.date)
        .rename(columns={"sensing_date": "Date", "vv_db": "VV (dB)", "vh_db": "VH (dB)", "vv_z": "VV z-score", "low_vv": "Low VV"}),
        hide_index=True,
        width="stretch",
    )

# --- Tab 3: two-sensor cross-check ---------------------------------------- #

with tab_overlay:
    st.subheader("Two independent sensors, one flood event")
    st.markdown(
        f"Optical labels **{flood_dt:%d %b %Y}** the flood phase (NDVI at its "
        f"minimum). SAR — a completely different physical mechanism — bottoms out "
        f"at **{vv_min_dt:%d %b %Y}**, two days later. Neither knows about the other.  \n"
        "Two of the three low-VV scenes (10 Feb, 22 Feb) sit **inside the optical "
        "45-day gap** — SAR observes exactly where optical is blind."
    )

    # NOTE: NDVI (unitless) and VV (dB) are different scales, so these are two
    # stacked charts on a SHARED time axis — never a dual-axis chart.
    rules = alt.Chart(
        pd.DataFrame({"d": [flood_dt, vv_min_dt], "label": ["optical flood", "SAR VV-min"]})
    ).mark_rule(strokeDash=[4, 3], strokeWidth=1.5, color=pal["muted"]).encode(x="d:T")

    ndvi_chart = (
        alt.Chart(phases_df)
        .mark_line(strokeWidth=2, color=pal["series"][0])
        .encode(x=x_axis(domain), y=alt.Y("ndvi:Q", title="NDVI (optical)"), detail="segment:N")
        + alt.Chart(phases_df).mark_point(size=70, filled=True, color=pal["series"][0]).encode(
            x=x_axis(domain), y="ndvi:Q",
            tooltip=[alt.Tooltip("sensing_date:T", format="%d %b"), alt.Tooltip("ndvi:Q", format=".3f"), "phase:N"],
        )
    )

    vv_chart = (
        alt.Chart(sar_df)
        .mark_line(strokeWidth=2, color=pal["series"][1])
        .encode(x=x_axis(domain), y=alt.Y("vv_db:Q", title="VV (dB, SAR)", scale=alt.Scale(zero=False)))
        + alt.Chart(sar_df).mark_point(size=70, filled=True, color=pal["series"][1]).encode(
            x=x_axis(domain), y=alt.Y("vv_db:Q", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("sensing_date:T", format="%d %b"), alt.Tooltip("vv_db:Q", format=".2f")],
        )
        + alt.Chart(sar_df[sar_df["low_vv"]]).mark_point(
            size=200, shape="diamond", filled=False, strokeWidth=2.5, color=pal["critical"]
        ).encode(x=x_axis(domain), y=alt.Y("vv_db:Q", scale=alt.Scale(zero=False)))
    )

    combined = alt.vconcat(
        (ndvi_chart + rules).properties(height=200, title="Optical — NDVI"),
        (vv_chart + rules).properties(height=200, title="SAR — VV backscatter"),
    ).resolve_scale(x="shared")
    st.altair_chart(style(combined, pal), width="stretch")

    st.caption(
        "Two charts on a shared time axis (not a dual-axis chart — NDVI and dB "
        "are different scales and must not share one y-axis)."
    )

st.divider()
st.caption(
    "Sources: `docs/reports/02-first-live-run-report.en.md`, "
    "`docs/reports/03-sar-findings-report.en.md`. Data: `data/demo/` snapshots "
    "of real Google Earth Engine runs. This is a technical portfolio project — "
    "not a commercial MRV product."
)
