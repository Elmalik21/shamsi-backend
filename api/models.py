# api/models.py
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
import uuid
import json


class BaseModel(models.Model):
    """Base model with common fields"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class APIConfig(BaseModel):
    """API Configuration settings"""
    
    CONFIG_TYPES = [
        ('CLIMATE', 'Climate Data API'),
        ('SOLAR', 'Solar Analysis API'),
        ('PRICE', 'Market Price API'),
        ('GENERAL', 'General API'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    config_type = models.CharField(max_length=20, choices=CONFIG_TYPES, default='GENERAL')
    description = models.TextField(blank=True, null=True)
    
    # Rate limiting
    rate_limit = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum requests per minute"
    )
    burst_limit = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
        help_text="Burst limit for immediate requests"
    )
    window_seconds = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(3600)],
        help_text="Time window for rate limiting in seconds"
    )
    
    # Security settings
    require_authentication = models.BooleanField(default=False)
    allowed_origins = models.TextField(
        blank=True,
        null=True,
        help_text="Comma-separated list of allowed origins for CORS"
    )
    cors_enabled = models.BooleanField(default=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, null=True)
    
    # Performance
    cache_enabled = models.BooleanField(default=True)
    cache_ttl = models.IntegerField(
        default=300,
        validators=[MinValueValidator(0), MaxValueValidator(86400)],
        help_text="Cache time-to-live in seconds"
    )
    
    def __str__(self):
        return f"{self.name} ({self.config_type})"
    
    def get_allowed_origins_list(self):
        """Get list of allowed origins"""
        if not self.allowed_origins:
            return []
        return [origin.strip() for origin in self.allowed_origins.split(',')]
    
    def get_rate_limit_info(self):
        """Get rate limiting information"""
        return {
            'rate_limit': self.rate_limit,
            'burst_limit': self.burst_limit,
            'window_seconds': self.window_seconds
        }
    
    class Meta:
        verbose_name = "API Configuration"
        verbose_name_plural = "API Configurations"
        ordering = ['name']


class APILog(BaseModel):
    """Logs for API requests and responses"""
    
    METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE'),
    ]
    
    # Request information
    timestamp = models.DateTimeField(auto_now_add=True)
    endpoint = models.CharField(max_length=500)
    method = models.CharField(max_length=10, choices=METHODS)
    request_data = models.JSONField(blank=True, null=True)
    
    # Response information
    status_code = models.IntegerField()
    response_data = models.JSONField(blank=True, null=True)
    response_time = models.FloatField(help_text="Response time in milliseconds")
    
    # Client information
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    user_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    api_config = models.ForeignKey(
        APIConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs'
    )
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"
    
    def get_request_summary(self):
        """Get summary of request data"""
        if not self.request_data:
            return {}
        
        try:
            data = self.request_data.copy()
            # Remove sensitive information if present
            sensitive_fields = ['password', 'token', 'key', 'secret']
            for field in sensitive_fields:
                if field in data:
                    data[field] = '***REDACTED***'
            return data
        except Exception:
            return {}
    
    def get_response_summary(self):
        """Get summary of response data"""
        if not self.response_data:
            return {}
        
        try:
            data = self.response_data.copy()
            # Limit size for large responses
            if isinstance(data, dict) and 'data' in data and len(str(data['data'])) > 500:
                data['data'] = f"Large data: {len(str(data['data']))} characters"
            return data
        except Exception:
            return {}
    
    def is_successful(self):
        """Check if request was successful"""
        return 200 <= self.status_code < 300
    
    class Meta:
        verbose_name = "API Log"
        verbose_name_plural = "API Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['endpoint', 'timestamp']),
            models.Index(fields=['status_code', 'timestamp']),
        ]


class APIAnalytics(BaseModel):
    """Analytics data for API usage"""
    
    date = models.DateField()
    endpoint = models.CharField(max_length=500)
    
    # Request counts
    total_requests = models.IntegerField(default=0)
    successful_requests = models.IntegerField(default=0)
    failed_requests = models.IntegerField(default=0)
    
    # Response times
    total_response_time = models.FloatField(default=0, help_text="Total response time in milliseconds")
    avg_response_time = models.FloatField(default=0, help_text="Average response time in milliseconds")
    p95_response_time = models.FloatField(default=0, help_text="95th percentile response time")
    p99_response_time = models.FloatField(default=0, help_text="99th percentile response time")
    min_response_time = models.FloatField(default=0)
    max_response_time = models.FloatField(default=0)
    
    # User statistics
    unique_users = models.IntegerField(default=0)
    peak_hour = models.IntegerField(default=0, help_text="Hour with most requests (0-23)")
    
    # Data statistics
    data_transferred = models.BigIntegerField(default=0, help_text="Total data transferred in bytes")
    avg_request_size = models.FloatField(default=0, help_text="Average request size in bytes")
    avg_response_size = models.FloatField(default=0, help_text="Average response size in bytes")
    
    def __str__(self):
        return f"{self.date} - {self.endpoint}"
    
    def calculate_success_rate(self):
        """Calculate success rate percentage"""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100
    
    def update_statistics(self, log_entry):
        """Update statistics with new log entry"""
        self.total_requests += 1
        
        if log_entry.is_successful():
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        # Update response times
        self.total_response_time += log_entry.response_time
        
        # Update data sizes (estimated)
        request_size = len(str(log_entry.request_data)) if log_entry.request_data else 0
        response_size = len(str(log_entry.response_data)) if log_entry.response_data else 0
        self.data_transferred += request_size + response_size
        
        self.save()
        
        # Recalculate averages
        self.recalculate_averages()
    
    def recalculate_averages(self):
        """Recalculate average values"""
        if self.total_requests > 0:
            self.avg_response_time = self.total_response_time / self.total_requests
            self.avg_request_size = self.data_transferred / (self.total_requests * 2)
            self.avg_response_size = self.avg_request_size  # Simplified for now
        
        self.save()
    
    class Meta:
        verbose_name = "API Analytics"
        verbose_name_plural = "API Analytics"
        ordering = ['-date', 'endpoint']
        unique_together = ['date', 'endpoint']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['endpoint', 'date']),
        ]