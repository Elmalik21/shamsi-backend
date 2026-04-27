import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.conf import settings
from solar_data.models import Location, Governorate, DailyClimateData

class Command(BaseCommand):
    help = 'Import solar energy data from CSV file with fixed paths and fields'

    def handle(self, *args, **options):
        # التعديل: الوصول للمجلد الرئيسي ثم الدخول لمجلد Data
        base_parent = os.path.dirname(settings.BASE_DIR)
        file_path = os.path.join(base_parent, 'Data', 'output', 'egypt_solar_data_2018_2026.csv')
        
        self.stdout.write(f"🔍 Searching for file at: {file_path}")

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"❌ File not found at {file_path}"))
            return

        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            self.stdout.write(f"📊 Loaded {len(df)} records. Processing...")

            def clean_float(val):
                try:
                    return float(val) if not pd.isna(val) else 0.0
                except:
                    return 0.0

            # 1. إعداد المواقع
            unique_locations = df[['Location_Name', 'Governorate', 'Latitude', 'Longitude']].drop_duplicates()
            loc_map = {}
            
            for _, row in unique_locations.iterrows():
                loc_name = row['Location_Name']
                gov, _ = Governorate.objects.get_or_create(name=row['Governorate'])
                
                # حذف data_source لأنه غير موجود في الموديل
                loc, created = Location.objects.get_or_create(
                    name=loc_name,
                    defaults={
                        'governorate': gov,
                        'latitude': row['Latitude'],
                        'longitude': row['Longitude'],
                        'location_id': abs(hash(loc_name)) % 1000000,
                        'location_type': 'CITY'
                    }
                )
                loc_map[loc_name] = loc

            # 2. استيراد بيانات المناخ
            self.stdout.write("☀️ Importing climate data...")
            batch_size = 2000
            climate_objects = []

            for index, row in df.iterrows():
                location = loc_map.get(row['Location_Name'])
                
                # إضافة الحقول الموجودة في models.py فقط
                climate_objects.append(DailyClimateData(
                    location=location,
                    date=row['Date'],
                    allsky_sfc_sw_dwn=clean_float(row.get('ALLSKY_SFC_SW_DWN')),
                    t2m=clean_float(row.get('T2M')),
                    t2m_max=clean_float(row.get('T2M_MAX')),
                    t2m_min=clean_float(row.get('T2M_MIN')),
                    rh2m=clean_float(row.get('RH2M')),
                    ws2m=clean_float(row.get('WS2M')),
                    prectotcorr=clean_float(row.get('PRECTOTCORR'))
                ))

                if len(climate_objects) >= batch_size:
                    DailyClimateData.objects.bulk_create(climate_objects, ignore_conflicts=True)
                    climate_objects = []
                    self.stdout.write(f"   💾 Saved {index} records...")

            if climate_objects:
                DailyClimateData.objects.bulk_create(climate_objects, ignore_conflicts=True)

            self.stdout.write(self.style.SUCCESS("✅ Success! Data imported correctly."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))