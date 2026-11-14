#!/usr/bin/env python3
"""Turn the algorithm's candidate raster into changes.geojson (schema/).

The algorithm (role 1, flood_detection_v2.py) writes rasters; the website
needs one polygon per change area with evidence and Smart Doubt values. This
script is that bridge:

  candidate raster (0/1, 255 = invalid)   -> connected areas -> polygons
  before/after HH (dB)                    -> evidence: mean before/after/delta
  HV change (dB, optional)                -> evidence: delta_hv_db
  Smart Doubt stability (0-3, 255 invalid) -> reliability

Usage:
    python backend/vectorize.py --candidate candidate_joint_HH_HV.tif \
        --before before.tif --after after.tif --stability smart_doubt_stability.tif \
        [--change-hv change_HV_db.tif] [--min-pixels 25] --out changes.geojson

All rasters must share one grid (same CRS, transform, size).
Needs numpy, rasterio, scipy, shapely.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from scipy import ndimage
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


def read(path: Path, ref=None):
    with rasterio.open(path) as ds:
        a = ds.read(1).astype("float64")
        if ds.nodata is not None:
            a[a == ds.nodata] = np.nan
        meta = (ds.crs, ds.transform, ds.width, ds.height)
    if ref is not None and (meta[0] != ref[0] or not meta[1].almost_equals(ref[1]) or meta[2:] != ref[2:]):
        raise SystemExit(f"{path.name} is not on the same grid as the candidate raster")
    return a, meta


def per_label_mean(values, labels, n):
    v = np.where(np.isfinite(values), values, 0.0)
    ok = np.isfinite(values) & (labels > 0)
    s = np.bincount(labels[ok], weights=v[ok], minlength=n + 1)
    c = np.bincount(labels[ok], minlength=n + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return s / c


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--before", type=Path, required=True, help="HH backscatter in dB")
    ap.add_argument("--after", type=Path, required=True, help="HH backscatter in dB")
    ap.add_argument("--stability", type=Path, help="Smart Doubt raster, 0-3 thresholds passed")
    ap.add_argument("--change-hv", type=Path, help="HV after-before in dB")
    ap.add_argument("--n-thresholds", type=int, default=3)
    ap.add_argument("--min-pixels", type=int, default=25, help="drop areas smaller than this (default 25)")
    ap.add_argument("--simplify-m", type=float, default=None, help="simplify tolerance in CRS units (default half a pixel)")
    ap.add_argument("--polarization", default="HH")
    ap.add_argument("--method", default="HH+HV joint log-ratio darkening (flood_detection_v2)")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)

    cand, ref = read(args.candidate)
    crs, transform, _, _ = ref
    before, _ = read(args.before, ref)
    after, _ = read(args.after, ref)
    stab = read(args.stability, ref)[0] if args.stability else None
    dhv = read(args.change_hv, ref)[0] if args.change_hv else None

    mask = np.nan_to_num(cand) == 1
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    counts = np.bincount(labels.ravel(), minlength=n + 1)
    keep = counts >= args.min_pixels
    keep[0] = False
    labels[~keep[labels]] = 0
    print(f"{n} connected areas, {int(keep.sum())} with >= {args.min_pixels} pixels")

    px_km2 = abs(transform.a * transform.e) / 1e6
    mb = per_label_mean(before, labels, n)
    ma = per_label_mean(after, labels, n)
    mhv = per_label_mean(dhv, labels, n) if dhv is not None else None
    if stab is not None:
        mstab = per_label_mean(stab, labels, n)
        strict = per_label_mean(np.where(np.isfinite(stab), (stab >= args.n_thresholds).astype(float), np.nan), labels, n)

    tol = args.simplify_m if args.simplify_m is not None else abs(transform.a) / 2
    polys: dict[int, list] = {}
    for geom, val in shapes(labels.astype("int32"), mask=labels > 0, transform=transform, connectivity=8):
        polys.setdefault(int(val), []).append(shape(geom))

    features = []
    order = sorted(polys, key=lambda k: -counts[k])
    for i, lab in enumerate(order, start=1):
        g = unary_union(polys[lab]).simplify(tol, preserve_topology=True)
        g4326 = transform_geom(crs, "EPSG:4326", mapping(g), precision=6)
        b, a = float(mb[lab]), float(ma[lab])
        d = a - b
        props = {
            "change_type": "possible_flood",
            "area_km2": round(counts[lab] * px_km2, 3),
            "evidence": {
                "before_backscatter_db": round(b, 2),
                "after_backscatter_db": round(a, 2),
                "delta_db": round(d, 2),
                "polarization": args.polarization,
                "pixel_count": int(counts[lab]),
                "reason": "",
            },
            "reliability": {"confidence": 0.0, "doubt_level": "high", "notes": ""},
        }
        if mhv is not None and np.isfinite(mhv[lab]):
            props["evidence"]["delta_hv_db"] = round(float(mhv[lab]), 2)
        if stab is not None:
            s_mean = float(mstab[lab]) / args.n_thresholds
            s_strict = float(strict[lab])
            level = "low" if s_strict >= 0.75 else "medium" if s_strict >= 0.4 else "high"
            props["reliability"] = {
                "confidence": round(s_strict, 2),
                "stable_across_thresholds": round(s_mean, 2),
                "doubt_level": level,
                "notes": (f"{s_strict:.0%} of this area passes all {args.n_thresholds} tested thresholds. "
                          "Threshold agreement only, not a calibrated probability."),
            }
            if level == "low" and a <= -15:
                props["change_type"] = "likely_flood"
        hv = props["evidence"].get("delta_hv_db")
        props["evidence"]["reason"] = (
            f"HH backscatter dropped {abs(d):.1f} dB to {a:.1f} dB"
            + (f" and HV dropped {abs(hv):.1f} dB" if hv is not None and hv < 0 else "")
            + (", consistent with smooth open water." if a <= -15 else
               "; darker surface that may be water, wet soil or another change.")
        )
        features.append({"type": "Feature", "id": f"chg-{i:04d}", "geometry": g4326, "properties": props})

    doc = {
        "type": "FeatureCollection",
        "properties": {"run_id": args.run_id, "method": args.method, "min_pixels": args.min_pixels},
        "features": features,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    levels = {k: sum(f["properties"]["reliability"]["doubt_level"] == k for f in features) for k in ("low", "medium", "high")}
    area = sum(f["properties"]["area_km2"] for f in features)
    print(f"wrote {len(features)} areas, {area:.1f} km2, doubt {levels}, "
          f"likely_flood {sum(f['properties']['change_type'] == 'likely_flood' for f in features)} -> {args.out} "
          f"({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
