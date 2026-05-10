# solar_data/management/commands/import_solar_data.py (updated version)
import csv
import os
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from solar_data.models import Governorate, Location, DailyClimateData

class Command(BaseCommand):
    help = 'Import solar data from Egypt solar data CSV file (2018-2026)'
    
    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the CSV file')
        parser.add_argument('--batch-size', type=int, default=1000, help='Batch size for bulk creation')
        parser.add_argument('--skip-existing', action='store_true', help='Skip existing records')
        parser.add_argument('--test-only', action='store_true', help='Test import without saving')
        parser.add_argument('--decimal-places', type=int, default=6, help='Number of decimal places for coordinates')
    
    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        batch_size = kwargs['batch_size']
        skip_existing = kwargs['skip_existing']
        test_only = kwargs['test_only']
        decimal_places = kwargs['decimal_places']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File {file_path} does not exist'))
            return
        
        start_time = datetime.now()
        self.stdout.write(self.style.SUCCESS(f'Starting import from {file_path}'))
        self.stdout.write(f'Batch size: {batch_size}, Skip existing: {skip_existing}, Test only: {test_only}')
        self.stdout.write(f'Decimal places for coordinates: {decimal_places}')
        
        self.import_combined_data(file_path, batch_size, skip_existing, test_only, decimal_places)
        
        end_time = datetime.now()
        duration = end_time - start_time
        self.stdout.write(self.style.SUCCESS(f'Import completed in {duration}'))
    
    def import_combined_data(self, file_path, batch_size, skip_existing, test_only, decimal_places):
        """Import combined location and climate data from your CSV"""
        self.stdout.write('\n=== Importing Combined Location & Climate Data ===')
        
        # Map your CSV columns to model fields
        column_map = {
            'location_id': 'Location_ID',
            'name': 'Location_Name',
            'governorate': 'Governorate',
            'latitude': 'Latitude',
            'longitude': 'Longitude',
            'date': 'Date',
            'allsky_sfc_sw_dwn': 'ALLSKY_SFC_SW_DWN',
            't2m': 'T2M',
            't2m_max': 'T2M_MAX',
            't2m_min': 'T2M_MIN',
            'rh2m': 'RH2M',
            'ws2m': 'WS2M',
            'allsky_sfc_sw_dni': 'ALLSKY_SFC_SW_DNI',
            'allsky_sfc_sw_diff': 'ALLSKY_SFC_SW_DIFF',
            'cloud_amt': 'CLOUD_AMT',
            'allsky_srf_alb': 'ALLSKY_SRF_ALB',
            'ps': 'PS',
            'prectotcorr': 'PRECTOTCORR',
        }
        
        # Track processed locations to avoid duplicates
        processed_locations = {}
        climate_data_to_create = []
        location_count = 0
        climate_count = 0
        skipped_locations = 0
        skipped_climate = 0
        errors = 0
        
        try:
            # Open file with BOM handling
            with open(file_path, 'r', encoding='utf-8-sig') as csvfile:  # utf-8-sig handles BOM
                # Manually specify comma as delimiter
                reader = csv.DictReader(csvfile)
                
                self.stdout.write(f'Processing CSV with columns: {reader.fieldnames}')
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Extract location information
                        location_id = row[column_map['location_id']].strip()
                        location_name = row[column_map['name']].strip()
                        governorate_name = row[column_map['governorate']].strip()
                        
                        # Round coordinates to specified decimal places
                        try:
                            lat = self._round_decimal(float(row[column_map['latitude']]), decimal_places)
                            lon = self._round_decimal(float(row[column_map['longitude']]), decimal_places)
                        except (ValueError, TypeError) as e:
                            self.stdout.write(self.style.WARNING(f'Row {row_num}: Invalid coordinates - {e}'))
                            errors += 1
                            continue
                        
                        # Create or get governorate
                        governorate = None
                        if governorate_name and not test_only:
                            governorate, created = Governorate.objects.get_or_create(
                                name=governorate_name,
                                defaults={'code': governorate_name[:3].upper()}
                            )
                            if created:
                                self.stdout.write(f'Created governorate: {governorate_name}')
                        
                        # Create or get location (only once per location_id)
                        if location_id not in processed_locations:
                            if not test_only:
                                try:
                                    location, created = Location.objects.update_or_create(
                                        location_id=location_id,
                                        defaults={
                                            'name': location_name,
                                            'governorate': governorate,
                                            'latitude': lat,
                                            'longitude': lon,
                                        }
                                    )
                                    processed_locations[location_id] = location
                                    if created:
                                        location_count += 1
                                        if location_count % 10 == 0:
                                            self.stdout.write(f'Created {location_count} locations...')
                                    else:
                                        skipped_locations += 1
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f'Row {row_num}: Error creating location - {e}'))
                                    self.stdout.write(f'Location data: ID={location_id}, Name={location_name}, Lat={lat}, Lon={lon}')
                                    errors += 1
                                    continue
                            else:
                                # In test mode, just track it
                                processed_locations[location_id] = {'id': location_id, 'name': location_name}
                                location_count += 1
                        
                        # Get location object (real or mock)
                        if test_only:
                            location = processed_locations[location_id]
                        else:
                            location = processed_locations[location_id]
                        
                        # Parse date (handle m/d/yyyy format)
                        date_str = row[column_map['date']].strip()
                        date = self._parse_date(date_str)
                        
                        if not date:
                            self.stdout.write(self.style.WARNING(f'Row {row_num}: Invalid date format: {date_str}'))
                            errors += 1
                            continue
                        
                        # Check if climate record already exists
                        if not test_only and skip_existing:
                            if DailyClimateData.objects.filter(location=location, date=date).exists():
                                skipped_climate += 1
                                continue
                        
                        # Create climate data object
                        if not test_only:
                            try:
                                climate_data = DailyClimateData(
                                    location=location,
                                    date=date,
                                    allsky_sfc_sw_dwn=self._safe_float(row[column_map['allsky_sfc_sw_dwn']]) or 0,
                                    t2m=self._safe_float(row[column_map['t2m']]) or 0,
                                    t2m_max=self._safe_float(row[column_map['t2m_max']]),
                                    t2m_min=self._safe_float(row[column_map['t2m_min']]),
                                    rh2m=self._safe_float(row[column_map['rh2m']]) or 0,
                                    ws2m=self._safe_float(row[column_map['ws2m']]) or 0,
                                    cloud_amt=self._safe_float(row[column_map['cloud_amt']]),
                                    prectotcorr=self._safe_float(row[column_map['prectotcorr']]) or 0,
                                )
                                
                                climate_data_to_create.append(climate_data)
                                
                                # Bulk create in batches
                                if len(climate_data_to_create) >= batch_size:
                                    DailyClimateData.objects.bulk_create(climate_data_to_create, ignore_conflicts=True)
                                    climate_count += len(climate_data_to_create)
                                    climate_data_to_create = []
                                    
                                    if climate_count % 10000 == 0:
                                        self.stdout.write(f'Processed {climate_count} climate records, {location_count} locations...')
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f'Row {row_num}: Error creating climate data - {e}'))
                                errors += 1
                                continue
                        else:
                            # Test mode: just count
                            climate_count += 1
                            if climate_count % 10000 == 0:
                                self.stdout.write(f'Would process {climate_count} climate records, {location_count} locations...')
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Row {row_num}: Error - {e}'))
                        self.stdout.write(f'Row data: {dict(list(row.items())[:6])}...')
                        errors += 1
                        if errors > 50:  # Increased error threshold
                            self.stdout.write(self.style.ERROR('Too many errors, stopping import'))
                            break
                
                # Create remaining climate records
                if not test_only and climate_data_to_create:
                    DailyClimateData.objects.bulk_create(climate_data_to_create, ignore_conflicts=True)
                    climate_count += len(climate_data_to_create)
                
                # Summary
                self.stdout.write('\n' + '='*50)
                self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
                self.stdout.write('='*50)
                self.stdout.write(f'Total locations: {location_count}')
                self.stdout.write(f'Skipped locations (existing): {skipped_locations}')
                self.stdout.write(f'Total climate records: {climate_count}')
                self.stdout.write(f'Skipped climate records (existing): {skipped_climate}')
                self.stdout.write(f'Errors: {errors}')
                
                if test_only:
                    self.stdout.write(self.style.WARNING('\nTEST MODE: No data was saved to database'))
                else:
                    self.stdout.write(self.style.SUCCESS('\nData import completed successfully!'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading CSV: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())
    
    def _round_decimal(self, value, decimal_places=6):
        """Round decimal to specified places"""
        if value is None:
            return None
        try:
            # Convert to Decimal for precise rounding
            decimal_value = Decimal(str(value))
            rounded = decimal_value.quantize(
                Decimal(f'1.{"0" * decimal_places}'),
                rounding=ROUND_HALF_UP
            )
            return float(rounded)
        except Exception:
            return round(value, decimal_places)
    
    def _parse_date(self, date_str):
        """Parse date from various formats including m/d/yyyy"""
        if not date_str:
            return None
        
        # Try standard format first
        date = parse_date(date_str)
        if date:
            return date
        
        # Try m/d/yyyy format (common in US dates)
        try:
            # Handle dates like "1/1/2018", "12/31/2018"
            parts = date_str.split('/')
            if len(parts) == 3:
                month, day, year = parts
                # Convert to YYYY-MM-DD format
                formatted_date = f"{year}-{int(month):02d}-{int(day):02d}"
                return parse_date(formatted_date)
        except (ValueError, IndexError):
            pass
        
        # Try other common formats
        formats = [
            '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y.%m.%d',
            '%d-%m-%Y', '%m-%d-%Y', '%Y/%m/%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _safe_float(self, value):
        """Safely convert to float, return None if invalid"""
        if value is None or value == '' or str(value).lower() in ['nan', 'null', 'none']:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value):
        """Safely convert to int, return None if invalid"""
        if value is None or value == '' or str(value).lower() in ['nan', 'null', 'none']:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None