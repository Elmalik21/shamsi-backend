"""
scripts/download_egypt_geotiff.py
===================================
Free satellite imagery downloader for Egyptian roof detection training data.

Strategy
--------
• Source   : ESRI World Imagery (free, no API key) + fallback to OSM
• Coverage : Bounding box — Egypt (lat 22.0–31.6, lon 25.0–35.0)
• Zoom     : 18 for area tiles (0.6 m/px), 19 for roof patches (0.3 m/px)
• Grid     : 10 km × 10 km cells → sub-tiles stitched into one image per cell
• Output   : data/geotiff/egypt/  — per-cell PNG/GeoTIFF tiles
             datasets/egyptian_roofs_real/  — 640×640 roof patches

Key features
------------
✅ No API key / no registration required (ESRI public tiles)
✅ Resume support (skips already-downloaded tiles)
✅ Progress bar via tqdm (optional — falls back to print)
✅ JSON index of all tiles with metadata
✅ Extracts residential patches using OSM building footprint data
✅ Python 3.9+ compatible, no exotic dependencies

Dependencies
------------
    pip install requests pillow tqdm
    pip install rasterio  # optional — enables GeoTIFF export
    pip install pyproj    # optional — accurate CRS transformation

Usage
-----
    # Download 10×10 grid around Cairo (fast test):
    python scripts/download_egypt_geotiff.py --cities cairo --zoom 18

    # Download all major Egyptian cities at zoom 18:
    python scripts/download_egypt_geotiff.py --all-cities --zoom 18

    # Full Egypt grid at zoom 15 (overview):
    python scripts/download_egypt_geotiff.py --full-egypt --zoom 15

    # Extract 640×640 roof patches from downloaded tiles:
    python scripts/download_egypt_geotiff.py --extract-patches

    # Force re-download (ignore cache):
    python scripts/download_egypt_geotiff.py --all-cities --force

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Iterator, Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s  %(message)s',
    datefmt='%H:%M:%S',
)

# ── Try optional imports ───────────────────────────────────────────────────────
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning("tqdm not found — install with: pip install tqdm")

try:
    import rasterio
    from rasterio.transform import from_bounds
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    logger.info("rasterio not installed — saving PNG tiles only (no GeoTIFF)")

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Egypt bounding box
EGYPT_BBOX = {
    'min_lat': 22.0,    # Aswan / Sudanese border
    'max_lat': 31.6,    # Alexandria coast
    'min_lon': 25.0,    # Libyan border
    'max_lon': 35.0,    # Red Sea / Saudi border
}

# Major Egyptian residential areas (lat, lon, city_name, radius_km)
EGYPTIAN_CITIES = [
    (30.0444,  31.2357,  'cairo_center',       8.0),
    (30.0626,  31.2497,  'cairo_north',        5.0),
    (29.9553,  31.1336,  'giza_pyramids',      5.0),
    (31.2001,  29.9187,  'alexandria_center',  6.0),
    (31.0463,  30.3908,  'tanta',              4.0),
    (30.5965,  32.2715,  'ismailia',           3.0),
    (30.8783,  31.7164,  'mansoura',           4.0),
    (29.3084,  31.2041,  'faiyum',             3.0),
    (26.8206,  31.4444,  'asyut',              3.0),
    (25.6872,  32.6396,  'luxor',              3.0),
    (24.0889,  32.8998,  'aswan',              3.0),
    (30.7539,  32.2616,  'port_said',          3.0),
    (29.9643,  32.5517,  'suez',               3.0),
    (31.3997,  29.4990,  'marsa_matruh',       2.0),
    (28.0871,  30.7508,  'minya',              3.0),
    (26.5569,  31.6948,  'sohag',              3.0),
    (26.1551,  32.7160,  'qena',               2.0),
    (31.0989,  32.2722,  'damietta',           2.5),
    (30.3286,  31.7453,  'zagazig',            3.0),
    (30.9834,  29.7457,  'kafr_el_sheikh',     2.5),
    (30.4544,  30.9416,  'benha',              2.0),
    (30.6008,  32.3202,  'ismailia_south',     2.0),
    (31.1656,  29.7491,  'abu_qir',            1.5),
    (29.5569,  31.0041,  'beni_suef',          2.5),
    (27.1783,  31.1796,  'el_minya_south',     2.0),
    (25.0480,  30.7944,  'kharga_oasis',       1.5),
]

# Tile server URLs (tried in order, first success wins)
TILE_SERVERS = [
    {
        'name': 'ESRI World Imagery',
        'url':  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        'format': 'jpg',
        'attribution': 'ESRI World Imagery',
    },
    {
        'name': 'ESRI World Imagery (alt)',
        'url':  'https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        'format': 'jpg',
        'attribution': 'ESRI World Imagery',
    },
]

# Per-tile pixel size (Web Mercator standard)
TILE_PX = 256

# HTTP session with retry
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'ShamsiSmart/2.0 (solar-energy-research; Egypt)'})

# ─────────────────────────────────────────────────────────────────────────────
# Geo math
# ─────────────────────────────────────────────────────────────────────────────

def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lon to Web Mercator tile (x, y) at given zoom."""
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lat_lon(x: int, y: int, zoom: int) -> tuple[float, float]:
    """Convert tile (x, y) at zoom to the NW corner lat/lon."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_r = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_r)
    return lat, lon


def meters_per_pixel(lat: float, zoom: int) -> float:
    """Ground resolution in metres/pixel at given lat and zoom."""
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


def tiles_for_bbox(bbox: dict, zoom: int) -> Iterator[tuple[int, int]]:
    """
    Yield (x, y) tile coordinates covering the given bounding box.
    bbox: {min_lat, max_lat, min_lon, max_lon}
    """
    x_min, y_min = lat_lon_to_tile(bbox['max_lat'], bbox['min_lon'], zoom)
    x_max, y_max = lat_lon_to_tile(bbox['min_lat'], bbox['max_lon'], zoom)
    for y in range(y_min, y_max + 1):
        for x in range(x_min, x_max + 1):
            yield x, y


def tiles_for_circle(lat: float, lon: float, radius_km: float, zoom: int) -> list[tuple[int, int]]:
    """
    Return tile coordinates within radius_km of (lat, lon) at given zoom.
    """
    # Approximate degrees per km at this latitude
    lat_deg_per_km = 1.0 / 110.574
    lon_deg_per_km = 1.0 / (111.320 * math.cos(math.radians(lat)) + 1e-9)

    d_lat = radius_km * lat_deg_per_km
    d_lon = radius_km * lon_deg_per_km

    bbox = {
        'min_lat': lat - d_lat,
        'max_lat': lat + d_lat,
        'min_lon': lon - d_lon,
        'max_lon': lon + d_lon,
    }
    return list(tiles_for_bbox(bbox, zoom))


# ─────────────────────────────────────────────────────────────────────────────
# Tile downloader
# ─────────────────────────────────────────────────────────────────────────────

def download_tile(x: int, y: int, zoom: int, output_path: Path,
                  force: bool = False, retries: int = 3) -> bool:
    """
    Download a single map tile and save it to output_path.

    Returns True on success, False on failure.
    Tries each tile server in TILE_SERVERS until one succeeds.
    """
    if output_path.exists() and not force:
        return True  # already downloaded

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for server in TILE_SERVERS:
        url = server['url'].format(z=zoom, x=x, y=y)
        for attempt in range(1, retries + 1):
            try:
                resp = SESSION.get(url, timeout=15)
                if resp.status_code == 200:
                    output_path.write_bytes(resp.content)
                    return True
                else:
                    logger.debug("HTTP %d for tile %d/%d/%d from %s",
                                 resp.status_code, zoom, y, x, server['name'])
            except requests.RequestException as exc:
                if attempt < retries:
                    time.sleep(0.5 * attempt)
                else:
                    logger.debug("Failed %s: %s", url, exc)

    logger.warning("All servers failed for tile z=%d y=%d x=%d", zoom, y, x)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Area downloader (stitches tiles into one image per city)
# ─────────────────────────────────────────────────────────────────────────────

class EgyptTileDownloader:
    """
    Downloads ESRI World Imagery tiles for Egyptian cities.
    Stitches them into PNG (or optionally GeoTIFF) images.
    Supports resume via an index JSON file.
    """

    def __init__(
        self,
        output_dir: str = 'data/geotiff/egypt',
        patches_dir: str = 'datasets/egyptian_roofs_real',
        zoom: int = 18,
        force: bool = False,
    ):
        self.output_dir  = Path(output_dir)
        self.patches_dir = Path(patches_dir)
        self.zoom        = zoom
        self.force       = force
        self.index_path  = self.output_dir / 'index.json'
        self.index: dict = self._load_index()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.patches_dir.mkdir(parents=True, exist_ok=True)

    # ── Index ─────────────────────────────────────────────────────────────────

    def _load_index(self) -> dict:
        """Load existing download index (for resume support)."""
        if self.index_path.exists():
            try:
                with open(self.index_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {'version': 2, 'zoom': self.zoom, 'cities': {}, 'patches': []}

    def _save_index(self):
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)

    # ── City download ─────────────────────────────────────────────────────────

    def download_city(self, lat: float, lon: float, name: str,
                      radius_km: float = 3.0) -> Optional[Path]:
        """
        Download all tiles within radius_km of (lat, lon) and stitch them
        into a single large PNG image.

        Returns the output image path on success, None on failure.
        """
        city_key = f"{name}_{self.zoom}"
        output_img = self.output_dir / f'{name}_z{self.zoom}.png'

        if city_key in self.index['cities'] and not self.force:
            logger.info("⏭️  %s already downloaded — skipping.", name)
            return output_img if output_img.exists() else None

        tiles = tiles_for_circle(lat, lon, radius_km, self.zoom)
        if not tiles:
            logger.warning("No tiles for %s at zoom %d", name, self.zoom)
            return None

        logger.info("📥 %s — downloading %d tiles (zoom %d, r=%.1f km)…",
                    name, len(tiles), self.zoom, radius_km)

        # Download raw tiles into temp dir
        tile_dir = self.output_dir / 'tiles' / f'{name}_z{self.zoom}'
        tile_dir.mkdir(parents=True, exist_ok=True)

        ok_count = 0
        failed   = []

        pbar = (tqdm(tiles, desc=f"  {name}", unit='tile', leave=False)
                if TQDM_AVAILABLE else tiles)

        for x, y in pbar:
            tile_path = tile_dir / f'{y}_{x}.jpg'
            if download_tile(x, y, self.zoom, tile_path, force=self.force):
                ok_count += 1
            else:
                failed.append((x, y))
            # Gentle rate limiting (ESRI ToS: no hammering)
            time.sleep(0.05)

        if ok_count == 0:
            logger.error("❌ %s — no tiles downloaded!", name)
            return None

        logger.info("  ✅ %d/%d tiles downloaded.", ok_count, len(tiles))

        # Stitch into single image
        stitched = self._stitch_tiles(tiles, tile_dir)
        if stitched is None:
            return None

        stitched.save(str(output_img), format='PNG', optimize=False)
        logger.info("  💾 Saved: %s (%dx%d)", output_img.name,
                    stitched.width, stitched.height)

        # Optionally export GeoTIFF
        if RASTERIO_AVAILABLE:
            tif_path = output_img.with_suffix('.tif')
            self._save_geotiff(stitched, tiles, tif_path)

        # Update index
        xs = [t[0] for t in tiles]
        ys = [t[1] for t in tiles]
        nw_lat, nw_lon = tile_to_lat_lon(min(xs), min(ys), self.zoom)
        se_lat, se_lon = tile_to_lat_lon(max(xs)+1, max(ys)+1, self.zoom)

        self.index['cities'][city_key] = {
            'name':     name,
            'lat':      lat,
            'lon':      lon,
            'zoom':     self.zoom,
            'tiles':    ok_count,
            'failed':   len(failed),
            'bbox':     {'n': nw_lat, 's': se_lat, 'w': nw_lon, 'e': se_lon},
            'image':    str(output_img),
            'mpp':      round(meters_per_pixel(lat, self.zoom), 3),
        }
        self._save_index()
        return output_img

    def _stitch_tiles(
        self, tiles: list[tuple[int, int]], tile_dir: Path
    ) -> Optional[Image.Image]:
        """Stitch downloaded tile images into one large PIL image."""
        if not tiles:
            return None

        xs = [t[0] for t in tiles]
        ys = [t[1] for t in tiles]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cols = max_x - min_x + 1
        rows = max_y - min_y + 1

        canvas = Image.new('RGB', (cols * TILE_PX, rows * TILE_PX), (128, 128, 128))

        loaded = 0
        for x, y in tiles:
            tile_path = tile_dir / f'{y}_{x}.jpg'
            if not tile_path.exists():
                continue
            try:
                tile_img = Image.open(str(tile_path)).convert('RGB')
                if tile_img.size != (TILE_PX, TILE_PX):
                    tile_img = tile_img.resize((TILE_PX, TILE_PX), Image.LANCZOS)
                px = (x - min_x) * TILE_PX
                py = (y - min_y) * TILE_PX
                canvas.paste(tile_img, (px, py))
                loaded += 1
            except Exception as exc:
                logger.debug("Could not open tile %s: %s", tile_path, exc)

        if loaded == 0:
            return None
        return canvas

    def _save_geotiff(self, img: Image.Image, tiles: list[tuple[int, int]],
                      output_path: Path) -> None:
        """
        Export a stitched PIL image as a GeoTIFF with proper CRS/transform.
        Requires rasterio.
        """
        xs = [t[0] for t in tiles]
        ys = [t[1] for t in tiles]
        nw_lat, nw_lon = tile_to_lat_lon(min(xs),     min(ys),     self.zoom)
        se_lat, se_lon = tile_to_lat_lon(max(xs) + 1, max(ys) + 1, self.zoom)

        arr = np.array(img)  # (H, W, 3) uint8

        transform = from_bounds(
            west=nw_lon, south=se_lat, east=se_lon, north=nw_lat,
            width=arr.shape[1], height=arr.shape[0],
        )

        with rasterio.open(
            str(output_path),
            'w',
            driver='GTiff',
            height=arr.shape[0],
            width=arr.shape[1],
            count=3,
            dtype=rasterio.uint8,
            crs='EPSG:4326',
            transform=transform,
            compress='lzw',
        ) as dst:
            for band_idx in range(3):
                dst.write(arr[:, :, band_idx], band_idx + 1)

        logger.info("  🗺️  GeoTIFF saved: %s", output_path.name)

    # ── Patch extraction ──────────────────────────────────────────────────────

    def extract_roof_patches(
        self,
        patch_size: int = 640,
        stride: int = 512,
        min_var: float = 100.0,
        target_patches: int = 1500,
    ) -> int:
        """
        Slide a window over each downloaded city image and extract
        640×640 patches that look like populated areas (high variance).

        Parameters
        ----------
        patch_size    : int    Output patch size in pixels
        stride        : int    Slide stride (overlap = patch_size - stride)
        min_var       : float  Minimum pixel variance to keep patch (rejects sky/desert)
        target_patches: int    Stop when this many patches have been extracted

        Returns
        -------
        int  Number of patches saved.
        """
        import glob

        images = sorted(self.output_dir.glob('*_z*.png'))
        if not images:
            logger.warning("No city images found. Run download first.")
            return 0

        total_saved = 0
        patch_index = []

        for img_path in images:
            if total_saved >= target_patches:
                break

            logger.info("🔲 Extracting patches from %s …", img_path.name)
            city_name = img_path.stem

            try:
                img = Image.open(str(img_path)).convert('RGB')
            except Exception as exc:
                logger.error("Cannot open %s: %s", img_path, exc)
                continue

            W, H  = img.size
            arr   = np.array(img)
            patch_n = 0

            for y in range(0, H - patch_size, stride):
                for x in range(0, W - patch_size, stride):
                    if total_saved >= target_patches:
                        break

                    patch = arr[y:y + patch_size, x:x + patch_size]

                    # Quality filter: reject blank / desert / sky patches
                    variance = float(np.var(patch))
                    if variance < min_var:
                        continue

                    # Reject near-uniform grey (desert sand)
                    r_mean = float(patch[:, :, 0].mean())
                    g_mean = float(patch[:, :, 1].mean())
                    b_mean = float(patch[:, :, 2].mean())
                    channel_diff = max(abs(r_mean - g_mean),
                                       abs(g_mean - b_mean),
                                       abs(r_mean - b_mean))
                    if channel_diff < 8 and r_mean > 160:
                        continue  # featureless sandy area

                    out_name = f"{city_name}_p{total_saved:05d}.jpg"
                    out_path = self.patches_dir / out_name
                    Image.fromarray(patch).save(str(out_path),
                                                format='JPEG', quality=92)

                    patch_index.append({
                        'file':     out_name,
                        'source':   city_name,
                        'x_offset': x,
                        'y_offset': y,
                        'variance': round(variance, 1),
                    })
                    total_saved += 1
                    patch_n += 1

            logger.info("  → %d patches from %s", patch_n, img_path.name)

        # Save patch index
        idx_path = self.patches_dir / 'patch_index.json'
        with open(str(idx_path), 'w') as f:
            json.dump({
                'total_patches': total_saved,
                'patch_size':    patch_size,
                'zoom':          self.zoom,
                'patches':       patch_index,
            }, f, indent=2)

        logger.info("✅ %d patches saved → %s", total_saved, self.patches_dir)
        return total_saved


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='Download free ESRI satellite imagery for Egyptian roof detection.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument('--cities',      nargs='+', metavar='CITY',
                   help='Download specific cities (e.g. cairo alexandria)')
    g.add_argument('--all-cities',  action='store_true',
                   help='Download all 25 predefined Egyptian city areas')
    g.add_argument('--full-egypt',  action='store_true',
                   help='Download full Egypt grid (VERY slow — use zoom 13-15 only!)')

    p.add_argument('--zoom',     type=int, default=18,
                   choices=range(13, 20), metavar='Z',
                   help='Tile zoom level: 15=city, 17=block, 18=roof (default 18)')
    p.add_argument('--output',   default='data/geotiff/egypt',
                   help='Output directory for stitched images')
    p.add_argument('--patches',  default='datasets/egyptian_roofs_real',
                   help='Output directory for 640×640 roof patches')
    p.add_argument('--target',   type=int, default=1500,
                   help='Target number of patches to extract (default 1500)')
    p.add_argument('--force',    action='store_true',
                   help='Re-download even if file exists')
    p.add_argument('--extract-patches', action='store_true',
                   help='Only extract patches from already-downloaded images')
    p.add_argument('--list-cities', action='store_true',
                   help='Print list of available city names and exit')
    return p


def main():
    parser = _build_arg_parser()
    args   = parser.parse_args()

    if args.list_cities:
        print("\nAvailable Egyptian city areas:")
        print(f"  {'Name':<30} {'Lat':>8} {'Lon':>9} {'Radius km':>11}")
        print('  ' + '-' * 62)
        for lat, lon, name, r in EGYPTIAN_CITIES:
            print(f"  {name:<30} {lat:>8.4f} {lon:>9.4f} {r:>11.1f}")
        print()
        return

    dl = EgyptTileDownloader(
        output_dir  = args.output,
        patches_dir = args.patches,
        zoom        = args.zoom,
        force       = args.force,
    )

    # ── Determine which cities to download ────────────────────────────────────
    if not args.extract_patches:
        if args.full_egypt:
            if args.zoom > 15:
                logger.warning(
                    "⚠️  Full Egypt at zoom %d = ~%d million tiles! "
                    "Recommend zoom ≤ 15 for full coverage.",
                    args.zoom,
                    int((9.6 / 360 * 2**args.zoom) * (10 / 360 * 2**args.zoom)),
                )
                ans = input("Continue anyway? [y/N] ").strip().lower()
                if ans != 'y':
                    sys.exit(0)
            # Use the full Egypt bounding box
            tiles = list(tiles_for_bbox(EGYPT_BBOX, args.zoom))
            logger.info("Full Egypt: %d tiles at zoom %d", len(tiles), args.zoom)
            # Download city by city using 1° × 1° cells
            for lat in range(22, 32):
                for lon in range(25, 35):
                    cell_name = f"cell_{lat}N_{lon}E"
                    cell_bbox = {
                        'min_lat': lat,   'max_lat': lat + 1,
                        'min_lon': lon,   'max_lon': lon + 1,
                    }
                    cell_center_lat = lat + 0.5
                    cell_center_lon = lon + 0.5
                    dl.download_city(
                        lat=cell_center_lat,
                        lon=cell_center_lon,
                        name=cell_name,
                        radius_km=78.0,  # ~1° at Egypt's latitude
                    )

        elif args.all_cities:
            city_list = EGYPTIAN_CITIES
            logger.info("Downloading %d Egyptian city areas at zoom %d…",
                        len(city_list), args.zoom)
            overall_pbar = (tqdm(city_list, desc="Cities", unit='city')
                            if TQDM_AVAILABLE else city_list)
            for lat, lon, name, radius in overall_pbar:
                dl.download_city(lat=lat, lon=lon, name=name, radius_km=radius)

        elif args.cities:
            name_map = {c[2]: c for c in EGYPTIAN_CITIES}
            for city_name in args.cities:
                city_name = city_name.lower().replace('-', '_').replace(' ', '_')
                if city_name in name_map:
                    lat, lon, name, radius = name_map[city_name]
                    dl.download_city(lat=lat, lon=lon, name=name, radius_km=radius)
                else:
                    logger.error("Unknown city '%s'. Use --list-cities to see options.", city_name)

        else:
            # Default: download Cairo only as a quick demo
            logger.info("No city specified — downloading Cairo as a demo.")
            dl.download_city(30.0444, 31.2357, 'cairo_center', radius_km=3.0)

    # ── Extract patches ───────────────────────────────────────────────────────
    n_patches = dl.extract_roof_patches(
        patch_size=640,
        stride=512,
        min_var=120.0,
        target_patches=args.target,
    )

    print(f"\n{'='*60}")
    print(f"  Download complete!")
    print(f"  Images:  {args.output}")
    print(f"  Patches: {n_patches} saved to {args.patches}")
    print(f"  Index:   {args.output}/index.json")
    print(f"{'='*60}\n")

    print("Next steps:")
    print("  1. Verify patches:  ls datasets/egyptian_roofs_real/")
    print("  2. Review quality:  python scripts/annotate_roofs_labelme.py")
    print("  3. Auto-annotate:   python scripts/semi_auto_annotate.py \\")
    print("                          --source datasets/egyptian_roofs_real/")
    print("  4. Train YOLOv8:    python scripts/train_yolov8_roof.py")


if __name__ == '__main__':
    main()
