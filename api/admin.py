# api/admin.py
from django.contrib import admin
from .models import APIConfig, APILog, APIAnalytics

@admin.register(APIConfig)
class APIConfigAdmin(admin.ModelAdmin):
    """Admin interface for API Configuration"""
    list_display = ['name', 'rate_limit', 'is_active', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit', 'burst_limit', 'window_seconds')
        }),
        ('Security Settings', {
            'fields': ('require_authentication', 'allowed_origins', 'cors_enabled'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    """Admin interface for API Logs"""
    list_display = ['timestamp', 'endpoint', 'method', 'status_code', 'response_time', 'user_id']
    list_filter = ['method', 'status_code', 'endpoint']
    search_fields = ['endpoint', 'ip_address', 'user_agent']
    date_hierarchy = 'timestamp'
    readonly_fields = ['timestamp', 'endpoint', 'method', 'status_code', 
                      'request_data', 'response_data', 'response_time', 
                      'ip_address', 'user_agent', 'user_id']
    list_per_page = 100
    
    fieldsets = (
        ('Request Information', {
            'fields': ('timestamp', 'endpoint', 'method', 'request_data')
        }),
        ('Response Information', {
            'fields': ('status_code', 'response_data', 'response_time')
        }),
        ('Client Information', {
            'fields': ('ip_address', 'user_agent', 'user_id'),
            'classes': ('collapse',)
        }),
    )

@admin.register(APIAnalytics)
class APIAnalyticsAdmin(admin.ModelAdmin):
    """Admin interface for API Analytics"""
    list_display = ['date', 'endpoint', 'total_requests', 'avg_response_time', 'unique_users']
    list_filter = ['endpoint']
    search_fields = ['endpoint']
    date_hierarchy = 'date'
    readonly_fields = ['date', 'endpoint', 'total_requests', 'successful_requests',
                      'failed_requests', 'total_response_time', 'avg_response_time',
                      'unique_users', 'peak_hour', 'data_transferred']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('date', 'endpoint')
        }),
        ('Request Statistics', {
            'fields': ('total_requests', 'successful_requests', 'failed_requests', 
                      'unique_users', 'peak_hour')
        }),
        ('Performance Metrics', {
            'fields': ('total_response_time', 'avg_response_time', 'p95_response_time',
                      'p99_response_time', 'min_response_time', 'max_response_time')
        }),
        ('Data Statistics', {
            'fields': ('data_transferred', 'avg_request_size', 'avg_response_size'),
            'classes': ('collapse',)
        }),
    )