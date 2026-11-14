# Shared output schema

Every role exchanges results in these formats.

| File | Format | Produced by | Used by |
|---|---|---|---|
| `before.tif`, `after.tif` | GeoTIFF (float32, dB, same CRS/grid) | data/ + sar/ | algorithm/, frontend previews |
| `before.png`, `after.png` | PNG + `bounds` in `run.json` | data/ | frontend slider |
| `change_map.tif` / `change_map.png` | GeoTIFF / PNG overlay | algorithm/ | frontend Reveal Changes |
| `changes.geojson` | GeoJSON FeatureCollection, EPSG:4326 | algorithm/ + validation/ | frontend Evidence Card & Smart Doubt |
| `run.json` | JSON metadata | backend/ | frontend |

- Coordinates: **EPSG:4326 (lon, lat)** for GeoJSON and bounds.
- Backscatter values in **dB**.
- `confidence` is 0–1; `doubt_level` is `low` | `medium` | `high` (high = needs review).

See `changes.example.geojson` and `run.example.json`.
