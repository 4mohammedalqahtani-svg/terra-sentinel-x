# data/ — NISAR Data Engineer (role 2)
- Find two compatible NISAR acquisitions (same track/frame, geometry, polarisation, product level) before and after a flood event.
- Download, co-register and clip them to the same grid/CRS.
- Output: `processed/before.tif`, `processed/after.tif` (+ small PNG previews in `samples/`), and fill `docs/DATA_SOURCES.md`.
- Raw and processed rasters are git-ignored; share large files by link.
