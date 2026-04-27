from django.shortcuts import render, get_object_or_404
# استيراد دوال التجميع المطلوبة بشكل صريح
from django.db.models import Avg, Max, Min, Count, Sum, Q
from django.http import JsonResponse
from datetime import datetime, timedelta
import json
from solar_data.models import Location, DailyClimateData, MonthlySummary

# ==========================================
# Main Views
# ==========================================

def dashboard_view(request):
    """لوحة التحكم الرئيسية"""
    # إحصائيات عامة
    total_locations = Location.objects.count()
    
    # متوسط الإشعاع الشمسي العام
    avg_radiation = DailyClimateData.objects.aggregate(
        avg=Avg('allsky_sfc_sw_dwn')
    )['avg'] or 0
    
    # أفضل 5 مواقع (التي لها قراءة إشعاع)
    top_locations = Location.objects.filter(
        avg_solar_radiation__isnull=False
    ).order_by('-avg_solar_radiation')[:5]
    
    # إحصائيات المحافظات - تجميع ذكي لتقليل الاستعلامات
    governorate_stats = []
    processed_govs = set()
    
    # نستخدم select_related لتقليل الضغط على قاعدة البيانات
    locations_with_gov = Location.objects.select_related('governorate').all()
    
    for location in locations_with_gov:
        if location.governorate and location.governorate.name not in processed_govs:
            gov_locations = locations_with_gov.filter(governorate=location.governorate)
            
            # حساب المتوسط يدوياً للقائمة المفلترة
            rads = [l.avg_solar_radiation for l in gov_locations if l.avg_solar_radiation]
            avg_gov_radiation = sum(rads) / len(rads) if rads else 0
            
            governorate_stats.append({
                'name': location.governorate.name,
                'location_count': gov_locations.count(),
                'avg_radiation': avg_gov_radiation
            })
            processed_govs.add(location.governorate.name)
    
    # ترتيب المحافظات حسب الإشعاع (الأعلى أولاً)
    governorate_stats = sorted(governorate_stats, key=lambda x: x['avg_radiation'], reverse=True)
    
    context = {
        'total_locations': total_locations,
        'avg_radiation': round(avg_radiation, 2),
        'top_locations': top_locations,
        'governorate_stats': governorate_stats[:10],  # أفضل 10 محافظات
        'page_title': 'لوحة تحكم شماسي سمارت',
        'data_years': '2018-2026',
        'data_source': f'البيانات الجديدة ({DailyClimateData.objects.count()}+ سجل)',
    }
    
    return render(request, 'dashboard.html', context)


def city_detail_view(request, city_id=None):
    """تفاصيل موقع معين مع التحليل والتوصيات"""
    if not city_id:
        return render(request, 'city_detail.html', {
            'error': 'لم يتم تحديد موقع', 
            'page_title': 'خطأ'
        })
    
    try:
        # البحث عن الموقع باستخدام location_id أو id
        location = Location.objects.filter(location_id=city_id).first()
        if not location:
             location = Location.objects.filter(id=city_id).first()
             
        if not location:
            raise Location.DoesNotExist

        # البيانات المناخية لهذا الموقع
        climate_data = DailyClimateData.objects.filter(location=location).order_by('-date')
        
        # ملخصات شهرية
        monthly_summaries = MonthlySummary.objects.filter(
            location=location
        ).order_by('-year', '-month')
        
        # إحصائيات عامة (Aggregate)
        stats = DailyClimateData.objects.filter(location=location).aggregate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            max_radiation=Max('allsky_sfc_sw_dwn'),
            min_radiation=Min('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            max_temp=Max('t2m_max'),
            min_temp=Min('t2m_min'),
            avg_humidity=Avg('rh2m'),
            avg_wind=Avg('ws2m'),
            total_precipitation=Sum('prectotcorr'),
            total_days=Count('id')
        )
        
        # بيانات الشهر الحالي
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        current_month_data = DailyClimateData.objects.filter(
            location=location,
            date__year=current_year,
            date__month=current_month
        )
        
        # أفضل وأسوأ أشهر
        best_month = monthly_summaries.order_by('-avg_radiation').first()
        worst_month = monthly_summaries.order_by('avg_radiation').first()
        
        # بيانات الرسم البياني (آخر 30 يوم)
        last_30_days = climate_data[:30]
        
        # إعداد بيانات JSON للرسم البياني
        # نستخدم[::-1] لعكس الترتيب بحيث يظهر التاريخ القديم على اليسار في الرسم البياني
        chart_data = {
            'dates': [str(data.date) for data in last_30_days][::-1], 
            'radiation': [float(data.allsky_sfc_sw_dwn or 0) for data in last_30_days][::-1],
            'temperature': [float(data.t2m or 0) for data in last_30_days][::-1],
            'humidity': [float(data.rh2m or 0) for data in last_30_days][::-1],
            'wind': [float(data.ws2m or 0) for data in last_30_days][::-1],
        }
        
        # تحليل وتوصيات
        solar_analysis = analyze_solar_potential(location)
        recommendations = generate_solar_recommendations(location, stats)
        
        context = {
            'location': location,
            'climate_data': climate_data[:100],  # عرض آخر 100 يوم فقط للأداء
            'monthly_summaries': monthly_summaries[:12],
            'stats': stats,
            'current_month_data': current_month_data,
            'best_month': best_month,
            'worst_month': worst_month,
            'chart_data': json.dumps(chart_data),
            'solar_analysis': solar_analysis,
            'recommendations': recommendations,
            'page_title': f'تفاصيل {location.name}',
            'current_year': current_year,
            'current_month': current_month,
            'total_days': climate_data.count(),
        }
        
        return render(request, 'city_detail.html', context)
        
    except Location.DoesNotExist:
        return render(request, 'city_detail.html', {
            'error': f'الموقع غير موجود',
            'page_title': 'خطأ'
        })


def api_docs_view(request):
    """وثائق API"""
    return render(request, 'api_docs.html', {
        'page_title': 'وثائق API - شماسي سمارت'
    })


def all_locations_view(request):
    """عرض جميع المواقع"""
    locations = Location.objects.select_related('governorate').all().order_by('name')
    
    # تقسيم حسب المحافظة
    locations_by_gov = {}
    for location in locations:
        gov_name = location.governorate.name if location.governorate else "غير محدد"
        if gov_name not in locations_by_gov:
            locations_by_gov[gov_name] = []
        locations_by_gov[gov_name].append(location)
    
    context = {
        'locations_by_gov': locations_by_gov,
        'total_locations': len(locations),
        'page_title': 'جميع المواقع'
    }
    
    return render(request, 'all_locations.html', context)


# ==========================================
# API Helper Views
# ==========================================

def get_climate_chart_data(request, location_id):
    """API لإرجاع بيانات الرسم البياني"""
    try:
        location = Location.objects.filter(location_id=location_id).first()
        if not location:
             location = Location.objects.filter(id=location_id).first()
             
        if not location:
            return JsonResponse({'error': 'Location not found'}, status=404)
        
        # بيانات آخر 30 يوم
        last_month = datetime.now() - timedelta(days=30)
        data = DailyClimateData.objects.filter(
            location=location,
            date__gte=last_month
        ).order_by('date')
        
        chart_data = {
            'dates': [str(d.date) for d in data],
            'radiation': [float(d.allsky_sfc_sw_dwn or 0) for d in data],
            'temperature': [float(d.t2m or 0) for d in data],
            'humidity': [float(d.rh2m or 0) for d in data],
            'wind': [float(d.ws2m or 0) for d in data],
        }
        
        return JsonResponse(chart_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# Helper Functions (Logic)
# ==========================================

def analyze_solar_potential(location):
    """تحليل الإمكانية الشمسية للموقع"""
    score = location.solar_potential_score or 0
    
    analysis = {
        'potential_score': score,
        'rating': 'غير محدد',
        'description': 'لا توجد بيانات كافية للتقييم',
        'advantages': [],
        'challenges': [],
        'optimal_seasons': ['الربيع', 'الصيف'],
    }
    
    # تقييم الإمكانية
    if score >= 80:
        analysis['rating'] = 'ممتازة'
        analysis['description'] = 'موقع مثالي للاستثمار في الطاقة الشمسية'
    elif score >= 60:
        analysis['rating'] = 'جيدة جداً'
        analysis['description'] = 'موقع ذو جدوى اقتصادية عالية'
    elif score >= 40:
        analysis['rating'] = 'جيدة'
        analysis['description'] = 'موقع مناسب مع بعض الاعتبارات'
    elif score > 0:
        analysis['rating'] = 'متوسطة'
        analysis['description'] = 'يمكن الاستفادة من الطاقة الشمسية بشكل محدود'
    
    # مزايا
    if location.avg_solar_radiation and location.avg_solar_radiation > 5.5:
        analysis['advantages'].append('إشعاع شمسي يومي مرتفع جداً')
    
    # تحديات (مثال بسيط)
    if location.governorate and location.governorate.name in ['أسوان', 'الوادى الجديد']:
         analysis['challenges'].append('درجات حرارة عالية قد تقلل كفاءة الألواح ظهراً')
    
    return analysis


def generate_solar_recommendations(location, stats):
    """توليد توصيات بناءً على الإحصائيات"""
    recommendations = []
    
    if not stats or not stats.get('avg_radiation'):
        return recommendations
    
    avg_rad = stats['avg_radiation']
    
    # 1. حجم النظام المقترح
    if avg_rad >= 6.0:
        recommendations.append({
            'type': 'high',
            'title': 'نظام إنتاج عالي',
            'description': 'المنطقة تدعم محطات توليد مركزية أو أنظمة منزلية عالية الكفاءة.',
            'details': 'متوسط الإنتاج المتوقع يتجاوز 5.5 ساعة شمسية ذروة يومياً.'
        })
    elif avg_rad >= 4.5:
        recommendations.append({
            'type': 'medium',
            'title': 'نظام منزلي قياسي',
            'description': 'مناسب جداً للأنظمة المنزلية المتصلة بالشبكة (On-Grid).',
            'details': 'فترة استرداد رأس المال تقدر بـ 4-6 سنوات.'
        })
    else:
        recommendations.append({
            'type': 'basic',
            'title': 'نظام هجين/احتياطي',
            'description': 'يفضل استخدام أنظمة مع بطاريات لضمان الاستقرار.',
            'details': 'الإشعاع قد يكون متذبذباً في الشتاء.'
        })

    # 2. نوع الألواح
    if stats.get('max_temp') and stats['max_temp'] > 40:
        recommendations.append({
            'type': 'tech',
            'title': 'مقاومة الحرارة',
            'description': 'ينصح باستخدام ألواح ذات معامل حراري منخفض (Low Temperature Coefficient).',
            'details': 'ألواح HJT أو N-type تعمل بشكل أفضل هنا.'
        })
    
    return recommendations