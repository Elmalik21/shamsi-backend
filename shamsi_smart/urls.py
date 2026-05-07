# [file name]: urls.py
"""
Shamsi Smart URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static
from solar_data.models import Location, DailyClimateData
from django.db.models import Avg
import json

# Temporary functions - will move to dashboard/views.py
def dashboard_view(request):
    """Main Dashboard Page"""
    try:
        total_locations = Location.objects.count()
        avg_radiation = DailyClimateData.objects.aggregate(
            avg=Avg('allsky_sfc_sw_dwn')
        )['avg'] or 0
        top_locations = Location.objects.filter(
            avg_solar_radiation__isnull=False
        ).order_by('-avg_solar_radiation')[:5]
    except Exception as e:
        total_locations = 117
        avg_radiation = 5.8
        top_locations = []
        print(f"Dashboard error: {e}")
    
    return render(request, 'dashboard.html', {
        'page_title': 'Shamsi Smart - Dashboard',
        'total_locations': total_locations,
        'avg_radiation': round(avg_radiation, 2),
        'top_locations': top_locations,
        'data_years': settings.SOLAR_DATA_YEARS
    })

def api_docs_view(request):
    """API Documentation"""
    return render(request, 'api_docs.html', {
        'page_title': 'API Documentation'
    })

def city_detail_view(request, city_id):
    """City/Location Details"""
    try:
        location = Location.objects.get(location_id=city_id)
        
        # Statistics
        stats = DailyClimateData.objects.filter(location=location).aggregate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            max_temp=Max('t2m_max'),
            min_temp=Min('t2m_min'),
        )
        
        # Chart data (last 30 days)
        last_30_days = DailyClimateData.objects.filter(
            location=location
        ).order_by('-date')[:30]
        
        chart_data = {
            'dates': [str(data.date) for data in last_30_days],
            'radiation': [float(data.allsky_sfc_sw_dwn or 0) for data in last_30_days],
            'temperature': [float(data.t2m or 0) for data in last_30_days],
        }
        
        return render(request, 'city_detail.html', {
            'location': location,
            'stats': stats,
            'chart_data': json.dumps(chart_data),
            'page_title': f'Location Details: {location.name}'
        })
    except Location.DoesNotExist:
        return render(request, 'city_detail.html', {
            'error': 'Location not found'
        }, status=404)
    except Exception as e:
        return render(request, 'city_detail.html', {
            'error': f'Error: {str(e)}'
        }, status=500)

def custom_404(request, exception):
    """Custom 404 handler"""
    return render(request, '404.html', {
        'page_title': '404 - Page Not Found'
    }, status=404)

def custom_500(request):
    """Custom 500 handler"""
    return render(request, '500.html', {
        'page_title': '500 - Server Error'
    }, status=500)

# URL patterns
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Dashboard
    path('', dashboard_view, name='dashboard'),
    path('api-docs/', api_docs_view, name='api-docs'),
    path('city/<int:city_id>/', city_detail_view, name='city-detail'),
    
    # API endpoints
    path('api/v1/', include('api.urls')),
    path('solar-data/', include('solar_data.urls')),
    #path('core/', include('core.urls')),
]

# Add Swagger/OpenAPI documentation
if settings.DEBUG:
    from drf_yasg.views import get_schema_view
    from drf_yasg import openapi
    from rest_framework import permissions
    
    schema_view = get_schema_view(
        openapi.Info(
            title="Shamsi Smart API",
            default_version='v1',
            description="AI-Powered Solar Energy Decision Support System for Egypt",
            terms_of_service="https://shamsi-smart.eg/terms/",
            contact=openapi.Contact(email="contact@shamsi-smart.eg"),
            license=openapi.License(name="MIT License"),
        ),
        public=True,
        permission_classes=(permissions.AllowAny,),
    )
    
    urlpatterns += [
        path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), 
             name='schema-swagger-ui'),
        path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), 
             name='schema-redoc'),
    ]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers
handler404 = custom_404
handler500 = custom_500