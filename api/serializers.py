# api/serializers.py
from rest_framework import serializers
from solar_data.models import Location, DailyClimateData, MonthlySummary
from .models import APIConfig, APILog, APIAnalytics


class APIConfigSerializer(serializers.ModelSerializer):
    """Serializer for API Configuration"""
    
    allowed_origins_list = serializers.SerializerMethodField()
    rate_limit_info = serializers.SerializerMethodField()
    
    class Meta:
        model = APIConfig
        fields = [
            'id', 'name', 'config_type', 'description',
            'rate_limit', 'burst_limit', 'window_seconds',
            'require_authentication', 'allowed_origins_list',
            'cors_enabled', 'is_active', 'maintenance_mode',
            'maintenance_message', 'cache_enabled', 'cache_ttl',
            'rate_limit_info', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_allowed_origins_list(self, obj):
        """Get list of allowed origins"""
        return obj.get_allowed_origins_list()
    
    def get_rate_limit_info(self, obj):
        """Get rate limiting information"""
        return obj.get_rate_limit_info()


class APILogSerializer(serializers.ModelSerializer):
    """Serializer for API Logs"""
    
    request_summary = serializers.SerializerMethodField()
    response_summary = serializers.SerializerMethodField()
    is_successful = serializers.SerializerMethodField()
    user_agent_short = serializers.SerializerMethodField()
    
    class Meta:
        model = APILog
        fields = [
            'id', 'timestamp', 'endpoint', 'method',
            'request_summary', 'response_summary', 'status_code',
            'response_time', 'ip_address', 'user_agent_short',
            'user_id', 'is_successful', 'api_config', 'created_at'
        ]
        read_only_fields = fields
    
    def get_request_summary(self, obj):
        """Get summary of request data"""
        return obj.get_request_summary()
    
    def get_response_summary(self, obj):
        """Get summary of response data"""
        return obj.get_response_summary()
    
    def get_is_successful(self, obj):
        """Check if request was successful"""
        return obj.is_successful()
    
    def get_user_agent_short(self, obj):
        """Get shortened user agent"""
        if not obj.user_agent:
            return ''
        
        # Extract browser/OS from user agent
        ua = obj.user_agent.lower()
        if 'chrome' in ua:
            return 'Chrome'
        elif 'firefox' in ua:
            return 'Firefox'
        elif 'safari' in ua:
            return 'Safari'
        elif 'edge' in ua:
            return 'Edge'
        elif 'postman' in ua:
            return 'Postman'
        else:
            return obj.user_agent[:50]


class APIAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for API Analytics"""
    
    success_rate = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    requests_per_hour = serializers.SerializerMethodField()
    
    class Meta:
        model = APIAnalytics
        fields = [
            'id', 'date', 'formatted_date', 'endpoint',
            'total_requests', 'successful_requests', 'failed_requests',
            'success_rate', 'avg_response_time', 'p95_response_time',
            'p99_response_time', 'unique_users', 'peak_hour',
            'data_transferred', 'requests_per_hour', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_success_rate(self, obj):
        """Calculate success rate"""
        return obj.calculate_success_rate()
    
    def get_formatted_date(self, obj):
        """Format date for display"""
        return obj.date.strftime('%Y-%m-%d')
    
    def get_requests_per_hour(self, obj):
        """Calculate average requests per hour"""
        if obj.total_requests == 0:
            return 0
        return obj.total_requests / 24


# Solar Data Serializers (Improved)
class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location model with enhanced data"""
    
    governorate_name = serializers.CharField(source='governorate.name', read_only=True)
    climate_data_count = serializers.SerializerMethodField()
    solar_potential_level = serializers.SerializerMethodField()
    coordinates = serializers.SerializerMethodField()
    
    class Meta:
        model = Location
        fields = [
            'location_id', 'name', 'governorate_name',
            'latitude', 'longitude', 'coordinates',
            'avg_solar_radiation', 'avg_temperature',
            'solar_potential_score', 'solar_potential_level',
            'climate_data_count', 'data_source', 'created_at'
        ]
        read_only_fields = fields
    
    def get_climate_data_count(self, obj):
        """Get count of climate data records"""
        return obj.climate_data.count()
    
    def get_solar_potential_level(self, obj):
        """Get solar potential level classification"""
        if not obj.solar_potential_score:
            return 'Unknown'
        
        if obj.solar_potential_score >= 70:
            return 'Excellent'
        elif obj.solar_potential_score >= 50:
            return 'Good'
        elif obj.solar_potential_score >= 30:
            return 'Moderate'
        else:
            return 'Poor'
    
    def get_coordinates(self, obj):
        """Get coordinates as a dictionary"""
        return {
            'latitude': float(obj.latitude),
            'longitude': float(obj.longitude)
        }


class ClimateDataSerializer(serializers.ModelSerializer):
    """Serializer for Daily Climate Data with enhanced fields"""
    
    location_name = serializers.CharField(source='location.name', read_only=True)
    governorate_name = serializers.CharField(source='location.governorate.name', read_only=True)
    weather_condition = serializers.SerializerMethodField()
    temperature_level = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyClimateData
        fields = [
            'id', 'formatted_date', 'location_name', 'governorate_name',
            'allsky_sfc_sw_dwn', 't2m', 't2m_max', 't2m_min',
            'temp_range', 'rh2m', 'ws2m', 'cloud_amt',
            'ps', 'prectotcorr', 'weather_condition',
            'temperature_level', 'solar_efficiency_factor',
            'dust_risk_score', 'created_at'
        ]
        read_only_fields = fields
    
    def get_weather_condition(self, obj):
        """Determine weather condition based on cloud cover and radiation"""
        if obj.cloud_amt < 20 and obj.allsky_sfc_sw_dwn > 5:
            return 'Sunny'
        elif obj.cloud_amt < 50:
            return 'Partly Cloudy'
        elif obj.cloud_amt < 80:
            return 'Cloudy'
        else:
            return 'Overcast'
    
    def get_temperature_level(self, obj):
        """Determine temperature level"""
        if obj.t2m >= 35:
            return 'Hot'
        elif obj.t2m >= 25:
            return 'Warm'
        elif obj.t2m >= 15:
            return 'Mild'
        else:
            return 'Cool'
    
    def get_formatted_date(self, obj):
        """Format date for display"""
        return obj.date.strftime('%Y-%m-%d')


class MonthlySummarySerializer(serializers.ModelSerializer):
    """Serializer for Monthly Summary with enhanced fields"""
    
    location_name = serializers.CharField(source='location.name', read_only=True)
    month_name = serializers.SerializerMethodField()
    solar_potential_percentage = serializers.SerializerMethodField()
    solar_grade = serializers.SerializerMethodField()
    season = serializers.SerializerMethodField()
    
    class Meta:
        model = MonthlySummary
        fields = '__all__'
        read_only_fields = fields
    
    def get_month_name(self, obj):
        """Get month name"""
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return month_names[obj.month - 1] if 1 <= obj.month <= 12 else 'Unknown'
    
    def get_solar_potential_percentage(self, obj):
        """Calculate solar potential percentage"""
        if not obj.avg_radiation:
            return 0
        
        # Normalize based on maximum possible (7 kWh/m²/day is excellent for Egypt)
        percentage = (obj.avg_radiation / 7) * 100
        return min(100, max(0, percentage))
    
    def get_solar_grade(self, obj):
        """Get solar grade based on radiation"""
        percentage = self.get_solar_potential_percentage(obj)
        
        if percentage >= 80:
            return 'A+'
        elif percentage >= 70:
            return 'A'
        elif percentage >= 60:
            return 'B'
        elif percentage >= 50:
            return 'C'
        elif percentage >= 40:
            return 'D'
        else:
            return 'F'
    
    def get_season(self, obj):
        """Determine season based on month (Egypt-specific)"""
        if obj.month in [12, 1, 2]:
            return 'Winter'
        elif obj.month in [3, 4, 5]:
            return 'Spring'
        elif obj.month in [6, 7, 8]:
            return 'Summer'
        else:
            return 'Autumn'