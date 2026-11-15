# Validation report — TERRA-SENTINEL X (role 6)

**Run:** `chokwe-2026-01` · Limpopo River flood, Chókwè, Mozambique · NISAR L2 GCOV BETA, before 2026-01-05, after 2026-01-17
**Status:** exploratory, not validated. Every number below describes how the method behaves; none of them is a flood-mapping accuracy.

## Summary

| Check | Result | What it tells us |
|---|---|---|
| Threshold sensitivity (Smart Doubt) | 72.3% of baseline candidate pixels survive the strictest thresholds | Most detected change is a strong signal, not a borderline one |
| Per-area reliability | 54 low / 94 medium / 32 high doubt; low-doubt areas = 69.8% of mapped area | The large floodplain areas are stable; the uncertain ones are small (2.1% of area) |
| Control pair (no flood) | 2,106 px (7.58 km²) vs 59,023 px (212.48 km²) for the event: **28× more change in the flood window**. At map level: 9 areas (1.01 km²) vs 180 areas (195.54 km²) | The signal is far above the method's own background false-alarm level |
| Copernicus EMS EMSR857 | 60.0% of reference flooded pixels overlap NISAR candidates; 47.0% of NISAR candidates overlap the reference | Spatially consistent, but over a small common area (6.7 km²) and with a 10-day date gap |

## 1. Threshold sensitivity (Smart Doubt)

Source: `algorithm/flood_detection_v2.py` → `algorithm/results_v2/evidence_v2.json`, `smart_doubt_stability.tif`.

The detector flags pixels where HH and HV backscatter both drop, the after-image is dark (≤ scene 40th percentile of HH) and the before-image was not already very dark (≥ scene 15th percentile); groups smaller than 9 pixels are removed. It is re-run with three threshold pairs:

| Test | HH drop | HV drop | Candidate pixels |
|---|---|---|---|
| Relaxed | ≥ 2 dB | ≥ 0.5 dB | 75,809 |
| **Baseline** | ≥ 3 dB | ≥ 1.5 dB | **59,023** (212.48 km²) |
| Strict | ≥ 4 dB | ≥ 2.5 dB | 42,675 |

Strict ÷ baseline = **72.3%**. Each pixel's stability (0–3 = number of tests it passes) is stored in `smart_doubt_stability.tif`; this is the **stability map**, shown on the website as `doubt_map.png`.

## 2. Reliability per change area

Source: `backend/vectorize.py` → `backend/outputs/chokwe-2026-01/changes.geojson` (180 areas of ≥ 25 pixels, 195.55 km²).

For each area:
- `confidence` = share of the area's pixels that pass all three tests
- `stable_across_thresholds` = mean stability ÷ 3
- `doubt_level`: **low** if confidence ≥ 0.75, **medium** if ≥ 0.40, otherwise **high**
- `change_type` = `likely_flood` when doubt is low **and** mean after-backscatter ≤ −15 dB (open-water-like); otherwise `possible_flood`

| Doubt level | Areas | Area (km²) | Share of area |
|---|---|---|---|
| Low | 54 | 136.54 | 69.8% |
| Medium | 94 | 54.83 | 28.0% |
| High (needs review) | 32 | 4.17 | 2.1% |

All 54 low-doubt areas are also `likely_flood`. "Confidence" here means **threshold agreement**, not a calibrated probability.

## 3. Control pair: false-alarm level

Script: `validation/control_pair_check.py` → `validation/results/control_pair_summary.json`, `control_vs_event.png`.

The same algorithm, unchanged, is run on two **pre-flood** acquisitions, 2025-12-24 → 2026-01-05 (same track 114 / frame 165, data in `validation/samples/`). The area was stable then: ASF browse images match and frame-wide HH changed only −0.8 dB (vs +3.1 dB in the flood window). Anything flagged is a false alarm of the method.

| | Control (no flood) | Event | Ratio |
|---|---|---|---|
| Candidate pixels | 2,106 (0.31% of valid) | 59,023 | 28× |
| Area | 7.58 km² | 212.48 km² | |
| Map areas ≥ 25 px | 9 (1.01 km²) | 180 (195.54 km²) | ~194× by area |
| Smart Doubt strict ÷ baseline | 11.6% | 72.3% | |

- Control false alarms are scattered specks; event candidates follow the Limpopo floodplain (`control_vs_event.png`).
- Only 0.46% of event candidate pixels were also flagged in the control pair.
- Control false alarms are **unstable** (11.6% survive the strict test vs 72.3% for the event), so Smart Doubt marks most of them as doubtful. This supports using Smart Doubt as a review filter.

## 4. Independent reference: Copernicus EMS EMSR857

Script: `validation/compare_copernicus.py` → `algorithm/results_v2/copernicus_spatial_comparison.json`, `copernicus_overlay.png`. Re-running it needs the EMSR857 shapefiles from Copernicus EMS (not in the repo).

Reference: EMSR857, AOI 11 (Barragem de Macarretane), Grading Monitoring 1, 2026-01-27, `observedEventA`, "Flooded area" only (flood trace excluded). Rasterised to the NISAR grid; only pixels both datasets cover are compared.

| Metric | Value |
|---|---|
| Common analysed pixels | 1,865 (6.7 km²) |
| Reference flooded pixels | 290 |
| NISAR candidate pixels | 370 |
| Overlap | 174 pixels (0.63 km²) |
| Reference covered by NISAR | **60.0%** |
| NISAR inside reference | **47.0%** |

This is **exploratory spatial agreement, not accuracy**: the reference is 10 days after the NISAR after-image, water moves in that time, and the common area is small. No NISAR acquisition exists on 2026-01-29 for this track/frame, so the gap cannot be closed with this data.

## 5. Limitations

1. Results are **candidate water-related changes**, not confirmed floods.
2. NISAR GCOV BETA data are not yet independently validated for this use.
3. All thresholds are heuristic and scene-relative (percentiles recomputed per pair).
4. Low backscatter can also come from wet soil, harvested or flattened fields, or smooth surfaces.
5. HH+HV joint darkening can miss flooding under vegetation, where double-bounce makes backscatter brighter.
6. The 60 m grid uses nearest-neighbour resampling of 10 m data (no speckle averaging); see `sar/`.
7. Only one partial independent reference, 10 days later, over 6.7 km².
8. Smart Doubt measures threshold agreement only; it is not a probability or model confidence.
9. No forecast is produced.

## Note for backend

`run.json` lists the limitation "No independent ground/optical flood reference has been used yet", while its `validation` block reports the Copernicus comparison. Suggested wording: *"Only one exploratory comparison with Copernicus EMS (10 days later, small common area); no validated reference."*
