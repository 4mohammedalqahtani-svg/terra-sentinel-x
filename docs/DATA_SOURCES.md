# Data sources, references and licences

| Source | What we use | Link | Licence / terms |
|---|---|---|---|
| NISAR (NASA-ISRO SAR) | Before/after radar scenes | https://search.asf.alaska.edu/ | NASA open data policy |
| NASA Earthdata | Data access & documentation | https://www.earthdata.nasa.gov/ | NASA open data policy |
| _Optical imagery for Radar vs. Clouds_ | TBD | TBD | TBD |
| _Land-cover / farmland layer for Impact Lens_ | TBD | TBD | TBD |

## Selected scene pair
- **Event / location:** January 2026 Limpopo River flood, Chókwè, Gaza Province, Mozambique
- **AOI (EPSG:4326):** `POLYGON((32.6656 -24.735, 33.3124 -24.735, 33.3124 -24.399, 32.6656 -24.399, 32.6656 -24.735))`
- **Product:** NISAR L2 GCOV BETA V1 (`10.5067/NIL2GCOV-B1`), frequency A (L-band, 1.239 GHz, 40 MHz), dual-pol DHDH (HHHH + HVHV), native 10 m, EPSG:32736, radiometric terrain corrected
- **Geometry:** track 114, frame 165, ascending, left-looking, 12-day repeat, all acquired at ~03:42 UTC, all processed with GCOV_L_PGE R05.00.8

| Role | Date | Scene ID | Cycle | Abs. orbit |
|---|---|---|---|---|
| Control (pre-flood) | 2025-12-24 | `NISAR_L2_PR_GCOV_008_114_A_165_4005_DHDH_A_20251224T034231_20251224T034253_X05010_N_P_J_001` | 008 | 2116 |
| **Before** | 2026-01-05 | `NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001` | 009 | 2289 |
| **After** | 2026-01-17 | `NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001` | 010 | 2462 |

- **Quality (ASF QA summary, all three scenes):** pixel-level checks PASS; `identification` metadata check FAIL (metadata fields only). Orbit type MOE.
- **Frame-wide mean HH change (from ISO metadata):** 24 Dec→5 Jan −0.82 dB (stable), 5 Jan→17 Jan +3.07 dB.
- **No acquisition on 29 Jan 2026** for this track/frame, so the Copernicus EMSR857 reference (27 Jan) stays 10 days after the "after" scene.
- **Limitations:** BETA, uncalibrated, not validated for flood mapping.
- Full per-scene record: [`data/scenes_provenance.json`](../data/scenes_provenance.json)

| Source | What we use | Link | Licence / terms |
|---|---|---|---|
| NISAR L2 GCOV BETA V1 (NASA JPL, distributed by ASF DAAC) | Control / before / after scenes | https://doi.org/10.5067/NIL2GCOV-B1 | CC0-1.0 |
| NISAR DEM v1.2 (from Copernicus DEM 30 m) | Used by JPL inside GCOV processing | https://doi.org/10.5067/NIDEM-1 | Copernicus DEM licence |
| Copernicus EMS EMSR857, AOI 11, Grading Monitoring 1 (27 Jan 2026) | Independent spatial comparison (algorithm/validation) | https://emergency.copernicus.eu/ | Copernicus EMS terms |

## References
- Challenge page: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/

## Software
List libraries used and their licences here (e.g. rasterio, numpy, Leaflet/MapLibre).
