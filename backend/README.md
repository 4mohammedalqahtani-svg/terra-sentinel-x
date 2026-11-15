# backend/ — Backend & Integration (role 4)

Turns everyone's outputs into one published run the website can load, checks
them against [`schema/`](../schema/README.md), and deploys the site.

No server is needed in production: outputs are **static files** served by
GitHub Pages next to the frontend.

## Quick start

```bash
pip install -r backend/requirements.txt
python backend/make_demo.py      # synthetic demo run (already committed)
python backend/serve.py          # http://localhost:8000
```

`serve.py` shows `frontend/` once `frontend/index.html` exists, otherwise the
integration preview in `backend/preview/` (slider, Reveal Changes, Evidence
Card, Smart Doubt on the demo data).

## How the website reads the data

Same URLs locally (`serve.py`) and on GitHub Pages (`build_site.py`):

```
data/runs.json                    list of runs + which one opens first ("default")
data/<run_id>/run.json            metadata, bounds, file names (schema/run.schema.json)
data/<run_id>/before.png          greyscale backscatter, stretched -25..0 dB
data/<run_id>/after.png           same stretch, same grid as before.png
data/<run_id>/change_map.png      RGBA overlay, transparent where nothing changed
data/<run_id>/doubt_map.png       optional Smart Doubt overlay
data/<run_id>/changes.geojson     polygons + evidence + reliability (schema/changes.schema.json)
```

All PNGs cover exactly `run.bounds` = `[west, south, east, north]` (EPSG:4326),
so in Leaflet: `L.imageOverlay(png, [[south, west], [north, east]])`.
File names inside `run.json` are relative to that `run.json`.
See `loadRun()` in [`preview/index.html`](preview/index.html) for a working example.

## Publishing a real run

**Option A — run the chain.** Each role's entry script is listed in
[`pipeline.json`](pipeline.json). Stages whose script doesn't exist yet are skipped.

```bash
python backend/pipeline.py --run-id riyadh-2026-11 --aoi "Riyadh, Saudi Arabia" \
    --before-id <scene> --before-date 2026-10-20 --after-id <scene> --after-date 2026-11-01 --polarization HH
```

**Option B — collect finished files** (e.g. a teammate shares a folder):

```bash
python backend/pipeline.py --run-id riyadh-2026-11 --aoi "Riyadh, Saudi Arabia" --collect path/to/folder
```

The folder needs `before.tif`, `after.tif` (any CRS; dB or linear power) and
`changes.geojson`; optionally `change_map.tif|png`, `doubt_map.tif|png` and a
`meta.json` holding part of `run.json` (scene ids, dates, method). GeoTIFFs are
reprojected to EPSG:4326 and turned into PNGs on one shared grid. A real run
becomes the default automatically over the demo.

Then commit `backend/outputs/<run_id>/` and open a PR. GeoTIFFs are never
committed; only the small web files are.

## How the Chokwe run (`chokwe-2026-01`) was built

Inputs (not in git, shared by the team as zips): role 2's `before.tif`,
`after.tif`, `meta.json` (HH, dB, EPSG:32736) and role 1's `results_v2/`
from `algorithm/flood_detection_v2.py`.

```bash
W=backend/work/chokwe-2026-01 && mkdir -p $W
cp <data>/before.tif <data>/after.tif $W/
cp <results_v2>/candidate_joint_HH_HV.tif $W/change_map.tif
cp <results_v2>/smart_doubt_stability.tif $W/doubt_map.tif
# meta.json = data meta + method, status, limitations (evidence_v2.json) + validation (copernicus_spatial_comparison.json)
python backend/vectorize.py --candidate $W/change_map.tif --before $W/before.tif --after $W/after.tif \
    --stability $W/doubt_map.tif --change-hv <results_v2>/change_HV_db.tif \
    --run-id chokwe-2026-01 --simplify-m 60 --out $W/changes.geojson
python backend/pipeline.py --run-id chokwe-2026-01 --collect $W
```

`vectorize.py` turns the candidate raster into one polygon per connected area
(>= 25 pixels = 0.09 km2), with mean before/after HH dB and HV change as
evidence, and Smart Doubt from the stability raster:
`confidence` = share of the area passing all 3 thresholds, `doubt_level` low
(>= 75%), medium (>= 40%), high (< 40%). `likely_flood` = low doubt and mean
after-HH <= -15 dB; everything else stays `possible_flood`.

## Stage contract (for roles 1, 2, 5, 6)

| Stage | Script (change in `pipeline.json`) | Reads | Writes into `{work}` |
|---|---|---|---|
| data (2) | `data/prepare.py --out {work}` | ASF / Earthdata | `before.tif`, `after.tif`, optional `meta.json` |
| sar (5) | `sar/process.py --before … --after … --out {work}` | `before.tif`, `after.tif` | calibrated + filtered `before.tif`, `after.tif` (overwrite) |
| algorithm (1) | `algorithm/detect.py --before … --after … --out {work}` | the two rasters | `changes.geojson`, `change_map.tif` |
| validation (6) | `validation/smart_doubt.py --before … --after … --changes … --out {work}` | rasters + `changes.geojson` | `changes.geojson` with `reliability` filled, optional `doubt_map.tif` |

## Scripts

| File | What it does |
|---|---|
| `validate.py` | Checks run folders / GeoJSON against `schema/` (`--all` for every run). Used by CI on every PR. |
| `pipeline.py` | Runs or collects a run and publishes it to `outputs/<run_id>/`. |
| `vectorize.py` | Candidate raster + before/after + stability -> `changes.geojson`. |
| `make_demo.py` | Writes the synthetic `demo-synthetic` run. |
| `serve.py` | Local dev server, same layout as the public site. |
| `build_site.py` | Builds `_site/` for GitHub Pages. |
| `pipeline.json` | Stage commands. |

## Deployment

`.github/workflows/pages.yml` validates outputs on every PR, and on every push
to `main` builds `_site/` and deploys it to GitHub Pages:
**https://4mohammedalqahtani-svg.github.io/terra-sentinel-x/**

One-time setup (repo owner): *Settings → Pages → Build and deployment → Source: GitHub Actions*.
