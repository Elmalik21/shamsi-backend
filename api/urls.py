# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from . import views
from .views.roof_analysis_view import analyze_roof_image, analyze_roof_by_coordinates
from .views.export_view import (
    export_pvsyst, export_helioscope, export_pdf,
    export_excel, export_csv, export_all,
)

# Create router
router = DefaultRouter()

# Solar Data API
router.register(r'governorates', views.GovernorateViewSet, basename='governorate')
router.register(r'locations', views.LocationViewSet, basename='location')
router.register(r'climate/daily', views.DailyClimateDataViewSet, basename='climate-daily')
router.register(r'climate/monthly', views.MonthlySummaryViewSet, basename='climate-monthly')

# API Management
router.register(r'config', views.APIConfigViewSet, basename='api-config')
router.register(r'logs', views.APILogViewSet, basename='api-log')
router.register(r'analytics', views.APIAnalyticsViewSet, basename='api-analytics')

# Projects ViewSet
router.register(r'projects', views.DesignProjectViewSet, basename='project')

urlpatterns = [
    path('', views.api_root, name='api-root'),
    path('', include(router.urls)),
    path('auth/token/', obtain_auth_token, name='api-token-auth'),
    path('auth/register/', views.RegisterView.as_view(), name='api-register'),
    path('auth/user/', views.CurrentUserView.as_view(), name='current-user'),
    path('solar/potential/', views.SolarPotentialAnalysisView.as_view(), name='solar-potential-analysis'),
    path('solar/top-locations/', views.TopSolarLocationsView.as_view(), name='top-solar-locations'),
    path('solar/recommendations/', views.SolarRecommendationsView.as_view(), name='solar-recommendations'),
    path('export/climate/csv/', views.ClimateDataCSVExportView.as_view(), name='climate-data-csv-export'),
    path('export/climate/json/', views.ClimateDataJSONExportView.as_view(), name='climate-data-json-export'),
    path('export/locations/csv/', views.LocationsCSVExportView.as_view(), name='locations-csv-export'),
    path('stats/summary/', views.APIStatsSummaryView.as_view(), name='api-stats-summary'),
    path('stats/usage/', views.APIUsageStatsView.as_view(), name='api-usage-stats'),
    path('stats/performance/', views.APIPerformanceStatsView.as_view(), name='api-performance-stats'),
    path('health/', views.HealthCheckView.as_view(), name='api-health-check'),
    path('health/detailed/', views.DetailedHealthCheckView.as_view(), name='api-detailed-health-check'),
    path('docs/schema/', views.APISchemaView.as_view(), name='api-schema'),
    path('docs/swagger/', views.SwaggerUIView.as_view(), name='swagger-ui'),
    path('docs/redoc/', views.RedocView.as_view(), name='redoc'),
    # 5A: Tariff endpoints
    path('tariffs/', views.TariffListView.as_view(), name='tariff-list'),
    path('tariffs/calculate-bill/', views.CalculateBillView.as_view(), name='calculate-bill'),
    path('tariffs/calculate-savings/', views.CalculateSavingsView.as_view(), name='calculate-savings'),
    path('tariffs/<str:usage_type>/', views.TariffByTypeView.as_view(), name='tariff-by-type'),
    # 5B: Equipment endpoints
    path('equipment/panels/', views.SolarPanelListView.as_view(), name='panel-list'),
    path('equipment/inverters/', views.InverterListView.as_view(), name='inverter-list'),
    path('equipment/installation-costs/', views.InstallationCostListView.as_view(), name='installation-costs'),
    # 5C: AI endpoints
    path('ai/status/', views.AIStatusView.as_view(), name='ai-status'),            # NEW: health/status
    path('ai/predict/', views.PredictYieldView.as_view(), name='ai-predict'),       # alias for /predict-yield/
    path('ai/optimize/', views.OptimizeView.as_view(), name='ai-optimize'),
    path('ai/predict-yield/', views.PredictYieldView.as_view(), name='ai-predict-yield'),
    path('ai/dust-zones/', views.DustZonesView.as_view(), name='ai-dust-zones'),
    path('ai/roi-range/', views.ROIRangeView.as_view(), name='ai-roi-range'),
    path('ai/analyze-roof/', analyze_roof_image, name='analyze-roof'),
    path('ai/analyze-roof-by-coords/', analyze_roof_by_coordinates, name='analyze-roof-by-coords'),
    # 5D: Project sub-endpoints
    path('projects/<uuid:pk>/select-design/', views.SelectDesignView.as_view(), name='project-select-design'),
    # 5E: Professional export endpoints
    path('export/<str:project_id>/pvsyst/',     export_pvsyst,     name='export-pvsyst'),
    path('export/<str:project_id>/helioscope/', export_helioscope, name='export-helioscope'),
    path('export/<str:project_id>/pdf/',        export_pdf,        name='export-pdf'),
    path('export/<str:project_id>/excel/',      export_excel,      name='export-excel'),
    path('export/<str:project_id>/csv/',        export_csv,        name='export-csv'),
    path('export/<str:project_id>/all/',        export_all,        name='export-all'),
]