"""TERRA-SENTINEL X | NISAR GCOV BETA extraction for Windows, GDAL 3.12.

Reads NISAR's own xCoordinates, yCoordinates, and projection directly from
HDF5, attaches the correct geometry to a virtual raster (VRT), and then crops
and exports GeoTIFF. No GDAL 3.13 upgrade or netCDF Windows /vsicurl support
is needed. Requires an existing authorized Earthdata ~/.netrc.

Quick start (CMD, activated nisar2 environment):
    python nisar_extract_v3.py before
    python nisar_extract_v3.py after
    python nisar_extract_v3.py check
Optional: --layer HV or --layer mask; --resolution 30 (metres)

BETA observations are not an operational/validated flood product.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
OUT = PROJECT / "data"
SCENES = {
    "before": "NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001",
    "after": "NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001",
}
BASE = "https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_BETA_V1"
GROUP_PATH = ["science", "LSAR", "GCOV", "grids", "frequencyA"]
CHANNELS = {"HH": "HHHH", "HV": "HVHV", "mask": "mask"}
AOI = "POLYGON((32.6656 -24.735,33.3124 -24.735,33.3124 -24.399,32.6656 -24.399,32.6656 -24.735))"


def data_url(scene):
    name = SCENES[scene]
    return f"{BASE}/{name}/{name}.h5"


def configure_gdal(gdal):
    if not (Path.home() / ".netrc").is_file():
        raise RuntimeError("Earthdata .netrc file was not found in your Windows home folder")
    cookie = str(Path(os.environ.get("TEMP", str(PROJECT))) / "nisar_cookies.txt")
    opts = {
        "GDAL_HTTP_NETRC": "YES",
        "GDAL_HTTP_COOKIEFILE": cookie,
        "GDAL_HTTP_COOKIEJAR": cookie,
        "GDAL_DISABLE_READDIR_ON_OPEN": "TRUE",
        "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
        "GDAL_HTTP_MULTIPLEX": "YES",
        "CPL_VSIL_CURL_CHUNK_SIZE": "2097152",
        "CPL_VSIL_CURL_CACHE_SIZE": "67108864",
    }
    for key, value in opts.items():
        gdal.SetConfigOption(key, value)


def frequency_group(root):
    group = root.GetRootGroup()
    if group is None:
        raise RuntimeError("HDF5 multidimensional root group could not be opened")
    for part in GROUP_PATH:
        group = group.OpenGroup(part)
        if group is None:
            raise RuntimeError(f"NISAR HDF5 group not found: {part}")
    return group


def get_geometry(gdal, path):
    # The native GCOV HDF5 raster in GDAL 3.12 does not expose its CF grid
    # mapping automatically. Recover it from the product's own arrays.
    container = gdal.OpenEx(path, gdal.OF_MULTIDIM_RASTER, allowed_drivers=["HDF5"])
    if container is None:
        raise RuntimeError("NISAR HDF5 container could not be opened; check network/Earthdata access")
    group = frequency_group(container)
    x = group.OpenMDArray("xCoordinates")
    y = group.OpenMDArray("yCoordinates")
    projection = group.OpenMDArray("projection")
    if x is None or y is None or projection is None:
        raise RuntimeError("NISAR coordinate/projection arrays missing")
    if len(x.GetShape()) != 1 or len(y.GetShape()) != 1:
        raise RuntimeError("Unexpected NISAR x/y coordinate dimensions")
    xv = x.ReadAsArray(array_start_idx=[0], count=[2])
    yv = y.ReadAsArray(array_start_idx=[0], count=[2])
    if xv is None or yv is None or len(xv) != 2 or len(yv) != 2:
        raise RuntimeError("Could not read NISAR grid axes")
    x0, x1 = float(xv[0]), float(xv[1])
    y0, y1 = float(yv[0]), float(yv[1])
    dx, dy = x1 - x0, y1 - y0
    if dx <= 0 or dy >= 0 or not (1 <= abs(dx) <= 1000 and 1 <= abs(dy) <= 1000):
        raise RuntimeError(f"Unexpected NISAR pixel spacing: dx={dx}; dy={dy}")

    # In GCOV, the projection dataset stores its EPSG code; confirm it from
    # the file rather than assuming a Mozambique-specific EPSG identifier.
    epsg_array = projection.ReadAsArray()
    if epsg_array is None:
        raise RuntimeError("Could not read NISAR projection EPSG code")
    epsg = int(epsg_array)
    if not (2000 <= epsg <= 999999):
        raise RuntimeError(f"Unexpected projection identifier: {epsg}")

    # x/y arrays describe pixel centres; GDAL requires the upper-left corner.
    transform = (x0 - dx / 2, dx, 0.0, y0 - dy / 2, 0.0, dy)
    shape = (int(y.GetShape()[0]), int(x.GetShape()[0]))
    print(f"Native grid: {shape[1]} columns x {shape[0]} rows")
    print(f"Native projection: EPSG:{epsg}; native spacing: {dx:g} x {dy:g} metres")
    return epsg, transform, shape


def extract(gdal, osr, scene, layer, resolution):
    OUT.mkdir(exist_ok=True, parents=True)
    target = OUT / f"{scene}_{layer}.tif"
    if target.exists() and target.stat().st_size:
        ds = None
        try:
            ds = gdal.Open(str(target), gdal.GA_ReadOnly)
        except Exception:
            pass
        if ds is not None and ds.RasterXSize > 0 and ds.RasterYSize > 0 and ds.GetProjection():
            print(f"ALREADY PRESENT: {target}; verify contents using the 'check' action")
            ds = None
            return True
        raise RuntimeError(f"Existing output appears incomplete; inspect before retrying: {target}")

    url = data_url(scene)
    remote_file = "/vsicurl/" + url
    print(f"\nWorking on: {scene} / {layer}", flush=True)
    print("Reading NISAR projection and coordinates from HDF5 (this may take time)...", flush=True)
    epsg, transform, shape = get_geometry(gdal, remote_file)

    variable = CHANNELS[layer]
    sub_name = f'HDF5:"{remote_file}"://science/LSAR/GCOV/grids/frequencyA/{variable}'
    source = gdal.Open(sub_name, gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError(f"Could not open NISAR variable {variable}")
    if (source.RasterYSize, source.RasterXSize) != shape:
        raise RuntimeError("Raster dimensions disagree with NISAR coordinates; aborting")

    srs = osr.SpatialReference()
    if srs.ImportFromEPSG(epsg) != 0:
        raise RuntimeError(f"EPSG:{epsg} could not be read by GDAL")
    vrt_file = f"/vsimem/terra_{scene}_{layer}.vrt"
    vrt = None
    try:
        vrt = gdal.Translate(vrt_file, source, format="VRT")
        if vrt is None:
            raise RuntimeError("GDAL could not create a temporary VRT")
        if vrt.SetGeoTransform(transform) != 0 or vrt.SetSpatialRef(srs) != 0:
            raise RuntimeError("GDAL could not assign source georeferencing")
        # Read-only original data; only metadata in the virtual wrapper changes.
        print(f"Source CRS attached to virtual raster: EPSG:{epsg}", flush=True)
        print(f"Saving crop at {resolution:g} m resolution: {target}", flush=True)
        opts = gdal.WarpOptions(
            format="GTiff",
            creationOptions=["TILED=YES", "COMPRESS=DEFLATE", "PREDICTOR=2"],
            cutlineWKT=AOI,
            cutlineSRS="EPSG:4326",
            cropToCutline=True,
            dstSRS=f"EPSG:{epsg}",
            xRes=resolution,
            yRes=resolution,
            resampleAlg="near",
            dstAlpha=True,
            multithread=False,
        )
        result = gdal.Warp(str(target), vrt, options=opts)
        if result is None:
            raise RuntimeError("GDAL warp returned no raster")
        result.FlushCache()
        print(f"Output size: {result.RasterXSize} x {result.RasterYSize}")
        result = None
    finally:
        vrt = None
        source = None
        gdal.Unlink(vrt_file)

    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("GeoTIFF not created")
    check_ds = gdal.Open(str(target), gdal.GA_ReadOnly)
    if check_ds is None or not check_ds.GetProjection():
        raise RuntimeError("Output GeoTIFF is invalid or has no spatial reference")
    check_ds = None
    print(f"SUCCESS: {target.name} ({target.stat().st_size / 1048576:.1f} MiB)")
    return True


def check():
    import rasterio
    grid = {}
    for name in ("before", "after"):
        target = OUT / f"{name}_HH.tif"
        if not target.exists():
            print(f"MISSING: {target.name}")
            continue
        with rasterio.open(target) as ds:
            print(f"{name}: {ds.width} x {ds.height}, CRS={ds.crs}, bands={ds.count}")
            print(f"  Bounds: {ds.bounds}")
            grid[name] = (ds.crs, ds.transform, ds.width, ds.height)
    if len(grid) == 2:
        print("SAME GRID:", "YES" if grid["before"] == grid["after"] else "NO - align before comparison")
    print("BETA data: not calibrated/validated flood boundaries; apply data masks and independent checks.")


def main():
    p = argparse.ArgumentParser(description="NISAR GCOV HDF5 georeferenced subset for GDAL 3.12")
    p.add_argument("action", choices=("before", "after", "both", "check"))
    p.add_argument("--layer", choices=tuple(CHANNELS), default="HH")
    p.add_argument("--resolution", type=float, default=60, help="Output metres/pixel; default 60 for faster prototype")
    args = p.parse_args()
    if args.action == "check":
        check()
        return
    if not 10 <= args.resolution <= 500:
        p.error("Output resolution must be 10 to 500 metres")
    from osgeo import gdal, osr
    gdal.UseExceptions()
    if gdal.GetDriverByName("HDF5") is None:
        raise SystemExit("ERROR: HDF5 GDAL driver unavailable in current environment")
    configure_gdal(gdal)
    print("GDAL:", gdal.VersionInfo("--version"))
    for name in (("before", "after") if args.action == "both" else (args.action,)):
        try:
            extract(gdal, osr, name, args.layer, args.resolution)
        except Exception as e:
            print(f"ERROR: {e}")
            print("Do not use an incomplete output; share this error only, never Earthdata credentials.")
            sys.exit(1)
    if args.layer == "HH":
        check()


if __name__ == "__main__":
    main()
