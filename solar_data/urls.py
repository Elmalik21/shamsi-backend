# solar_data/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from django.conf import settings

# Router for API views
router = DefaultRouter()
router.register(r'governorates', views.GovernorateViewSet, basename='governorate')
router.register(r'locations', views.LocationViewSet, basename='location')
router.register(r'climate-data', views.DailyClimateDataViewSet, basename='climate-data')
router.register(r'monthly-summaries', views.MonthlySummaryViewSet, basename='monthly-summary')

# Basic URL patterns
urlpatterns = [
    path('', include(router.urls)),
    
    # Health check endpoint
    path('health/', views.HealthCheckView.as_view(), name='health-check'),
    
    # Analytics endpoints
  #  path('analytics/solar-potential/', views.solar_potential_analytics, name='solar-potential-analytics'),
   # path('analytics/temporal-trends/', views.temporal_trends_analytics, name='temporal-trends-analytics'),
    
    # Search endpoint
    #path('search/', views.search_locations, name='search-locations'),
]

