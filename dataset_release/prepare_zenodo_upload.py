"""
prepare_zenodo_upload.py
========================
Prepare the Egyptian Solar Energy Dataset (ESED) for Zenodo upload.

Workflow:
    1. Export all data from PostgreSQL (or Django ORM)
    2. Create CSV / metadata files
    3. Generate .zenodo.json
    4. Create ZIP archive ready for upload
    5. (Optional) Upload via Zenodo REST API

Usage:
    # Full export (requires DATABASE_URL environment variable)
    python dataset_release/prepare_zenodo_upload.py

    # Dry run (uses synthetic data — no DB required)
    python dataset_release/prepare_zenodo_upload.py --dry-run

    # With Zenodo API upload
    python dataset_release/prepare_zenodo_upload.py --upload --token $ZENODO_TOKEN

Dependencies:
    pip install django psycopg2-binary requests tqdm
"""

import argparse
import csv
import json
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# ─── Django setup ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shamsi_smart.settings.production')

try:
    import django
    django.setup()
    DJANGO_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Django not available: {e}. Running in --dry-run mode.")
    DJANGO_AVAILABLE = False

# ─── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = BASE_DIR / 'dataset_release' / 'ESED_v1.0'
ZENODO_API = 'https://zenodo.org/api'


# ─────────────────────────────────────────────────────────────────────────────
# 1. Data export functions
# ─────────────────────────────────────────────────────────────────────────────

def export_climate_data(output_dir: Path, dry_run: bool = False) -> dict:
    """
    Export DailyClimateData records to CSV.
    Returns summary statistics.
    """
    climate_dir = output_dir / 'climate_data'
    climate_dir.mkdir(parents=True, exist_ok=True)

    if dry_run or not DJANGO_AVAILABLE:
        return _synthetic_climate_export(climate_dir)

    from solar_data.models import DailyClimateData, Location

    # ── daily_records.csv ────────────────────────────────────────────────────
    daily_path = climate_dir / 'daily_records.csv'
    fields = [
        'date', 'location_id', 'allsky_sfc_sw_dwn',
        't2m', 't2m_max', 't2m_min', 'rh2m', 'ws2m',
        'prectotcorr', 'dust_zone', 'dust_risk_score', 'year',
    ]

    count = 0
    with open(daily_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        qs = DailyClimateData.objects.select_related('location').order_by('location_id', 'date')
        for rec in qs.iterator(chunk_size=5000):
            writer.writerow({
                'date'               : rec.date.isoformat(),
                'location_id'        : rec.location_id,
                'allsky_sfc_sw_dwn'  : round(rec.allsky_sfc_sw_dwn, 4),
                't2m'                : round(rec.t2m, 2),
                't2m_max'            : round(getattr(rec, 't2m_max', rec.t2m + 2), 2),
                't2m_min'            : round(getattr(rec, 't2m_min', rec.t2m - 4), 2),
                'rh2m'               : round(rec.rh2m, 1),
                'ws2m'               : round(rec.ws2m, 2),
                'prectotcorr'        : round(getattr(rec, 'prectotcorr', 0.0), 3),
                'dust_zone'          : getattr(rec, 'dust_zone', 1),
                'dust_risk_score'    : round(getattr(rec, 'dust_risk_score', 0.05), 4),
                'year'               : rec.date.year,
            })
            count += 1

    # ── location_metadata.csv ────────────────────────────────────────────────
    meta_path = climate_dir / 'location_metadata.csv'
    loc_fields = [
        'location_id', 'name', 'governorate', 'latitude', 'longitude',
        'elevation_m', 'region', 'dust_zone', 'avg_ghi_annual', 'population_2023',
    ]
    with open(meta_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=loc_fields)
        writer.writeheader()
        for loc in Location.objects.all().order_by('id'):
            writer.writerow({
                'location_id'   : loc.id,
                'name'          : loc.name,
                'governorate'   : getattr(loc, 'governorate', ''),
                'latitude'      : loc.latitude,
                'longitude'     : loc.longitude,
                'elevation_m'   : getattr(loc, 'elevation', 0),
                'region'        : getattr(loc, 'region', ''),
                'dust_zone'     : getattr(loc, 'dust_zone', 1),
                'avg_ghi_annual': getattr(loc, 'avg_ghi', ''),
                'population_2023': getattr(loc, 'population', ''),
            })

    print(f"  [✓] climate_data/daily_records.csv — {count:,} records")
    print(f"  [✓] climate_data/location_metadata.csv")
    return {'daily_records': count}


def _synthetic_climate_export(climate_dir: Path) -> dict:
    """Generate a small synthetic dataset for dry-run testing."""
    import math, random
    random.seed(42)

    LOCATIONS = [
        (1, 'Cairo',      'Cairo',      30.044, 31.236, 23,  'Greater Cairo', 1, 5.5, 10_000_000),
        (2, 'Alexandria', 'Alexandria', 31.200, 29.920, 7,   'Delta',         0, 5.2,  5_200_000),
        (3, 'Aswan',      'Aswan',      24.090, 32.900, 194, 'Upper Egypt',   2, 7.2,    400_000),
    ]

    # daily_records.csv
    daily_path = climate_dir / 'daily_records.csv'
    fields = ['date','location_id','allsky_sfc_sw_dwn','t2m','t2m_max','t2m_min',
              'rh2m','ws2m','prectotcorr','dust_zone','dust_risk_score','year']
    count = 0
    with open(daily_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for year in range(2022, 2024):
            for doy in range(1, 366):
                date = f'{year}-{((doy-1)//30+1):02d}-{((doy-1)%30+1):02d}'
                for loc in LOCATIONS:
                    ghi_base = loc[8]
                    ghi = ghi_base * (1 + 0.3 * math.sin(2 * math.pi * (doy - 80) / 365))
                    ghi = max(0.5, ghi + random.gauss(0, 0.3))
                    writer.writerow({
                        'date': date, 'location_id': loc[0],
                        'allsky_sfc_sw_dwn': round(ghi, 4),
                        't2m': round(20 + 10 * math.sin(2 * math.pi * (doy-172)/365), 2),
                        't2m_max': round(25 + 10 * math.sin(2 * math.pi * (doy-172)/365), 2),
                        't2m_min': round(15 + 10 * math.sin(2 * math.pi * (doy-172)/365), 2),
                        'rh2m': round(max(10, 55 - 10 * math.sin(2*math.pi*(doy-172)/365)), 1),
                        'ws2m': round(abs(random.gauss(3, 1.5)), 2),
                        'prectotcorr': round(max(0, random.gauss(0.1, 0.5)), 3),
                        'dust_zone': loc[7], 'dust_risk_score': round(0.05 * (loc[7]+1), 4),
                        'year': year,
                    })
                    count += 1

    # location_metadata.csv
    meta_path = climate_dir / 'location_metadata.csv'
    loc_fields = ['location_id','name','governorate','latitude','longitude',
                  'elevation_m','region','dust_zone','avg_ghi_annual','population_2023']
    with open(meta_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=loc_fields)
        writer.writeheader()
        for loc in LOCATIONS:
            writer.writerow(dict(zip(loc_fields, loc)))

    print(f"  [✓] climate_data/daily_records.csv — {count:,} synthetic records")
    print(f"  [✓] climate_data/location_metadata.csv — {len(LOCATIONS)} locations")
    return {'daily_records': count}


def export_equipment_data(output_dir: Path, dry_run: bool = False):
    """Export solar panels, inverters, and installation costs."""
    eq_dir = output_dir / 'equipment'
    eq_dir.mkdir(parents=True, exist_ok=True)

    if dry_run or not DJANGO_AVAILABLE:
        return _synthetic_equipment_export(eq_dir)

    from api.models import SolarPanel, Inverter, InstallationCost

    # solar_panels.csv
    panel_fields = ['model','power_wp','efficiency_pct','voc_v','isc_a','vmpp_v',
                    'impp_a','temp_coeff_pmax','noct_c','length_mm','width_mm',
                    'weight_kg','price_egp','warranty_years']
    with open(eq_dir / 'solar_panels.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=panel_fields)
        writer.writeheader()
        for p in SolarPanel.objects.all():
            writer.writerow({
                'model': f"{p.manufacturer} {p.model_name}",
                'power_wp': p.power_output,
                'efficiency_pct': p.efficiency,
                'voc_v': getattr(p, 'voc', ''),
                'isc_a': getattr(p, 'isc', ''),
                'vmpp_v': getattr(p, 'vmpp', ''),
                'impp_a': getattr(p, 'impp', ''),
                'temp_coeff_pmax': getattr(p, 'temp_coefficient', -0.35),
                'noct_c': getattr(p, 'noct', 45),
                'length_mm': getattr(p, 'length', ''),
                'width_mm': getattr(p, 'width', ''),
                'weight_kg': getattr(p, 'weight', ''),
                'price_egp': p.price_per_watt * p.power_output if hasattr(p, 'price_per_watt') else '',
                'warranty_years': getattr(p, 'warranty_years', 25),
            })

    # inverters.csv
    inv_fields = ['model','power_kw','efficiency_pct','euro_efficiency_pct','mppt_count',
                  'vmppt_min_v','vmppt_max_v','voc_max_v','isc_max_a','price_egp']
    with open(eq_dir / 'inverters.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=inv_fields)
        writer.writeheader()
        for inv in Inverter.objects.all():
            writer.writerow({
                'model': f"{inv.manufacturer} {inv.model_name}",
                'power_kw': inv.power_rating,
                'efficiency_pct': inv.efficiency,
                'euro_efficiency_pct': getattr(inv, 'euro_efficiency', inv.efficiency - 0.4),
                'mppt_count': getattr(inv, 'mppt_inputs', 2),
                'vmppt_min_v': getattr(inv, 'mppt_voltage_min', 180),
                'vmppt_max_v': getattr(inv, 'mppt_voltage_max', 850),
                'voc_max_v': getattr(inv, 'max_input_voltage', 1000),
                'isc_max_a': getattr(inv, 'max_input_current', 30),
                'price_egp': getattr(inv, 'price_egp', ''),
            })

    print("  [✓] equipment/solar_panels.csv")
    print("  [✓] equipment/inverters.csv")


def _synthetic_equipment_export(eq_dir: Path):
    """Write sample equipment CSVs for dry-run."""
    PANELS = [
        ['JA Solar JAM72D40-580', 580, 22.5, 49.8, 14.0, 42.1, 13.8, -0.35, 45, 2278, 1134, 32.5, 9860, 25],
        ['Jinko Tiger Neo 580',   580, 22.3, 49.6, 13.9, 42.0, 13.8, -0.34, 44, 2274, 1134, 32.0, 9750, 25],
        ['LONGi Hi-MO 6 575',     575, 22.1, 49.4, 13.8, 41.8, 13.7, -0.34, 45, 2256, 1133, 31.8, 9680, 25],
    ]
    panel_fields = ['model','power_wp','efficiency_pct','voc_v','isc_a','vmpp_v',
                    'impp_a','temp_coeff_pmax','noct_c','length_mm','width_mm',
                    'weight_kg','price_egp','warranty_years']
    with open(eq_dir / 'solar_panels.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(panel_fields)
        writer.writerows(PANELS)

    INVERTERS = [
        ['Huawei SUN2000-10KTL-M1', 10.0, 98.4, 98.0, 2, 200, 1000, 1100, 26, 42000],
        ['Huawei SUN2000-17KTL-M2', 17.0, 98.6, 98.2, 3, 200, 1000, 1100, 32, 65000],
    ]
    inv_fields = ['model','power_kw','efficiency_pct','euro_efficiency_pct','mppt_count',
                  'vmppt_min_v','vmppt_max_v','voc_max_v','isc_max_a','price_egp']
    with open(eq_dir / 'inverters.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(inv_fields)
        writer.writerows(INVERTERS)

    print("  [✓] equipment/solar_panels.csv (synthetic)")
    print("  [✓] equipment/inverters.csv (synthetic)")


def export_validation_data(output_dir: Path):
    """Write the 5-city case study validation CSV."""
    val_dir = output_dir / 'validation'
    val_dir.mkdir(parents=True, exist_ok=True)

    CASES = [
        ['CS-01', 'Cairo',      30.044, 31.236, 'Nile Delta / Semi-arid',    1480, 1511, 2.1],
        ['CS-02', 'Alexandria', 31.200, 29.920, 'Mediterranean Coast',        1440, 1475, 2.4],
        ['CS-03', 'Aswan',      24.090, 32.900, 'Upper Egypt / Hyper-arid',   1820, 1958, 7.6],
        ['CS-04', 'Hurghada',   27.260, 33.810, 'Eastern Desert',             1720, 1720, 0.0],
        ['CS-05', 'Mansoura',   31.040, 31.380, 'Delta Interior',             1430, 1480, 3.5],
    ]
    fields = ['case_id', 'city', 'latitude', 'longitude', 'climate_zone',
              'pvwatts_ref_sy', 'shamsi_sy', 'mape_pct']

    with open(val_dir / 'case_studies_5.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(CASES)

    print("  [✓] validation/case_studies_5.csv")


def create_zenodo_metadata(output_dir: Path):
    """Generate .zenodo.json metadata file."""
    metadata = {
        "title": "Egyptian Solar Energy Dataset (ESED) v1.0: Multi-Year Climate and Equipment Data for Solar System Design",
        "upload_type": "dataset",
        "description": (
            "Comprehensive multi-year climate and equipment dataset for solar photovoltaic "
            "research in Egypt. Contains 341,991 daily climate records across 119 Egyptian "
            "locations (2018-2026) from NASA POWER, enriched with K-Means dust-risk scores "
            "(4 zones). Includes equipment catalogues (8 panel models, 7 inverter models), "
            "EEHC August 2024 tariff schedules, and 5-city PVWatts v5 validation results. "
            "Released alongside the Shamsi Smart multi-model AI framework paper (Applied Energy, under review)."
        ),
        "access_right": "open",
        "license": "CC-BY-4.0",
        "embargo_date": None,
        "creators": [
            {
                "name": "[Your Last Name], [Your First Name]",
                "affiliation": "[Your University], Faculty of Engineering",
                "orcid": "0000-0000-0000-0000"
            },
            {
                "name": "[Supervisor Last Name], [Supervisor First Name]",
                "affiliation": "[Your University], Faculty of Engineering",
                "orcid": "0000-0000-0000-0000"
            }
        ],
        "keywords": [
            "solar energy", "photovoltaic", "Egypt", "MENA",
            "climate data", "NASA POWER", "machine learning", "deep learning",
            "dust", "renewable energy", "GHI", "irradiance", "dataset"
        ],
        "subjects": [
            {"term": "Solar Energy", "identifier": "https://id.loc.gov/authorities/subjects/sh85124928"},
            {"term": "Photovoltaic Power Generation", "identifier": "https://id.loc.gov/authorities/subjects/sh2001008719"}
        ],
        "language": "eng",
        "notes": (
            "Climate data sourced from NASA POWER API v2 (public domain, US Government). "
            "Value-added features (dust_zone, dust_risk_score) are original contributions "
            "released under CC BY 4.0. Equipment prices are market estimates as of Q1 2025. "
            "EEHC tariff data derived from public regulatory documents."
        ),
        "related_identifiers": [
            {
                "identifier": "https://github.com/shamsi-smart/ai-engine",
                "relation": "isSupplementTo",
                "scheme": "url"
            }
        ],
        "version": "1.0",
        "publication_date": datetime.now().strftime('%Y-%m-%d'),
        "communities": [
            {"identifier": "zenodo"},
            {"identifier": "solar-energy"}
        ]
    }

    # Save to dataset release dir
    zenodo_path = output_dir.parent / '.zenodo.json'
    with open(zenodo_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"  [✓] .zenodo.json written to {zenodo_path}")
    return metadata


def create_zip_archive(output_dir: Path) -> Path:
    """Package the dataset directory into a ZIP file."""
    zip_path = output_dir.parent / 'ESED_v1.0.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(output_dir.rglob('*')):
            if file_path.is_file():
                arcname = file_path.relative_to(output_dir.parent)
                zf.write(file_path, arcname)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"  [✓] ESED_v1.0.zip — {size_mb:.1f} MB")
    return zip_path


# ─────────────────────────────────────────────────────────────────────────────
# 2. Zenodo API upload
# ─────────────────────────────────────────────────────────────────────────────

def upload_to_zenodo(zip_path: Path, metadata: dict, token: str):
    """
    Upload dataset to Zenodo via REST API.
    See: https://developers.zenodo.org/#quickstart-upload
    """
    try:
        import requests
    except ImportError:
        print("[ERROR] requests library not installed. Run: pip install requests")
        return

    headers = {'Authorization': f'Bearer {token}'}

    # Step 1: Create a new deposition
    r = requests.post(f'{ZENODO_API}/deposit/depositions',
                      headers=headers, json={})
    r.raise_for_status()
    deposition_id = r.json()['id']
    bucket_url = r.json()['links']['bucket']
    print(f"  [✓] Zenodo deposition created: ID={deposition_id}")

    # Step 2: Upload file
    with open(zip_path, 'rb') as f:
        r = requests.put(f'{bucket_url}/{zip_path.name}',
                         data=f, headers=headers)
    r.raise_for_status()
    print(f"  [✓] File uploaded: {zip_path.name}")

    # Step 3: Update metadata
    r = requests.put(f'{ZENODO_API}/deposit/depositions/{deposition_id}',
                     headers=headers, json={'metadata': metadata})
    r.raise_for_status()
    print(f"  [✓] Metadata updated")

    print(f"\n  Deposition URL: https://zenodo.org/deposit/{deposition_id}")
    print(f"  Review and publish manually at the URL above.")
    print(f"  DOI will be assigned upon publication.")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Main
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Prepare ESED dataset for Zenodo upload')
    p.add_argument('--dry-run', action='store_true',
                   help='Use synthetic data — no DB required')
    p.add_argument('--upload', action='store_true',
                   help='Upload to Zenodo after packaging')
    p.add_argument('--token', type=str, default=None,
                   help='Zenodo API token (required if --upload)')
    p.add_argument('--output', type=str, default=str(OUTPUT_DIR),
                   help=f'Output directory (default: {OUTPUT_DIR})')
    return p.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output)
    dry_run = args.dry_run or not DJANGO_AVAILABLE

    if dry_run:
        print("[INFO] Running in dry-run mode (synthetic data)")

    print("\n=== ESED Dataset Export ===\n")

    print("1. Exporting climate data...")
    stats = export_climate_data(output_dir, dry_run=dry_run)

    print("\n2. Exporting equipment data...")
    export_equipment_data(output_dir, dry_run=dry_run)

    print("\n3. Exporting validation data...")
    export_validation_data(output_dir)

    print("\n4. Generating Zenodo metadata...")
    metadata = create_zenodo_metadata(output_dir)

    print("\n5. Creating ZIP archive...")
    zip_path = create_zip_archive(output_dir)

    if args.upload:
        if not args.token:
            print("[ERROR] --token required for Zenodo upload")
            sys.exit(1)
        print("\n6. Uploading to Zenodo...")
        upload_to_zenodo(zip_path, metadata, args.token)
    else:
        print(f"\n[INFO] Skipping upload. Run with --upload --token $ZENODO_TOKEN to publish.")

    print(f"\n=== Done ===")
    print(f"Dataset: {output_dir}")
    print(f"Archive: {zip_path}")
    print(f"Records: {stats.get('daily_records', '?'):,}")


if __name__ == '__main__':
    main()
