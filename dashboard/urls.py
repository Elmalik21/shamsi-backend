from django.urls import path
from . import views

urlpatterns = [
    path('',              views.home,            name='home'),
    path('login/',        views.login_view,       name='login'),
    path('logout/',       views.logout_view,      name='logout'),
    path('locations/',    views.locations_view,   name='locations'),
    path('locations/<int:location_id>/', views.location_detail, name='location_detail'),
    path('governorates/', views.governorates_view, name='governorates'),
    path('climate/',      views.climate_view,     name='climate'),
    path('equipment/',    views.equipment_view,   name='equipment'),
    path('projects/',     views.projects_view,    name='projects'),

    # AJAX
    path('ajax/gov-radiation/',  views.ajax_gov_radiation,  name='ajax_gov_radiation'),
    path('ajax/monthly-trend/',  views.ajax_monthly_trend,  name='ajax_monthly_trend'),
    path('ajax/top-locations/',  views.ajax_top_locations,  name='ajax_top_locations'),
]
