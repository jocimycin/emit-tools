# EMIT Converter

Convert NASA EMIT `.nc` files to **ENVI** and **GeoTIFF** formats — with a cross-platform GUI for macOS and Windows.

Supports all standard EMIT products:
- L1B Radiance
- L1B Obs
- L2A Reflectance
- L2A Reflectance Uncertainty
- L2A Mask

---

## Requirements

- Python 3.9+
- A [NASA Earthdata](https://urs.earthdata.nasa.gov) account (to download EMIT data)

---

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/jocimycin/emit-tools.git
cd emit-tools
```

**2. Create a virtual environment**

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install numpy xarray netCDF4 rasterio spectral
```

---

## Running the GUI

**macOS** — double-click `launch_mac.command` in Finder, or run:
```bash
bash launch_mac.command
```

**Windows** — double-click `launch_windows.bat`

> On first launch on macOS, right-click → Open if Gatekeeper blocks it.

---

## Using the GUI

![EMIT Converter GUI](docs/screenshot.png)

1. **Add Files** — select one or more `.nc` files, or use **Add Folder** to load all `.nc` files in a directory
2. **Output Directory** — choose where converted files will be saved
3. **Format** — choose `Both`, `ENVI only`, or `GeoTIFF only`
4. **ENVI Interleave** — `BIL` (default), `BIP`, or `BSQ`
5. **Orthorectify** — applies the embedded GLT to produce a georectified output (recommended)
6. **Overwrite** — replace existing output files if checked
7. Click **Convert** — progress and status appear in the log panel

Output is organised automatically:
```
output/
├── envi/
│   ├── EMIT_L2A_RFL_001_*.img
│   └── EMIT_L2A_RFL_001_*.hdr
└── geotiff/
    └── EMIT_L2A_RFL_001_*.tif
```

---

## Command-Line Usage

The converter can also be run without the GUI:

```bash
python3 emit_convert.py <input.nc> <output_dir> [options]
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `both` | `envi`, `geotiff`, or `both` |
| `--ortho` | off | Apply GLT orthorectification |
| `--interleave` | `BIL` | ENVI interleave: `BIL`, `BIP`, or `BSQ` |
| `--overwrite` | off | Overwrite existing output files |

**Examples:**
```bash
# Convert a single file to both formats with orthorectification
python3 emit_convert.py EMIT_L2A_RFL_001_20220903T163129.nc ./output --format both --ortho

# Batch convert a folder
for f in "Armenia Emit"/*.nc; do
  python3 emit_convert.py "$f" ./output --format both --ortho
done

# GeoTIFF only, no orthorectification
python3 emit_convert.py EMIT_L2A_RFL_001_*.nc ./output --format geotiff
```

---

## Output Details

### ENVI
- Flat binary `.img` + `.hdr` header pair
- Wavelength metadata embedded in the header (Nanometers)
- Supports BIL, BIP, BSQ interleave
- Float32 data type

### GeoTIFF
- Tiled, deflate-compressed
- EPSG:4326 (WGS84) georeferenced
- Wavelengths stored as per-band tags
- Float32, NaN nodata

---

## Data Access

EMIT data is available via [NASA Earthdata Search](https://search.earthdata.nasa.gov) or the [LP DAAC Data Pool](https://lpdaac.usgs.gov/data/get-started-data/collection-overview/missions/emit-overview/).

You will need a free NASA Earthdata account to download files.

---

## References

- [LP DAAC EMIT Resources](https://lpdaac.usgs.gov/data/get-started-data/collection-overview/missions/emit-overview/)
- [How to Convert EMIT .nc to ENVI — LP DAAC Tutorial](https://nasa.github.io/LPDAAC-Data-Resources/external/How_to_Convert_to_ENVI.html)
- [emit-sds/emit-utils](https://github.com/emit-sds/emit-utils)
