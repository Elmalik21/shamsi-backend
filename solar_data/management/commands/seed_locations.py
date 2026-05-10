# solar_data/management/commands/seed_locations.py
"""
Seed governorates and locations from the built-in coordinates CSV.
Run on Railway via: python manage.py seed_locations
"""
import csv
import os
from django.core.management.base import BaseCommand
from solar_data.models import Governorate, Location


COORDS_CSV = os.path.join(
    os.path.dirname(__file__),  # commands/
    '..', '..', '..',           # back to project root (solar_data/management/commands -> root)
    'data', 'egypt_coordinates_corrected.csv'
)


class Command(BaseCommand):
    help = 'Seed Governorate and Location tables from the bundled coordinates CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing Governorate/Location rows before seeding',
        )

    def handle(self, *args, **options):
        csv_path = os.path.normpath(COORDS_CSV)
        self.stdout.write(f'Reading coordinates from: {csv_path}')

        if not os.path.exists(csv_path):
            self.stderr.write(self.style.ERROR(f'CSV not found: {csv_path}'))
            return

        if options['clear']:
            deleted_loc = Location.objects.all().delete()
            deleted_gov = Governorate.objects.all().delete()
            self.stdout.write(self.style.WARNING(
                f'Cleared {deleted_loc[0]} locations and {deleted_gov[0]} governorates.'
            ))

        gov_cache = {}
        loc_created = 0
        loc_updated = 0
        gov_created = 0

        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_id   = row.get('#', '').strip()
                name     = row.get('Location', '').strip()
                gov_name = row.get('Governorate', '').strip()
                lat      = row.get('Latitude', '').strip()
                lon      = row.get('Longitude', '').strip()

                if not raw_id or not name or not gov_name:
                    continue

                try:
                    location_id = int(raw_id)
                    latitude    = float(lat)
                    longitude   = float(lon)
                except ValueError as exc:
                    self.stderr.write(f'Skipping row {raw_id!r}: {exc}')
                    continue

                # --- Governorate ---
                if gov_name not in gov_cache:
                    gov, created = Governorate.objects.get_or_create(
                        name=gov_name,
                        defaults={'code': gov_name[:3].upper()},
                    )
                    gov_cache[gov_name] = gov
                    if created:
                        gov_created += 1
                gov = gov_cache[gov_name]

                # --- Location ---
                loc, created = Location.objects.update_or_create(
                    location_id=location_id,
                    defaults={
                        'name':        name,
                        'governorate': gov,
                        'latitude':    latitude,
                        'longitude':   longitude,
                        'location_type': 'CITY',
                    },
                )
                if created:
                    loc_created += 1
                else:
                    loc_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done — governorates created: {gov_created}, '
            f'locations created: {loc_created}, updated: {loc_updated}'
        ))
