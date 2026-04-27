# solar_data/admin.py
"""
Admin interface configuration for Solar Data Management System
"""
from django.contrib import admin
from django.contrib.admin import ModelAdmin, TabularInline, StackedInline
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Avg, Count, Max, Min, Q, Sum
import csv
import json
from django.http import HttpResponse
from datetime import datetime
from decimal import Decimal
from .models import Governorate, Location, DailyClimateData, MonthlySummary


# CUSTOM ADMIN SITE
class SolarDataAdminSite(admin.AdminSite):
    site_header = "Solar Data Management System"
    site_title = "Solar Data Admin"
    index_title = "Welcome to Solar Data Management"
    
    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        for app in app_list:
            if app['app_label'] == 'solar_data':
                model_order = ['Governorate', 'Location', 'DailyClimateData', 'MonthlySummary']
                app['models'].sort(key=lambda x: model_order.index(x['name']) if x['name'] in model_order else 99)
        return app_list

custom_admin_site = SolarDataAdminSite(name='admin')


class ExportMixin:
    actions = ['export_as_csv', 'export_as_json']
    
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="solar_data_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        
        if self.model == Governorate:
            headers = ['ID', 'Name', 'Code', 'Location Count', 'Average Solar Radiation', 'Created At', 'Updated At']
        elif self.model == Location:
            headers = ['ID', 'Location ID', 'Name', 'Governorate', 'Latitude', 'Longitude', 'Solar Potential Score',
                      'Average Solar Radiation', 'Average Temperature', 'Data Source', 'Created At', 'Updated At']
        elif self.model == DailyClimateData:
            headers = ['ID', 'Location', 'Date', 'Solar Radiation (kWh/m²)', 'Temperature (°C)', 'Max Temp', 'Min Temp',
                      'Humidity (%)', 'Wind Speed (m/s)', 'Cloud Cover (%)', 'Precipitation (mm)',
                      'Solar Efficiency Factor', 'Dust Risk Score']
        elif self.model == MonthlySummary:
            headers = ['ID', 'Location', 'Year', 'Month', 'Avg Radiation', 'Avg Temperature', 'Total Precipitation',
                      'Clear Days', 'Solar Potential %', 'Created At', 'Updated At']
        else:
            headers = [field.name for field in self.model._meta.fields]
        
        writer.writerow(headers)
        
        for obj in queryset:
            if self.model == Governorate:
                row = [obj.id, obj.name, obj.code, obj.location_set.count(),
                      getattr(obj, 'avg_rad', ''), obj.created_at, obj.updated_at]
            elif self.model == Location:
                row = [obj.id, obj.location_id, obj.name, obj.governorate.name if obj.governorate else '',
                      float(obj.latitude), float(obj.longitude), obj.solar_potential_score or '',
                      obj.avg_solar_radiation or '', obj.avg_temperature or '', obj.data_source or '',
                      obj.created_at, obj.updated_at]
            elif self.model == DailyClimateData:
                row = [obj.id, obj.location.name if obj.location else '', obj.date, obj.allsky_sfc_sw_dwn or '',
                      obj.t2m or '', obj.t2m_max or '', obj.t2m_min or '', obj.rh2m or '', obj.ws2m or '',
                      obj.cloud_amt or '', obj.prectotcorr or '', obj.solar_efficiency_factor or '', obj.dust_risk_score or '']
            elif self.model == MonthlySummary:
                row = [obj.id, obj.location.name if obj.location else '', obj.year, obj.month,
                      obj.avg_radiation or '', obj.avg_temperature or '', obj.total_precipitation or '',
                      obj.clear_days or '', obj.solar_potential_percentage or '', obj.created_at, obj.updated_at]
            else:
                row = [getattr(obj, field.name, '') for field in self.model._meta.fields]
            writer.writerow(row)
        
        return response
    
    export_as_csv.short_description = "Export selected items as CSV"
    
    def export_as_json(self, request, queryset):
        data = []
        for obj in queryset:
            item_data = {}
            for field in self.model._meta.fields:
                value = getattr(obj, field.name)
                if hasattr(value, '__str__'):
                    item_data[field.name] = str(value)
                else:
                    item_data[field.name] = value
            data.append(item_data)
        
        response = HttpResponse(json.dumps(data, indent=2, default=str), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="solar_data_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        return response
    
    export_as_json.short_description = "Export selected items as JSON"


class DailyClimateDataInline(TabularInline):
    model = DailyClimateData
    fields = ['date', 'allsky_sfc_sw_dwn', 't2m', 'rh2m', 'ws2m']
    readonly_fields = []
    extra = 0
    max_num = 10
    can_delete = False
    show_change_link = True
    ordering = ['-date']


class MonthlySummaryInline(StackedInline):
    model = MonthlySummary
    fields = ['year', 'month', 'avg_radiation', 'avg_temperature', 'solar_grade']
    readonly_fields = ['solar_grade']    
    extra = 0
    max_num = 6
    can_delete = False
    show_change_link = True
    ordering = ['-year', '-month']


@admin.register(Governorate)
class GovernorateAdmin(ExportMixin, ModelAdmin):
    list_display = ['name', 'code', 'location_count', 'average_solar_radiation', 'action_buttons']
    search_fields = ['name', 'code']
    list_per_page = 25
    ordering = ['name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {'fields': ('name', 'code')}),
    (   'Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(loc_count=Count('locations'), avg_rad=Avg('locations__avg_solar_radiation'))
    
    def location_count(self, obj):
        count = obj.loc_count
        url = reverse('admin:solar_data_location_changelist') + f'?governorate__id__exact={obj.id}'
        return format_html('<a href="{}">{}</a>', url, count)
    location_count.short_description = 'Locations'
    location_count.admin_order_field = 'loc_count'
    
    def average_solar_radiation(self, obj):
        if obj.avg_rad:
            try:
                avg_rad = float(obj.avg_rad) if isinstance(obj.avg_rad, (Decimal, int, float)) else 0
            except (TypeError, ValueError):
                avg_rad = 0
            
            color = 'green' if avg_rad >= 5 else 'orange' if avg_rad >= 3 else 'red'
            return format_html('<span style="color: {};"><strong>{}</strong> kWh/m²</span>', color, f"{avg_rad:.2f}")
        return "-"
    average_solar_radiation.short_description = 'Avg Solar Radiation'
    average_solar_radiation.admin_order_field = 'avg_rad'
    
    def action_buttons(self, obj):
        view_url = reverse('admin:solar_data_governorate_change', args=[obj.id])
        locations_url = reverse('admin:solar_data_location_changelist') + f'?governorate__id__exact={obj.id}'
        return format_html('<a href="{}" class="button">Edit</a> <a href="{}" class="button">View Locations</a>',
                          view_url, locations_url)
    action_buttons.short_description = 'Actions'


@admin.register(Location)
class LocationAdmin(ExportMixin, ModelAdmin):
    list_display = ['location_id', 'name', 'governorate_link', 'solar_potential_display', 'climate_data_count',
                   'last_data_date', 'action_buttons']
    list_filter = ['governorate']
    search_fields = ['name', 'governorate__name', 'location_id']
    readonly_fields = ['avg_solar_radiation', 'avg_temperature', 'solar_potential_score', 'created_at', 'updated_at']
    list_per_page = 50
    inlines = [MonthlySummaryInline]
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {'fields': ('location_id', 'name', 'governorate', 'latitude', 'longitude', 'elevation')}),
        ('Calculated Statistics', {'fields': ('avg_solar_radiation', 'avg_temperature', 'solar_potential_score'), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(data_count=Count('climate_data'), last_date=Max('climate_data__date')).select_related('governorate')
    
    def governorate_link(self, obj):
        if obj.governorate:
            url = reverse('admin:solar_data_governorate_change', args=[obj.governorate.id])
            return format_html('<a href="{}">{}</a>', url, obj.governorate.name)
        return "-"
    governorate_link.short_description = 'Governorate'
    governorate_link.admin_order_field = 'governorate__name'
    
    def solar_potential_display(self, obj):
        if not obj.solar_potential_score:
            return format_html('<span style="color: gray;">-</span>')
        
        try:
            if isinstance(obj.solar_potential_score, (Decimal, int, float)):
                score = float(obj.solar_potential_score)
            else:
                score = float(str(obj.solar_potential_score))
        except (TypeError, ValueError, AttributeError):
            return format_html('<span style="color: gray;">Invalid data</span>')
            
        if score >= 80:
            color, label, icon = '#2ecc71', 'Excellent', '⭐'
        elif score >= 60:
            color, label, icon = '#f39c12', 'Good', '☀️'
        elif score >= 40:
            color, label, icon = '#e74c3c', 'Fair', '⛅'
        else:
            color, label, icon = '#95a5a6', 'Poor', '☁️'
        
        return format_html(
            '<div style="display: flex; align-items: center;"><span style="color: {}; font-weight: bold; margin-right: 5px;">{} {}</span><span style="color: {};">{}</span></div>',
            color, icon, f"{score:.1f}", color, label        )
    solar_potential_display.short_description = 'Solar Potential'
    solar_potential_display.admin_order_field = 'solar_potential_score'
    
    def climate_data_count(self, obj):
        count = obj.data_count
        if count > 0:
            url = reverse('admin:solar_data_dailyclimatedata_changelist') + f'?location__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return "0"
    climate_data_count.short_description = 'Data Points'
    climate_data_count.admin_order_field = 'data_count'
    
    def last_data_date(self, obj):
        if obj.last_date:
            return obj.last_date.strftime('%Y-%m-%d')
        return "-"
    last_data_date.short_description = 'Last Data'
    last_data_date.admin_order_field = 'last_date'
    
    def action_buttons(self, obj):
        view_url = reverse('admin:solar_data_location_change', args=[obj.id])
        climate_url = reverse('admin:solar_data_dailyclimatedata_changelist') + f'?location__id__exact={obj.id}'
        analyze_url = reverse('admin:solar_data_location_changelist') + f'{obj.id}/analyze/'
        return format_html(
            '<a href="{}" class="button" style="padding: 2px 8px; background: #4CAF50; color: white; text-decoration: none; border-radius: 3px; margin-right: 5px;">Edit</a> '
            '<a href="{}" class="button" style="padding: 2px 8px; background: #2196F3; color: white; text-decoration: none; border-radius: 3px; margin-right: 5px;">Climate Data</a> '
            '<a href="{}" class="button" style="padding: 2px 8px; background: #FF9800; color: white; text-decoration: none; border-radius: 3px;">Analyze</a>',
            view_url, climate_url, analyze_url
        )
    action_buttons.short_description = 'Actions'
    
    def recalculate_statistics(self, request, queryset):
        count = 0
        for location in queryset:
            location.calculate_statistics()
            count += 1
        self.message_user(request, f"Successfully recalculated statistics for {count} location(s).")
    recalculate_statistics.short_description = "Recalculate solar statistics"
    
    actions = ExportMixin.actions + ['recalculate_statistics']


@admin.register(DailyClimateData)
class DailyClimateDataAdmin(ExportMixin, ModelAdmin):
    list_display = ['date', 'location_link', 'solar_radiation_display', 'temperature_display',
                   'humidity_display']
    list_filter = ['location__governorate', 'date', 'location']
    search_fields = ['location__name', 'location__governorate__name']
    date_hierarchy = 'date'
    readonly_fields = ['solar_efficiency_factor', 'dust_risk_score', 'created_at', 'updated_at'] 
    list_per_page = 100
    list_select_related = ['location', 'location__governorate']
    ordering = ['-date']
    
    fieldsets = (
        ('Basic Information', {'fields': ('location', 'year', 'month')}),
        ('Solar & Temp Statistics', {'fields': ('avg_radiation', 'avg_temperature', 'total_precipitation')}),
        ('Calculated Metrics', {'fields': ('solar_grade',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('location', 'location__governorate')
    
    def location_link(self, obj):
        if obj.location:
            url = reverse('admin:solar_data_location_change', args=[obj.location.id])
            return format_html('<a href="{}">{}</a>', url, obj.location.name)
        return "-"
    location_link.short_description = 'Location'
    location_link.admin_order_field = 'location__name'
    
    def _get_numeric_value(self, value):
        """Helper method to safely convert values to float"""
        if value is None:
            return None
        try:
            if isinstance(value, (Decimal, int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(value)
            else:
                # Try to convert to string first, then to float
                return float(str(value))
        except (TypeError, ValueError, AttributeError):
            return None
    
    def solar_radiation_display(self, obj):
        radiation = self._get_numeric_value(obj.allsky_sfc_sw_dwn)
        
        if radiation is None:
            return format_html('<span style="color: gray;">-</span>')
        
        if radiation >= 6:
            color, icon, intensity = '#e74c3c', '☀️', 'High'
        elif radiation >= 4:
            color, icon, intensity = '#f39c12', '⛅', 'Medium'
        elif radiation >= 2:
            color, icon, intensity = '#3498db', '🌤️', 'Low'
        else:
            color, icon, intensity = '#95a5a6', '☁️', 'Very Low'
        
        # Use Python string formatting first, then pass to format_html
        radiation_formatted = f"{radiation:.2f}"
        html_content = f'<span style="color: {color};">{icon} <strong>{radiation_formatted}</strong> kWh/m² <small>({intensity})</small></span>'
        return mark_safe(html_content)
    
    solar_radiation_display.short_description = 'Solar Radiation'
    solar_radiation_display.admin_order_field = 'allsky_sfc_sw_dwn'
    
    def temperature_display(self, obj):
        temp = self._get_numeric_value(obj.t2m)
        
        if temp is None:
            return format_html('<span style="color: gray;">-</span>')
        
        if temp >= 35:
            color, icon, feel = '#e74c3c', '🔥', 'Very Hot'
        elif temp >= 30:
            color, icon, feel = '#f39c12', '🌡️', 'Hot'
        elif temp >= 25:
            color, icon, feel = '#f1c40f', '☀️', 'Warm'
        elif temp >= 20:
            color, icon, feel = '#2ecc71', '🌤️', 'Mild'
        elif temp >= 15:
            color, icon, feel = '#3498db', '🌥️', 'Cool'
        else:
            color, icon, feel = '#9b59b6', '❄️', 'Cold'
        
        # Use Python string formatting first, then pass to format_html
        temp_formatted = f"{temp:.1f}"
        html_content = f'<span style="color: {color};">{icon} <strong>{temp_formatted}°C</strong> <small>({feel})</small></span>'
        return mark_safe(html_content)
    
    temperature_display.short_description = 'Temperature'
    temperature_display.admin_order_field = 't2m'
    
    def humidity_display(self, obj):
        humidity = self._get_numeric_value(obj.rh2m)
        
        if humidity is None:
            return format_html('<span style="color: gray;">-</span>')
        
        if humidity >= 80:
            color, feel = '#3498db', 'Humid'
        elif humidity >= 60:
            color, feel = '#2ecc71', 'Comfortable'
        elif humidity >= 40:
            color, feel = '#f1c40f', 'Dry'
        else:
            color, feel = '#e74c3c', 'Very Dry'
        
        # Use Python string formatting first, then pass to format_html
        humidity_formatted = f"{humidity:.0f}"
        html_content = f'<span style="color: {color};"><strong>{humidity_formatted}%</strong> <small>({feel})</small></span>'
        return mark_safe(html_content)
    
    humidity_display.short_description = 'Humidity'
    humidity_display.admin_order_field = 'rh2m'
    
    def weather_conditions(self, obj):
        summary = obj.get_weather_summary()
        return format_html('<small>{}</small>', summary)
    weather_conditions.short_description = 'Conditions'
    
    def data_quality(self, obj):
        missing_fields = sum([
            not obj.allsky_sfc_sw_dwn, not obj.t2m, not obj.rh2m, not obj.ws2m, not obj.cloud_amt
        ])
        quality_score = ((5 - missing_fields) / 5) * 100
        
        if quality_score >= 90:
            color, label, icon = '#2ecc71', 'Excellent', '✅'
        elif quality_score >= 70:
            color, label, icon = '#f1c40f', 'Good', '⚠️'
        elif quality_score >= 50:
            color, label, icon = '#f39c12', 'Fair', 'ℹ️'
        else:
            color, label, icon = '#e74c3c', 'Poor', '❌'
        
        # Use Python string formatting first
        quality_formatted = f"{quality_score:.0f}"
        html_content = f'<span style="color: {color};">{icon} {quality_formatted}% ({label})</span>'
        return mark_safe(html_content)
    
    data_quality.short_description = 'Quality'
    
    def generate_monthly_summaries(self, request, queryset):
        from .models import MonthlySummary
        count = 0
        processed_locations = set()
        
        for location in queryset.values('location').distinct():
            loc_id = location['location']
            try:
                location_obj = Location.objects.get(id=loc_id)
                monthly_groups = queryset.filter(location=location_obj).extra(
                    select={'year': 'EXTRACT(YEAR FROM date)', 'month': 'EXTRACT(MONTH FROM date)'}
                ).values('year', 'month').annotate(record_count=Count('id')).order_by('year', 'month')
                
                for group in monthly_groups:
                    year, month = int(group['year']), int(group['month'])
                    monthly_data = queryset.filter(location=location_obj, date__year=year, date__month=month)
                    
                    stats = monthly_data.aggregate(
                        avg_radiation=Avg('allsky_sfc_sw_dwn'), max_radiation=Max('allsky_sfc_sw_dwn'),
                        min_radiation=Min('allsky_sfc_sw_dwn'), total_radiation=Sum('allsky_sfc_sw_dwn'),
                        avg_temperature=Avg('t2m'), avg_temp_max=Avg('t2m_max'), avg_temp_min=Avg('t2m_min'),
                        max_temperature=Max('t2m_max'), min_temperature=Min('t2m_min'),
                        avg_humidity=Avg('rh2m'), avg_wind_speed=Avg('ws2m'),
                        total_precipitation=Sum('prectotcorr'), avg_cloud_cover=Avg('cloud_amt'),
                        days_count=Count('id'), clear_days=Count('id', filter=Q(cloud_amt__lt=20)),
                        cloudy_days=Count('id', filter=Q(cloud_amt__gt=80)),
                        hot_days=Count('id', filter=Q(t2m__gt=35)),
                        rainy_days=Count('id', filter=Q(prectotcorr__gt=1))
                    )
                    
                    MonthlySummary.objects.update_or_create(
                        location=location_obj, year=year, month=month,
                        defaults={k: v or 0 for k, v in stats.items()}
                    )
                    count += 1
                processed_locations.add(loc_id)
            except Location.DoesNotExist:
                continue
        
        self.message_user(request, f"Generated {count} monthly summaries for {len(processed_locations)} location(s).")
    generate_monthly_summaries.short_description = "Generate monthly summaries"
    
    actions = ExportMixin.actions + ['generate_monthly_summaries']


@admin.register(MonthlySummary)
class MonthlySummaryAdmin(ExportMixin, ModelAdmin):
    list_display = ['year', 'month', 'location_link', 'average_radiation_display', 'average_temperature_display', 'solar_potential_percentage_display']
    list_filter = ['location__governorate', 'year', 'month']
    search_fields = ['location__name', 'location__governorate__name']
    list_per_page = 50
    list_select_related = ['location', 'location__governorate']
    ordering = ['-year', '-month']
    readonly_fields = ['solar_grade', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {'fields': ('location', 'year', 'month', 'days_count')}),
        ('Solar Radiation Statistics', {'fields': ('avg_radiation', 'max_radiation', 'min_radiation', 'total_radiation'), 'description': 'All values in kWh/m²'}),
        ('Temperature Statistics', {'fields': ('avg_temperature', 'avg_temp_max', 'avg_temp_min', 'max_temperature', 'min_temperature'), 'description': 'All values in °C'}),
        ('Atmospheric Conditions', {'fields': ('avg_humidity', 'avg_wind_speed', 'total_precipitation', 'avg_cloud_cover')}),
        ('Special Day Counts', {'fields': ('clear_days', 'cloudy_days', 'hot_days', 'rainy_days'), 'classes': ('collapse',), 'description': 'Count of days with specific conditions'}),
        ('Calculated Metrics', {'fields': ('solar_potential_percentage',), 'classes': ('collapse',)}),
        ('Metadata', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def location_link(self, obj):
        if obj.location:
            url = reverse('admin:solar_data_location_change', args=[obj.location.id])
            return format_html('<a href="{}">{}</a>', url, obj.location.name)
        return "-"
    location_link.short_description = 'Location'
    location_link.admin_order_field = 'location__name'
    
    def _get_numeric_value(self, value):
        """Helper method to safely convert values to float"""
        if value is None:
            return None
        try:
            if isinstance(value, (Decimal, int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(value)
            else:
                # Try to convert to string first, then to float
                return float(str(value))
        except (TypeError, ValueError, AttributeError):
            return None
    
    def average_radiation_display(self, obj):
        radiation = self._get_numeric_value(obj.avg_radiation)
        
        if radiation is None:
            return format_html('<span style="color: gray;">-</span>')
            
        percentage = min(100, (radiation / 8) * 100)
        
        if percentage >= 80:
            color, label = '#2ecc71', 'Excellent'
        elif percentage >= 60:
            color, label = '#f1c40f', 'Good'
        elif percentage >= 40:
            color, label = '#f39c12', 'Fair'
        else:
            color, label = '#e74c3c', 'Poor'
        
        # Format the radiation value first
        radiation_formatted = f"{radiation:.2f}"
        percentage_formatted = f"{percentage:.0f}"
        
        html_content = (
            f'<div style="display: flex; align-items: center; width: 150px;">'
            f'<div style="flex-grow: 1; background: #ecf0f1; border-radius: 3px; height: 20px; margin-right: 10px;">'
            f'<div style="width: {percentage_formatted}%; background: {color}; height: 100%; border-radius: 3px;"></div></div>'
            f'<div><strong>{radiation_formatted}</strong> <small>({label})</small></div></div>'
        )
        return mark_safe(html_content)
    
    average_radiation_display.short_description = 'Avg Radiation'
    average_radiation_display.admin_order_field = 'avg_radiation'
    
    def average_temperature_display(self, obj):
        temp = self._get_numeric_value(obj.avg_temperature)
        
        if temp is None:
            return format_html('<span style="color: gray;">-</span>')
            
        if temp >= 30:
            color, icon = '#e74c3c', '🔥'
        elif temp >= 25:
            color, icon = '#f39c12', '🌡️'
        elif temp >= 20:
            color, icon = '#f1c40f', '☀️'
        elif temp >= 15:
            color, icon = '#2ecc71', '🌤️'
        else:
            color, icon = '#3498db', '🌥️'
        
        # Format the temperature value first
        temp_formatted = f"{temp:.1f}"
        html_content = f'<span style="color: {color};">{icon} <strong>{temp_formatted}°C</strong></span>'
        return mark_safe(html_content)
    
    average_temperature_display.short_description = 'Avg Temperature'
    average_temperature_display.admin_order_field = 'avg_temperature'
    
    def solar_potential_percentage_display(self, obj):
        # استخدام solar_grade بدلاً من solar_potential_percentage
        grade = obj.solar_grade or 'N/A'
        
        # تحديد الألوان والأيقونات بناءً على التقييم
        grade_colors = {'A': '#2ecc71', 'B': '#3498db', 'C': '#f1c40f', 'D': '#e67e22'}
        grade_icons = {'A': '⭐', 'B': '☀️', 'C': '⛅', 'D': '🌤️'}
        
        color = grade_colors.get(grade, '#95a5a6')
        icon = grade_icons.get(grade, '📊')
        
        # تنسيق العرض بشكل جميل مع الدرجة
        html_content = (
            f'<div style="display: flex; align-items: center;">'
            f'<div style="background: {color}; color: white; width: 35px; height: 35px; border-radius: 50%; '
            f'display: flex; align-items: center; justify-content: center; font-weight: bold; margin-right: 12px; '
            f'font-size: 18px;">{icon}</div>'
            f'<div><div style="font-weight: bold; color: {color}; font-size: 16px;">Grade {grade}</div>'
            f'<div style="font-size: 11px; color: #7f8c8d;">Solar Performance</div></div></div>'
        )
        return mark_safe(html_content)
    
    solar_potential_percentage_display.short_description = 'Solar Grade'
    solar_potential_percentage_display.admin_order_field = 'solar_grade'
    
    def clear_days_count(self, obj):
        if not obj.clear_days:
            return "0"
        
        clear_days = obj.clear_days
        percentage = (clear_days / obj.days_count * 100) if obj.days_count else 0
        
        if percentage >= 70:
            color, icon = '#2ecc71', '☀️'
        elif percentage >= 50:
            color, icon = '#f1c40f', '⛅'
        else:
            color, icon = '#e74c3c', '☁️'
        
        # Format the percentage value first
        percentage_formatted = f"{percentage:.0f}"
        html_content = f'<span style="color: {color};">{icon} {clear_days}/{obj.days_count} ({percentage_formatted}%)</span>'
        return mark_safe(html_content)
    
    clear_days_count.short_description = 'Clear Days'


# Register models
custom_admin_site.register(Governorate, GovernorateAdmin)
custom_admin_site.register(Location, LocationAdmin)
custom_admin_site.register(DailyClimateData, DailyClimateDataAdmin)
custom_admin_site.register(MonthlySummary, MonthlySummaryAdmin)

# Set as default
admin.site = custom_admin_site