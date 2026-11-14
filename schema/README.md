# Shared output schema

Every role exchanges results in these formats.

| File | Format | Produced by | Used by |
|---|---|---|---|
| `before.tif`, `after.tif` | GeoTIFF (float32, dB, same CRS/grid) | data/ + sar/ | algorithm/, frontend previews |
| `before.png`, `after.png` | PNG + `bounds` in `run.json` | data/ | frontend slider |
| `change_map.tif` / `change_map.png` | GeoTIFF / PNG overlay | algorithm/ | frontend Reveal Changes |
| `changes.geojson` | GeoJSON FeatureCollection, EPSG:4326 | algorithm/ + validation/ | frontend Evidence Card & Smart Doubt |
| `doubt_map.tif` / `doubt_map.png` | GeoTIFF / PNG overlay (optional) | validation/ | frontend Smart Doubt |
| `run.json` | JSON metadata | backend/ | frontend |
| `runs.json` | Index of published runs | backend/ | frontend run picker |

- Coordinates: **EPSG:4326 (lon, lat)** for GeoJSON and bounds.
- Backscatter values in **dB**.
- `confidence` is 0–1; `doubt_level` is `low` | `medium` | `high` (high = needs review).

- `change_type` is `likely_flood` | `possible_flood` | `other_change`.
- `delta_db` = `after_backscatter_db - before_backscatter_db` (negative = darker = possible water).
- `run.json` with `"demo": true` is synthetic data; the site must show a banner.

Machine-readable versions: [`run.schema.json`](run.schema.json) and
[`changes.schema.json`](changes.schema.json) (JSON Schema 2020-12).
Check your files before opening a PR:

```bash
python backend/validate.py path/to/changes.geojson     # one file
python backend/validate.py backend/outputs/<run_id>    # a whole run
```

See `changes.example.geojson` and `run.example.json`, and a full working run in
[`backend/outputs/demo-synthetic/`](../backend/outputs/demo-synthetic/).
How the website loads these files: [`backend/README.md`](../backend/README.md).
