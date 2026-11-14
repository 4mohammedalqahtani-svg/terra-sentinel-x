# Data sources, references and licences

| Source | What we use | Link | Licence / terms |
|---|---|---|---|
| NISAR (NASA-ISRO SAR) | Before/after radar scenes | https://search.asf.alaska.edu/ | NASA open data policy |
| NASA Earthdata | Data access & documentation | https://www.earthdata.nasa.gov/ | NASA open data policy |
| Copernicus Emergency Management Service, EMSR857 AOI11 (Grading Monitoring 1, 2026-01-27) | Independent flood reference for exploratory comparison | https://emergency.copernicus.eu/ | Copernicus EMS terms (free, attribution required) |
| _Optical imagery for Radar vs. Clouds_ | TBD | TBD | TBD |
| _Land-cover / farmland layer for Impact Lens_ | TBD | TBD | TBD |

## Selected scene pair
- Event / location: Limpopo River flood, January 2026 · Chokwe, Gaza Province, Mozambique
- Before: `NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001` (2026-01-05)
- After: `NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001` (2026-01-17)
- Control (extra pre-flood scene): 2025-12-24
- Product level, polarisation, track/frame: L2 GCOV BETA V1, HH + HV, track 114 / frame 165, ascending
- Grid: EPSG:32736, 60 m, 1093 x 620 pixels (see `data/meta.chokwe.json`)

## References
- Challenge page: https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/

## Software
List libraries used and their licences here (e.g. rasterio, numpy, Leaflet/MapLibre).

| Library / service | Used in | Licence |
|---|---|---|
| numpy | backend/ | BSD-3-Clause |
| Pillow | backend/ | MIT-CMU (HPND) |
| rasterio | backend/ | BSD-3-Clause |
| jsonschema | backend/ (validation) | MIT |
| scipy | backend/vectorize.py | BSD-3-Clause |
| shapely | backend/vectorize.py | BSD-3-Clause |
| GDAL | data/nisar_extract_v3.py | MIT |
| matplotlib | algorithm/, validation/ figures | PSF-based (matplotlib licence) |
| Leaflet 1.9 | backend/preview | BSD-2-Clause |
| OpenStreetMap tiles | backend/preview basemap | ODbL (data), OSM tile usage policy |
