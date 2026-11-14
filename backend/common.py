"""Shared helpers for backend/ scripts: paths, PNG export, run index."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "backend" / "outputs"
INDEX = OUTPUTS / "runs.json"

# Greyscale stretch for backscatter previews. Same for before and after so the
# slider compares like with like.
DB_MIN, DB_MAX = -25.0, 0.0


def pixel_to_lonlat(x: float, y: float, w: int, h: int, bounds) -> list[float]:
    west, south, east, north = bounds
    lon = west + (x / w) * (east - west)
    lat = north - (y / h) * (north - south)
    return [round(lon, 6), round(lat, 6)]


def pixel_area_km2(w: int, h: int, bounds) -> float:
    west, south, east, north = bounds
    lat = math.radians((south + north) / 2)
    dx = (east - west) / w * 111.32 * math.cos(lat)
    dy = (north - south) / h * 110.57
    return dx * dy


def save_db_png(db, path: Path, vmin: float = DB_MIN, vmax: float = DB_MAX) -> None:
    """Save a dB array as an 8-bit greyscale PNG (NaN -> transparent)."""
    import numpy as np
    from PIL import Image

    a = np.asarray(db, dtype="float32")
    valid = np.isfinite(a)
    g = np.clip((np.nan_to_num(a, nan=vmin) - vmin) / (vmax - vmin), 0, 1)
    g = (g * 255).astype("uint8")
    if valid.all():
        Image.fromarray(g, "L").save(path, optimize=True)
    else:
        alpha = (valid * 255).astype("uint8")
        Image.fromarray(np.dstack([g, alpha]), "LA").save(path, optimize=True)


def summarise(changes: dict) -> dict:
    feats = changes.get("features") or []
    area = sum(f.get("properties", {}).get("area_km2", 0) or 0 for f in feats)
    high = sum(1 for f in feats if f.get("properties", {}).get("reliability", {}).get("doubt_level") == "high")
    return {"n_changes": len(feats), "total_area_km2": round(area, 3), "n_high_doubt": high}


def finalise_run(run_dir: Path, run: dict, make_default: bool | None = None) -> None:
    """Fill run.summary, write run.json and register the run in outputs/runs.json."""
    changes_path = run_dir / run["changes"]
    if changes_path.exists():
        run["summary"] = summarise(json.loads(changes_path.read_text(encoding="utf-8")))
    (run_dir / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    update_index(run_dir, run, make_default)


def update_index(run_dir: Path, run: dict, make_default: bool | None = None) -> None:
    """outputs/runs.json lists every run so the frontend can offer a picker.

    The default run is the one the website opens first. A real (non-demo) run
    becomes the default automatically unless make_default=False.
    """
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    index = {"default": None, "runs": []}
    if INDEX.exists():
        index = json.loads(INDEX.read_text(encoding="utf-8"))
    entry = {
        "run_id": run["run_id"],
        "aoi_name": run.get("aoi_name"),
        "event": run.get("event"),
        "demo": bool(run.get("demo")),
        "before_date": run.get("before", {}).get("date"),
        "after_date": run.get("after", {}).get("date"),
        "path": f"{run_dir.name}/run.json",
    }
    index["runs"] = [r for r in index.get("runs", []) if r["run_id"] != run["run_id"]] + [entry]
    index["runs"].sort(key=lambda r: (r["demo"], r["run_id"]))
    current = next((r for r in index["runs"] if r["run_id"] == index.get("default")), None)
    if make_default is True or (make_default is None and (current is None or (current["demo"] and not entry["demo"]))):
        index["default"] = run["run_id"]
    INDEX.write_text(json.dumps(index, indent=2), encoding="utf-8")
