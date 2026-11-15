#!/usr/bin/env python3
"""Run the whole TERRA-SENTINEL X chain and publish one run for the website.

    data/ -> sar/ -> algorithm/ -> validation/ -> backend/outputs/<run_id>/

Two ways to use it:

1. Run every stage (scripts are listed in backend/pipeline.json; a stage whose
   script does not exist yet is skipped):

       python backend/pipeline.py --run-id riyadh-2026-11 --aoi "Riyadh, Saudi Arabia"

2. Collect files a teammate already produced (e.g. shared by Drive) and
   publish them without running anything:

       python backend/pipeline.py --run-id riyadh-2026-11 --collect ~/Downloads/results

The work/collect folder may contain:
    before.tif, after.tif           GeoTIFF, dB (or linear power, auto-converted)
    before.png, after.png           only if no GeoTIFF; then --bounds is required
    changes.geojson                 required (algorithm/ + validation/)
    change_map.tif|png, doubt_map.tif|png   optional overlays
    meta.json                       optional partial run.json (scene ids, dates, method...)

Result: backend/outputs/<run_id>/{run.json, before.png, after.png,
change_map.png, doubt_map.png, changes.geojson} + an entry in
backend/outputs/runs.json. The run is validated against schema/ at the end.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import common
import validate

CONFIG = Path(__file__).with_name("pipeline.json")
MAX_PNG_SIDE = 2048  # keep web overlays light


def log(msg: str) -> None:
    print(f"[pipeline] {msg}", flush=True)


# ---------------------------------------------------------------- stages

def run_stages(work: Path, only: set[str] | None, skip: set[str]) -> None:
    stages = json.loads(CONFIG.read_text(encoding="utf-8"))["stages"]
    for st in stages:
        name = st["name"]
        if (only and name not in only) or name in skip:
            log(f"{name}: skipped (by option)")
            continue
        cmd = [part.replace("{work}", str(work)) for part in st["cmd"]]
        script = common.ROOT / cmd[1]
        if not script.exists():
            log(f"{name}: skipped - {cmd[1]} not written yet ({st.get('owner', '')})")
            continue
        if cmd[0] == "python":
            cmd[0] = sys.executable
        log(f"{name}: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=common.ROOT)
        if res.returncode != 0:
            raise SystemExit(f"[pipeline] {name} failed with exit code {res.returncode}")
        missing = [f for f in st.get("produces", []) if not (work / f).exists()]
        if missing:
            raise SystemExit(f"[pipeline] {name} finished but did not write {missing} into {work}")


# ---------------------------------------------------------------- rasters

def _to_db(a):
    import numpy as np

    finite = a[np.isfinite(a)]
    if finite.size and finite.min() >= 0 and np.median(finite) < 1.5:
        log("  values look like linear power, converting to dB")
        with np.errstate(divide="ignore", invalid="ignore"):
            a = 10 * np.log10(a)
        a[~np.isfinite(a)] = np.nan
    return a


def read_on_grid(tif: Path, grid=None, categorical: bool = False):
    """Read band 1 of a GeoTIFF reprojected to EPSG:4326.

    grid = (transform, width, height) to resample onto an existing grid (so
    before/after/change maps line up pixel for pixel). Returns (array, grid, bounds).
    """
    import numpy as np
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    with rasterio.open(tif) as src:
        if grid is None:
            transform, w, h = calculate_default_transform(src.crs, "EPSG:4326", src.width, src.height, *src.bounds)
            scale = max(w, h) / MAX_PNG_SIDE
            if scale > 1:
                w, h = int(round(w / scale)), int(round(h / scale))
                transform, w, h = calculate_default_transform(
                    src.crs, "EPSG:4326", src.width, src.height, *src.bounds, dst_width=w, dst_height=h)
            grid = (transform, w, h)
        transform, w, h = grid
        dst = np.full((h, w), np.nan, dtype="float32")
        src_arr = src.read(1).astype("float32")
        if src.nodata is not None:
            src_arr[src_arr == src.nodata] = np.nan
        reproject(src_arr, dst, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                  dst_transform=transform, dst_crs="EPSG:4326", dst_nodata=np.nan,
                  resampling=Resampling.nearest if categorical else Resampling.bilinear)
    west, north = transform.c, transform.f
    east, south = west + transform.a * w, north + transform.e * h
    return dst, grid, [round(west, 6), round(south, 6), round(east, 6), round(north, 6)]


# value -> RGBA. Anything not listed (0, nodata) is transparent.
CHANGE_PALETTE = {1: (0, 140, 255, 170)}
# Smart Doubt = number of tested thresholds a pixel passes (validation/ legend):
DOUBT_PALETTE = {1: (255, 214, 0, 170),    # relaxed only      -> most doubt
                 2: (255, 140, 0, 170),    # relaxed + baseline
                 3: (220, 0, 160, 170)}    # all three         -> least doubt


def overlay_png(arr, path: Path, palette: dict) -> None:
    import numpy as np
    from PIL import Image

    vals = np.nan_to_num(arr, nan=0).round().astype("int32")
    out = np.zeros(arr.shape + (4,), np.uint8)
    if max(palette) == 1:          # binary mask: any positive value counts
        out[vals > 0] = palette[1]
    else:
        for v, rgba in palette.items():
            out[vals == v] = rgba
    Image.fromarray(out, "RGBA").save(path, optimize=True)


def export_rasters(work: Path, out: Path, bounds_arg) -> list[float]:
    """Write before/after/change/doubt PNGs into out/. Returns bounds."""
    have_tif = (work / "before.tif").exists() and (work / "after.tif").exists()
    if have_tif:
        try:
            import rasterio  # noqa: F401
        except ImportError:
            raise SystemExit("[pipeline] GeoTIFFs found but rasterio is not installed: pip install -r backend/requirements.txt")
        log("rasters: reprojecting GeoTIFFs to EPSG:4326 PNGs")
        before, grid, bounds = read_on_grid(work / "before.tif")
        after, _, _ = read_on_grid(work / "after.tif", grid)
        common.save_db_png(_to_db(before), out / "before.png")
        common.save_db_png(_to_db(after), out / "after.png")
        for name, colour in (("change_map", CHANGE_PALETTE), ("doubt_map", DOUBT_PALETTE)):
            if (work / f"{name}.png").exists():
                log(f"  {name}.png provided - copying as is (must match before/after bounds)")
                shutil.copy2(work / f"{name}.png", out / f"{name}.png")
            elif (work / f"{name}.tif").exists():
                arr, _, _ = read_on_grid(work / f"{name}.tif", grid, categorical=True)
                overlay_png(arr, out / f"{name}.png", colour)
        return bounds

    if not ((work / "before.png").exists() and (work / "after.png").exists()):
        raise SystemExit(f"[pipeline] need before/after .tif or .png in {work}")
    if not bounds_arg:
        raise SystemExit("[pipeline] PNG-only input: pass --bounds WEST SOUTH EAST NORTH (EPSG:4326)")
    log("rasters: copying PNGs as provided")
    for name in ("before", "after", "change_map", "doubt_map"):
        if (work / f"{name}.png").exists():
            shutil.copy2(work / f"{name}.png", out / f"{name}.png")
    return list(bounds_arg)


# ---------------------------------------------------------------- run.json

def build_run(args, work: Path, out: Path, bounds) -> dict:
    meta = {}
    if (work / "meta.json").exists():
        meta = json.loads((work / "meta.json").read_text(encoding="utf-8"))
        log("meta: using meta.json from the work folder")
    if (work / "changes.geojson").exists():
        props = json.loads((work / "changes.geojson").read_text(encoding="utf-8")).get("properties") or {}
        meta.setdefault("method", {})
        if props.get("method"):
            meta["method"].setdefault("name", props["method"])
        if props.get("threshold_db") is not None:
            meta["method"].setdefault("threshold_db", props["threshold_db"])

    def scene(key, sid, date):
        s = dict(meta.get(key) or {})
        s.setdefault("scene_id", "TBD")
        s.setdefault("date", "1970-01-01")
        if sid:
            s["scene_id"] = sid
        if date:
            s["date"] = date
        if args.polarization:
            s["polarization"] = args.polarization
        s["png"] = f"{key}.png"
        s.pop("geotiff", None)  # GeoTIFFs are not published to the website
        return s

    run = {
        "run_id": args.run_id,
        "aoi_name": args.aoi or meta.get("aoi_name") or args.run_id,
        "crs": "EPSG:4326",
        "bounds": bounds,
        "before": scene("before", args.before_id, args.before_date),
        "after": scene("after", args.after_id, args.after_date),
        "change_map": {"png": "change_map.png"},
        "changes": "changes.geojson",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    if args.event or meta.get("event"):
        run["event"] = args.event or meta["event"]
    if (out / "doubt_map.png").exists():
        run["doubt_map"] = {"png": "doubt_map.png"}
    for key in ("method", "status", "validation", "limitations"):
        if meta.get(key):
            run[key] = meta[key]
    if args.demo or meta.get("demo"):
        run["demo"] = True
    for k in ("before", "after"):
        if run[k]["scene_id"] == "TBD" or run[k]["date"] == "1970-01-01":
            log(f"warning: {k} scene id/date unknown - pass --{k}-id/--{k}-date or add meta.json")
    return run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True, help="lowercase id, e.g. riyadh-2026-11")
    ap.add_argument("--aoi", help="area name shown on the site")
    ap.add_argument("--event", help="flood event label")
    ap.add_argument("--collect", type=Path, metavar="DIR", help="don't run stages, publish files from DIR")
    ap.add_argument("--work", type=Path, help="work folder (default backend/work/<run_id>)")
    ap.add_argument("--only", nargs="+", metavar="STAGE", help="run only these stages")
    ap.add_argument("--skip", nargs="+", default=[], metavar="STAGE", help="skip these stages")
    ap.add_argument("--bounds", nargs=4, type=float, metavar=("W", "S", "E", "N"), help="needed only for PNG-only input")
    ap.add_argument("--before-id"), ap.add_argument("--before-date", help="YYYY-MM-DD")
    ap.add_argument("--after-id"), ap.add_argument("--after-date", help="YYYY-MM-DD")
    ap.add_argument("--polarization", choices=["HH", "HV", "VH", "VV"])
    ap.add_argument("--demo", action="store_true", help="mark run as demo/synthetic")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--default", dest="make_default", action="store_true", default=None, help="open this run first on the site")
    g.add_argument("--no-default", dest="make_default", action="store_false")
    args = ap.parse_args(argv)

    if args.collect:
        work = args.collect.expanduser().resolve()
        if not work.is_dir():
            raise SystemExit(f"[pipeline] --collect folder not found: {work}")
    else:
        work = (args.work or common.ROOT / "backend" / "work" / args.run_id).resolve()
        work.mkdir(parents=True, exist_ok=True)
        log(f"work folder: {work}")
        run_stages(work, set(args.only) if args.only else None, set(args.skip))

    if not (work / "changes.geojson").exists():
        raise SystemExit(f"[pipeline] no changes.geojson in {work} - algorithm/ has not produced output yet")

    out = common.OUTPUTS / args.run_id
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    bounds = export_rasters(work, out, args.bounds)
    shutil.copy2(work / "changes.geojson", out / "changes.geojson")
    if not (out / "change_map.png").exists():
        log("warning: no change_map.tif/png - Reveal Changes will rely on the polygons only")
    run = build_run(args, work, out, bounds)
    if "change_map" in run and not (out / "change_map.png").exists():
        # Transparent placeholder so run.json stays valid.
        from PIL import Image
        Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(out / "change_map.png")
    common.finalise_run(out, run, args.make_default)

    rep = validate.check_run(out)
    rep.print()
    s = run.get("summary", {})
    log(f"published {out.relative_to(common.ROOT)}: {s.get('n_changes', 0)} areas, "
        f"{s.get('total_area_km2', 0)} km2, {s.get('n_high_doubt', 0)} need review")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
