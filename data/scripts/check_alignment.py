"""TERRA-SENTINEL X | Geographic alignment check (NISAR Data Engineer).

Checks, with numbers only, that every data file and every web image is on the
same grid, so before/after/control and the flood layers line up exactly.

Run from the project folder (activated nisar2 environment):
    python check_alignment.py

Writes alignment_report.json and prints PASS/FAIL for each check.
"""
from __future__ import annotations

import json
from pathlib import Path

import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA, WEB = ROOT / "data", ROOT / "web_assets"
TOL_DEG = 1e-9  # bounds must agree to ~0.1 mm


def main() -> None:
    checks = []

    def record(name, ok, detail):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # 1. All GeoTIFFs in data/ share CRS, transform and size.
    tifs = sorted(DATA.glob("*.tif"))
    grids = {}
    for p in tifs:
        with rasterio.open(p) as ds:
            grids[p.name] = (str(ds.crs), tuple(round(v, 6) for v in ds.transform[:6]), ds.width, ds.height)
    ref = grids.get("before_HH.tif")
    bad = [n for n, g in grids.items() if g != ref]
    record("data GeoTIFFs on one grid", ref is not None and not bad,
           f"{len(grids)} files; reference before_HH.tif {ref[2]}x{ref[3]} {ref[0]}" + (f"; mismatched: {bad}" if bad else ""))

    # 2. Display images match the overlay grid (size + bounds).
    ov = json.loads((WEB / "overlay_metadata.json").read_text(encoding="utf-8"))
    ba_path = WEB / "before_after_metadata.json"
    if not ba_path.is_file():
        record("before/after metadata present", False, "run export_before_after.py first")
    else:
        ba = json.loads(ba_path.read_text(encoding="utf-8"))
        same_bounds = all(abs(a - b) <= TOL_DEG for pa, pb in zip(ov["leaflet_bounds"], ba["leaflet_bounds"]) for a, b in zip(pa, pb))
        record("before/after bounds == overlay bounds", same_bounds, f"{ba['leaflet_bounds']}")
        same_size = ov["image_size_pixels"] == ba["image_size_pixels"]
        record("before/after size == overlay size", same_size, f"{ba['image_size_pixels']}")

        expected = (ov["image_size_pixels"]["width"], ov["image_size_pixels"]["height"])
        pngs = [ov["assets"]["flood_candidates"], ov["assets"]["smart_doubt"]] + [v["file"] for v in ba["images"].values()]
        sizes = {}
        for f in pngs:
            with Image.open(WEB / f) as im:
                sizes[f] = im.size
        wrong = {f: s for f, s in sizes.items() if s != expected}
        record("all web PNGs have identical pixel size", not wrong,
               f"{len(sizes)} images at {expected[0]}x{expected[1]}" + (f"; wrong: {wrong}" if wrong else ""))

    overall = all(c["result"] == "PASS" for c in checks)
    report = {"project": "TERRA-SENTINEL X", "overall": "PASS" if overall else "FAIL", "checks": checks}
    (ROOT / "alignment_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nOVERALL: {report['overall']}  (saved alignment_report.json)")


if __name__ == "__main__":
    main()
