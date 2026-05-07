# solar_data/serializers.py
"""
Serializers for Solar Data Management System API.
Fields are matched exactly to actual model fields to prevent startup errors.
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Avg, Max, Min, Sum, Count
from .models import Governorate, Location, DailyClimateData, MonthlySummary


# ─────────────────────────────────────────────────────────────────────────────
# Governorate
# ─────────────────────────────────────────────────────────────────────────────

class GovernorateSerializer(serializers.ModelSerializer):
    """
    Governorate serializer.
    location_count / avg_solar_radiation / avg_solar_potential are annotated
    by the ViewSet queryset — they must not be model fields.
    """
    location_count = serializers.IntegerField(read_only=True, default=0)
    avg_solar_radiation = serializers.FloatField(read_only=True, allow_null=True, default=None)
    avg_solar_potential = serializers.FloatField(read_only=True, allow_null=True, default=None)

    class Meta:
        model = Governorate
        fields = [
            'id', 'name', 'code',
            'centroid_lat', 'centroid_lon',
            'location_count', 'avg_solar_radiation', 'avg_solar_potential',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


# ─────────────────────────────────────────────────────────────────────────────
# Location
# ─────────────────────────────────────────────────────────────────────────────

class LocationSerializer(serializers.ModelSerializer):
    """Location serializer — uses only real model fields."""
    governorate_name = serializers.CharField(source='governorate.name', read_only=True)
    governorate_code = serializers.CharField(source='governorate.code', read_only=True)
    coordinates = serializers.SerializerMethodField()
    data_count = serializers.SerializerMethodField()
    solar_potential_rating = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            'id', 'location_id', 'name', 'governorate', 'governorate_name', 'governorate_code',
            'latitude', 'longitude', 'coordinates', 'elevation',
            'avg_solar_radiation', 'avg_temperature',
            'solar_potential_score', 'solar_potential_rating',
            'data_count', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'avg_solar_radiation', 'avg_temperature',
            'solar_potential_score', 'created_at', 'updated_at',
        ]

    def get_coordinates(self, obj):
        if obj.latitude and obj.longitude:
            return {'lat': float(obj.latitude), 'lng': float(obj.longitude)}
        return None

    def get_solar_potential_rating(self, obj):
        if not obj.solar_potential_score:
            return None
        score = obj.solar_potential_score
        if score >= 80: return 'Excellent'
        if score >= 60: return 'Good'
        if score >= 40: return 'Fair'
        return 'Poor'

    def get_data_count(self, obj):
        return obj.climate_data.count()


# ─────────────────────────────────────────────────────────────────────────────
# DailyClimateData
# ─────────────────────────────────────────────────────────────────────────────

class DailyClimateDataSerializer(serializers.ModelSerializer):
    """
    Daily climate data serializer.
    Only includes fields that exist in the DailyClimateData model.
    Removed non-existent fields: allsky_sfc_sw_dni, allsky_sfc_sw_diff,
      allsky_srf_alb, ps, get_weather_summary().
    """
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_coordinates = serializers.SerializerMethodField()
    governorate_name = serializers.CharField(source='location.governorate.name', read_only=True)

    class Meta:
        model = DailyClimateData
        fields = [
            'id', 'location', 'location_name', 'location_coordinates', 'governorate_name',
            'date',
            'allsky_sfc_sw_dwn',
            't2m', 't2m_max', 't2m_min',
            'rh2m', 'ws2m', 'cloud_amt',
            'prectotcorr',
            'solar_efficiency_factor', 'dust_risk_score',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'solar_efficiency_factor', 'dust_risk_score',
            'created_at', 'updated_at',
        ]

    def get_location_coordinates(self, obj):
        if obj.location and obj.location.latitude and obj.location.longitude:
            return {'lat': float(obj.location.latitude), 'lng': float(obj.location.longitude)}
        return None

    def validate(self, data):
        if 'date' in data and data['date'] > timezone.now().date():
            raise serializers.ValidationError({'date': 'Date cannot be in the future'})
        if 'allsky_sfc_sw_dwn' in data and data['allsky_sfc_sw_dwn'] is not None:
            if not (0 <= data['allsky_sfc_sw_dwn'] <= 12):
                raise serializers.ValidationError(
                    {'allsky_sfc_sw_dwn': 'Solar radiation must be between 0 and 12 kWh/m2'})
        return data


# ─────────────────────────────────────────────────────────────────────────────
# MonthlySummary
# ─────────────────────────────────────────────────────────────────────────────

class MonthlySummarySerializer(serializers.ModelSerializer):
    """
    Monthly summary serializer.
    Only includes fields that exist in the MonthlySummary model.
    Removed non-existent fields: max_radiation, min_radiation, total_radiation,
      avg_temp_max, avg_temp_min, max_temperature, min_temperature,
      avg_humidity, avg_wind_speed, avg_cloud_cover.
    """
    location_name = serializers.CharField(source='location.name', read_only=True)
    governorate_name = serializers.CharField(source='location.governorate.name', read_only=True)
    season = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()

    class Meta:
        model = MonthlySummary
        fields = [
            'id', 'location', 'location_name', 'governorate_name',
            'year', 'month', 'season',
            'avg_radiation', 'avg_temperature', 'total_precipitation',
            'days_count', 'solar_grade',
            'recommendations', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_season(self, obj):
        m = obj.month
        if m in (12, 1, 2): return 'Winter'
        if m in (3, 4, 5): return 'Spring'
        if m in (6, 7, 8): return 'Summer'
        return 'Autumn'

    def get_recommendations(self, obj):
        recs = []
        grade_map = {
            'A': 'Excellent month for solar energy production',
            'B': 'Good month for solar energy',
            'C': 'Moderate solar potential this month',
            'D': 'Low solar potential — consider alternative energy sources',
        }
        if obj.solar_grade in grade_map:
            recs.append(grade_map[obj.solar_grade])
        if obj.avg_temperature and obj.avg_temperature > 35:
            recs.append('High temperatures may reduce panel efficiency')
        if obj.avg_temperature and obj.avg_temperature < 10:
            recs.append('Low temperatures may affect battery performance')
        return recs

    def validate(self, data):
        if 'month' in data and not (1 <= data['month'] <= 12):
            raise serializers.ValidationError({'month': 'Month must be 1–12'})
        current_year = timezone.now().year
        if 'year' in data and not (1900 <= data['year'] <= current_year + 5):
            raise serializers.ValidationError({'year': f'Year must be 1900–{current_year + 5}'})
        return data


# ─────────────────────────────────────────────────────────────────────────────
# Equipment + Tariffs + Projects (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

from .models import ElectricityTariff, SolarPanel, Inverter, InstallationCost, DesignProject


class ElectricityTariffSerializer(serializers.ModelSerializer):
    price_egp_per_kwh = serializers.FloatField(read_only=True)

    class Meta:
        model = ElectricityTariff
        fields = [
            'id', 'usage_type', 'tier_min_kwh', 'tier_max_kwh',
            'consumption_bracket_min', 'consumption_bracket_max',
            'price_piasters', 'price_egp_per_kwh', 'customer_service_fee',
            'effective_date', 'source_url', 'notes',
        ]


class SolarPanelSerializer(serializers.ModelSerializer):
    area_m2 = serializers.FloatField(read_only=True)

    class Meta:
        model = SolarPanel
        fields = [
            'id', 'brand', 'model', 'capacity_w', 'panel_type', 'technology',
            'efficiency_pct', 'temp_coefficient_pct', 'degradation_rate_pct',
            'warranty_years', 'price_egp', 'price_per_watt_egp',
            'supplier', 'governorate', 'data_date', 'in_stock', 'area_m2',
        ]


class InverterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inverter
        fields = [
            'id', 'brand', 'model', 'capacity_kw', 'inverter_type',
            'efficiency_pct', 'warranty_years', 'price_egp',
            'supplier', 'data_date', 'in_stock', 'notes',
        ]


class InstallationCostSerializer(serializers.ModelSerializer):
    price_avg = serializers.FloatField(read_only=True)

    class Meta:
        model = InstallationCost
        fields = [
            'id', 'item_name', 'item_name_ar', 'unit',
            'price_min_egp', 'price_max_egp', 'price_avg_egp', 'price_avg',
            'governorate', 'data_date', 'notes',
        ]


class DesignProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = DesignProject
        fields = [
            'project_id', 'client_name', 'location', 'available_area_m2',
            'monthly_consumption_kwh', 'usage_type', 'budget_egp',
            'shading_loss_pct', 'include_battery', 'status',
            'optimization_run_id', 'pareto_solutions', 'selected_design',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'project_id', 'status', 'optimization_run_id',
            'pareto_solutions', 'selected_design',
            'created_at', 'updated_at',
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Solar Analysis request serializer (kept for compatibility)
# ─────────────────────────────────────────────────────────────────────────────

class SolarAnalysisSerializer(serializers.Serializer):
    analysis_type = serializers.ChoiceField(
        choices=['ranking', 'statistics', 'comparison', 'trends'], required=True)
    governorate = serializers.IntegerField(required=False)
    min_solar_potential = serializers.FloatField(required=False, min_value=0, max_value=100)
    max_solar_potential = serializers.FloatField(required=False, min_value=0, max_value=100)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=10)
    comparison_locations = serializers.ListField(child=serializers.IntegerField(), required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class LocationDetailSerializer(LocationSerializer):
    """Extended location serializer (for detail views)."""
    governorate_details = GovernorateSerializer(source='governorate', read_only=True)

    class Meta(LocationSerializer.Meta):
        fields = LocationSerializer.Meta.fields + ['governorate_details']
