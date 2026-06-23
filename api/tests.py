# api/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from solar_data.models import Governorate, Location, DailyClimateData, MonthlySummary
from .models import APIConfig, APILog, APIAnalytics
import json
from datetime import datetime, timedelta


class BaseAPITestCase(APITestCase):
    """Base test case for API testing"""
    
    def setUp(self):
        """Set up test data"""
        # Create API configuration
        self.api_config = APIConfig.objects.create(
            name='test_config',
            config_type='CLIMATE',
            description='Test API configuration',
            rate_limit=1000,
            burst_limit=100,
            window_seconds=60,
            require_authentication=False,
            cors_enabled=True,
            is_active=True
        )
        
        # Create test governorate
        self.governorate = Governorate.objects.create(
            name="Cairo Governorate",
            code="CAI"
        )
        
        # Create test location
        self.location = Location.objects.create(
            location_id=1001,
            name="Cairo City",
            governorate=self.governorate,
            latitude=30.044420,
            longitude=31.235712,
            avg_solar_radiation=5.5,
            avg_temperature=25.5,
            solar_potential_score=85.0,
            data_source="NASA_POWER"
        )
        
        # Create test climate data
        self.climate_data = DailyClimateData.objects.create(
            location=self.location,
            date=timezone.now().date(),
            allsky_sfc_sw_dwn=5.8,
            t2m=26.0,
            t2m_max=32.0,
            t2m_min=20.0,
            rh2m=45.0,
            ws2m=3.5,
            cloud_amt=15.0,
            prectotcorr=0.0
        )
        
        # Create test monthly summary
        self.monthly_summary = MonthlySummary.objects.create(
            location=self.location,
            year=timezone.now().year,
            month=timezone.now().month,
            avg_radiation=5.5,
            avg_temperature=25.5,
            total_precipitation=2.0,
            days_count=30
        )
        
        # Create test client
        self.client = Client()


class APIConfigTests(BaseAPITestCase):
    """Tests for API Configuration"""
    
    def test_api_config_creation(self):
        """Test API configuration creation"""
        self.api_config.refresh_from_db()
        self.assertEqual(self.api_config.name, 'test_config')
        self.assertEqual(self.api_config.config_type, 'CLIMATE')
        self.assertTrue(self.api_config.is_active)
    
    def test_get_allowed_origins_list(self):
        """Test get allowed origins list"""
        self.api_config.allowed_origins = 'http://localhost:3000,http://127.0.0.1:8000'
        self.api_config.save()
        
        origins = self.api_config.get_allowed_origins_list()
        self.assertEqual(len(origins), 2)
        self.assertIn('http://localhost:3000', origins)
        self.assertIn('http://127.0.0.1:8000', origins)
    
    def test_get_rate_limit_info(self):
        """Test get rate limit information"""
        rate_info = self.api_config.get_rate_limit_info()
        self.assertEqual(rate_info['rate_limit'], 1000)
        self.assertEqual(rate_info['burst_limit'], 100)
        self.assertEqual(rate_info['window_seconds'], 60)


class APILogTests(BaseAPITestCase):
    """Tests for API Logs"""
    
    def test_api_log_creation(self):
        """Test API log creation"""
        log = APILog.objects.create(
            endpoint='/api/test/',
            method='GET',
            status_code=200,
            response_time=150.5,
            ip_address='127.0.0.1',
            user_agent='Test Client',
            api_config=self.api_config
        )
        
        self.assertEqual(log.endpoint, '/api/test/')
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)
        self.assertTrue(log.is_successful())
    
    def test_request_summary_with_sensitive_data(self):
        """Test request summary with sensitive data"""
        request_data = {
            'username': 'testuser',
            'password': 'secret123',
            'token': 'abc123',
            'data': 'normal data'
        }
        
        log = APILog.objects.create(
            endpoint='/api/login/',
            method='POST',
            request_data=request_data,
            status_code=200,
            response_time=100.0,
            ip_address='127.0.0.1'
        )
        
        summary = log.get_request_summary()
        self.assertEqual(summary['username'], 'testuser')
        self.assertEqual(summary['password'], '***REDACTED***')
        self.assertEqual(summary['token'], '***REDACTED***')
        self.assertEqual(summary['data'], 'normal data')
    
    def test_response_summary_with_large_data(self):
        """Test response summary with large data"""
        large_data = {'data': 'x' * 1000}  # Large data
        
        log = APILog.objects.create(
            endpoint='/api/large-data/',
            method='GET',
            response_data=large_data,
            status_code=200,
            response_time=200.0,
            ip_address='127.0.0.1'
        )
        
        summary = log.get_response_summary()
        self.assertIn('Large data', summary['data'])


class APIAnalyticsTests(BaseAPITestCase):
    """Tests for API Analytics"""
    
    def test_api_analytics_creation(self):
        """Test API analytics creation"""
        analytics = APIAnalytics.objects.create(
            date=timezone.now().date(),
            endpoint='/api/test/',
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            total_response_time=5000.0,
            unique_users=50
        )
        
        self.assertEqual(analytics.total_requests, 100)
        self.assertEqual(analytics.successful_requests, 95)
        self.assertEqual(analytics.failed_requests, 5)
    
    def test_calculate_success_rate(self):
        """Test calculate success rate"""
        analytics = APIAnalytics.objects.create(
            date=timezone.now().date(),
            endpoint='/api/test/',
            total_requests=100,
            successful_requests=90,
            failed_requests=10
        )
        
        success_rate = analytics.calculate_success_rate()
        self.assertEqual(success_rate, 90.0)
    
    def test_update_statistics(self):
        """Test update statistics"""
        analytics = APIAnalytics.objects.create(
            date=timezone.now().date(),
            endpoint='/api/test/',
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            total_response_time=0.0
        )
        
        log = APILog.objects.create(
            endpoint='/api/test/',
            method='GET',
            request_data={'test': 'data'},
            response_data={'result': 'ok'},
            status_code=200,
            response_time=150.5,
            ip_address='127.0.0.1'
        )
        
        analytics.update_statistics(log)
        analytics.refresh_from_db()
        
        self.assertEqual(analytics.total_requests, 1)
        self.assertEqual(analytics.successful_requests, 1)
        self.assertEqual(analytics.failed_requests, 0)
        self.assertEqual(analytics.total_response_time, 150.5)


class APIViewTests(BaseAPITestCase):
    """Tests for API Views"""
    
    def test_governorates_endpoint(self):
        """Test governorates endpoint"""
        url = reverse('governorate-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Cairo Governorate')
        self.assertEqual(data[0]['location_count'], 1)
    
    def test_locations_endpoint(self):
        """Test locations endpoint"""
        url = reverse('location-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Cairo City')
    
    def test_location_detail_endpoint(self):
        """Test location detail endpoint"""
        url = reverse('location-detail', args=[self.location.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Cairo City')
        
        # Support flexible serialization styles for governorate relation check
        gov = response.data.get('governorate')
        if isinstance(gov, int):
            self.assertEqual(gov, self.governorate.id)
        elif isinstance(gov, dict):
            self.assertEqual(gov.get('name'), 'Cairo Governorate')
        else:
            self.assertEqual(gov, 'Cairo Governorate')
    
    def test_climate_data_endpoint(self):
        """Test climate data endpoint"""
        url = reverse('climate-daily-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['allsky_sfc_sw_dwn'], 5.8)
    
    def test_climate_data_with_location_filter(self):
        """Test climate data endpoint with location filter"""
        url = reverse('climate-daily-list')
        response = self.client.get(f'{url}?location={self.location.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
    
    def test_location_stats_endpoint(self):
        """Test location stats endpoint"""
        url = reverse('location-stats', args=[self.location.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('location', response.data)
        self.assertIn('stats', response.data)
        self.assertEqual(response.data['location']['name'], 'Cairo City')
    
    def test_top_locations_endpoint(self):
        """Test top locations endpoint"""
        url = reverse('top-solar-locations')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Cairo City')
    
    def test_monthly_summary_endpoint(self):
        """Test monthly summary endpoint"""
        url = reverse('climate-monthly-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['avg_radiation'], 5.5)
    
    def test_monthly_summary_with_filters(self):
        """Test monthly summary endpoint with filters"""
        url = reverse('climate-monthly-list')
        response = self.client.get(
            f'{url}?location={self.location.id}&year={timezone.now().year}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 1)


class APIErrorTests(BaseAPITestCase):
    """Tests for API error handling"""
    
    def test_invalid_location_id(self):
        """Test with invalid location ID"""
        url = reverse('climate-daily-list')
        response = self.client.get(f'{url}?location=99999')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_nonexistent_endpoint(self):
        """Test non-existent endpoint"""
        response = self.client.get('/api/nonexistent/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_invalid_http_method(self):
        """Test invalid HTTP method"""
        url = reverse('climate-daily-list')
        response = self.client.post(url, data={})
        
        # Might return 405 Method Not Allowed or 200 with empty data
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_405_METHOD_NOT_ALLOWED])


class APIPerformanceTests(BaseAPITestCase):
    """Performance tests for API"""
    
    def test_query_performance(self):
        """Test query performance with large dataset"""
        import time
        
        # Create multiple locations for testing
        locations = []
        for i in range(10):
            location = Location.objects.create(
                location_id=2000 + i,
                name=f"Test Location {i}",
                governorate=self.governorate,
                latitude=30.0 + (i * 0.1),
                longitude=31.0 + (i * 0.1),
                avg_solar_radiation=5.0,
                avg_temperature=25.0,
                solar_potential_score=70.0,
                data_source="TEST"
            )
            locations.append(location)
        
        start_time = time.time()
        url = reverse('location-list')
        response = self.client.get(url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data.get('results', response.data)
        self.assertEqual(len(data), 11)  # 10 new + 1 original
        
        # Should complete in reasonable time
        self.assertLess(end_time - start_time, 1.0)  # Less than 1 second


class APISerializerTests(BaseAPITestCase):
    """Tests for API Serializers"""
    
    def test_location_serializer(self):
        """Test LocationSerializer"""
        from .serializers import LocationSerializer
        
        serializer = LocationSerializer(self.location)
        data = serializer.data
        
        self.assertEqual(data['name'], 'Cairo City')
        self.assertEqual(data['governorate_name'], 'Cairo Governorate')
        self.assertEqual(data['solar_potential_level'], 'Excellent')
        self.assertIn('coordinates', data)
    
    def test_climate_data_serializer(self):
        """Test ClimateDataSerializer"""
        from .serializers import ClimateDataSerializer
        
        serializer = ClimateDataSerializer(self.climate_data)
        data = serializer.data
        
        self.assertEqual(data['weather_condition'], 'Sunny')
        self.assertEqual(data['temperature_level'], 'Warm')
        self.assertIn('formatted_date', data)
    
    def test_monthly_summary_serializer(self):
        """Test MonthlySummarySerializer"""
        from .serializers import MonthlySummarySerializer
        
        serializer = MonthlySummarySerializer(self.monthly_summary)
        data = serializer.data
        
        self.assertIn('month_name', data)
        self.assertIn('solar_grade', data)
        self.assertIn('season', data)
    
    def test_api_config_serializer(self):
        """Test APIConfigSerializer"""
        from .serializers import APIConfigSerializer
        
        serializer = APIConfigSerializer(self.api_config)
        data = serializer.data
        
        self.assertEqual(data['name'], 'test_config')
        self.assertIn('rate_limit_info', data)
        self.assertIn('allowed_origins_list', data)


class APILoggingTests(BaseAPITestCase):
    """Tests for API logging"""
    
    def test_api_request_logging(self):
        """Test that API requests are logged"""
        initial_log_count = APILog.objects.count()
        
        url = reverse('climate-daily-list')
        response = self.client.get(url)
        
        final_log_count = APILog.objects.count()
        
        # Should have logged the request
        self.assertGreater(final_log_count, initial_log_count)
    
    def test_log_contains_correct_data(self):
        """Test that log contains correct data"""
        url = reverse('climate-daily-list')
        user_agent = 'TestBrowser/1.0'
        
        response = self.client.get(
            url,
            HTTP_USER_AGENT=user_agent,
            REMOTE_ADDR='192.168.1.100'
        )
        
        # Get the latest log entry
        log_entry = APILog.objects.latest('timestamp')
        
        self.assertEqual(log_entry.endpoint, url)
        self.assertEqual(log_entry.method, 'GET')
        self.assertEqual(log_entry.status_code, 200)
        self.assertEqual(log_entry.user_agent, user_agent)


# Run tests
if __name__ == '__main__':
    # This allows running tests directly with: python manage.py test api
    import django
    django.setup()
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'test', 'api'])