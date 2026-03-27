#!/usr/bin/env python3
"""
EMIT .nc → ENVI + GeoTIFF converter

Supports:
  - L1B Radiance
  - L1B Obs
  - L2A Reflectance
  - L2A Reflectance Uncertainty
  - L2A Mask

Usage:
  python emit_convert.py <input.nc> <output_dir> [--format envi|geotiff|both] [--ortho] [--interleave BIL|BIP|BSQ]

Examples:
  python emit_convert.py EMIT_L2A_RFL_001_*.nc ./output --format both --ortho
  python emit_convert.py EMIT_L2A_RFL_001_*.nc ./output/envi --format envi
  python emit_convert.py EMIT_L2A_RFL_001_*.nc ./output/tif --format geotiff --ortho
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_deps():
    missing = []
    for pkg in ("numpy", "xarray", "netCDF4", "rasterio", "spectral"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[ERROR] Missing packages: {', '.join(missing)}")
        print("Install with:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)

check_deps()

import numpy as np
import xarray as xr
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

# ---------------------------------------------------------------------------
# emit_tools (inline — no external dependency needed)
# Based on the LP DAAC emit_tools module
# ---------------------------------------------------------------------------

def emit_xarray(filepath: str, ortho: bool = False) -> xr.Dataset:
    """
    Open an EMIT .nc file and return an xarray Dataset.
    Optionally orthorectify using the embedded GLT.
    """
    ds = xr.open_dataset(filepath, engine="netcdf4")

    # Merge location group if present (coordinates stored separately in /location)
    try:
        loc = xr.open_dataset(filepath, engine="netcdf4", group="location")
        ds = ds.assign_coords(
            latitude=(["downtrack", "crosstrack"], loc["lat"].values),
            longitude=(["downtrack", "crosstrack"], loc["lon"].values),
        )
    except Exception:
        pass  # location group absent in some products

    if ortho:
        ds = orthorectify(ds, filepath)

    return ds


def orthorectify(ds: xr.Dataset, filepath: str) -> xr.Dataset:
    """Apply the GLT (geographic lookup table) embedded in the .nc file."""
    try:
        glt_ds = xr.open_dataset(filepath, engine="netcdf4", group="location")
        glt_x = glt_ds["glt_x"].values.astype(int)
        glt_y = glt_ds["glt_y"].values.astype(int)
    except Exception as e:
        print(f"[WARN] Could not read GLT — skipping orthorectification: {e}")
        return ds

    valid = (glt_x > 0) & (glt_y > 0)

    ortho_vars = {}
    for var in ds.data_vars:
        data = ds[var].values
        if data.ndim < 2:
            ortho_vars[var] = ds[var]
            continue

        # Determine band axis (assumes downtrack × crosstrack × bands OR downtrack × crosstrack)
        if data.ndim == 3:
            out = np.full((glt_x.shape[0], glt_x.shape[1], data.shape[2]), np.nan, dtype=np.float32)
            out[valid] = data[glt_y[valid] - 1, glt_x[valid] - 1, :]
            ortho_vars[var] = xr.DataArray(out, dims=["latitude", "longitude", ds[var].dims[-1]])
        else:
            out = np.full((glt_x.shape[0], glt_x.shape[1]), np.nan, dtype=np.float32)
            out[valid] = data[glt_y[valid] - 1, glt_x[valid] - 1]
            ortho_vars[var] = xr.DataArray(out, dims=["latitude", "longitude"])

    return xr.Dataset(ortho_vars, attrs=ds.attrs)


# ---------------------------------------------------------------------------
# ENVI writer
# ---------------------------------------------------------------------------

def write_envi(ds: xr.Dataset, outpath: str, stem: str = "", interleave: str = "BIL", overwrite: bool = False):
    """
    Write each data variable in the Dataset to an ENVI flat-binary file
    with an accompanying .hdr header.
    """
    import spectral.io.envi as envi

    os.makedirs(outpath, exist_ok=True)

    for var in ds.data_vars:
        data = ds[var].values.astype(np.float32)

        if data.ndim == 2:
            # Treat as single-band — add band axis
            data = data[:, :, np.newaxis]

        if data.ndim != 3:
            print(f"[SKIP] {var}: unexpected shape {data.shape}")
            continue

        rows, cols, bands = data.shape

        base = stem if stem else var
        out_img = os.path.join(outpath, f"{base}.img")
        out_hdr = os.path.join(outpath, f"{base}.hdr")

        if os.path.isfile(out_img) and not overwrite:
            print(f"[SKIP] {out_img} already exists (use --overwrite to replace)")
            continue

        # Build wavelength list from coords if available
        wavelengths = None
        band_dim = ds[var].dims[-1] if len(ds[var].dims) == 3 else None
        if band_dim and band_dim in ds.coords:
            wavelengths = ds.coords[band_dim].values.tolist()

        metadata = {
            "lines": rows,
            "samples": cols,
            "bands": bands,
            "interleave": interleave.lower(),
            "data type": 4,  # float32
            "byte order": 0,
        }
        if wavelengths:
            metadata["wavelength"] = wavelengths
            metadata["wavelength units"] = "Nanometers"

        # Rearrange to requested interleave
        if interleave.upper() == "BIL":
            out_data = np.transpose(data, (0, 2, 1))  # rows × bands × cols
        elif interleave.upper() == "BSQ":
            out_data = np.transpose(data, (2, 0, 1))  # bands × rows × cols
        else:  # BIP
            out_data = data  # rows × cols × bands

        envi.save_image(out_hdr, out_data, metadata=metadata, force=overwrite)
        print(f"[ENVI] Written: {out_img}")


# ---------------------------------------------------------------------------
# GeoTIFF writer
# ---------------------------------------------------------------------------

def write_geotiff(ds: xr.Dataset, outpath: str, stem: str = "", overwrite: bool = False):
    """
    Write each data variable to a multi-band Cloud-Optimised GeoTIFF.
    Requires latitude/longitude coordinates on the dataset.
    """
    os.makedirs(outpath, exist_ok=True)

    # Determine geographic extent
    has_coords = "latitude" in ds.coords and "longitude" in ds.coords
    if not has_coords:
        # Try to pull lat/lon from data vars
        lat = ds.get("lat", ds.get("latitude", None))
        lon = ds.get("lon", ds.get("longitude", None))
        if lat is not None and lon is not None:
            ds = ds.assign_coords(latitude=lat, longitude=lon)
            has_coords = True

    if has_coords:
        lats = ds.coords["latitude"].values
        lons = ds.coords["longitude"].values
        south, north = float(np.nanmin(lats)), float(np.nanmax(lats))
        west, east   = float(np.nanmin(lons)), float(np.nanmax(lons))
        crs = CRS.from_epsg(4326)
    else:
        print("[WARN] No spatial coordinates found — GeoTIFF will have no georeference.")
        south, north, west, east = 0, 1, 0, 1
        crs = None

    for var in ds.data_vars:
        if var in ("lat", "lon", "latitude", "longitude", "glt_x", "glt_y", "elev"):
            continue

        data = ds[var].values.astype(np.float32)

        if data.ndim == 2:
            data = data[np.newaxis, :, :]   # 1 × rows × cols
        elif data.ndim == 3:
            data = np.transpose(data, (2, 0, 1))  # bands × rows × cols
        else:
            print(f"[SKIP] {var}: unexpected shape {data.shape}")
            continue

        bands, rows, cols = data.shape
        base = stem if stem else var
        out_tif = os.path.join(outpath, f"{base}.tif")

        if os.path.isfile(out_tif) and not overwrite:
            print(f"[SKIP] {out_tif} already exists (use --overwrite to replace)")
            continue

        transform = from_bounds(west, south, east, north, cols, rows)

        profile = {
            "driver":    "GTiff",
            "dtype":     "float32",
            "width":     cols,
            "height":    rows,
            "count":     bands,
            "nodata":    np.nan,
            "compress":  "deflate",
            "predictor": 3,        # floating-point predictor
            "tiled":     True,
            "blockxsize": 256,
            "blockysize": 256,
        }
        if transform:
            profile["transform"] = transform
        if crs:
            profile["crs"] = crs

        with rasterio.open(out_tif, "w", **profile) as dst:
            dst.write(data)

            # Store wavelengths as band descriptions if available
            band_dim = ds[var].dims[-1] if len(ds[var].dims) == 3 else None
            if band_dim and band_dim in ds.coords:
                wavs = ds.coords[band_dim].values
                for i, w in enumerate(wavs, 1):
                    dst.update_tags(i, wavelength_nm=f"{w:.4f}")

        print(f"[GeoTIFF] Written: {out_tif}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Convert EMIT .nc files to ENVI and/or GeoTIFF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input", help="Path to EMIT .nc file")
    p.add_argument("output_dir", help="Output directory")
    p.add_argument(
        "--format", choices=["envi", "geotiff", "both"], default="both",
        help="Output format (default: both)",
    )
    p.add_argument(
        "--ortho", action="store_true",
        help="Orthorectify using embedded GLT",
    )
    p.add_argument(
        "--interleave", choices=["BIL", "BIP", "BSQ"], default="BIL",
        help="ENVI interleave format (default: BIL)",
    )
    p.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing output files",
    )
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(args.input):
        print(f"[ERROR] Input file not found: {args.input}")
        sys.exit(1)

    print(f"[INFO] Loading: {args.input}")
    ds = emit_xarray(args.input, ortho=args.ortho)
    print(f"[INFO] Variables: {list(ds.data_vars)}")

    stem = os.path.splitext(os.path.basename(args.input))[0]
    fmt = args.format

    if fmt in ("envi", "both"):
        envi_dir = os.path.join(args.output_dir, "envi") if fmt == "both" else args.output_dir
        print(f"\n[INFO] Writing ENVI → {envi_dir}")
        write_envi(ds, envi_dir, stem=stem, interleave=args.interleave, overwrite=args.overwrite)

    if fmt in ("geotiff", "both"):
        tif_dir = os.path.join(args.output_dir, "geotiff") if fmt == "both" else args.output_dir
        print(f"\n[INFO] Writing GeoTIFF → {tif_dir}")
        write_geotiff(ds, tif_dir, stem=stem, overwrite=args.overwrite)

    print("\n[DONE]")


if __name__ == "__main__":
    main()
