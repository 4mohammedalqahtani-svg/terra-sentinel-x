#!/usr/bin/env python3
"""TERRA-SENTINEL X | data/ stage for backend/pipeline.py (role 2, NISAR Data Engineer).

    python data/prepare.py --out <work>

Writes into <work>:
    before.tif, after.tif   HH backscatter in dB, float32, EPSG:32736, 60 m, same grid, nodata -9999
    meta.json               partial run.json: AOI, event, scene ids, dates, polarisation, product, track/frame

GeoTIFFs are not committed to git (team rule). Download the shared data zip
(shared in the team WhatsApp group, see data/README.md) and unzip it into data/processed/, or point --src at
the folder that holds before.tif / after.tif.
Use --with-control to also copy the pre-flood control scene (control.tif).
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SAMPLES = HERE / "samples"          # bounds.json + PNG previews (committed)
DEFAULT_SRC = HERE / "processed"     # GeoTIFFs (git-ignored, shared by link)


def scene(name: str, info: dict) -> dict:
    return {
        "scene_id": info["scene_id"],
        "date": info["date"],
        "polarization": "HH",
        "product": "GCOV",
        "track_frame": "114/165",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", required=True, help="pipeline work folder")
    p.add_argument("--src", default=str(DEFAULT_SRC), help="folder with before.tif / after.tif (default data/processed)")
    p.add_argument("--with-control", action="store_true", help="also copy control.tif (24 Dec 2025)")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bounds = json.loads((SAMPLES / "bounds.json").read_text(encoding="utf-8"))
    names = ["before", "after"] + (["control"] if args.with_control else [])
    for name in names:
        src = Path(args.src) / f"{name}.tif"
        if not src.is_file() and args.src == str(DEFAULT_SRC):
            src = SAMPLES / f"{name}.tif"  # committed copy in data/samples/
        if not src.is_file():
            raise SystemExit(f"[data] missing {src}: download the data zip (shared in the team WhatsApp group, see data/README.md) into data/processed/")
        shutil.copy2(src, out / f"{name}.tif")
        print(f"[data] {name}.tif -> {out}")

    meta = {
        "aoi_name": "Chokwe, Gaza Province, Mozambique",
        "event": "Limpopo River flood, January 2026",
        "before": scene("before", bounds["scenes"]["before"]),
        "after": scene("after", bounds["scenes"]["after"]),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[data] meta.json -> {out}")


if __name__ == "__main__":
    main()
