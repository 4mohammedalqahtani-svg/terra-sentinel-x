"""TERRA-SENTINEL X | NISAR GCOV BETA exploratory HH+HV change detection.

Windows CMD, from C:\\Users\\Bassma\\NASA_NISAR:
    conda run -n nisar2 python flood_detection_v2.py

Requires six GeoTIFFs in data/:
    before_HH.tif after_HH.tif before_HV.tif after_HV.tif
    before_mask.tif after_mask.tif

Writes new results_v2/ files. Never overwrites original results/.

CAUTION: Uncalibrated BETA observations; NOT a validated flood map, forecast,
confidence probability, or emergency alert. This specifically detects
open-water-like radar darkening, and may miss flooding beneath vegetation.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from scipy.ndimage import label

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
OUT = ROOT / 'results_v2'
FILES = {
    'before_HH': DATA / 'before_HH.tif',
    'after_HH': DATA / 'after_HH.tif',
    'before_HV': DATA / 'before_HV.tif',
    'after_HV': DATA / 'after_HV.tif',
    'before_mask': DATA / 'before_mask.tif',
    'after_mask': DATA / 'after_mask.tif',
}

NODATA_CLASS = 255
NODATA_FLOAT = -9999.0
MIN_CONNECTED_PIXELS = 9
BEFORE_FLOOR_PERCENTILE = 15
AFTER_LOW_PERCENTILE = 40
# Progressive strictness in HH decrease and HV decrease (dB).
SENSITIVITY_PAIRS_DB = [(2.0, 0.5), (3.0, 1.5), (4.0, 2.5)]


def remove_small_clusters(binary: np.ndarray, minimum: int) -> np.ndarray:
    labels, n = label(binary, structure=np.ones((3, 3), dtype=np.uint8))
    if n == 0:
        return np.zeros(binary.shape, dtype=bool)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= minimum
    keep[0] = False
    return keep[labels]


def save_tif(path: Path, arr: np.ndarray, source_profile: dict, nodata, dtype: str) -> None:
    profile = source_profile.copy()
    # Input rasters often have an alpha as band 2. Output is one-band only.
    for key in ('photometric', 'alpha', 'blockxsize', 'blockysize'):
        profile.pop(key, None)
    profile.update(driver='GTiff', count=1, dtype=dtype, nodata=nodata,
                   compress='deflate', tiled=True)
    with rasterio.open(path, 'w', **profile) as ds:
        ds.write(arr.astype(dtype), 1)


def main() -> None:
    missing = [str(p) for p in FILES.values() if not p.is_file()]
    if missing:
        raise SystemExit('ERROR: Missing input files:\n' + '\n'.join(missing))

    raw = {}
    coverage = {}
    profile = None
    reference = None
    for key, path in FILES.items():
        with rasterio.open(path) as ds:
            if ds.crs is None:
                raise SystemExit(f'ERROR: Missing CRS in {path.name}')
            signature = (ds.width, ds.height, ds.crs, ds.transform)
            if reference is None:
                reference = signature
                profile = ds.profile.copy()
                transform = ds.transform
                print(f'Grid: {ds.width} x {ds.height} | {ds.crs}')
            elif signature != reference:
                raise SystemExit(f'ERROR: Grid mismatch at {path.name}; do NOT compare unaligned pixels.')
            if ds.count < 1:
                raise SystemExit(f'ERROR: No raster band in {path.name}')
            raw[key] = ds.read(1)
            coverage[key] = (ds.dataset_mask() > 0)
            print(f'Loaded {path.name} | {ds.count} bands | {ds.dtypes[0]}')

    for key in ('before_HH', 'after_HH', 'before_HV', 'after_HV'):
        if np.iscomplexobj(raw[key]):
            raise SystemExit(f'ERROR: {key} should be real-valued GCOV diagonal power.')
        raw[key] = raw[key].astype(np.float32)

    # GCOV mask: 0 = invalid/partly focused; 1..N = valid subswath;
    # 255 = outside radar footprint. Band 2 may be output alpha: ignore it.
    mask_before = raw['before_mask']
    mask_after = raw['after_mask']
    common_mask = ((mask_before > 0) & (mask_before < 255)
                   & (mask_after > 0) & (mask_after < 255))
    print(f'Quality mask accepted on both dates: {int(common_mask.sum()):,} pixels')
    for key in ('before_mask', 'after_mask'):
        unique, counts = np.unique(raw[key], return_counts=True)
        print(f'{key} values: {dict(zip(map(int, unique), map(int, counts)))}')

    valid = common_mask.copy()
    for key, power in raw.items():
        valid &= coverage[key]
        if not key.endswith('mask'):
            valid &= np.isfinite(power) & (power > 0)
    valid_count = int(valid.sum())
    total_count = int(valid.size)
    print(f'Usable HH and HV power on both dates: {valid_count:,} / {total_count:,}')
    if valid_count < 100:
        raise SystemExit('ERROR: Fewer than 100 usable pixels; inspect quality masks and power layers.')

    # GCOV HHHH/HVHV are linear *power*, not amplitudes; dB = 10 log10(power).
    db = {}
    for key in ('before_HH', 'after_HH', 'before_HV', 'after_HV'):
        out = np.full(valid.shape, np.nan, dtype=np.float32)
        out[valid] = 10.0 * np.log10(raw[key][valid])
        db[key] = out
    delta_hh = db['after_HH'] - db['before_HH']
    delta_hv = db['after_HV'] - db['before_HV']
    after_low_db = float(np.percentile(db['after_HH'][valid], AFTER_LOW_PERCENTILE))
    before_floor_db = float(np.percentile(db['before_HH'][valid], BEFORE_FLOOR_PERCENTILE))
    print(f'After-HH low threshold: <= {after_low_db:.2f} dB (scene 40th percentile)')
    print(f'Before-HH floor: >= {before_floor_db:.2f} dB (scene 15th percentile)')

    # Open-water-style heuristic: dark HH after the event, decreases in HH/HV,
    # and not already extremely dark before the event.
    scene_filters = (valid & (db['after_HH'] <= after_low_db)
                     & (db['before_HH'] >= before_floor_db))
    candidates_by_threshold = []
    for hh_limit, hv_limit in SENSITIVITY_PAIRS_DB:
        candidate = scene_filters & (delta_hh <= -hh_limit) & (delta_hv <= -hv_limit)
        candidate = remove_small_clusters(candidate, MIN_CONNECTED_PIXELS)
        candidates_by_threshold.append(candidate)
        print(f'HH <= -{hh_limit:g} dB; HV <= -{hv_limit:g} dB: {int(candidate.sum()):,} pixels')

    baseline = candidates_by_threshold[1]
    strict = candidates_by_threshold[2]
    stability = np.zeros(valid.shape, dtype=np.uint8)
    for candidate in candidates_by_threshold:
        stability += candidate.astype(np.uint8)

    area_per_pixel_km2 = abs(transform.a * transform.e - transform.b * transform.d) / 1e6
    area_km2 = float(baseline.sum() * area_per_pixel_km2)
    # Compare to HH-only signal to expose where HV does not support the change.
    hh_only = remove_small_clusters(scene_filters & (delta_hh <= -3.0), MIN_CONNECTED_PIXELS)

    OUT.mkdir(parents=True, exist_ok=True)
    def class_raster(binary):
        out = np.full(valid.shape, NODATA_CLASS, dtype=np.uint8)
        out[valid] = binary[valid].astype(np.uint8)
        return out

    def float_raster(measurement):
        out = np.full(valid.shape, NODATA_FLOAT, dtype=np.float32)
        out[valid] = measurement[valid]
        return out

    save_tif(OUT / 'candidate_joint_HH_HV.tif', class_raster(baseline), profile, NODATA_CLASS, 'uint8')
    save_tif(OUT / 'candidate_HH_only.tif', class_raster(hh_only), profile, NODATA_CLASS, 'uint8')
    save_tif(OUT / 'change_HH_db.tif', float_raster(delta_hh), profile, NODATA_FLOAT, 'float32')
    save_tif(OUT / 'change_HV_db.tif', float_raster(delta_hv), profile, NODATA_FLOAT, 'float32')
    stability_out = np.full(valid.shape, NODATA_CLASS, dtype=np.uint8)
    stability_out[valid] = stability[valid]
    save_tif(OUT / 'smart_doubt_stability.tif', stability_out, profile, NODATA_CLASS, 'uint8')

    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    joint = np.concatenate((db['before_HH'][valid], db['after_HH'][valid]))
    lo, hi = np.percentile(joint, [3, 97])
    if hi <= lo:
        hi = lo + 1
    axes[0, 0].imshow(np.ma.masked_invalid(db['before_HH']), cmap='gray', vmin=lo, vmax=hi)
    axes[0, 0].set_title('HH before | 05 Jan 2026 (dB)')
    axes[0, 1].imshow(np.ma.masked_invalid(db['after_HH']), cmap='gray', vmin=lo, vmax=hi)
    axes[0, 1].set_title('HH after | 17 Jan 2026 (dB)')
    change_im = axes[1, 0].imshow(np.ma.masked_invalid(delta_hh), cmap='RdBu_r', vmin=-6, vmax=6)
    axes[1, 0].set_title('HH change (dB) | after - before')
    fig.colorbar(change_im, ax=axes[1, 0], fraction=0.046, pad=0.02)
    axes[1, 1].imshow(np.ma.masked_invalid(db['after_HH']), cmap='gray', vmin=lo, vmax=hi)
    # Orange overlay only at locations supported by both HH and HV.
    overlay = np.ma.masked_where(~baseline, np.ones(valid.shape, dtype=np.float32))
    axes[1, 1].imshow(overlay, cmap='autumn', vmin=0, vmax=1, alpha=0.75)
    axes[1, 1].set_title('Orange: joint HH+HV candidate | NOT validated flood')
    for ax in axes.flat:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle('TERRA-SENTINEL X | NISAR GCOV BETA | preliminary SAR analysis', fontsize=13)
    fig.savefig(OUT / 'comparison_v2.png', dpi=160, facecolor='white')
    plt.close(fig)

    report = {
        'project': 'TERRA-SENTINEL X',
        'status': 'EXPLORATORY_NOT_VALIDATED',
        'study_area': 'Chokwe, Gaza Province, Mozambique',
        'dates': {'before': '2026-01-05', 'after': '2026-01-17'},
        'source': 'NISAR L2 GCOV BETA V1 HHHH/HVHV and valid-subsample mask',
        'crs': str(reference[2]),
        'pixel_size_m': [abs(float(transform.a)), abs(float(transform.e))],
        'shape_rows_cols': [int(valid.shape[0]), int(valid.shape[1])],
        'valid_pixels_both_dates_and_polarizations': valid_count,
        'valid_coverage_pct': round(100 * valid_count / total_count, 2),
        'masked_out_pixels': total_count - valid_count,
        'HH_and_HV_joint_candidate_pixels': int(baseline.sum()),
        'HH_and_HV_joint_candidate_area_km2_unvalidated': round(area_km2, 3),
        'HH_only_heuristic_pixels': int(hh_only.sum()),
        'sensitivity': {
            'description': 'three relative darkening thresholds; counts are not probabilities',
            'thresholds_HH_decrease_dB_HV_decrease_dB': SENSITIVITY_PAIRS_DB,
            'candidate_counts_relaxed_baseline_strict': [int(v.sum()) for v in candidates_by_threshold],
            'strict_share_of_baseline_pct': round(100 * int(strict.sum()) / max(int(baseline.sum()), 1), 1),
            'stability_raster': 'smart_doubt_stability.tif',
            'stability_value_meaning': {'0': 'no tested thresholds', '1': 'relaxed only', '2': 'relaxed and baseline', '3': 'all three thresholds', '255': 'invalid'},
        },
        'thresholds': {
            'HH_after_low_percentile': AFTER_LOW_PERCENTILE,
            'HH_before_floor_percentile': BEFORE_FLOOR_PERCENTILE,
            'HH_after_low_dB': round(after_low_db, 3),
            'HH_before_floor_dB': round(before_floor_db, 3),
            'min_connected_pixels': MIN_CONNECTED_PIXELS,
        },
        'quality_mask_semantics': 'GCOV subswath mask: 0 invalid; 1..254 valid; 255 outside radar footprint',
        'interpretation': 'Potential open-water-like SAR darkening only, NOT a confirmed or exhaustive flood extent.',
        'limitations': [
            'NISAR GCOV BETA data not yet independently radiometrically validated for this use',
            'Low radar backscatter can reflect non-flood surface changes',
            'HH+HV joint darkening may miss vegetation-covered inundation',
            'All thresholds are heuristic and scene-relative',
            'No independent ground/optical flood reference has been used yet',
            'Smart Doubt is threshold sensitivity, NOT a calibrated probability or model confidence',
            'No prospective forecast is produced',
        ],
        'output_files': [
            'candidate_joint_HH_HV.tif', 'candidate_HH_only.tif',
            'change_HH_db.tif', 'change_HV_db.tif',
            'smart_doubt_stability.tif', 'comparison_v2.png', 'evidence_v2.json',
        ],
    }
    (OUT / 'evidence_v2.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f'\nSUCCESS: HH+HV joint candidate pixels = {int(baseline.sum()):,}')
    print(f'Unvalidated HH+HV candidate area = {area_km2:.3f} km2')
    print(f'Smart Doubt strict share of baseline = {report["sensitivity"]["strict_share_of_baseline_pct"]}%')
    print(f'Saved files in: {OUT}')
    print('IMPORTANT: NOT a confirmed flood footprint. Validate against independent observations.')


if __name__ == '__main__':
    main()
