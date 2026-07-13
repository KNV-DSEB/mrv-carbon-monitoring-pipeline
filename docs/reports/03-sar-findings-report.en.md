# SAR Findings Report — MRV Carbon Monitoring Pipeline

**Scope**: First Sentinel-1 SAR run, pilot AOI, Bắc Ninh, Vietnam
**Date**: July 2026
**Version**: English ([Bản tiếng Việt](03-sar-findings-report.vi.md))

**Status**: First Sentinel-1 run over the pilot AOI, orbit-locked to
**DESCENDING / 91** across both seasons. It proves cloud-free year-round coverage
and cross-confirms the optical flood signal with an independent sensor. **No
field / ground-truth validation has been done, and no accuracy percentage is
claimed.** All numbers come from `data/processed/s1_backscatter.csv`.

## 1. Executive Summary

Sentinel-1 C-band SAR **solves the year-round coverage problem** that optical
could not (report 02): where the rainy-season optical run returned **0 usable
scenes**, SAR returns a dense, cloud-free series in both seasons. The SAR series
also **independently cross-confirms the optical flood signal** — the lowest VV
backscatter of the dry season falls two days from the optical flood scene, via a
completely different physical mechanism — and it **fills the exact 45-day optical
gap** that had forced the crop-phase baseline to return `undetermined` at the
real NDVI peak.

What SAR does **not** yet do: detect the sub-monthly AWD flood/dry *event*. That
remains a per-parcel, denser-revisit problem (Section 5).

## 2. Configuration

- **Orbit lock: DESCENDING / relative orbit 91**, applied to both windows. This
  was the **only orbit strong in both seasons**, so its backscatter is comparable
  across the year — ascending/other orbits image the AOI at a different incidence
  angle and cannot be mixed in (spec 07 R2).
- Both windows queried on `COPERNICUS/S1_GRD`, IW mode, VV+VH, **no cloud
  filter** (SAR penetrates cloud), AOI-mean computed in linear power then
  reported in dB (spec 07 R3).

## 3. Coverage — optical vs SAR (both seasons)

| Season (window) | Optical usable | SAR usable | SAR day-gaps (min/median/max) |
|---|---|---|---|
| Vụ Mùa `2025-07-01..08-15` | **0** | **5** | 6 / 9 / 12 |
| Đông-Xuân `2026-01-15..06-30` | **7** | **14** | 7 / 12 / 24 |

SAR returned **0 scenes with the AOI outside the footprint** in either window
(optical frequently lands at swath edges → no-data). The rainy-season result is
the decisive one: **5 usable SAR scenes where optical had 0** — the falsifiable
prediction of spec 07 held.

## 4. Main Finding — two independent sensors, one flood event

The Đông-Xuân SAR series (DESCENDING/91, 14 scenes):

| Date | VV (dB) | VH (dB) | note |
|---|---|---|---|
| 2026-01-17 | −7.53 | −14.48 | |
| 2026-01-29 | **−11.32** | −19.10 | **VV min (z = −2.00)** |
| 2026-02-10 | −10.22 | −18.38 | low VV (z = −1.06) |
| 2026-02-22 | −10.75 | −19.20 | low VV (z = −1.51) |
| 2026-03-18 | −9.16 | −18.73 | |
| 2026-03-30 | −8.21 | −18.05 | |
| 2026-04-11 | −7.54 | −16.92 | |
| 2026-04-23 | −8.36 | −16.23 | |
| 2026-05-05 | −8.06 | −15.86 | |
| 2026-05-17 | −8.53 | −15.10 | |
| 2026-05-29 | −9.11 | −14.50 | |
| 2026-06-10 | −8.11 | **−14.05** | **VH max** |
| 2026-06-22 | −9.08 | −15.94 | |
| 2026-06-29 | −9.77 | −16.47 | |

(VV mean −8.98 dB, sd 1.17.)

**Cross-sensor flood confirmation.** The lowest VV of the season is
**−11.32 dB on 29 Jan** (z = −2.00). A flooded paddy is a smooth water surface
that reflects the radar pulse away from the satellite → low VV. Optical,
independently, marks **27 Jan** as the flood/puddling phase (NDVI 0.049 — the
series minimum; NDWI −0.005 — the most water-like). **Two different physical
mechanisms, two days apart, point at the same flood event.**

**An extended flood window.** VV is anomalously low on **three consecutive**
dates — 29 Jan (z = −2.00), 10 Feb (z = −1.06), 22 Feb (z = −1.51) — indicating
a flood window spanning late January into February.

**SAR fills the hole that broke optical.** Of those three, **10 Feb and 22 Feb
fall inside optical's 45-day gap** (27 Jan → 13 Mar) — the very gap that hid the
transplanting stage and the rising side of the NDVI peak, forcing the crop-phase
baseline to return `undetermined` (report 02 / spec 06). SAR observes exactly
where optical was blind.

**VH tracks canopy growth.** VH rises steadily from **−19.2 dB (22 Feb)** to
**−14.05 dB (10 Jun)**, consistent with increasing canopy biomass — the same arc
the optical NDVI traces.

## 5. Preliminary field cross-check (NOT validation)

A brief phone check with local farmers in the AOI area recalled that the paddies
were **flooded in late January** — consistent with both the SAR VV minimum
(29 Jan) and the optical flood scene (27 Jan). This is **anecdotal, not
validation**: a handful of recall-based phone conversations, small n, no
structured ground-truth protocol, no plot-level georeferencing. It is reported
only as a weak, independent sanity check pointing the same way as the two
sensors — never as a measured accuracy.

## 6. Limitations (stated explicitly, not hidden)

1. **−11.3 dB is moderate flooding, not open water.** Open water typically reads
   −15 to −20 dB VV. The 2 km² AOI mean blends paddies with bunds, tracks, and
   village edges, diluting the signal. **No "open-water detection" is claimed.**
2. **n = 14, one season, one AOI, no ground truth.** No accuracy percentage is
   claimed for any signal.
3. **This is the seasonal flood phase (weeks long), not an AWD event.** The
   12-day repeat (max gap 24) **will miss 5–10-day AWD drydowns** entirely.
4. **AWD may be unmeasurable at AOI scale.** Hundreds of parcels draining out of
   sync would cancel in a whole-AOI mean. Real AWD detection needs **per-parcel**
   analysis — out of current scope, stated plainly.
5. **AOI-level speckle filtering is near-negligible** (~20,300 pixels already
   suppress speckle in the mean); it is future-proofing for per-parcel work.

## 7. Conclusion

On this AOI's own measurements: **SAR solves the year-round coverage problem** —
proven, with the rainy season (optical 0) now covered by 5 scenes and the dry
season doubled (7 → 14). **SAR does not yet solve AWD-event detection**, which is
sub-monthly and would need per-parcel granularity and multi-orbit density —
beyond this project's scope. The work concludes here as a **technical portfolio
piece**, not a commercial product (see the README for why).
