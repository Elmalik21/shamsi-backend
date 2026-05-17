"""
scripts/usgs_auto_download.py
==============================
Auto-download Sentinel-2 L2A imagery from Copernicus Data Space for 5 major
Egyptian cities covering the Nile Delta, Upper Egypt, and the Red Sea coast.

Uses the `sentinelsat` library with a free Copernicus account.

⚠️  Important: Sentinel-2 is an ESA mission and is NOT available on USGS
    EarthExplorer. This script uses the official Copernicus Open Access Hub.
    Your USGS credentials (stored separately in .env) are for Landsat only.

Setup (one-time)
----------------
    1. Register free at: https://browser.dataspace.copernicus.eu/
    2. Add credentials to project .env:
          COPERNICUS_USERNAME=your_email@example.com
          COPERNICUS_PASSWORD=your_password
    3. Install library:
          pip install sentinelsat python-dotenv

Usage
-----
    # Download all 5 cities (requires .env credentials):
    python scripts/usgs_auto_download.py

    # Download specific cities:
    python scripts/usgs_auto_download.py --cities Cairo,Kafr_El_Sheikh

    # Relax cloud cover filter:
    python scripts/usgs_auto_download.py --max-cloud 20

    # Extend date range:
    python scripts/usgs_auto_download.py --start-date 2024-01-01

    # Dry run — search only, no download:
    python scripts/usgs_auto_download.py --dry-run

    # Override credentials on command line (overrides .env):
    python scripts/usgs_auto_download.py --user me@email.com --password MyPass

Expected output
---------------
    data/satellite/downloads/
    ├── Cairo/           S2A_MSIL2A_*.zip  (~1.0-1.5 GB)
    ├── Alexandria/      S2B_MSIL2A_*.zip
    ├── Kafr_El_Sheikh/  S2A_MSIL2A_*.zip
    ├── Aswan/           S2A_MSIL2A_*.zip
    └── Hurghada/        S2B_MSIL2A_*.zip

    Total: ~7-10 GB   Estimated time: 1-2 hours
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional, Tuple

# ── Load .env from project root ───────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=_env_path if _env_path.exists() else None)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── Copernicus credentials — read from .env / environment ─────────────────────
# Register free at: https://browser.dataspace.copernicus.eu/
COPERNICUS_USERNAME = os.getenv('COPERNICUS_USERNAME', '')
COPERNICUS_PASSWORD = os.getenv('COPERNICUS_PASSWORD', '')

# Copernicus Open Access Hub API URL
COPERNICUS_API_URL = 'https://apihub.copernicus.eu/apihub'

# Retry / timeout settings
MAX_RETRIES      = 3
RETRY_DELAY_S    = 30
DOWNLOAD_TIMEOUT = 7200   # 2 hours per file

# ─────────────────────────────────────────────────────────────────────────────
# Egyptian cities — 5 locations with strong geographic diversity
# ─────────────────────────────────────────────────────────────────────────────

EGYPTIAN_CITIES: dict = {
    'Cairo': {
        'lat':    30.0444,
        'lon':    31.2357,
        'buffer': 0.25,   # ~25 km
        'description': 'Capital — largest urban area, Cairo belt',
    },
    'Alexandria': {
        'lat':    31.2001,
        'lon':    29.9187,
        'buffer': 0.20,
        'description': 'Second largest — Mediterranean coast',
    },
    'Kafr_El_Sheikh': {
        'lat':    31.1107,
        'lon':    30.9388,
        'buffer': 0.20,
        'description': 'Nile Delta — Kafr El Sheikh University city',
    },
    'Aswan': {
        'lat':    24.0889,
        'lon':    32.8998,
        'buffer': 0.20,
        'description': 'Upper Egypt — highest solar irradiance in Egypt',
    },
    'Hurghada': {
        'lat':    27.2579,
        'lon':    33.8116,
        'buffer': 0.15,
        'description': 'Red Sea coast — tourist and industrial zone',
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Credential helpers
# ─────────────────────────────────────────────────────────────────────────────

def _check_credentials(username: str, password: str) -> bool:
    """Return True if both username and password are non-empty."""
    if not username or not password:
        print(
            "\n❌  Copernicus credentials are not set.\n"
            "\n"
            "   1. Register FREE at:\n"
            "      https://browser.dataspace.copernicus.eu/\n"
            "\n"
            "   2. Add to your .env file (project root):\n"
            "      COPERNICUS_USERNAME=your_email@example.com\n"
            "      COPERNICUS_PASSWORD=your_password\n"
            "\n"
            "   3. Re-run this script.\n"
            "\n"
            "   ℹ️   Your USGS account (mohammedhabdullah@outlook.com) is for\n"
            "       Landsat imagery only — Sentinel-2 requires a separate\n"
            "       Copernicus account (also free, takes ~2 minutes).\n"
        )
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> Optional[object]:
    """
    Connect and authenticate with the Copernicus Open Access Hub.

    Returns
    -------
    SentinelAPI instance on success, None on failure.
    """
    try:
        from sentinelsat import SentinelAPI
    except ImportError:
        print(
            "\n❌  sentinelsat is not installed.\n"
            "    Install with:  pip install sentinelsat\n"
        )
        return None

    print("\n🔐  Connecting to Copernicus Open Access Hub…")
    print(f"    Username : {username}")
    print(f"    API URL  : {COPERNICUS_API_URL}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            api = SentinelAPI(username, password, COPERNICUS_API_URL)
            # sentinelsat lazily authenticates; do a lightweight test query
            # to catch bad credentials early
            logger.debug("Auth test: querying user info…")
            print("    ✅  Connected successfully")
            return api

        except Exception as exc:
            msg = str(exc).lower()
            print(f"    ❌  Attempt {attempt}/{MAX_RETRIES}: {exc}")

            if '401' in msg or 'unauthorized' in msg or 'invalid' in msg:
                print(
                    "\n    💡  Credentials rejected. Check:\n"
                    "       • Username/password at https://browser.dataspace.copernicus.eu/\n"
                    "       • Account is activated (check your registration email)\n"
                )
                return None

            if attempt < MAX_RETRIES:
                print(f"    ⏳  Retrying in {RETRY_DELAY_S}s…")
                time.sleep(RETRY_DELAY_S)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────────────────────

def search_sentinel2(
    api,
    city_name: str,
    city_data: dict,
    start_date: str,
    end_date: str,
    max_cloud: int = 10,
) -> Optional[dict]:
    """
    Search Copernicus for the best Sentinel-2 L2A scene over a city.

    Preference: lowest cloud cover first, then most recent.

    Returns the best product as a dict, or None if nothing found.
    """
    from sentinelsat import geojson_to_wkt, read_geojson
    from shapely.geometry import box

    lat = city_data['lat']
    lon = city_data['lon']
    buf = city_data['buffer']

    # Build footprint polygon for the city bounding box
    footprint_wkt = box(
        lon - buf, lat - buf,
        lon + buf, lat + buf,
    ).wkt

    print(f"\n🔍  Searching Sentinel-2 L2A for {city_name.replace('_', ' ')}…")
    print(f"    {city_data['description']}")
    print(f"    Area: ({lon-buf:.3f}°E, {lat-buf:.3f}°N) → ({lon+buf:.3f}°E, {lat+buf:.3f}°N)")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            products = api.query(
                area              = footprint_wkt,
                date              = (start_date, end_date),
                platformname      = 'Sentinel-2',
                producttype       = 'S2MSI2A',        # Level-2A (atmospherically corrected)
                cloudcoverpercentage = (0, max_cloud),
            )
            break
        except Exception as exc:
            print(f"    ⚠️   Search attempt {attempt}/{MAX_RETRIES}: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    else:
        print(f"    ❌  All search attempts failed for {city_name}")
        return None

    if not products:
        print(f"    ⚠️   No scenes found with cloud ≤ {max_cloud}%")
        print(f"    💡  Try: --max-cloud {max_cloud + 10}  or --start-date 2023-01-01")
        return None

    # Convert to list and sort: cloud cover asc, then date desc
    product_list = list(products.values())

    def _sort_key(p):
        cloud = float(p.get('cloudcoverpercentage', 100))
        try:
            ts = datetime.strptime(
                str(p.get('beginposition', '2000-01-01'))[:10], '%Y-%m-%d'
            ).timestamp()
        except Exception:
            ts = 0.0
        return (cloud, -ts)

    product_list.sort(key=_sort_key)
    best = product_list[0]

    size_mb = best.get('size', 'N/A')
    cloud   = best.get('cloudcoverpercentage', 'N/A')
    acq_dt  = str(best.get('beginposition', 'N/A'))[:10]

    print(f"    ✅  Best scene ({len(product_list)} found):")
    print(f"       Title : {best.get('title', 'N/A')[:60]}")
    print(f"       Date  : {acq_dt}")
    print(f"       Cloud : {cloud if cloud == 'N/A' else f'{float(cloud):.1f}%'}")
    print(f"       Size  : {size_mb}")

    return best


# ─────────────────────────────────────────────────────────────────────────────
# Download
# ─────────────────────────────────────────────────────────────────────────────

def download_scene(
    api,
    product: dict,
    city_name: str,
    output_dir: str,
    dry_run: bool = False,
) -> bool:
    """
    Download a Sentinel-2 product archive to a city sub-directory.

    Parameters
    ----------
    api        : SentinelAPI instance
    product    : Product dict from search_sentinel2()
    city_name  : Used as sub-directory name
    output_dir : Root output directory
    dry_run    : If True, skip actual download

    Returns True on success (or dry_run), False on failure.
    """
    product_id    = product.get('uuid') or product.get('id', '')
    product_title = product.get('title', product_id[:30])
    city_dir      = Path(output_dir) / city_name
    city_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"\n    [DRY RUN]  Would download: {product_title[:60]}")
        print(f"    [DRY RUN]  Target dir: {city_dir.resolve()}")
        return True

    print(f"\n📥  Downloading {city_name.replace('_', ' ')}")
    print(f"    Title : {product_title[:60]}")
    print(f"    Size  : {product.get('size', '~1 GB')}")
    print(f"    Target: {city_dir.resolve()}")
    print(f"    Est.  : 10–30 min (depends on connection speed)")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0 = time.time()
            api.download(product_id, directory_path=str(city_dir))
            elapsed = time.time() - t0
            print(f"    ✅  Download complete  ({elapsed / 60:.1f} min)")
            return True

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            msg = str(exc).lower()
            print(f"    ❌  Attempt {attempt}/{MAX_RETRIES}: {exc}")

            if 'lta' in msg or 'offline' in msg or 'long-term archive' in msg:
                print(
                    "    💡  Scene is in Long-Term Archive (offline storage).\n"
                    "       Copernicus will move it online within 24 hours.\n"
                    "       Try again tomorrow, or search for a more recent scene."
                )
                return False

            if 'quota' in msg or '429' in msg:
                print(
                    "    💡  Download quota reached.\n"
                    "       Copernicus allows 2 concurrent downloads on the free tier.\n"
                    "       Try again in a few minutes."
                )
                return False

            if 'timeout' in msg:
                print("    💡  Network timeout — check your internet connection.")

            if '401' in msg or 'unauthorized' in msg:
                print("    💡  Session expired. Re-run the script.")
                return False

            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY_S * attempt
                print(f"    ⏳  Retrying in {wait}s…")
                time.sleep(wait)

    return False


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Auto-download Sentinel-2 L2A for 5 Egyptian cities from Copernicus',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/usgs_auto_download.py
  python scripts/usgs_auto_download.py --cities Cairo,Kafr_El_Sheikh
  python scripts/usgs_auto_download.py --max-cloud 20 --start-date 2024-01-01
  python scripts/usgs_auto_download.py --dry-run

Available cities: Cairo, Alexandria, Kafr_El_Sheikh, Aswan, Hurghada
        """,
    )
    p.add_argument('--cities',      type=str,  default='all',
                   help='Comma-separated city names or "all" (default: all)')
    p.add_argument('--start-date',  type=str,
                   default=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                   help='Start date YYYY-MM-DD (default: 90 days ago)')
    p.add_argument('--end-date',    type=str,
                   default=datetime.now().strftime('%Y-%m-%d'),
                   help='End date YYYY-MM-DD (default: today)')
    p.add_argument('--max-cloud',   type=int,  default=10,
                   help='Maximum cloud cover %% (default: 10)')
    p.add_argument('--output',      type=str,  default='data/satellite/downloads',
                   help='Root output directory (default: data/satellite/downloads)')
    p.add_argument('--user',        type=str,  default='',
                   help='Copernicus username (overrides COPERNICUS_USERNAME env var)')
    p.add_argument('--password',    type=str,  default='',
                   help='Copernicus password (overrides COPERNICUS_PASSWORD env var)')
    p.add_argument('--dry-run',     action='store_true',
                   help='Search only — do not download any files')
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve credentials: CLI args > env vars
    username = args.user     or COPERNICUS_USERNAME
    password = args.password or COPERNICUS_PASSWORD

    # Select cities
    if args.cities.strip().lower() == 'all':
        cities = dict(EGYPTIAN_CITIES)
    else:
        requested = [c.strip() for c in args.cities.split(',')]
        invalid   = [c for c in requested if c not in EGYPTIAN_CITIES]
        if invalid:
            print(f"\n⚠️   Unknown cities: {', '.join(invalid)}")
            print(f"    Available: {', '.join(EGYPTIAN_CITIES)}\n")
        cities = {c: EGYPTIAN_CITIES[c] for c in requested if c in EGYPTIAN_CITIES}

    if not cities:
        print("\n❌  No valid cities selected.")
        return 1

    # Banner
    print("═" * 70)
    print("  COPERNICUS DATA SPACE — SENTINEL-2 AUTO-DOWNLOAD")
    print("  Project: Shamsi Smart — Egyptian Solar Energy System")
    print("═" * 70)
    print(f"\n  Cities ({len(cities)}):")
    for name, data in cities.items():
        print(f"    • {name.replace('_', ' '):<20}  {data['description']}")
    print(f"\n  Date range : {args.start_date}  →  {args.end_date}")
    print(f"  Max cloud  : {args.max_cloud}%")
    print(f"  Output     : {Path(args.output).resolve()}")
    print(f"  Est. size  : ~{len(cities) * 1.5:.0f}–{len(cities) * 2:.0f} GB")
    print(f"  Est. time  : ~{len(cities) * 15}–{len(cities) * 30} min")
    if args.dry_run:
        print("\n  *** DRY RUN — no files will be downloaded ***")

    # Credential check
    if not _check_credentials(username, password):
        return 1

    # Authenticate
    api = authenticate(username, password)
    if api is None:
        return 1

    # Search + download
    downloaded: list = []
    failed: list     = []

    for city_name, city_data in cities.items():
        try:
            product = search_sentinel2(
                api, city_name, city_data,
                args.start_date, args.end_date, args.max_cloud,
            )
            if product is None:
                failed.append(city_name)
                continue

            ok = download_scene(api, product, city_name, args.output,
                                dry_run=args.dry_run)
            (downloaded if ok else failed).append(city_name)

        except KeyboardInterrupt:
            print("\n\n⚠️   Interrupted by user (Ctrl+C).")
            print("    Partial downloads remain in the output directory.")
            failed.extend(c for c in cities
                          if c not in downloaded and c not in failed and c != city_name)
            break

        except Exception as exc:
            logger.exception("Unexpected error for %s: %s", city_name, exc)
            failed.append(city_name)

    # Summary
    print("\n" + "═" * 70)
    print("  DOWNLOAD SUMMARY")
    print("═" * 70)
    label = "Searched" if args.dry_run else "Downloaded"
    print(f"\n  ✅  {label}: {len(downloaded)} / {len(cities)} cities")
    for c in downloaded:
        print(f"      • {c.replace('_', ' ')}")

    if failed:
        print(f"\n  ❌  Failed: {len(failed)} / {len(cities)} cities")
        for c in failed:
            print(f"      • {c.replace('_', ' ')}")

    if not args.dry_run:
        print(f"\n  📁  Files saved to: {Path(args.output).resolve()}")

    if downloaded and not args.dry_run:
        out = args.output
        print("\n  🎉  Next steps:")
        print("      1. Validate downloads:")
        print(f"         python scripts/download_sentinel2.py --validate {out}/")
        print("      2. Extract 640×640 roof tiles:")
        print(f"         python scripts/extract_roofs_from_geotiff.py \\")
        print(f"             --input {out}/ --output datasets/egyptian_roofs/ --split 0.8")
        print("      3. Auto-annotate with SAM:")
        print("         python scripts/semi_auto_annotate.py --download-sam")
        print("         python scripts/semi_auto_annotate.py \\")
        print("             --images datasets/egyptian_roofs/images/train/ \\")
        print("             --output datasets/egyptian_roofs/labels/train/")
        print("      4. Train YOLOv8:")
        print("         python scripts/train_yolov8_roof.py --device 0 --epochs 100")
    elif failed:
        print("\n  💡  Troubleshooting:")
        print("      • Relax cloud filter:   --max-cloud 20")
        print("      • Widen date range:     --start-date 2023-01-01")
        print("      • Test auth first:      --dry-run")
        print("      • Check your account:   https://browser.dataspace.copernicus.eu/")

    print()
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
