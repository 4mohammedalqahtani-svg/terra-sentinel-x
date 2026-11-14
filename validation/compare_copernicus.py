"""Exploratory spatial comparison: NISAR 17 Jan 2026 vs Copernicus EMSR857 AOI11 27 Jan.

Run from NASA_NISAR using the nisar2 conda environment.
Requires numpy, rasterio, matplotlib, and osgeo (GDAL bindings).
This is NOT an accuracy/validation test due to different acquisition dates.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import rasterio
from rasterio.features import rasterize
from osgeo import ogr, osr

PROJECT = Path(__file__).resolve().parent
REFERENCE = Path.home() / "Downloads" / "EMSR857_AOI11_GRA_MONIT01_v1"
RESULTS = PROJECT / "results_v2"
CANDIDATE = RESULTS / "candidate_joint_HH_HV.tif"
AFTER = PROJECT / "data" / "after_HH.tif"
BEFORE_MASK = PROJECT / "data" / "before_mask.tif"
AFTER_MASK = PROJECT / "data" / "after_mask.tif"


def matching_shp(fragment: str, required: bool = True) -> Path | None:
    matches = list(REFERENCE.glob(f"*{fragment}*.shp"))
    if not matches:
        if required:
            raise FileNotFoundError(f"Missing {fragment} shapefile in {REFERENCE}")
        return None
    return matches[0]


def projected_geometries(path: Path, target_crs: str, notation: str | None = None):
    ds = ogr.Open(str(path))
    if ds is None:
        raise RuntimeError(f"Cannot open shapefile: {path}")
    layer = ds.GetLayer()
    src_srs = layer.GetSpatialRef()
    if src_srs is None:
        raise ValueError(f"Missing coordinate system for {path.name}")
    source = src_srs.Clone()
    target = osr.SpatialReference()
    if target.SetFromUserInput(target_crs) != 0:
        raise ValueError(f"Unknown target CRS: {target_crs}")
    for s in (source, target):
        s.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transformation = osr.CoordinateTransformation(source, target)
    shapes = []
    selected = 0
    for feature in layer:
        if notation is not None and str(feature.GetField("notation")).strip().lower() != notation.lower():
            continue
        g = feature.GetGeometryRef()
        if g is None or g.IsEmpty():
            continue
        copy = g.Clone()
        if copy.Transform(transformation) != 0:
            continue
        shapes.append((json.loads(copy.ExportToJson()), 1))
        selected += 1
    ds = None
    return shapes, selected


def make_mask(fragment: str, crs: str, shape, transform, required=False, notation=None):
    path = matching_shp(fragment, required=required)
    if path is None:
        return None, 0
    shapes, n = projected_geometries(path, crs, notation=notation)
    if not shapes:
        return np.zeros(shape, dtype=bool), n
    burned = rasterize(shapes, out_shape=shape, transform=transform,
                       fill=0, default_value=1, dtype="uint8", all_touched=False)
    return burned.astype(bool), n


def main():
    for f in (CANDIDATE, AFTER, BEFORE_MASK, AFTER_MASK):
        if not f.is_file():
            raise FileNotFoundError(f"Missing input: {f}")
    if not REFERENCE.is_dir():
        raise FileNotFoundError(f"Missing Copernicus folder: {REFERENCE}")
    with rasterio.open(CANDIDATE) as src:
        candidate_data = src.read(1)
        candidate_nodata = src.nodata
        cand_valid = src.read_masks(1) > 0
        if candidate_nodata is not None:
            cand_valid &= candidate_data != candidate_nodata
        cand_valid &= candidate_data != 255
        candidate = candidate_data == 1
        values = set(int(x) for x in np.unique(candidate_data))
        if not values.issubset({0, 1, 255}):
            raise ValueError(f"Unexpected candidate raster classes: {sorted(values)}")
        shape, transform, crs, res = src.shape, src.transform, src.crs, src.res
        bounds = src.bounds
        if crs is None:
            raise ValueError("Candidate raster has no CRS")
        crs_text = crs.to_string()
    def read_aligned(path):
        with rasterio.open(path) as src:
            if (src.shape != shape or src.transform != transform or src.crs != crs):
                raise ValueError(f"Raster grid differs from candidate: {path.name}")
            return src.read(1)

    # NISAR GCOV subswath masks: 1..254 valid; 0 or 255 invalid.
    mb, ma = read_aligned(BEFORE_MASK), read_aligned(AFTER_MASK)
    radar_valid = (mb >= 1) & (mb <= 254) & (ma >= 1) & (ma <= 254) & cand_valid
    radar_after = read_aligned(AFTER)

    flooded, n_flood = make_mask("observedEventA", crs_text, shape, transform,
                                 required=True, notation="Flooded area")
    aoi, n_aoi = make_mask("areaOfInterestA", crs_text, shape, transform)
    footprint, n_footprint = make_mask("imageFootprintA", crs_text, shape, transform)
    not_analysed, n_not_analysed = make_mask("notAnalysedA", crs_text, shape, transform)

    if aoi is None:
        raise FileNotFoundError("Area of interest shapefile is required for a fair spatial comparison")
    analysed = radar_valid & aoi
    if footprint is not None:
        analysed &= footprint
    if not_analysed is not None:
        analysed &= ~not_analysed
    if not np.any(analysed):
        raise RuntimeError("No overlap with the analyzed Copernicus AOI. Stop; no metrics calculated.")

    ref = flooded & analysed
    pred = candidate & analysed
    both = ref & pred
    px_km2 = abs(res[0] * res[1]) / 1_000_000
    ref_count = int(ref.sum())
    pred_count = int(pred.sum())
    both_count = int(both.sum())
    candidate_share = round(100 * both_count / pred_count, 2) if pred_count else None
    reference_share = round(100 * both_count / ref_count, 2) if ref_count else None

    print("REFERENCE: Copernicus EMSR857 AOI 11 — 27 Jan 2026")
    print("NISAR: HH+HV change — 05 to 17 Jan 2026")
    print("Reference flooded polygons loaded:", n_flood)
    print("AOI features:", n_aoi, "footprints:", n_footprint,
          "not-analyzed geometries:", n_not_analysed)
    print("Analyzed common pixels:", int(analysed.sum()))
    print("Reference flooded pixels in common area:", ref_count)
    print("NISAR candidate pixels in common area:", pred_count)
    print("Intersection pixels:", both_count)
    print("Intersection area (km2):", round(both_count * px_km2, 3))
    print("Share of reference flooded pixels overlapping NISAR (%):", reference_share)
    print("Share of NISAR candidate pixels overlapping reference (%):", candidate_share)
    print("WARNING: 10-day date difference; NOT classification accuracy or ground truth.")

    RESULTS.mkdir(exist_ok=True)
    metrics = {
        "reference": "Copernicus EMSR857 AOI11 Grading Monitoring 1, observedEventA",
        "reference_acquisition_date": "2026-01-27",
        "nisar_after_date": "2026-01-17",
        "comparison": "Exploratory spatial agreement only; NOT validated accuracy",
        "reference_category": "Flooded area only; Flood trace excluded",
        "common_analyzed_pixels": int(analysed.sum()),
        "reference_flooded_pixels": ref_count,
        "nisar_candidate_pixels": pred_count,
        "intersection_pixels": both_count,
        "intersection_km2": round(both_count * px_km2, 4),
        "share_reference_overlapping_nisar_percent": reference_share,
        "share_nisar_overlapping_reference_percent": candidate_share,
        "pixel_area_km2": px_km2,
        "notes": [
            "10-day mismatch between acquisition dates prevents accuracy claims",
            "Only common, analyzed AOI and valid NISAR pixels included",
            "Rasterization uses center-of-pixel criterion",
            "Copernicus Flood trace excluded; only Flooded area included",
            "NISAR BETA change candidates are unvalidated"
        ],
    }
    (RESULTS / "copernicus_spatial_comparison.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Map contextual SAR and overlays; zoom to analyzed AOI.
    backscatter = np.full(shape, np.nan, dtype=np.float32)
    ok = radar_valid & np.isfinite(radar_after) & (radar_after > 0)
    backscatter[ok] = 10 * np.log10(radar_after[ok])
    finite = backscatter[np.isfinite(backscatter)]
    if finite.size:
        vmin, vmax = np.percentile(finite, (3, 97))
    else:
        vmin, vmax = -25.0, 0.0
    fig, ax = plt.subplots(figsize=(11, 7.3))
    ax.imshow(backscatter, cmap="gray", vmin=vmin, vmax=vmax,
              interpolation="nearest")
    # Render three disjoint classes over the same grid.
    ref_only = ref & ~pred
    pred_only = pred & ~ref
    rgba = np.zeros((*shape, 4), dtype=np.float32)
    rgba[ref_only] = [0.0, 0.95, 1.0, 0.80]   # cyan: Copernicus only
    rgba[pred_only] = [1.0, 0.85, 0.0, 0.80]  # yellow: NISAR only
    rgba[both] = [1.0, 0.15, 0.70, 0.93]      # magenta: spatial intersection
    ax.imshow(rgba, interpolation="nearest")
    ys, xs = np.where(aoi)
    if xs.size:
        pad = 22
        ax.set_xlim(max(0, xs.min() - pad), min(shape[1], xs.max() + pad))
        ax.set_ylim(min(shape[0], ys.max() + pad), max(0, ys.min() - pad))
    ax.set_title("NISAR (17 Jan) vs Copernicus EMSR857 (27 Jan) | AOI11", fontsize=12)
    ax.set_xlabel("Raster columns")
    ax.set_ylabel("Raster rows")
    ax.legend(handles=[
        Patch(facecolor="#00f2ff", label="Copernicus flooded area only"),
        Patch(facecolor="#ffda00", label="NISAR candidate only"),
        Patch(facecolor="#ff26b3", label="Spatial overlap")
    ], loc="lower right", framealpha=0.87, fontsize=9)
    fig.text(0.5, 0.01, "Exploratory spatial agreement only — 10-day acquisition gap; NOT accuracy",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    destination = RESULTS / "copernicus_overlay.png"
    fig.savefig(destination, dpi=175)
    plt.close(fig)
    print("SAVED:", destination)
    print("SAVED:", RESULTS / "copernicus_spatial_comparison.json")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
