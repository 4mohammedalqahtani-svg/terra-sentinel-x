"""TERRA-SENTINEL X | Before/After display images (NISAR Data Engineer).

Turns the NISAR HH GeoTIFFs in data/ into grayscale PNG display images on the
SAME EPSG:4326 grid as Basma's web overlays (web_assets/overlay_metadata.json),
so before, after and the flood layer line up pixel for pixel.

Run from the project folder (activated nisar2 environment):
    python export_before_after.py

Writes to web_assets/:
    before_HH.png, after_HH.png, control_HH.png (if control data exists)
    before_after_metadata.json
Does not modify any existing file.

Display choices (documented in the JSON):
  * values shown in dB (10*log10 of HH power)
  * ONE shared grey stretch for all dates (2nd-98th percentile of all dates
    together), so brightness differences between images are real, not caused
    by per-image contrast
  * invalid / outside-AOI pixels are transparent
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
WEB = ROOT / "web_assets"
DEST_CRS = "EPSG:4326"
SCENES = {
    "control": ("2025-12-24", "NISAR_L2_PR_GCOV_008_114_A_165_4005_DHDH_A_20251224T034231_20251224T034253_X05010_N_P_J_001"),
    "before": ("2026-01-05", "NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001"),
    "after": ("2026-01-17", "NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001"),
}
STRETCH_PERCENTILES = (2, 98)


def load_db(name: str):
    hh, mask = DATA / f"{name}_HH.tif", DATA / f"{name}_mask.tif"
    if not hh.is_file() or not mask.is_file():
        return None
    with rasterio.open(hh) as ds:
        power = ds.read(1).astype(np.float32)
        grid = (ds.crs, ds.transform, ds.width, ds.height, ds.bounds)
    with rasterio.open(mask) as ds:
        m = ds.read(1)
    valid = (m > 0) & (m < 255) & np.isfinite(power) & (power > 0)
    db = np.full(power.shape, np.nan, dtype=np.float32)
    db[valid] = 10 * np.log10(power[valid])
    return db, grid


def main() -> None:
    loaded = {k: load_db(k) for k in SCENES}
    for required in ("before", "after"):
        if loaded[required] is None:
            raise SystemExit(f"ERROR: data/{required}_HH.tif or data/{required}_mask.tif is missing")
    present = {k: v for k, v in loaded.items() if v is not None}

    grids = {k: v[1][:4] for k, v in present.items()}
    if len(set(grids.values())) != 1:
        raise SystemExit(f"ERROR: input rasters are not on one grid: {list(grids)}")
    crs, transform, width, height, bounds = present["before"][1]

    # Same target grid as export_web_layer.py -> same size and bounds as the overlays.
    dst_transform, w, h = calculate_default_transform(crs, DEST_CRS, width, height, *bounds)

    all_valid = np.concatenate([v[0][np.isfinite(v[0])] for v in present.values()])
    lo, hi = (float(x) for x in np.percentile(all_valid, STRETCH_PERCENTILES))
    print(f"Shared stretch for all dates: {lo:.2f} dB (black) to {hi:.2f} dB (white)")

    WEB.mkdir(exist_ok=True)
    images = {}
    for name, (db, _) in present.items():
        out = np.full((h, w), np.nan, dtype=np.float32)
        reproject(source=db, destination=out, src_transform=transform, src_crs=crs,
                  src_nodata=np.nan, dst_transform=dst_transform, dst_crs=DEST_CRS,
                  dst_nodata=np.nan, resampling=Resampling.bilinear)
        ok = np.isfinite(out)
        grey = np.zeros((h, w), dtype=np.uint8)
        grey[ok] = np.clip((out[ok] - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
        alpha = np.where(ok, 255, 0).astype(np.uint8)
        fname = f"{name}_HH.png"
        Image.fromarray(np.dstack([grey, alpha]), "LA").save(WEB / fname, optimize=True)
        images[name] = {"file": fname, "date": SCENES[name][0], "granule_id": SCENES[name][1],
                        "valid_display_pixels": int(ok.sum())}
        print(f"Saved web_assets/{fname} ({w} x {h})")

    left, top = dst_transform.c, dst_transform.f
    right, bottom = left + dst_transform.a * w, top + dst_transform.e * h
    meta = {
        "project": "TERRA-SENTINEL X",
        "content": "NISAR L2 GCOV BETA HH backscatter display images (not analysis data)",
        "coordinate_system": DEST_CRS,
        "leaflet_bounds": [[float(bottom), float(left)], [float(top), float(right)]],
        "image_size_pixels": {"width": int(w), "height": int(h)},
        "same_grid_as": "overlay_metadata.json (flood_candidates_overlay.png, smart_doubt_overlay.png)",
        "images": images,
        "display": {
            "quantity": "HH backscatter in dB (10*log10 power)",
            "stretch_dB": {"black": round(lo, 2), "white": round(hi, 2),
                           "percentiles": list(STRETCH_PERCENTILES), "shared_across_dates": True},
            "interpretation": "Darker = lower radar return (smooth open water is typically dark)",
            "transparent": "invalid pixels and AOI border fill",
            "resampling_to_EPSG4326": "bilinear on dB values (display only)",
        },
        "source_grid": {"crs": str(crs), "pixel_size_m": abs(transform.a), "size": [width, height]},
        "provenance": "scenes_provenance.json",
    }
    (WEB / "before_after_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Saved web_assets/before_after_metadata.json")
    print("Leaflet bounds:", meta["leaflet_bounds"])


if __name__ == "__main__":
    main()
