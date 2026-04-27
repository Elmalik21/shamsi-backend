# solar_data/serializers.py
"""
Serializers for Solar Data Management System API
"""
from rest_framework import serializers
from django.utils import timezone
from django.db.models import Avg, Max, Min, Sum, Count
#from django.contrib.gis.geos import Point
from .models import Governorate, Location, DailyClimateData, MonthlySummary
import math



class GovernorateSerializer(serializers.ModelSerializer):
    """
    Serializer for Governorate model
    """
    location_count = serializers.IntegerField(read_only=True)
    avg_solar_radiation = serializers.FloatField(read_only=True)
    avg_solar_potential = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Governorate
        fields = [
            'id', 'name', 'code',
            'location_count', 'avg_solar_radiation', 'avg_solar_potential',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class LocationSerializer(serializers.ModelSerializer):
    """
    Serializer for Location model - Cleaned for current database structure
    """
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
            'data_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'avg_solar_radiation', 'avg_temperature',
            'solar_potential_score', 'created_at', 'updated_at'
        ]
    
    def get_coordinates(self, obj):
        """
        Get coordinates as tuple
        """
        if obj.latitude and obj.longitude:
            return {
                'lat': float(obj.latitude),
                'lng': float(obj.longitude)
            }
        return None
    
    def get_solar_potential_rating(self, obj):
        """
        Get solar potential rating (Excellent, Good, etc.)
        """
        if not obj.solar_potential_score:
            return None
        
        score = obj.solar_potential_score
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Fair'
        else:
            return 'Poor'
    
    def get_data_count(self, obj):
        """
        Get count of climate data points for this location
        """
        return obj.climate_data.count()
    
    def validate_latitude(self, value):
        """
        Validate latitude value
        """
        if value < -90 or value > 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value
    
    def validate_longitude(self, value):
        """
        Validate longitude value
        """
        if value < -180 or value > 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value
    
    def create(self, validated_data):
        """
        Create location with automatic coordinate point
        """
        location = super().create(validated_data)
        
        # Calculate initial statistics if climate data exists
        if location.climate_data.exists():
            location.calculate_statistics()
            location.save()
        
        return location


class LocationDetailSerializer(LocationSerializer):
    """
    Detailed serializer for Location model with related data
    """
    governorate_details = GovernorateSerializer(source='governorate', read_only=True)
    climate_summary = serializers.SerializerMethodField()
    monthly_summaries_count = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()
    
    class Meta(LocationSerializer.Meta):
        fields = LocationSerializer.Meta.fields + [
            'governorate_details', 'climate_summary',
            'monthly_summaries_count', 'recommendations'
        ]
    
    def get_climate_summary(self, obj):
        """
        Get climate data summary
        """
        climate_data = obj.climate_data.all()
        
        if not climate_data.exists():
            return None
        
        summary = climate_data.aggregate(
            total_days=Count('id'),
            date_range_start=Min('date'),
            date_range_end=Max('date'),
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            avg_temperature=Avg('t2m'),
            avg_humidity=Avg('rh2m'),
            total_precipitation=Sum('prectotcorr')
        )
        
        # Calculate solar potential from climate data
        avg_radiation = summary['avg_radiation'] or 0
        solar_potential = min(100, (avg_radiation / 8) * 100)
        
        summary['calculated_solar_potential'] = solar_potential
        summary['data_quality'] = self.calculate_data_quality(climate_data)
        
        return summary
    
    def get_monthly_summaries_count(self, obj):
        """
        Get count of monthly summaries for this location
        """
        return obj.monthly_summaries.count()
    
    def get_recommendations(self, obj):
        """
        Get solar installation recommendations
        """
        if not obj.solar_potential_score:
            return []
        
        score = obj.solar_potential_score
        recommendations = []
        
        if score >= 80:
            recommendations = [
                "Excellent location for solar installations",
                "Consider large-scale solar systems (10+ kW)",
                "High return on investment expected",
                "Ideal for commercial and industrial applications"
            ]
        elif score >= 60:
            recommendations = [
                "Good location for solar installations",
                "Consider medium-scale systems (5-10 kW)",
                "Suitable for residential and commercial use",
                "Moderate return on investment"
            ]
        elif score >= 40:
            recommendations = [
                "Moderate solar potential",
                "Consider small to medium systems (3-5 kW)",
                "Suitable for residential use",
                "Consider hybrid systems with battery backup"
            ]
        else:
            recommendations = [
                "Limited solar potential",
                "Consider energy efficiency improvements first",
                "Consult with solar experts for site assessment",
                "Explore alternative energy sources"
            ]
        
        # Add location-specific recommendations
        if obj.avg_temperature and obj.avg_temperature > 35:
            recommendations.append("High temperatures may reduce panel efficiency - consider cooling solutions")
        
        return recommendations
    
    def calculate_data_quality(self, climate_data):
        """
        Calculate data quality score
        """
        total_records = climate_data.count()
        if total_records == 0:
            return 0
        
        # Count records with complete data
        complete_records = climate_data.filter(
            allsky_sfc_sw_dwn__isnull=False,
            t2m__isnull=False,
            rh2m__isnull=False,
            ws2m__isnull=False
        ).count()
        
        quality_score = (complete_records / total_records) * 100
        
        if quality_score >= 90:
            return "Excellent"
        elif quality_score >= 70:
            return "Good"
        elif quality_score >= 50:
            return "Fair"
        else:
            return "Poor"


class DailyClimateDataSerializer(serializers.ModelSerializer):
    """
    Serializer for Daily Climate Data
    """
    location_name = serializers.CharField(source='location.name', read_only=True)
    location_coordinates = serializers.SerializerMethodField()
    governorate_name = serializers.CharField(source='location.governorate.name', read_only=True)
    weather_summary = serializers.SerializerMethodField()
    solar_efficiency_factor = serializers.FloatField(read_only=True)
    dust_risk_score = serializers.FloatField(read_only=True)
    
    class Meta:
        model = DailyClimateData
        fields = [
            'id', 'location', 'location_name', 'location_coordinates', 'governorate_name',
            'date', 'allsky_sfc_sw_dwn', 'allsky_sfc_sw_dni', 'allsky_sfc_sw_diff',
            't2m', 't2m_max', 't2m_min',
            'rh2m', 'ws2m', 'cloud_amt', 'allsky_srf_alb',
            'ps', 'prectotcorr', 'solar_efficiency_factor',
            'dust_risk_score', 'weather_summary',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'solar_efficiency_factor', 'dust_risk_score',
            'created_at', 'updated_at'
        ]
    
    def get_location_coordinates(self, obj):
        """
        Get location coordinates
        """
        if obj.location and obj.location.latitude and obj.location.longitude:
            return {
                'lat': float(obj.location.latitude),
                'lng': float(obj.location.longitude)
            }
        return None
    
    def get_weather_summary(self, obj):
        """
        Get weather summary
        """
        return obj.get_weather_summary()
    
    def validate(self, data):
        """
        Validate climate data
        """
        # Check date range (allow past dates only)
        if 'date' in data and data['date'] > timezone.now().date():
            raise serializers.ValidationError({
                'date': 'Date cannot be in the future'
            })
        
        # Check temperature consistency
        if 't2m_max' in data and 't2m_min' in data and 't2m' in data:
            if data['t2m'] > data['t2m_max']:
                raise serializers.ValidationError({
                    't2m': 'Temperature cannot be higher than maximum temperature'
                })
            if data['t2m'] < data['t2m_min']:
                raise serializers.ValidationError({
                    't2m': 'Temperature cannot be lower than minimum temperature'
                })
        
        # Validate solar radiation values
        if 'allsky_sfc_sw_dwn' in data and data['allsky_sfc_sw_dwn']:
            if data['allsky_sfc_sw_dwn'] < 0 or data['allsky_sfc_sw_dwn'] > 12:
                raise serializers.ValidationError({
                    'allsky_sfc_sw_dwn': 'Solar radiation must be between 0 and 12 kWh/m²'
                })
        
        return data


class MonthlySummarySerializer(serializers.ModelSerializer):
    """
    Serializer for Monthly Summary - Cleaned for current database structure
    """
    location_name = serializers.CharField(source='location.name', read_only=True)
    governorate_name = serializers.CharField(source='location.governorate.name', read_only=True)
    solar_grade = serializers.CharField(read_only=True)
    season = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()
    
    class Meta:
        model = MonthlySummary
        fields = [
            'id', 'location', 'location_name', 'governorate_name',
            'year', 'month', 'season',
            'avg_radiation', 'max_radiation', 'min_radiation', 'total_radiation',
            'avg_temperature', 'avg_temp_max', 'avg_temp_min',
            'max_temperature', 'min_temperature',
            'avg_humidity', 'avg_wind_speed', 'total_precipitation', 'avg_cloud_cover',
            'days_count', 'solar_grade',
            'recommendations', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_season(self, obj):
        """
        Determine season based on month
        """
        month = obj.month
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        elif month in [9, 10, 11]:
            return 'Autumn'
        return 'Unknown'
    
    def get_recommendations(self, obj):
        """
        Get month-specific recommendations
        """
        recommendations = []
        
        # Solar grade recommendations
        if obj.solar_grade == 'A':
            recommendations.append("Excellent month for solar energy production")
        elif obj.solar_grade == 'B':
            recommendations.append("Good month for solar energy")
        elif obj.solar_grade == 'C':
            recommendations.append("Moderate solar potential this month")
        elif obj.solar_grade == 'D':
            recommendations.append("Low solar potential this month - consider alternative energy sources")
        
        # Temperature-based recommendations
        if obj.avg_temperature and obj.avg_temperature > 35:
            recommendations.append("High temperatures may reduce panel efficiency")
        
        if obj.avg_temperature and obj.avg_temperature < 10:
            recommendations.append("Low temperatures may affect battery performance")
        
        return recommendations
    
    def validate(self, data):
        """
        Validate monthly summary data
        """
        # Validate month range
        if 'month' in data and (data['month'] < 1 or data['month'] > 12):
            raise serializers.ValidationError({
                'month': 'Month must be between 1 and 12'
            })
        
        # Validate year range (reasonable past/future)
        current_year = timezone.now().year
        if 'year' in data and (data['year'] < 1900 or data['year'] > current_year + 5):
            raise serializers.ValidationError({
                'year': f'Year must be between 1900 and {current_year + 5}'
            })
        
        # Validate day counts
        if 'days_count' in data and data['days_count']:
            if data['days_count'] < 0 or data['days_count'] > 31:
                raise serializers.ValidationError({
                    'days_count': 'Days count must be between 0 and 31'
                })
        
        return data


class SolarAnalysisSerializer(serializers.Serializer):
    """
    Serializer for solar analysis requests
    """
    analysis_type = serializers.ChoiceField(
        choices=['ranking', 'statistics', 'comparison', 'trends'],
        required=True
    )
    governorate = serializers.IntegerField(required=False)
    min_solar_potential = serializers.FloatField(required=False, min_value=0, max_value=100)
    max_solar_potential = serializers.FloatField(required=False, min_value=0, max_value=100)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=1000, default=10)
    comparison_locations = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate(self, data):
        """
        Validate analysis parameters
        """
        # For comparison analysis, require comparison_locations
        if data.get('analysis_type') == 'comparison':
            if not data.get('comparison_locations'):
                raise serializers.ValidationError({
                    'comparison_locations': 'This field is required for comparison analysis'
                })
            if len(data['comparison_locations']) < 2:
                raise serializers.ValidationError({
                    'comparison_locations': 'At least 2 locations required for comparison'
                })
        
        # Validate date range
        if data.get('start_date') and data.get('end_date'):
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError({
                    'start_date': 'Start date must be before end date'
                })
        
        # Validate solar potential range
        if data.get('min_solar_potential') and data.get('max_solar_potential'):
            if data['min_solar_potential'] > data['max_solar_potential']:
                raise serializers.ValidationError({
                    'min_solar_potential': 'Minimum solar potential cannot be greater than maximum'
                })
        
        return data

# ============================================================
# NEW SERIALIZERS: Equipment, Tariffs, Projects
# ============================================================
from .models import ElectricityTariff, SolarPanel, Inverter, InstallationCost, DesignProject


class ElectricityTariffSerializer(serializers.ModelSerializer):
    price_egp_per_kwh = serializers.FloatField(read_only=True)
    class Meta:
        model  = ElectricityTariff
        fields = [
            'id', 'usage_type', 'tier_min_kwh', 'tier_max_kwh',
            'consumption_bracket_min', 'consumption_bracket_max',
            'price_piasters', 'price_egp_per_kwh', 'customer_service_fee',
            'effective_date', 'source_url', 'notes',
        ]


class SolarPanelSerializer(serializers.ModelSerializer):
    area_m2 = serializers.FloatField(read_only=True)
    class Meta:
        model  = SolarPanel
        fields = [
            'id', 'brand', 'model', 'capacity_w', 'panel_type', 'technology',
            'efficiency_pct', 'temp_coefficient_pct', 'degradation_rate_pct',
            'warranty_years', 'price_egp', 'price_per_watt_egp',
            'supplier', 'governorate', 'data_date', 'in_stock', 'area_m2',
        ]


class InverterSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Inverter
        fields = [
            'id', 'brand', 'model', 'capacity_kw', 'inverter_type',
            'efficiency_pct', 'warranty_years', 'price_egp',
            'supplier', 'data_date', 'in_stock', 'notes',
        ]


class InstallationCostSerializer(serializers.ModelSerializer):
    price_avg = serializers.FloatField(read_only=True)
    class Meta:
        model  = InstallationCost
        fields = [
            'id', 'item_name', 'item_name_ar', 'unit',
            'price_min_egp', 'price_max_egp', 'price_avg_egp', 'price_avg',
            'governorate', 'data_date', 'notes',
        ]


class DesignProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DesignProject
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
