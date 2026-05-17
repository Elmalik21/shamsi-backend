"""
scripts/extract_roofs_from_geotiff.py
=======================================
Extract 640×640 px training tiles from Sentinel-2 GeoTIFF files for
YOLOv8 roof detection training.

Reads multi-band GeoTIFF files (Sentinel-2 TCI at 10 m/pixel) and produces
JPEG/PNG tiles ready for annotation and YOLO training.

Usage
-----
    # Extract tiles from all GeoTIFFs in a folder:
    python scripts/extract_roofs_from_geotiff.py \\
        --input  datasets/sentinel2/raw/ \\
        --output datasets/egyptian_roofs/images/train/ \\
        --tile-size 640 --stride 320

    # Extract with 80/20 train/val split:
    python scripts/extract_roofs_from_geotiff.py \\
        --input  datasets/sentinel2/raw/ \\
        --output datasets/egyptian_roofs/ \\
        --tile-size 640 --stride 320 --split 0.8

    # Extract from a single file, skip dark tiles:
    python scripts/extract_roofs_from_geotiff.py \\
        --input  datasets/sentinel2/raw/cairo_TCI.tif \\
        --output datasets/egyptian_roofs/images/train/ \\
        --min-brightness 30

    # Dry run — count tiles without writing:
    python scripts/extract_roofs_from_geotiff.py \\
        --input  datasets/sentinel2/raw/ --dry-run

Notes
-----
  - Requires: rasterio, numpy, Pillow (pip install rasterio Pillow)
  - Tiles darker than --min-brightness (mean DN < threshold) are skipped
    (e.g. cloud edges, black nodata borders).
  - Stride < tile-size creates overlapping tiles (data augmentation effect).
  - When --split is used, output must be a directory; train/ and val/
    subdirectories are created automatically.
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────

def find_geotiff_files(input_path: str) -> List[Path]:
    """
    Return all GeoTIFF files under *input_path* (file or directory).

    Parameters
    ----------
    input_path : str   Path to a .tif file OR a directory.

    Returns
    -------
    List[Path]  Sorted list of .tif / .tiff paths found.
    """
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        tifs = (
            list(p.glob('**/*.tif'))  +
            list(p.glob('**/*.tiff')) +
            list(p.glob('**/*.TIF'))  +
            list(p.glob('**/*.TIFF'))
        )
        return sorted(tifs)
    logger.error("Input path not found: %s", input_path)
    return []


def extract_tile(
    data: np.ndarray,
    row: int,
    col: int,
    tile_size: int,
) -> np.ndarray:
    """
    Extract a (tile_size, tile_size, C) sub-array from *data*.

    Parameters
    ----------
    data      : np.ndarray  Shape (H, W, C) — image data, uint8 or uint16.
    row, col  : int         Top-left corner of the tile in pixel coordinates.
    tile_size : int         Tile width and height in pixels.

    Returns
    -------
    np.ndarray  Shape (tile_size, tile_size, C), dtype uint8.
    """
    tile = data[row: row + tile_size, col: col + tile_size]

    # Pad if near edge
    if tile.shape[0] < tile_size or tile.shape[1] < tile_size:
        pad_h = tile_size - tile.shape[0]
        pad_w = tile_size - tile.shape[1]
        pad_width = [(0, pad_h), (0, pad_w), (0, 0)] if data.ndim == 3 else [(0, pad_h), (0, pad_w)]
        tile = np.pad(tile, pad_width, mode='reflect')

    # Normalise to uint8 if needed
    if tile.dtype != np.uint8:
        t_min = tile.min()
        t_max = tile.max()
        if t_max > t_min:
            tile = ((tile - t_min) / (t_max - t_min) * 255).astype(np.uint8)
        else:
            tile = np.zeros_like(tile, dtype=np.uint8)

    return tile


def extract_all_tiles(
    tif_path: Path,
    output_dir: Path,
    tile_size: int = 640,
    stride: int = 320,
    min_brightness: int = 20,
    dry_run: bool = False,
    prefix: str = '',
) -> int:
    """
    Slide a window over a GeoTIFF and save tiles to *output_dir*.

    Parameters
    ----------
    tif_path       : Path   Input GeoTIFF file.
    output_dir     : Path   Directory to save PNG tiles.
    tile_size      : int    Tile size in pixels (default 640).
    stride         : int    Step between tiles (default 320 = 50% overlap).
    min_brightness : int    Skip tiles whose mean pixel value < this (0–255).
    dry_run        : bool   If True, count tiles but do not write files.
    prefix         : str    Filename prefix (default = stem of tif_path).

    Returns
    -------
    int  Number of tiles saved (or would-be-saved in dry_run).
    """
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError:
        logger.error(
            "rasterio is not installed.  Install with:  pip install rasterio"
        )
        sys.exit(1)

    try:
        from PIL import Image as PILImage
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False
        logger.warning("Pillow not found — tiles will be saved as raw .npy files")

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    if not prefix:
        prefix = tif_path.stem

    saved = 0
    skipped_dark  = 0
    skipped_nodata = 0

    logger.info("Opening: %s", tif_path.name)
    with rasterio.open(str(tif_path)) as src:
        width  = src.width
        height = src.height
        bands  = src.count
        logger.info(
            "  %d × %d px  |  %d bands  |  %.1f m/px",
            width, height, bands, abs(src.transform.a),
        )

        # Read all bands as (H, W, C)
        data_chw = src.read()                      # (C, H, W)
        data = np.transpose(data_chw, (1, 2, 0))   # (H, W, C)

        # Use only first 3 bands (RGB / TCI)
        if data.shape[2] >= 3:
            data = data[:, :, :3]
        else:
            # Repeat single band to RGB
            data = np.stack([data[:, :, 0]] * 3, axis=-1)

        rows = range(0, height, stride)
        cols = range(0, width,  stride)
        total_candidates = len(rows) * len(cols)
        logger.info(
            "  Tile grid: %d rows × %d cols = %d candidates  "
            "(size=%d, stride=%d)",
            len(rows), len(cols), total_candidates, tile_size, stride,
        )

        for row in rows:
            for col in cols:
                tile = extract_tile(data, row, col, tile_size)

                # Skip near-black tiles (nodata / cloud shadow border)
                mean_val = tile.mean()
                if mean_val < min_brightness:
                    skipped_dark += 1
                    continue

                # Skip tiles that are almost entirely uniform (nodata fill)
                std_val = tile.std()
                if std_val < 2.0:
                    skipped_nodata += 1
                    continue

                saved += 1
                if dry_run:
                    continue

                fname = f"{prefix}_r{row:05d}_c{col:05d}.jpg"
                out_path = output_dir / fname

                if HAS_PIL:
                    img = PILImage.fromarray(tile, mode='RGB')
                    img.save(str(out_path), quality=95)
                else:
                    # Fallback: save as NPY
                    np.save(str(out_path).replace('.jpg', '.npy'), tile)

    logger.info(
        "  Saved: %d tiles  |  Skipped dark: %d  |  Skipped uniform: %d",
        saved, skipped_dark, skipped_nodata,
    )
    return saved


# ─────────────────────────────────────────────────────────────────────────────

def split_tiles(
    tiles_dir: Path,
    output_root: Path,
    train_ratio: float = 0.8,
    seed: int = 42,
) -> Tuple[int, int]:
    """
    Move tiles from *tiles_dir* into output_root/train/ and output_root/val/.

    Parameters
    ----------
    tiles_dir    : Path   Directory containing all extracted tiles.
    output_root  : Path   Root output directory (train/ and val/ created here).
    train_ratio  : float  Fraction of tiles for training (default 0.8).
    seed         : int    Random seed for reproducible split.

    Returns
    -------
    (n_train, n_val)
    """
    import shutil

    tiles = sorted(tiles_dir.glob('*.jpg')) + sorted(tiles_dir.glob('*.png'))
    if not tiles:
        logger.warning("No tiles found in %s to split.", tiles_dir)
        return 0, 0

    random.seed(seed)
    random.shuffle(tiles)

    n_train = int(len(tiles) * train_ratio)
    train_tiles = tiles[:n_train]
    val_tiles   = tiles[n_train:]

    train_dir = output_root / 'images' / 'train'
    val_dir   = output_root / 'images' / 'val'
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)

    for t in train_tiles:
        shutil.move(str(t), str(train_dir / t.name))
    for t in val_tiles:
        shutil.move(str(t), str(val_dir / t.name))

    logger.info("Split: %d train  /  %d val", len(train_tiles), len(val_tiles))
    return len(train_tiles), len(val_tiles)


# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Extract 640×640 training tiles from Sentinel-2 GeoTIFF files'
    )
    p.add_argument('--input',  '-i', type=str, required=True,
                   help='Path to a .tif file or folder containing .tif files')
    p.add_argument('--output', '-o', type=str, required=True,
                   help='Output directory for tiles (or root for train/val split)')
    p.add_argument('--tile-size', type=int, default=640,
                   help='Tile width and height in pixels (default: 640)')
    p.add_argument('--stride',    type=int, default=320,
                   help='Pixel stride between tiles (default: 320 = 50%% overlap)')
    p.add_argument('--min-brightness', type=int, default=20,
                   help='Skip tiles with mean brightness below this (0–255, default: 20)')
    p.add_argument('--split', type=float, default=None,
                   help='Train/val split ratio, e.g. 0.8 → 80%% train 20%% val')
    p.add_argument('--dry-run', action='store_true',
                   help='Count tiles without writing any files')
    p.add_argument('--seed', type=int, default=42,
                   help='Random seed for train/val split (default: 42)')
    return p.parse_args()


def main() -> None:
    args = parse_args()

    tif_files = find_geotiff_files(args.input)
    if not tif_files:
        logger.error("No GeoTIFF files found at: %s", args.input)
        sys.exit(1)

    logger.info("Found %d GeoTIFF file(s)", len(tif_files))

    output_path = Path(args.output)

    # If split requested, extract to a temp dir first, then split
    if args.split is not None:
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp(prefix='shamsi_tiles_'))
        logger.info("Extracting to temp dir: %s", tmp_dir)
        total = 0
        for tif in tif_files:
            n = extract_all_tiles(
                tif_path       = tif,
                output_dir     = tmp_dir,
                tile_size      = args.tile_size,
                stride         = args.stride,
                min_brightness = args.min_brightness,
                dry_run        = args.dry_run,
            )
            total += n
        logger.info("Total tiles extracted: %d", total)

        if not args.dry_run:
            n_train, n_val = split_tiles(
                tiles_dir   = tmp_dir,
                output_root = output_path,
                train_ratio = args.split,
                seed        = args.seed,
            )
            print(f"\n  ✅  Done!  {n_train} train tiles  /  {n_val} val tiles")
            print(f"  Train dir: {output_path / 'images' / 'train'}")
            print(f"  Val dir  : {output_path / 'images' / 'val'}")
            print(f"\n  Next: python scripts/semi_auto_annotate.py "
                  f"--images {output_path}/images/train/")

    else:
        total = 0
        for tif in tif_files:
            n = extract_all_tiles(
                tif_path       = tif,
                output_dir     = output_path,
                tile_size      = args.tile_size,
                stride         = args.stride,
                min_brightness = args.min_brightness,
                dry_run        = args.dry_run,
            )
            total += n

        if args.dry_run:
            print(f"\n  [DRY RUN]  Would extract {total} tiles.")
        else:
            print(f"\n  ✅  Done!  {total} tiles saved to: {output_path}")
            print(f"\n  Next: python scripts/semi_auto_annotate.py "
                  f"--images {output_path}/")


if __name__ == '__main__':
    main()
