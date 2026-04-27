# data/import_climate_data.py
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from django.db import transaction, models

# إضافة مسار المشروع
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shamsi_smart.settings')

import django
django.setup()

from solar_data.models import Governorate, Location, DailyClimateData, MonthlySummary

def clean_and_validate_data(chunk):
    """تنظيف وتحقق من صحة البيانات"""
    # نسخة من البيانات للتحقق
    cleaned = chunk.copy()
    
    # 1. التأكد من أسماء الأعمدة
    expected_columns = [
        'Location_ID', 'Location_Name', 'Governorate', 'Latitude', 'Longitude', 'Date',
        'ALLSKY_SFC_SW_DWN', 'T2M', 'T2M_MAX', 'T2M_MIN', 'RH2M', 'WS2M',
        'ALLSKY_SFC_SW_DNI', 'ALLSKY_SFC_SW_DIFF', 'CLOUD_AMT', 'ALLSKY_SRF_ALB', 'PS', 'PRECTOTCORR'
    ]
    
    missing_cols = [col for col in expected_columns if col not in cleaned.columns]
    if missing_cols:
        print(f"⚠️  أعمدة مفقودة: {missing_cols}")
        # محاولة العثور على أعمدة بأسماء مشابهة
        for missing in missing_cols:
            for col in cleaned.columns:
                if missing.lower() in col.lower():
                    cleaned.rename(columns={col: missing}, inplace=True)
                    print(f"   - تمت إعادة تسمية '{col}' إلى '{missing}'")
    
    # 2. تحويل أنواع البيانات
    numeric_columns = ['Latitude', 'Longitude', 'ALLSKY_SFC_SW_DWN', 'T2M', 'T2M_MAX', 'T2M_MIN', 
                      'RH2M', 'WS2M', 'ALLSKY_SFC_SW_DNI', 'ALLSKY_SFC_SW_DIFF', 
                      'CLOUD_AMT', 'ALLSKY_SRF_ALB', 'PS', 'PRECTOTCORR']
    
    for col in numeric_columns:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')
    
    # 3. تحويل التواريخ
    if 'Date' in cleaned.columns:
        cleaned['Date'] = pd.to_datetime(cleaned['Date'], format='%m/%d/%Y', errors='coerce')
    
    # 4. إزالة الصفوف ذات القيم المفقودة الأساسية
    required_cols = ['Location_ID', 'Location_Name', 'Governorate', 'Latitude', 'Longitude', 'Date', 'T2M']
    cleaned = cleaned.dropna(subset=required_cols, how='any')
    
    # 5. إضافة أعمدة محسوبة
    if 'T2M_MAX' in cleaned.columns and 'T2M_MIN' in cleaned.columns:
        cleaned['TEMP_RANGE'] = cleaned['T2M_MAX'] - cleaned['T2M_MIN']
    
    return cleaned

def parse_date(date_str):
    """تحويل التاريخ من mm/dd/yyyy إلى كائن تاريخ"""
    try:
        return datetime.strptime(str(date_str), '%m/%d/%Y').date()
    except:
        try:
            return datetime.strptime(str(date_str), '%Y-%m-%d').date()
        except:
            # محاولة التحليل التلقائي
            return pd.to_datetime(date_str, errors='coerce').date()

@transaction.atomic
def import_climate_data(csv_path, batch_size=5000):
    """
    تحميل البيانات المناخية من CSV مع الأعمدة الصحيحة
    """
    print(f"📂 جاري قراءة ملف البيانات: {csv_path}")
    
    # قراءة حجم الملف أولاً
    file_size = os.path.getsize(csv_path) / (1024 * 1024)
    print(f"📊 حجم الملف: {file_size:.2f} MB")
    
    # قراءة CSV مع chunks
    chunks = pd.read_csv(csv_path, chunksize=20000, low_memory=False)
    
    total_records = 0
    processed_records = 0
    location_cache = {}
    governorate_cache = {}
    
    for chunk_idx, chunk in enumerate(chunks):
        print(f"\n🔢 معالجة الجزء {chunk_idx + 1}...")
        
        # تنظيف البيانات
        cleaned_chunk = clean_and_validate_data(chunk)
        
        if cleaned_chunk.empty:
            print("   ⚠️  لا توجد بيانات صالحة في هذا الجزء")
            continue
        
        print(f"   📝 عدد الصفوط الصالحة: {len(cleaned_chunk):,}")
        
        # قائمة لحفظ البيانات قبل الـ bulk_create
        daily_data_to_create = []
        
        for idx, row in cleaned_chunk.iterrows():
            total_records += 1
            
            try:
                # 1. المحافظة
                gov_name = str(row['Governorate']).strip()
                if gov_name not in governorate_cache:
                    governorate, created = Governorate.objects.get_or_create(name=gov_name)
                    governorate_cache[gov_name] = governorate
                governorate = governorate_cache[gov_name]
                
                # 2. الموقع
                location_id = int(row['Location_ID'])
                location_key = f"{location_id}_{gov_name}"
                
                if location_key not in location_cache:
                    location, created = Location.objects.update_or_create(
                        location_id=location_id,
                        defaults={
                            'name': str(row['Location_Name']).strip(),
                            'governorate': governorate,
                            'latitude': float(row['Latitude']),
                            'longitude': float(row['Longitude']),
                        }
                    )
                    location_cache[location_key] = location
                location = location_cache[location_key]
                
                # 3. التاريخ
                date_obj = row['Date'].date() if isinstance(row['Date'], pd.Timestamp) else parse_date(row['Date'])
                if not date_obj:
                    continue
                
                # 4. إنشاء كائن البيانات المناخية
                climate_data = DailyClimateData(
                    location=location,
                    date=date_obj,
                    allsky_sfc_sw_dwn=float(row.get('ALLSKY_SFC_SW_DWN', 0)),
                    t2m=float(row['T2M']),
                    t2m_max=float(row.get('T2M_MAX', row['T2M'])),
                    t2m_min=float(row.get('T2M_MIN', row['T2M'])),
                    rh2m=float(row.get('RH2M', 0)),
                    ws2m=float(row.get('WS2M', 0)),
                    allsky_sfc_sw_dni=float(row.get('ALLSKY_SFC_SW_DNI', 0)) if pd.notna(row.get('ALLSKY_SFC_SW_DNI')) else None,
                    allsky_sfc_sw_diff=float(row.get('ALLSKY_SFC_SW_DIFF', 0)) if pd.notna(row.get('ALLSKY_SFC_SW_DIFF')) else None,
                    cloud_amt=float(row.get('CLOUD_AMT', 0)) if pd.notna(row.get('CLOUD_AMT')) else None,
                    allsky_srf_alb=float(row.get('ALLSKY_SRF_ALB', 0.2)) if pd.notna(row.get('ALLSKY_SRF_ALB')) else None,
                    ps=float(row.get('PS', 101.3)) if pd.notna(row.get('PS')) else None,
                    prectotcorr=float(row.get('PRECTOTCORR', 0)) if pd.notna(row.get('PRECTOTCORR')) else 0
                )
                
                daily_data_to_create.append(climate_data)
                processed_records += 1
                
                # حفظ كل batch_size
                if len(daily_data_to_create) >= batch_size:
                    print(f"   💾 حفظ {len(daily_data_to_create):,} سجل...")
                    DailyClimateData.objects.bulk_create(daily_data_to_create, ignore_conflicts=True)
                    daily_data_to_create = []
                    print(f"   ✅ إجمالي السجلات المحفوظة: {processed_records:,}")
                    
            except Exception as e:
                print(f"   ❌ خطأ في الصف {total_records}: {str(e)}")
                continue
        
        # حفظ البقية
        if daily_data_to_create:
            print(f"   💾 حفظ {len(daily_data_to_create):,} سجل...")
            DailyClimateData.objects.bulk_create(daily_data_to_create, ignore_conflicts=True)
        
        print(f"   ✅ تم معالجة الجزء {chunk_idx + 1}")
        print(f"   📊 إجمالي المعالجة: {processed_records:,} من {total_records:,}")
    
    print(f"\n{'='*60}")
    print(f"🎉 اكتمل التحميل بنجاح!")
    print(f"{'='*60}")
    print(f"📊 إجمالي السجلات المعالجة: {processed_records:,}")
    print(f"📍 عدد المواقع: {len(location_cache)}")
    print(f"🏛️  عدد المحافظات: {len(governorate_cache)}")
    print(f"📅 نطاق التواريخ المتوقع: 2018-2026 ({8*365*119:,} سجل محتمل)")
    
    return processed_records

def create_monthly_summaries():
    """إنشاء ملخصات شهرية باستخدام تجميعات قاعدة البيانات"""
    print("\n📈 جاري إنشاء الملخصات الشهرية (قد يستغرق وقتًا)...")
    
    from django.db.models import Avg, Max, Min, Sum, Count
    
    # الحصول على جميع المواقع
    locations = Location.objects.all()
    total_locations = locations.count()
    
    for idx, location in enumerate(locations, 1):
        print(f"   🔄 معالجة الموقع {idx}/{total_locations}: {location.name}")
        
        # استعلام لتجميع البيانات شهرياً
        from django.db.models.functions import TruncMonth
        
        monthly_data = DailyClimateData.objects.filter(location=location).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            max_radiation=Max('allsky_sfc_sw_dwn'),
            min_radiation=Min('allsky_sfc_sw_dwn'),
            total_radiation=Sum('allsky_sfc_sw_dwn'),
            
            avg_temp=Avg('t2m'),
            avg_temp_max=Avg('t2m_max'),
            avg_temp_min=Avg('t2m_min'),
            max_temp=Max('t2m_max'),
            min_temp=Min('t2m_min'),
            
            avg_humidity=Avg('rh2m'),
            avg_wind=Avg('ws2m'),
            total_precipitation=Sum('prectotcorr'),
            avg_cloud=Avg('cloud_amt'),
            
            clear_days=Count('id', filter=models.Q(cloud_amt__lt=20)),
            cloudy_days=Count('id', filter=models.Q(cloud_amt__gt=80)),
            hot_days=Count('id', filter=models.Q(t2m_max__gt=35)),
            rainy_days=Count('id', filter=models.Q(prectotcorr__gt=1)),
            
            days_count=Count('id')
        ).order_by('month')
        
        # حفظ النتائج
        for data in monthly_data:
            if data['month']:
                summary, created = MonthlySummary.objects.update_or_create(
                    location=location,
                    year=data['month'].year,
                    month=data['month'].month,
                    defaults={
                        'avg_radiation': data['avg_radiation'] or 0,
                        'max_radiation': data['max_radiation'] or 0,
                        'min_radiation': data['min_radiation'] or 0,
                        'total_radiation': data['total_radiation'] or 0,
                        
                        'avg_temperature': data['avg_temp'] or 0,
                        'avg_temp_max': data['avg_temp_max'] or 0,
                        'avg_temp_min': data['avg_temp_min'] or 0,
                        'max_temperature': data['max_temp'] or 0,
                        'min_temperature': data['min_temp'] or 0,
                        
                        'avg_humidity': data['avg_humidity'] or 0,
                        'avg_wind_speed': data['avg_wind'] or 0,
                        'total_precipitation': data['total_precipitation'] or 0,
                        'avg_cloud_cover': data['avg_cloud'] or 0,
                        
                        'clear_days': data['clear_days'] or 0,
                        'cloudy_days': data['cloudy_days'] or 0,
                        'hot_days': data['hot_days'] or 0,
                        'rainy_days': data['rainy_days'] or 0,
                        
                        'days_count': data['days_count'] or 0,
                    }
                )
    
    print("✅ اكتملت الملخصات الشهرية")

def update_location_statistics():
    """تحديث الإحصائيات في جدول المواقع باستخدام تجميعات قاعدة البيانات"""
    print("\n📊 جاري تحديث إحصائيات المواقع...")
    
    from django.db.models import Avg, Max, Min
    
    locations = Location.objects.all()
    
    for location in locations:
        # استخدام تجميعات SQL لتحسين الأداء
        stats = DailyClimateData.objects.filter(location=location).aggregate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            avg_temp_max=Avg('t2m_max'),
            avg_temp_min=Avg('t2m_min'),
            avg_wind=Avg('ws2m'),
            max_radiation=Max('allsky_sfc_sw_dwn'),
            max_temp=Max('t2m_max'),
            min_temp=Min('t2m_min'),
        )
        
        location.avg_solar_radiation = stats['avg_radiation'] or 0
        location.avg_temperature = stats['avg_temp'] or 0
        location.avg_wind_speed = stats['avg_wind'] or 0
        
        # حساب درجة الإمكانية الشمسية
        if stats['avg_radiation'] and stats['avg_temp']:
            avg_radiation = stats['avg_radiation']
            avg_temp = stats['avg_temp']
            
            # معادلة مبسطة لدرجة الإمكانية الشمسية (0-100)
            radiation_score = min((avg_radiation / 7.0) * 70, 70)  # 70% للإشعاع
            temp_score = max(30 - abs(avg_temp - 25), 0)  # 30% لدرجة الحرارة
            
            location.solar_potential_score = radiation_score + temp_score
        
        location.save()
    
    print("✅ اكتمل تحديث إحصائيات المواقع")

def verify_data_integrity():
    """التحقق من سلامة البيانات"""
    print("\n🔍 جاري التحقق من سلامة البيانات...")

    from django.db.models import Min, Max  # أضف هذا الاستيراد

    
    total_locations = Location.objects.count()
    total_climate_data = DailyClimateData.objects.count()
    total_months = MonthlySummary.objects.count()
    
    print(f"   📍 عدد المواقع: {total_locations}")
    print(f"   📅 عدد السجلات اليومية: {total_climate_data:,}")
    print(f"   📊 عدد الملخصات الشهرية: {total_months}")
    
    # التحقق من نطاق التواريخ
    earliest = DailyClimateData.objects.aggregate(Min('date'))['date__min']
    latest = DailyClimateData.objects.aggregate(Max('date'))['date__max']
    
    print(f"   📅 نطاق التواريخ: {earliest} إلى {latest}")
    
    # عينة عشوائية للتحقق
    sample = DailyClimateData.objects.order_by('?')[:5]
    print(f"\n   🧪 عينة عشوائية (5 سجلات):")
    for data in sample:
        print(f"      • {data.location.name} - {data.date}: {data.t2m:.1f}°C, {data.allsky_sfc_sw_dwn:.2f} kWh/m²")
    
    print("\n✅ اكتمل التحقق")

if __name__ == "__main__":
    # المسار إلى ملف البيانات
    csv_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'smart_raw', 'egypt_solar_data_2018_2026.csv'
    )
    
    if not os.path.exists(csv_file_path):
        print(f"❌ ملف البيانات غير موجود: {csv_file_path}")
        print("📁 تأكد من وضع الملف في: data/smart_raw/egypt_solar_data_2018_2026.csv")
        sys.exit(1)
    
    print("🚀 بدء تحميل البيانات المناخية لمصر (2018-2026)")
    print("=" * 60)
    
    try:
        # 1. تحميل البيانات
        total_loaded = import_climate_data(csv_file_path)
        
        if total_loaded > 0:
            # 2. إنشاء الملخصات الشهرية
            create_monthly_summaries()
            
            # 3. تحديث إحصائيات المواقع
            update_location_statistics()
            
            # 4. التحقق من سلامة البيانات
            verify_data_integrity()
            
            print("\n" + "=" * 60)
            print("✨ اكتمل تحميل البيانات بنجاح!")
            print("=" * 60)
            print(f"📈 الإحصائيات النهائية:")
            print(f"   • عدد المواقع: {Location.objects.count()}")
            print(f"   • عدد السجلات اليومية: {DailyClimateData.objects.count():,}")
            print(f"   • عدد الملخصات الشهرية: {MonthlySummary.objects.count():,}")
            print(f"   • عدد المحافظات: {Governorate.objects.count()}")
            
            # تقدير حجم البيانات
            estimated_size = (DailyClimateData.objects.count() * 0.1) / 1024  # تقدير بـ 100بايت لكل سجل
            print(f"   • الحجم التقريبي: {estimated_size:.2f} MB")
            
        else:
            print("⚠️  لم يتم تحميل أي سجلات. تحقق من ملف البيانات.")
            
    except Exception as e:
        print(f"\n❌ حدث خطأ أثناء التحميل: {str(e)}")
        import traceback
        traceback.print_exc()