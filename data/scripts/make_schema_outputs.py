"""TERRA-SENTINEL X | Write role-2 outputs in the shared schema/ format.

Run from the working project folder (same layout as the other scripts:
data/*.tif + web_assets/*.png produced by nisar_extract_v4.py and
export_before_after.py), activated nisar2 environment:
    python make_schema_outputs.py

Creates samples/:
    before.tif, after.tif, control.tif   single-band float32 backscatter (HH, dB),
                                         EPSG:32736, 60 m, identical grid, nodata -9999
    before.png, after.png, control.png   display previews (EPSG:4326)
    bounds.json                          bounds [west, south, east, north] (schema order)
                                         + the same bounds in Leaflet order
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent
DATA, WEB, OUT = ROOT / "data", ROOT / "web_assets", ROOT / "samples"
NODATA = -9999.0


def main() -> None:
    OUT.mkdir(exist_ok=True)
    meta = json.loads((WEB / "before_after_metadata.json").read_text(encoding="utf-8"))
    for name in ("before", "after", "control"):
        hh, mask = DATA / f"{name}_HH.tif", DATA / f"{name}_mask.tif"
        if not hh.is_file():
            if name == "control":
                continue
            raise SystemExit(f"ERROR: missing {hh}")
        with rasterio.open(hh) as ds:
            power = ds.read(1).astype(np.float32)
            profile = ds.profile.copy()
        with rasterio.open(mask) as ds:
            m = ds.read(1)
        valid = (m > 0) & (m < 255) & np.isfinite(power) & (power > 0)
        db = np.full(power.shape, NODATA, dtype=np.float32)
        db[valid] = 10 * np.log10(power[valid])
        for k in ("photometric", "alpha", "blockxsize", "blockysize"):
            profile.pop(k, None)
        profile.update(driver="GTiff", count=1, dtype="float32", nodata=NODATA,
                       compress="deflate", predictor=3, tiled=True)
        with rasterio.open(OUT / f"{name}.tif", "w", **profile) as dst:
            dst.write(db, 1)
            dst.set_band_description(1, f"NISAR GCOV HH backscatter (dB), {meta['images'][name]['date']}")
        shutil.copy2(WEB / f"{name}_HH.png", OUT / f"{name}.png")
        print(f"samples/{name}.tif + samples/{name}.png")

    (south, west), (north, east) = meta["leaflet_bounds"]
    bounds = {
        "crs": "EPSG:4326",
        "bounds": [west, south, east, north],
        "bounds_order": "[west, south, east, north] (schema/run.json order)",
        "leaflet_bounds": [[south, west], [north, east]],
        "png_size_pixels": meta["image_size_pixels"],
        "same_bounds_as": "algorithm overlays (flood_candidates_overlay.png, smart_doubt_overlay.png)",
        "scenes": {k: {"scene_id": v["granule_id"], "date": v["date"], "png": f"{k}.png", "geotiff": f"{k}.tif"}
                   for k, v in meta["images"].items() if (OUT / f"{k}.png").is_file()},
        "geotiff_grid": {"crs": "EPSG:32736", "pixel_size_m": 60, "units": "dB (10*log10 HH power)", "nodata": NODATA},
    }
    (OUT / "bounds.json").write_text(json.dumps(bounds, indent=2), encoding="utf-8")
    print("samples/bounds.json")


if __name__ == "__main__":
    main()
