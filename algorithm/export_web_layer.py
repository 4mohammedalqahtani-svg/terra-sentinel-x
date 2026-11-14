"""TERRA-SENTINEL X: export NISAR detection and Smart Doubt layers for web maps.

Windows CMD from C:\\Users\\Bassma\\NASA_NISAR:
    conda run -n nisar2 python export_web_layer.py

Requires two rasters created by flood_detection_v2.py:
  results_v2/candidate_joint_HH_HV.tif  (0 background, 1 candidate, 255 invalid)
  results_v2/smart_doubt_stability.tif (0-3 tested-threshold count, 255 invalid)

Exports transparent north-up PNGs on EPSG:4326 and Leaflet imageOverlay
bounds. This is a preliminary change-detection visualization, not a validated
flood footprint or an early-warning product.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "results_v2"
TARGET = ROOT / "web_assets"
CANDIDATES = SOURCE / "candidate_joint_HH_HV.tif"
STABILITY = SOURCE / "smart_doubt_stability.tif"
DEST_CRS = "EPSG:4326"


def read_raster(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {path}")
    with rasterio.open(path) as ds:
        if ds.count != 1:
            raise ValueError(f"Expected one band in {path.name}; got {ds.count}")
        if ds.crs is None:
            raise ValueError(f"No CRS in {path.name}")
        return ds.read(1), ds.crs, ds.transform, ds.bounds, ds.nodata


def main():
    cand, crs, affine, bounds, nodata = read_raster(CANDIDATES)
    stability, crs_s, affine_s, bounds_s, nodata_s = read_raster(STABILITY)
    if (cand.shape != stability.shape or crs != crs_s or
            not affine.almost_equals(affine_s)):
        raise ValueError("Detection and stability rasters are not on the same grid")
    if not set(np.unique(cand)).issubset({0, 1, 255}):
        raise ValueError("Unexpected candidate class values; inspect the GeoTIFF before exporting")
    if not set(np.unique(stability)).issubset({0, 1, 2, 3, 255}):
        raise ValueError("Unexpected Smart Doubt values; inspect the GeoTIFF")

    height, width = cand.shape
    geo_transform, w, h = calculate_default_transform(
        crs, DEST_CRS, width, height, *bounds
    )

    def warped(array, source_nodata):
        out = np.full((h, w), 255, dtype=np.uint8)
        reproject(
            source=array, destination=out,
            src_transform=affine, src_crs=crs,
            src_nodata=source_nodata if source_nodata is not None else 255,
            dst_transform=geo_transform, dst_crs=DEST_CRS,
            dst_nodata=255,
            resampling=Resampling.nearest,
        )
        return out

    ca = warped(cand, nodata)
    st = warped(stability, nodata_s)
    TARGET.mkdir(exist_ok=True, parents=True)

    image = np.zeros((h, w, 4), dtype=np.uint8)
    image[ca == 1] = [255, 185, 0, 190]  # yellow - candidate only
    Image.fromarray(image, "RGBA").save(TARGET / "flood_candidates_overlay.png", optimize=True)

    stability_image = np.zeros((h, w, 4), dtype=np.uint8)
    stability_image[st == 1] = [255, 210, 60, 155]  # passes relaxed only
    stability_image[st == 2] = [255, 115, 50, 185]  # passes two thresholds
    stability_image[st == 3] = [195, 38, 120, 210]  # passes all three
    Image.fromarray(stability_image, "RGBA").save(TARGET / "smart_doubt_overlay.png", optimize=True)

    left = geo_transform.c
    top = geo_transform.f
    right = left + geo_transform.a * w
    bottom = top + geo_transform.e * h
    metadata = {
        "project": "TERRA-SENTINEL X",
        "site": "Chokwe, Gaza, Mozambique",
        "source": "NISAR GCOV BETA (HH+HV), 2026-01-05 and 2026-01-17",
        "coordinate_system": DEST_CRS,
        "leaflet_bounds": [[float(bottom), float(left)], [float(top), float(right)]],
        "image_size_pixels": {"width": w, "height": h},
        "assets": {
            "flood_candidates": "flood_candidates_overlay.png",
            "smart_doubt": "smart_doubt_overlay.png",
        },
        "legend": {
            "flood_candidates": "Yellow: radar darkening consistent with possible water-related change",
            "smart_doubt": {
                "yellow": "passed relaxed threshold only",
                "orange": "passed relaxed and baseline thresholds",
                "magenta": "passed all three thresholds",
            },
        },
        "limitations": (
            "Not confirmed flood extent; NISAR BETA observations are uncalibrated "
            "for this purpose; Smart Doubt measures threshold sensitivity, not "
            "probability or accuracy. Copernicus validation layer is 10 days later."
        ),
    }
    (TARGET / "overlay_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SUCCESS: web overlay files created")
    for filename in ("flood_candidates_overlay.png", "smart_doubt_overlay.png", "overlay_metadata.json"):
        print("  ", TARGET / filename)
    print("Leaflet bounds (south/west, north/east):", metadata["leaflet_bounds"])
    print("CAUTION: possible water-related change, not verified flood extent")


if __name__ == "__main__":
    main()
