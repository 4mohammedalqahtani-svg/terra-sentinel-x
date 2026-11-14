#!/usr/bin/env python3
"""Check that a run folder follows the shared schema in schema/.

Usage:
    python backend/validate.py backend/outputs/jeddah-demo-001
    python backend/validate.py path/to/changes.geojson        # one file only
    python backend/validate.py --all                          # every run in backend/outputs/

Exit code 0 = OK (warnings allowed), 1 = errors found.
Works with only the standard library; uses `jsonschema` and `Pillow` for
extra checks when they are installed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema"
OUTPUTS = ROOT / "backend" / "outputs"


class Report:
    def __init__(self, label: str):
        self.label = label
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def print(self) -> None:
        status = "FAIL" if self.errors else "OK"
        print(f"[{status}] {self.label}")
        for m in self.errors:
            print(f"   error:   {m}")
        for m in self.warnings:
            print(f"   warning: {m}")


def _load_json(path: Path, rep: Report):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rep.err(f"missing file: {path}")
    except json.JSONDecodeError as e:
        rep.err(f"{path.name} is not valid JSON: {e}")
    return None


def _jsonschema_check(doc, schema_name: str, rep: Report) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in e.path) or "(root)"
        rep.err(f"{where}: {e.message}")


def _check_bounds(b, rep: Report) -> bool:
    if not (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)):
        rep.err("bounds must be [west, south, east, north] numbers")
        return False
    w, s, e, n = b
    ok = True
    if not (-180 <= w < e <= 180):
        rep.err(f"bounds: need -180 <= west < east <= 180, got west={w} east={e}")
        ok = False
    if not (-90 <= s < n <= 90):
        rep.err(f"bounds: need -90 <= south < north <= 90, got south={s} north={n}")
        ok = False
    return ok


def _rings(geom):
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon" and isinstance(c, list):
        yield from c
    elif t == "MultiPolygon" and isinstance(c, list):
        for poly in c:
            if isinstance(poly, list):
                yield from poly


def check_changes(doc, rep: Report, bounds=None) -> dict:
    """Validate a changes.geojson document. Returns a summary dict."""
    _jsonschema_check(doc, "changes.schema.json", rep)
    summary = {"n_changes": 0, "total_area_km2": 0.0, "n_high_doubt": 0}
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        rep.err("changes: must be a GeoJSON FeatureCollection")
        return summary
    feats = doc.get("features")
    if not isinstance(feats, list):
        rep.err("changes: 'features' must be a list")
        return summary
    if not feats:
        rep.warn("changes: no features (nothing detected?)")

    seen: set[str] = set()
    for i, f in enumerate(feats):
        fid = f.get("id") if isinstance(f, dict) else None
        tag = f"feature {fid or '#' + str(i)}"
        if not isinstance(f, dict):
            rep.err(f"{tag}: not an object")
            continue
        if not fid:
            rep.err(f"{tag}: missing 'id' (needed to link map and Evidence Card)")
        elif fid in seen:
            rep.err(f"{tag}: duplicate id")
        else:
            seen.add(fid)

        geom = f.get("geometry") or {}
        for ring in _rings(geom):
            if not isinstance(ring, list) or len(ring) < 4:
                rep.err(f"{tag}: polygon ring needs at least 4 positions")
                continue
            if ring[0] != ring[-1]:
                rep.err(f"{tag}: polygon ring is not closed (first != last point)")
            for pt in ring:
                if not (isinstance(pt, list) and len(pt) >= 2):
                    rep.err(f"{tag}: bad coordinate {pt!r}")
                    break
                lon, lat = pt[0], pt[1]
                if not (-180 <= lon <= 180 and -90 <= lat <= 90):
                    rep.err(f"{tag}: coordinate {pt} out of range - are lon/lat swapped or still in a projected CRS?")
                    break
                if bounds and not (bounds[0] - 1e-3 <= lon <= bounds[2] + 1e-3 and bounds[1] - 1e-3 <= lat <= bounds[3] + 1e-3):
                    rep.warn(f"{tag}: point {pt} lies outside run bounds")
                    break

        props = f.get("properties") or {}
        ev = props.get("evidence") or {}
        try:
            d = ev["after_backscatter_db"] - ev["before_backscatter_db"]
            if abs(d - ev["delta_db"]) > 0.2:
                rep.warn(f"{tag}: delta_db={ev['delta_db']} but after-before={d:.2f}")
        except (KeyError, TypeError):
            pass
        rel = props.get("reliability") or {}
        summary["n_changes"] += 1
        if isinstance(props.get("area_km2"), (int, float)):
            summary["total_area_km2"] += props["area_km2"]
        if rel.get("doubt_level") == "high":
            summary["n_high_doubt"] += 1
    summary["total_area_km2"] = round(summary["total_area_km2"], 3)
    return summary


def _png_size(path: Path):
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return None
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def check_run(run_dir: Path) -> Report:
    rep = Report(str(run_dir))
    run = _load_json(run_dir / "run.json", rep)
    if run is None:
        return rep
    _jsonschema_check(run, "run.schema.json", rep)
    bounds = run.get("bounds")
    bounds_ok = _check_bounds(bounds, rep)
    if run.get("run_id") and run_dir.name != run["run_id"]:
        rep.warn(f"folder name '{run_dir.name}' differs from run_id '{run['run_id']}'")
    if run.get("demo"):
        rep.warn("demo=true: synthetic placeholder data, not real NISAR analysis")

    sizes = {}
    for key in ("before", "after", "change_map", "doubt_map"):
        block = run.get(key)
        if not isinstance(block, dict):
            continue
        png = block.get("png")
        if png:
            p = run_dir / png
            if not p.exists():
                rep.err(f"{key}.png points to missing file {png}")
            else:
                sizes[key] = _png_size(p)
        # GeoTIFFs are optional on the website (git-ignored), so only warn.
        tif = block.get("geotiff")
        if tif and not (run_dir / tif).exists():
            rep.warn(f"{key}.geotiff '{tif}' not present (fine for the website, PNGs are used)")
    known = {k: v for k, v in sizes.items() if v}
    if len(set(known.values())) > 1:
        rep.warn(f"PNG sizes differ {known} - overlays may not line up")

    changes_path = run.get("changes")
    if isinstance(changes_path, str):
        doc = _load_json(run_dir / changes_path, rep)
        if doc is not None:
            check_changes(doc, rep, bounds if bounds_ok else None)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="run folder(s) or a changes.geojson file")
    ap.add_argument("--all", action="store_true", help="validate every run in backend/outputs/")
    args = ap.parse_args(argv)

    targets = list(args.paths)
    if args.all:
        targets += sorted(p for p in OUTPUTS.iterdir() if (p / "run.json").exists()) if OUTPUTS.exists() else []
    if not targets:
        ap.error("give a run folder, a .geojson file, or --all")

    failed = False
    for t in targets:
        if t.is_file():
            rep = Report(str(t))
            doc = _load_json(t, rep)
            if doc is not None:
                check_changes(doc, rep)
        else:
            rep = check_run(t)
        rep.print()
        failed |= bool(rep.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
