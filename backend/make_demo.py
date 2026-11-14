#!/usr/bin/env python3
"""Generate a SYNTHETIC demo run that follows schema/ exactly.

This lets the frontend (role 3) build the slider, Reveal Changes, Evidence
Card and Smart Doubt before the real NISAR outputs exist. The run is marked
"demo": true and the website must show a "demo data" banner for it.
Replace it with a real run from backend/pipeline.py before submission.

Usage:
    python backend/make_demo.py                # writes backend/outputs/demo-synthetic/
    python backend/make_demo.py --size 600

Needs numpy and Pillow.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

import common

RUN_ID = "demo-synthetic"
BOUNDS = [39.10, 21.45, 39.30, 21.65]  # Jeddah area, [W, S, E, N]
THRESHOLD_DB = -3.0
THRESHOLDS_TESTED = [-1.5, -2.0, -2.5, -3.0, -3.5, -4.0, -4.5, -5.0, -5.5, -6.0]

# Synthetic flood patches: centre (fraction of width/height), radii, dB drop.
PATCHES = [
    {"c": (0.32, 0.58), "r": (0.10, 0.05), "rot": 25, "drop": -10.5},   # open water, strong
    {"c": (0.62, 0.36), "r": (0.07, 0.04), "rot": -15, "drop": -8.0},   # open water
    {"c": (0.72, 0.72), "r": (0.06, 0.035), "rot": 60, "drop": -3.6},   # weak, borderline
    {"c": (0.20, 0.22), "r": (0.04, 0.03), "rot": 0, "drop": -2.6},     # barely above noise
]


def box_blur(a: np.ndarray, k: int) -> np.ndarray:
    """Mean filter with a k x k window (k odd), edges padded."""
    p = k // 2
    pad = np.pad(a, p, mode="edge")
    c = pad.cumsum(0).cumsum(1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def ellipse_mask(h, w, patch):
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = patch["c"][0] * w, patch["c"][1] * h
    rx, ry = patch["r"][0] * w, patch["r"][1] * h
    t = math.radians(patch["rot"])
    dx, dy = xx - cx, yy - cy
    u = (dx * math.cos(t) + dy * math.sin(t)) / rx
    v = (-dx * math.sin(t) + dy * math.cos(t)) / ry
    return u * u + v * v <= 1.0


def ellipse_ring(h, w, patch, n=48):
    cx, cy = patch["c"][0] * w, patch["c"][1] * h
    rx, ry = patch["r"][0] * w, patch["r"][1] * h
    t = math.radians(patch["rot"])
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = cx + rx * math.cos(a) * math.cos(t) - ry * math.sin(a) * math.sin(t)
        y = cy + rx * math.cos(a) * math.sin(t) + ry * math.sin(a) * math.cos(t)
        pts.append(common.pixel_to_lonlat(x, y, w, h, BOUNDS))
    pts.append(pts[0])
    return pts


def speckle_db(mean_db: np.ndarray, rng, looks=4) -> np.ndarray:
    """Multiplicative gamma speckle, like a 4-look SAR intensity image."""
    lin = 10 ** (mean_db / 10)
    noisy = lin * rng.gamma(looks, 1.0 / looks, size=lin.shape)
    return 10 * np.log10(noisy)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=800, help="image width/height in pixels")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=common.OUTPUTS / RUN_ID)
    args = ap.parse_args(argv)

    n = args.size
    rng = np.random.default_rng(args.seed)
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    # Smooth land texture around -8 dB, a brighter "urban" strip, a darker wadi.
    base = box_blur(rng.normal(0, 3.0, (n, n)), 41) * 6 - 8.0
    yy, xx = np.mgrid[0:n, 0:n] / n
    base += np.where((xx > 0.80) & (xx < 0.95), 4.0, 0.0)         # urban, bright
    base -= 3.0 * np.exp(-((yy - (0.3 + 0.5 * xx)) ** 2) / 0.0008)  # wadi channel

    after_mean = base.copy()
    masks = []
    for p in PATCHES:
        m = ellipse_mask(n, n, p)
        masks.append(m)
        if p["drop"] < -6:  # open water: very dark, at most -18 dB
            after_mean[m] = np.minimum(after_mean[m] + p["drop"], -18.0)
        else:
            after_mean[m] += p["drop"]

    before_db = speckle_db(base, rng)
    after_db = speckle_db(after_mean, rng)

    # Simple log-ratio detection, the same idea algorithm/ will use.
    delta = box_blur(after_db, 7) - box_blur(before_db, 7)
    detected = delta < THRESHOLD_DB
    likely = detected & (box_blur(after_db, 7) < -15)

    common.save_db_png(before_db, out / "before.png")
    common.save_db_png(after_db, out / "after.png")
    rgba = np.zeros((n, n, 4), np.uint8)
    rgba[detected] = (255, 160, 0, 150)   # orange = possible
    rgba[likely] = (0, 140, 255, 170)     # blue = likely flood (water)
    Image.fromarray(rgba, "RGBA").save(out / "change_map.png", optimize=True)

    # Smart Doubt raster: how many thresholds flag each pixel.
    votes = sum((delta < t).astype(np.float32) for t in THRESHOLDS_TESTED) / len(THRESHOLDS_TESTED)
    doubt = np.zeros((n, n, 4), np.uint8)
    flagged = votes > 0
    unstable = flagged & (votes < 0.7)
    doubt[unstable] = (255, 40, 120, 170)
    Image.fromarray(doubt, "RGBA").save(out / "doubt_map.png", optimize=True)

    px_km2 = common.pixel_area_km2(n, n, BOUNDS)
    features = []
    for i, (p, m) in enumerate(zip(PATCHES, masks), start=1):
        b = float(before_db[m].mean())
        a = float(after_db[m].mean())
        d = a - b
        stab = float(np.mean([d < t for t in THRESHOLDS_TESTED]))
        conf = round(min(0.98, max(0.05, 0.25 + 0.7 * stab)), 2)
        level = "low" if stab >= 0.8 else "medium" if stab >= 0.5 else "high"
        if a < -15 and d < -6:
            ctype = "likely_flood"
            reason = "Strong backscatter drop to a very low value, consistent with smooth open water."
        elif d < -2:
            ctype = "possible_flood"
            reason = "Moderate backscatter drop; could be shallow water, wet soil or flooded vegetation."
        else:
            ctype = "other_change"
            reason = "Small change close to speckle noise level."
        hits = sum(d < t for t in THRESHOLDS_TESTED)
        features.append({
            "type": "Feature",
            "id": f"chg-{i:04d}",
            "geometry": {"type": "Polygon", "coordinates": [ellipse_ring(n, n, p)]},
            "properties": {
                "change_type": ctype,
                "area_km2": round(float(m.sum()) * px_km2, 3),
                "evidence": {
                    "before_backscatter_db": round(b, 2),
                    "after_backscatter_db": round(a, 2),
                    "delta_db": round(d, 2),
                    "polarization": "HH",
                    "pixel_count": int(m.sum()),
                    "reason": reason,
                },
                "reliability": {
                    "confidence": conf,
                    "stable_across_thresholds": round(stab, 2),
                    "doubt_level": level,
                    "notes": f"Detected at {hits} of {len(THRESHOLDS_TESTED)} tested thresholds.",
                },
            },
        })

    changes = {
        "type": "FeatureCollection",
        "properties": {"run_id": RUN_ID, "method": "log-ratio threshold (synthetic demo)", "threshold_db": THRESHOLD_DB},
        "features": features,
    }
    (out / "changes.geojson").write_text(json.dumps(changes, indent=1), encoding="utf-8")

    run = {
        "run_id": RUN_ID,
        "aoi_name": "Jeddah, Saudi Arabia (synthetic demo)",
        "event": "Synthetic flood for frontend development - NOT real NISAR data",
        "demo": True,
        "crs": "EPSG:4326",
        "bounds": BOUNDS,
        "before": {"scene_id": "SYNTHETIC-BEFORE", "date": "2026-10-20", "png": "before.png", "polarization": "HH", "product": "GCOV"},
        "after": {"scene_id": "SYNTHETIC-AFTER", "date": "2026-11-01", "png": "after.png", "polarization": "HH", "product": "GCOV"},
        "change_map": {"png": "change_map.png"},
        "doubt_map": {"png": "doubt_map.png"},
        "changes": "changes.geojson",
        "method": {
            "name": "log-ratio threshold",
            "threshold_db": THRESHOLD_DB,
            "thresholds_tested_db": THRESHOLDS_TESTED,
            "speckle_filter": "7x7 mean (boxcar)",
        },
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    common.finalise_run(out, run)
    print(f"demo run written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
