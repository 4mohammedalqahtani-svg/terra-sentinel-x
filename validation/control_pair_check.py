#!/usr/bin/env python3
"""TERRA-SENTINEL X | Control-pair false-alarm test (role 6, Validation).

Runs the flood algorithm (algorithm/flood_detection_v2.py) UNCHANGED on two
PRE-flood NISAR dates: 2025-12-24 -> 2026-01-05. No flood is expected between
them, so whatever it flags is the method's background false-alarm level
(speckle, soil moisture, farming). That is compared with the event pair
(2026-01-05 -> 2026-01-17) already in algorithm/results_v2/.

Run from the repository root:
    python validation/control_pair_check.py

Inputs (all committed):
    validation/samples/control_{HH,HV,mask}.tif   24 Dec 2025, same grid as algorithm/data
    algorithm/data/before_{HH,HV,mask}.tif        5 Jan 2026
    algorithm/results_v2/candidate_joint_HH_HV.tif  event result
Outputs:
    validation/results/control_pair_summary.json
    validation/results/control_vs_event.png
The algorithm runs in a temporary folder; nothing in algorithm/ is modified.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy import ndimage

REPO = Path(__file__).resolve().parents[1]
ALGO = REPO / "algorithm"
CONTROL = REPO / "validation" / "samples"
OUT = REPO / "validation" / "results"
LAYERS = ("HH", "HV", "mask")
MIN_AREA_PX = 25  # same minimum polygon size as the website (backend/vectorize.py)


def read(path: Path):
    with rasterio.open(path) as ds:
        return ds.read(1), (str(ds.crs), tuple(ds.transform)[:6], ds.width, ds.height), ds.transform


def components(mask: np.ndarray, px_km2: float) -> dict:
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    sizes = np.bincount(lab.ravel())[1:]
    big = sizes[sizes >= MIN_AREA_PX]
    return {"connected_areas": int(n), f"areas_ge_{MIN_AREA_PX}px": int(big.size),
            f"area_ge_{MIN_AREA_PX}px_km2": round(float(big.sum()) * px_km2, 2)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp)
        (run / "data").mkdir()
        for layer in LAYERS:  # "before" = 24 Dec, "after" = 5 Jan
            shutil.copy2(CONTROL / f"control_{layer}.tif", run / "data" / f"before_{layer}.tif")
            shutil.copy2(ALGO / "data" / f"before_{layer}.tif", run / "data" / f"after_{layer}.tif")
        shutil.copy2(ALGO / "flood_detection_v2.py", run / "flood_detection_v2.py")
        print("Running algorithm/flood_detection_v2.py unchanged on 2025-12-24 -> 2026-01-05 ...")
        proc = subprocess.run([sys.executable, "flood_detection_v2.py"], cwd=run, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout[-1500:], proc.stderr[-1500:])
            raise SystemExit("ERROR: control run failed")
        control, g_c, transform = read(run / "results_v2" / "candidate_joint_HH_HV.tif")
        control_report = json.loads((run / "results_v2" / "evidence_v2.json").read_text(encoding="utf-8"))

    event, g_e, _ = read(ALGO / "results_v2" / "candidate_joint_HH_HV.tif")
    if g_c != g_e:
        raise SystemExit("ERROR: control and event results are not on the same grid")
    event_report = json.loads((ALGO / "results_v2" / "evidence_v2.json").read_text(encoding="utf-8"))

    px_km2 = abs(transform.a * transform.e) / 1e6
    valid = (control != 255) & (event != 255)
    c, e = (control == 1) & valid, (event == 1) & valid
    n_c, n_e, n_both, n_valid = int(c.sum()), int(e.sum()), int((c & e).sum()), int(valid.sum())
    sd_c = control_report["sensitivity"]["candidate_counts_relaxed_baseline_strict"]
    sd_e = event_report["sensitivity"]["candidate_counts_relaxed_baseline_strict"]

    summary = {
        "test": "Control pair: same algorithm and thresholds on two pre-flood dates",
        "control_pair": {"before": "2025-12-24", "after": "2026-01-05"},
        "event_pair": {"before": "2026-01-05", "after": "2026-01-17"},
        "algorithm": "algorithm/flood_detection_v2.py, unchanged",
        "valid_pixels": n_valid,
        "pixels": {
            "control_candidates": n_c,
            "control_area_km2": round(n_c * px_km2, 2),
            "control_false_alarm_pct_of_valid": round(100 * n_c / n_valid, 3),
            "event_candidates": n_e,
            "event_area_km2": round(n_e * px_km2, 2),
            "event_to_control_ratio": round(n_e / n_c, 1) if n_c else None,
            "event_candidates_also_in_control": n_both,
            "event_candidates_also_in_control_pct": round(100 * n_both / max(n_e, 1), 2),
        },
        "map_polygons": {"min_area_px": MIN_AREA_PX, "control": components(c, px_km2), "event": components(e, px_km2)},
        "smart_doubt": {
            "control_relaxed_baseline_strict": sd_c,
            "control_strict_share_of_baseline_pct": round(100 * sd_c[2] / max(sd_c[1], 1), 1),
            "event_relaxed_baseline_strict": sd_e,
            "event_strict_share_of_baseline_pct": round(100 * sd_e[2] / max(sd_e[1], 1), 1),
        },
        "interpretation": ("Control candidates estimate the method's background false-alarm level when no "
                           "flood is expected. This is a plausibility check, NOT an accuracy score."),
        "limitations": [
            "Assumes no significant flooding between 2025-12-24 and 2026-01-05 (supported by ASF browse images and stable frame-wide backscatter, -0.8 dB)",
            "Scene-relative percentile thresholds are recomputed for each pair, as in the original algorithm",
            "Different 12-day intervals can have different weather and soil moisture",
            "NISAR GCOV BETA, uncalibrated",
        ],
    }
    (OUT / "control_pair_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), constrained_layout=True)
    for ax, m, title, n in ((axes[0], c, "Control: 24 Dec -> 5 Jan (no flood expected)", n_c),
                            (axes[1], e, "Event: 5 Jan -> 17 Jan", n_e)):
        img = np.full(m.shape, 0.92)
        img[~valid] = 1.0
        img[m] = 0.0
        ax.imshow(img, cmap="gray", vmin=0, vmax=1)
        ax.set_title(f"{title}\n{n:,} candidate pixels ({n * px_km2:.1f} km²)")
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("TERRA-SENTINEL X | same algorithm, same thresholds | NISAR GCOV BETA", fontsize=12)
    fig.savefig(OUT / "control_vs_event.png", dpi=150, facecolor="white")
    plt.close(fig)

    p = summary["pixels"]
    print(f"Control: {n_c:,} px ({p['control_area_km2']} km2, {p['control_false_alarm_pct_of_valid']}% of valid)")
    print(f"Event:   {n_e:,} px ({p['event_area_km2']} km2) -> {p['event_to_control_ratio']}x control")
    print(f"Polygons >= {MIN_AREA_PX} px: control {summary['map_polygons']['control']}, event {summary['map_polygons']['event']}")
    print("Saved validation/results/control_pair_summary.json and control_vs_event.png")


if __name__ == "__main__":
    main()
