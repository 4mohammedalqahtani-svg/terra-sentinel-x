# data/ — NISAR Data Engineer (role 2)
- Find two compatible NISAR acquisitions (same track/frame, geometry, polarisation, product level) before and after a flood event.
- Download, co-register and clip them to the same grid/CRS.
- Output: `processed/before.tif`, `processed/after.tif` (+ small PNG previews in `samples/`), and fill `docs/DATA_SOURCES.md`.
- Raw and processed rasters are git-ignored; share large files by link.

## Delivered (issue #1)

Event: January 2026 Limpopo flood, Chókwè, Mozambique. Scenes, IDs and quality: [`docs/DATA_SOURCES.md`](../docs/DATA_SOURCES.md) and [`scenes_provenance.json`](scenes_provenance.json).

**GeoTIFFs (shared by link, not in git):** `before.tif`, `after.tif`, `control.tif`
→ **Get it:** `terra_sentinel_data.zip`, shared by Ali in the team WhatsApp group → unzip into `data/processed/`

| File | Content |
|---|---|
| `before.tif`, `after.tif` | HH backscatter in **dB**, float32, single band, EPSG:32736, 60 m, 1093×620, identical grid, nodata −9999 |
| `control.tif` | Same, for the extra pre-flood scene (24 Dec 2025), used for false-alarm checks |

**In git, `samples/`:**

| File | Content |
|---|---|
| `before.png`, `after.png`, `control.png` | Grey display previews in EPSG:4326, 1117×579, transparent edges, one shared dB stretch for all dates |
| `bounds.json` | PNG bounds as `[west, south, east, north]` (schema order) **and** in Leaflet order, plus scene IDs/dates |

The PNG previews use exactly the same bounds and pixel size as the algorithm overlays, so before/after/change layers line up pixel for pixel (checked by `check_alignment.py`: PASS).

## Pipeline stage
`backend/pipeline.py` runs `python data/prepare.py --out {work}`. It copies `processed/before.tif` and `processed/after.tif` (dB, from the shared zip) into the work folder and writes `meta.json` (AOI, event, scene ids, dates, HH, GCOV, track/frame 114/165). Add `--with-control` to also copy `control.tif`.

## Scripts (`scripts/`)

Run in a conda env: `conda create -n nisar2 -c conda-forge python=3.11 gdal libgdal-hdf5 rasterio numpy scipy matplotlib pillow`.
Earthdata credentials go in `~/.netrc` (never commit it). The scripts expect a working folder with `data/` (GeoTIFFs) and `web_assets/` next to them.

| Script | What it does |
|---|---|
| `nisar_extract_v4.py` | Reads only the AOI from the remote NISAR HDF5 (GDAL `/vsicurl`), georeferences it from the product's own coordinate arrays, clips to the AOI at 60 m. Grid-locked to the first extracted scene so every date is pixel-aligned. `python nisar_extract_v4.py control --layer all` |
| `export_before_after.py` | PNG previews in EPSG:4326 on the same grid as the web overlays + `before_after_metadata.json` |
| `make_schema_outputs.py` | Writes the `schema/` files (dB GeoTIFFs, PNGs, `bounds.json`) |
| `check_alignment.py` | Numeric check that all rasters and PNGs share one grid / bounds / size |

## Notes for other roles
- **sar/ (5):** native GCOV spacing is 10 m; the 60 m grid uses nearest-neighbour (`near`), which keeps 1 of 36 pixels. Averaging (`average`) would reduce speckle; extraction can be re-run if you recommend it.
- **validation/ (6):** `control.tif` (24 Dec) + `before.tif` (5 Jan) form a no-flood control pair for estimating false alarms.
- Frame-wide HH rose ~+3 dB between 5 and 17 Jan (stable before that); likely wet soil after rain, calibration difference not excluded (BETA).

## Software used in data/
| Library | Used for | Licence |
|---|---|---|
| GDAL 3.12 (+ libgdal-hdf5) | Remote HDF5 read (/vsicurl), clipping, reprojection | MIT |
| rasterio | GeoTIFF I/O | BSD-3-Clause |
| NumPy | Array processing | BSD-3-Clause |
| Pillow | PNG previews | MIT-CMU (HPND) |
