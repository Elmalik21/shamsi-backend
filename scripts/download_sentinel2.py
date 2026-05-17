"""
scripts/download_sentinel2.py
==============================
Sentinel-2 satellite imagery download guide and validator for Egyptian roof detection.

This script does NOT download images automatically (Copernicus Hub requires
manual authentication + scene selection). Instead it:
  1. Prints a step-by-step guide for downloading Sentinel-2 TCI GeoTIFFs
     covering Egyptian cities via the Copernicus Browser.
  2. Validates already-downloaded GeoTIFF files (checks resolution, bands,
     CRS, coverage of Egyptian bounding box).

Usage
-----
    # Print download guide:
    python scripts/download_sentinel2.py --guide

    # Validate downloaded GeoTIFFs in a folder:
    python scripts/download_sentinel2.py --validate data/sentinel2/

    # Validate and show detailed per-file info:
    python scripts/download_sentinel2.py --validate data/sentinel2/ --verbose

    # List recommended tiles for Egypt coverage:
    python scripts/download_sentinel2.py --tiles

Expected GeoTIFF format
-----------------------
    Band       : TCI (True Colour Image, 3-band RGB)
    Resolution : 10 m/pixel
    CRS        : EPSG:32636 or EPSG:32637 (UTM Zone 36N / 37N)
    File size  : ~200–800 MB per full granule
    Naming     : *_TCI_10m.tif  or  *B02*.tif / *B03*.tif / *B04*.tif

Egyptian UTM Tiles (MGRS)
--------------------------
    36RUU, 36RUT, 36RUS  — Nile Delta / Cairo
    36RVU, 36RVT, 36RVS  — Cairo / Middle Egypt
    36QVL, 36QVK          — Upper Egypt
    36PVH, 36PUH          — Aswan / Deep South
    37RBL, 37QBK          — Sinai / Red Sea coast
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Egyptian bounding box (WGS84)
EGYPT_BBOX = {
    'min_lon': 24.7,
    'max_lon': 37.0,
    'min_lat': 21.9,
    'max_lat': 31.7,
}

# Recommended MGRS tiles for broad Egypt coverage
EGYPT_TILES = [
    ('36RUU', 'Nile Delta (Alexandria, Damietta)'),
    ('36RUT', 'Cairo / Giza'),
    ('36RUS', 'Suez Canal region'),
    ('36RVU', 'Nile Delta east'),
    ('36RVT', 'Cairo surroundings'),
    ('36QVL', 'Middle Egypt (Minya, Asyut)'),
    ('36QVK', 'Upper Egypt (Sohag, Qena)'),
    ('36PVH', 'Luxor / Aswan area'),
    ('36PUH', 'Deep south (Abu Simbel)'),
    ('37RBL', 'Sinai Peninsula'),
    ('37QBK', 'Red Sea coast (Hurghada)'),
]


# ─────────────────────────────────────────────────────────────────────────────

def show_guide() -> None:
    """Print the step-by-step Sentinel-2 download guide."""
    guide = """
╔══════════════════════════════════════════════════════════════════════════╗
║          Shamsi Smart — Sentinel-2 Download Guide (Egypt)               ║
╚══════════════════════════════════════════════════════════════════════════╝

STEP 1 — Create a free Copernicus account
─────────────────────────────────────────
  1. Go to https://browser.dataspace.copernicus.eu/
  2. Click "Register" → fill in your details → confirm email.
  3. Log in.

STEP 2 — Search for Egyptian tiles
───────────────────────────────────
  1. In the search box, type a city name (e.g. "Cairo") OR manually
     pan the map to Egypt.
  2. Set filters:
       • Data source : Sentinel-2
       • Product type: S2MSI2A  (Level-2A, atmospherically corrected)
       • Cloud cover : 0%–10%
       • Date range  : 2022-01-01 → 2024-12-31  (pick cloud-free summer months)
  3. Click "Search".

STEP 3 — Select and download GeoTIFF
──────────────────────────────────────
  1. In the results panel, click a scene thumbnail.
  2. Click "Visualize" to check it looks good (no clouds over cities).
  3. Click the download icon → "Product download" → choose:
       • Format : GeoTIFF
       • Band   : TCI (True Colour Image, RGB composite at 10 m)
  4. Save to:  datasets/sentinel2/raw/<TILE_ID>_TCI.tif

  Alternative: Download individual bands for false-colour analysis
       • B02 (Blue, 10m), B03 (Green, 10m), B04 (Red, 10m)

STEP 4 — Recommended tiles for training diversity
──────────────────────────────────────────────────
  Download at least one scene per tile listed below.
  Run:  python scripts/download_sentinel2.py --tiles

STEP 5 — Validate downloads
────────────────────────────
  python scripts/download_sentinel2.py --validate datasets/sentinel2/raw/

STEP 6 — Extract roof tiles
────────────────────────────
  python scripts/extract_roofs_from_geotiff.py \\
      --input  datasets/sentinel2/raw/ \\
      --output datasets/egyptian_roofs/images/train/ \\
      --tile-size 640 --stride 320

STEP 7 — Auto-annotate with SAM
─────────────────────────────────
  python scripts/semi_auto_annotate.py \\
      --images datasets/egyptian_roofs/images/train/ \\
      --output datasets/egyptian_roofs/labels/train/ \\
      --sam-checkpoint ai_engine/models/sam_vit_h.pth

STEP 8 — Train YOLOv8
──────────────────────
  python scripts/train_yolov8_roof.py --device 0 --epochs 100 --copy-best

══════════════════════════════════════════════════════════════════════════════
  Alternative: Use the Sentinel Hub EO Browser API (requires API key)
  pip install sentinelhub
  See: https://sentinelhub-py.readthedocs.io/
══════════════════════════════════════════════════════════════════════════════
"""
    print(guide)


def list_tiles() -> None:
    """Print recommended MGRS tiles for Egypt."""
    print("\n  Recommended Sentinel-2 MGRS Tiles for Egypt")
    print("  " + "─" * 55)
    for tile, desc in EGYPT_TILES:
        print(f"  {tile:<8}  {desc}")
    print()
    print("  Total tiles:  ", len(EGYPT_TILES))
    print("  Coverage:      Nile Valley, Delta, Sinai, Red Sea coast")
    print("  At 10m/pixel:  1 granule ≈ 100 km × 100 km")
    print()


def validate_downloads(folder: str, verbose: bool = False) -> bool:
    """
    Validate GeoTIFF files in *folder*.

    Checks:
      - File is a valid GeoTIFF (rasterio can open it)
      - Resolution is ≤ 15 m/pixel (warns if coarser)
      - Has 3 or 4 bands
      - CRS is defined
      - Bounding box overlaps Egypt

    Returns True if all files pass.
    """
    try:
        import rasterio
        from rasterio.crs import CRS
    except ImportError:
        print(
            "\n  [ERROR] rasterio is not installed.\n"
            "  Install with:  pip install rasterio\n"
        )
        return False

    folder_path = Path(folder)
    if not folder_path.exists():
        print(f"\n  [ERROR] Folder not found: {folder}")
        return False

    tif_files = (
        list(folder_path.glob('**/*.tif')) +
        list(folder_path.glob('**/*.tiff')) +
        list(folder_path.glob('**/*.TIF')) +
        list(folder_path.glob('**/*.TIFF'))
    )

    if not tif_files:
        print(f"\n  [WARNING] No GeoTIFF files found in: {folder}")
        print("  Expected files matching: *.tif / *.tiff")
        return False

    print(f"\n  Validating {len(tif_files)} GeoTIFF file(s) in: {folder}\n")
    all_ok = True

    for tif in sorted(tif_files):
        status = '✅'
        issues = []

        try:
            with rasterio.open(str(tif)) as src:
                width      = src.width
                height     = src.height
                bands      = src.count
                crs        = src.crs
                transform  = src.transform
                res_x      = abs(transform.a)   # metres per pixel (x)
                res_y      = abs(transform.e)   # metres per pixel (y)

                # Get bounds in WGS84
                from rasterio.warp import transform_bounds
                if crs and not crs.is_geographic:
                    wgs84 = CRS.from_epsg(4326)
                    bounds = transform_bounds(crs, wgs84, *src.bounds)
                else:
                    bounds = src.bounds  # already geographic

                min_lon, min_lat, max_lon, max_lat = bounds

                # ── Checks ────────────────────────────────────────────────────
                if bands < 3:
                    issues.append(f"Only {bands} band(s) — need ≥3 (RGB)")
                if res_x > 15:
                    issues.append(f"Coarse resolution {res_x:.1f} m/px — target 10 m")
                if crs is None:
                    issues.append("No CRS defined")

                # Check overlap with Egypt
                overlaps_egypt = (
                    min_lon < EGYPT_BBOX['max_lon'] and
                    max_lon > EGYPT_BBOX['min_lon'] and
                    min_lat < EGYPT_BBOX['max_lat'] and
                    max_lat > EGYPT_BBOX['min_lat']
                )
                if not overlaps_egypt:
                    issues.append(
                        f"Does not overlap Egypt "
                        f"(bounds: {min_lon:.2f}°E–{max_lon:.2f}°E, "
                        f"{min_lat:.2f}°N–{max_lat:.2f}°N)"
                    )

                if issues:
                    status = '⚠️ '
                    all_ok = False

                size_mb = tif.stat().st_size / 1_048_576

                if verbose or issues:
                    print(f"  {status} {tif.name}")
                    print(f"       Size   : {size_mb:.1f} MB")
                    print(f"       Dims   : {width} × {height} px  ({bands} bands)")
                    print(f"       Res    : {res_x:.1f} × {res_y:.1f} m/px")
                    print(f"       CRS    : {crs.to_string() if crs else 'None'}")
                    print(f"       Bounds : {min_lon:.3f}°E – {max_lon:.3f}°E, "
                          f"{min_lat:.3f}°N – {max_lat:.3f}°N")
                    for issue in issues:
                        print(f"       ⚠  {issue}")
                    print()
                else:
                    print(f"  {status} {tif.name:<50}  {size_mb:7.1f} MB  "
                          f"{res_x:.0f}m  {bands}b")

        except Exception as exc:
            status = '❌'
            all_ok = False
            print(f"  {status} {tif.name}")
            print(f"       ERROR: {exc}")
            print()

    print()
    if all_ok:
        print("  ✅  All files passed validation.")
    else:
        print("  ⚠️   Some files have issues — see above.")
    print()
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Sentinel-2 download guide and GeoTIFF validator for Egyptian roof detection'
    )
    p.add_argument('--guide',    action='store_true',
                   help='Print step-by-step Sentinel-2 download guide')
    p.add_argument('--tiles',    action='store_true',
                   help='List recommended MGRS tiles for Egypt')
    p.add_argument('--validate', type=str, metavar='FOLDER',
                   help='Validate GeoTIFF files in FOLDER')
    p.add_argument('--verbose',  action='store_true',
                   help='Show detailed per-file info during validation')
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not any([args.guide, args.tiles, args.validate]):
        # Default: show guide
        show_guide()
        list_tiles()
        return

    if args.guide:
        show_guide()

    if args.tiles:
        list_tiles()

    if args.validate:
        ok = validate_downloads(args.validate, verbose=args.verbose)
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
