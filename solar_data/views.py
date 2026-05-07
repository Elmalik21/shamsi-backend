# solar_data/views.py
"""
API Views for Solar Data Management System
"""
from django.shortcuts import render
from rest_framework import viewsets, generics, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg, Max, Min, Sum, Count, F
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
import math
from io import StringIO

from .models import Governorate, Location, DailyClimateData, MonthlySummary
from .serializers import (
    GovernorateSerializer, LocationSerializer,
    DailyClimateDataSerializer, MonthlySummarySerializer,
    SolarAnalysisSerializer, LocationDetailSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination configuration"""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
    page_query_param = 'page'


from django.http import JsonResponse
from django.views import View

class HealthCheckView(View):
    def get(self, request):
        return JsonResponse({
            'status': 'healthy',
            'service': 'solar_data'
        })

# ============================================
# API VIEWSETS
# ============================================

class GovernorateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Governorate data
    Provides CRUD operations for Egyptian governorates
    """
    queryset = Governorate.objects.all().order_by('name')
    serializer_class = GovernorateSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['code']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    @action(detail=True, methods=['get'])
    def locations(self, request, pk=None):
        """Get all locations for a specific governorate"""
        governorate = self.get_object()
        locations = governorate.locations.all()
        
        # Apply pagination
        page = self.paginate_queryset(locations)
        if page is not None:
            serializer = LocationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get governorate statistics"""
        cache_key = 'governorate_statistics'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        statistics = Governorate.objects.annotate(
            location_count=Count('location'),
            avg_solar_radiation=Avg('location__avg_solar_radiation'),
            avg_temperature=Avg('location__avg_temperature'),
            avg_solar_potential=Avg('location__solar_potential_score')
        ).values(
            'id', 'name', 'code',
            'location_count', 'avg_solar_radiation',
            'avg_temperature', 'avg_solar_potential'
        ).order_by('-avg_solar_potential')
        
        result = {
            'total_governorates': statistics.count(),
            'total_locations': sum(g['location_count'] for g in statistics),
            'statistics': list(statistics),
            'top_governorates': list(statistics[:5]),
            'timestamp': timezone.now().isoformat()
        }
        
        # Cache for 1 hour
        cache.set(cache_key, result, timeout=3600)
        
        return Response(result)


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Location data
    Provides CRUD operations for Egyptian locations
    """
    queryset = Location.objects.all().order_by('name')
    serializer_class = LocationSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['governorate', 'data_source']
    search_fields = ['name', 'governorate__name', 'description']
    ordering_fields = ['name', 'solar_potential_score', 'avg_solar_radiation', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Optimize queryset with prefetching"""
        queryset = super().get_queryset()
        return queryset.select_related('governorate').prefetch_related(
            'climate_data', 'monthly_summaries'
        )
    
    @action(detail=True, methods=['get'])
    def detail(self, request, pk=None):
        """Get detailed location information"""
        location = self.get_object()
        serializer = LocationDetailSerializer(location)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def climate_data(self, request, pk=None):
        """Get climate data for specific location"""
        location = self.get_object()
        
        # Get query parameters
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        limit = int(request.GET.get('limit', 100))
        format_type = request.GET.get('format', 'json')
        
        # Build queryset
        queryset = location.climate_data.all()
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        queryset = queryset.order_by('-date')[:limit]
        
        if format_type == 'csv':
            return self.export_climate_data_csv(queryset, location)
        
        # Apply pagination for JSON
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = DailyClimateDataSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DailyClimateDataSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def monthly_summaries(self, request, pk=None):
        """Get monthly summaries for specific location"""
        location = self.get_object()
        
        # Get query parameters
        year = request.GET.get('year')
        month = request.GET.get('month')
        
        queryset = location.monthly_summaries.all()
        
        if year:
            queryset = queryset.filter(year=year)
        if month:
            queryset = queryset.filter(month=month)
        
        queryset = queryset.order_by('-year', '-month')
        
        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = MonthlySummarySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MonthlySummarySerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def recalculate_statistics(self, request, pk=None):
        """Recalculate location statistics"""
        location = self.get_object()
        
        try:
            location.calculate_statistics()
            location.refresh_from_db()
            
            return Response({
                'status': 'success',
                'message': 'Statistics recalculated successfully',
                'updated_values': {
                    'avg_solar_radiation': location.avg_solar_radiation,
                    'avg_temperature': location.avg_temperature,
                    'solar_potential_score': location.solar_potential_score,
                    'updated_at': location.updated_at
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to recalculate statistics: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search locations by name or governorate"""
        query = request.GET.get('q', '')
        
        if not query or len(query) < 2:
            return Response({
                'error': 'Search query must be at least 2 characters'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        locations = Location.objects.filter(
            Q(name__icontains=query) |
            Q(governorate__name__icontains=query) |
            Q(description__icontains=query)
        ).select_related('governorate').order_by('name')
        
        # Apply pagination
        page = self.paginate_queryset(locations)
        if page is not None:
            serializer = LocationSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = LocationSerializer(locations, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def top_solar_potential(self, request):
        """Get locations with highest solar potential"""
        cache_key = 'top_solar_locations'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response(cached_data)
        
        limit = int(request.GET.get('limit', 10))
        
        locations = Location.objects.filter(
            solar_potential_score__isnull=False
        ).order_by('-solar_potential_score').select_related('governorate')[:limit]
        
        result = {
            'locations': LocationSerializer(locations, many=True).data,
            'count': locations.count(),
            'timestamp': timezone.now().isoformat()
        }
        
        # Cache for 30 minutes
        cache.set(cache_key, result, timeout=1800)
        
        return Response(result)
    
    def export_climate_data_csv(self, queryset, location):
        """Export climate data as CSV"""
        response = Response(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{location.name}_climate_data.csv"'
        
        writer = csv.writer(response)
        
        # Write headers
        headers = [
            'Date', 'Solar Radiation (kWh/m²)', 'Temperature (°C)',
            'Max Temperature (°C)', 'Min Temperature (°C)',
            'Humidity (%)', 'Wind Speed (m/s)', 'Cloud Cover (%)',
            'Precipitation (mm)', 'Solar Efficiency Factor',
            'Dust Risk Score', 'Weather Summary'
        ]
        writer.writerow(headers)
        
        # Write data
        for data in queryset:
            row = [
                data.date.strftime('%Y-%m-%d'),
                data.allsky_sfc_sw_dwn or '',
                data.t2m or '',
                data.t2m_max or '',
                data.t2m_min or '',
                data.rh2m or '',
                data.ws2m or '',
                data.cloud_amt or '',
                data.prectotcorr or '',
                data.solar_efficiency_factor or '',
                data.dust_risk_score or '',
                data.get_weather_summary() or ''
            ]
            writer.writerow(row)
        
        return response


class DailyClimateDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Daily Climate Data
    """
    queryset = DailyClimateData.objects.all().order_by('-date')
    serializer_class = DailyClimateDataSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['location', 'location__governorate']
    ordering_fields = ['date', 'allsky_sfc_sw_dwn', 't2m']
    ordering = ['-date']
    
    def get_queryset(self):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset()
        return queryset.select_related('location', 'location__governorate')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get climate data statistics"""
        # Get filters from query parameters
        location_id = request.GET.get('location_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        queryset = self.filter_queryset(self.get_queryset())
        
        if location_id:
            queryset = queryset.filter(location_id=location_id)
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        # Calculate statistics
        stats = queryset.aggregate(
            total_records=Count('id'),
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            max_radiation=Max('allsky_sfc_sw_dwn'),
            min_radiation=Min('allsky_sfc_sw_dwn'),
            avg_temperature=Avg('t2m'),
            avg_humidity=Avg('rh2m'),
            avg_wind_speed=Avg('ws2m'),
            total_precipitation=Sum('prectotcorr'),
            clear_days=Count('id', filter=Q(cloud_amt__lt=20)),
            sunny_days=Count('id', filter=Q(allsky_sfc_sw_dwn__gt=5)),
            hot_days=Count('id', filter=Q(t2m__gt=30))
        )
        
        # Calculate solar potential score
        avg_radiation = stats['avg_radiation'] or 0
        solar_potential = min(100, (avg_radiation / 8) * 100) if avg_radiation else 0
        
        result = {
            'statistics': stats,
            'solar_potential_score': round(solar_potential, 2),
            'solar_potential_rating': self.get_solar_rating(solar_potential),
            'date_range': {
                'start_date': queryset.aggregate(min_date=Min('date'))['min_date'],
                'end_date': queryset.aggregate(max_date=Max('date'))['max_date']
            },
            'record_count': stats['total_records']
        }
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def daily_summary(self, request):
        """Get daily climate summary for today"""
        today = timezone.now().date()
        
        # Get today's data aggregated by location
        today_data = DailyClimateData.objects.filter(date=today).values(
            'location__name', 'location__governorate__name'
        ).annotate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            avg_temperature=Avg('t2m'),
            avg_humidity=Avg('rh2m')
        ).order_by('-avg_radiation')
        
        # Calculate overall summary
        overall = DailyClimateData.objects.filter(date=today).aggregate(
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            avg_temperature=Avg('t2m'),
            location_count=Count('location', distinct=True)
        )
        
        result = {
            'date': today.isoformat(),
            'overall_summary': overall,
            'location_data': list(today_data),
            'best_location': today_data.first() if today_data else None,
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(result)
    
    def get_solar_rating(self, score):
        """Convert solar potential score to rating"""
        if score >= 80:
            return 'Excellent'
        elif score >= 60:
            return 'Good'
        elif score >= 40:
            return 'Fair'
        elif score >= 20:
            return 'Poor'
        else:
            return 'Very Poor'


class MonthlySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Monthly Summary Data
    """
    queryset = MonthlySummary.objects.all().order_by('-year', '-month')
    serializer_class = MonthlySummarySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['location', 'year', 'month', 'location__governorate']
    ordering_fields = ['year', 'month', 'avg_radiation', 'avg_temperature']
    ordering = ['-year', '-month']
    
    def get_queryset(self):
        """Optimize queryset with select_related"""
        queryset = super().get_queryset()
        return queryset.select_related('location', 'location__governorate')
    
    @action(detail=False, methods=['get'])
    def yearly_summary(self, request):
        """Get yearly summary statistics"""
        year = request.GET.get('year')
        
        if not year:
            return Response({
                'error': 'Year parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get monthly summaries for the year
        summaries = MonthlySummary.objects.filter(year=year).aggregate(
            avg_radiation=Avg('avg_radiation'),
            avg_temperature=Avg('avg_temperature'),
            total_precipitation=Sum('total_precipitation'),
            total_days=Sum('days_count'),
            clear_days_total=Sum('clear_days'),
            location_count=Count('location', distinct=True),
            month_count=Count('month', distinct=True)
        )
        
        # Get monthly breakdown
        monthly_breakdown = MonthlySummary.objects.filter(year=year).values(
            'month'
        ).annotate(
            avg_radiation=Avg('avg_radiation'),
            avg_temperature=Avg('avg_temperature'),
            location_count=Count('location', distinct=True)
        ).order_by('month')
        
        result = {
            'year': year,
            'summary': summaries,
            'monthly_breakdown': list(monthly_breakdown),
            'solar_potential_analysis': self.analyze_solar_potential(year)
        }
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def comparison(self, request):
        """Compare monthly summaries across locations or time periods"""
        location_id = request.GET.get('location_id')
        year1 = request.GET.get('year1')
        year2 = request.GET.get('year2')
        
        if not location_id or not year1:
            return Response({
                'error': 'location_id and year1 parameters are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get data for first year
        year1_data = MonthlySummary.objects.filter(
            location_id=location_id, year=year1
        ).order_by('month')
        
        comparison_data = {
            'year1': {
                'year': year1,
                'data': MonthlySummarySerializer(year1_data, many=True).data,
                'statistics': year1_data.aggregate(
                    avg_radiation=Avg('avg_radiation'),
                    avg_temperature=Avg('avg_temperature')
                )
            }
        }
        
        # Add second year data if provided
        if year2:
            year2_data = MonthlySummary.objects.filter(
                location_id=location_id, year=year2
            ).order_by('month')
            
            comparison_data['year2'] = {
                'year': year2,
                'data': MonthlySummarySerializer(year2_data, many=True).data,
                'statistics': year2_data.aggregate(
                    avg_radiation=Avg('avg_radiation'),
                    avg_temperature=Avg('avg_temperature')
                )
            }
            
            # Calculate differences
            stats1 = comparison_data['year1']['statistics']
            stats2 = comparison_data['year2']['statistics']
            
            comparison_data['comparison'] = {
                'radiation_change': (
                    (stats2['avg_radiation'] - stats1['avg_radiation']) / 
                    stats1['avg_radiation'] * 100 if stats1['avg_radiation'] else 0
                ),
                'temperature_change': (
                    stats2['avg_temperature'] - stats1['avg_temperature'] 
                    if stats1['avg_temperature'] and stats2['avg_temperature'] else 0
                )
            }
        
        return Response(comparison_data)
    
    def analyze_solar_potential(self, year):
        """Analyze solar potential for a given year"""
        summaries = MonthlySummary.objects.filter(year=year)
        
        if not summaries.exists():
            return None
        
        # Calculate solar potential metrics
        metrics = summaries.aggregate(
            avg_solar_potential=Avg(F('avg_radiation') * 12.5),  # Convert to score
            best_month=Max('avg_radiation'),
            worst_month=Min('avg_radiation'),
            consistency=Avg('avg_radiation') / Max('avg_radiation') * 100
        )
        
        # Determine seasonality
        season_data = summaries.values('month').annotate(
            avg_rad=Avg('avg_radiation')
        ).order_by('month')
        
        # Find peak and low seasons
        months = list(season_data)
        peak_season = max(months, key=lambda x: x['avg_rad']) if months else None
        low_season = min(months, key=lambda x: x['avg_rad']) if months else None
        
        return {
            'average_potential_score': metrics['avg_solar_potential'],
            'peak_season': peak_season,
            'low_season': low_season,
            'consistency_score': metrics['consistency'],
            'recommendation': self.get_recommendation(metrics['avg_solar_potential'])
        }
    
    def get_recommendation(self, score):
        """Get recommendation based on solar potential score"""
        if score >= 80:
            return "Excellent for solar installations. Consider large-scale systems."
        elif score >= 60:
            return "Good for solar installations. Standard systems recommended."
        elif score >= 40:
            return "Moderate potential. Consider smaller systems or hybrid solutions."
        else:
            return "Limited solar potential. Evaluate alternative energy sources."


# ============================================
# SPECIALIZED API VIEWS
# ============================================

@api_view(['GET'])
@permission_classes([AllowAny])
def dashboard_summary(request):
    """
    Get dashboard summary statistics
    """
    cache_key = 'dashboard_summary'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return Response(cached_data)
    
    # Calculate statistics
    statistics = {
        'governorates': {
            'total': Governorate.objects.count(),
            'with_locations': Governorate.objects.filter(location__isnull=False).distinct().count()
        },
        'locations': {
            'total': Location.objects.count(),
            'with_data': Location.objects.filter(climate_data__isnull=False).distinct().count(),
            'with_solar_score': Location.objects.filter(solar_potential_score__isnull=False).count()
        },
        'climate_data': {
            'total_records': DailyClimateData.objects.count(),
            'date_range': DailyClimateData.objects.aggregate(
                first_date=Min('date'),
                last_date=Max('date')
            ),
            'avg_daily_records': DailyClimateData.objects.count() / max(
                1, (timezone.now().date() - DailyClimateData.objects.aggregate(
                    Min('date'))['date__min']).days
            ) if DailyClimateData.objects.exists() else 0
        },
        'monthly_summaries': {
            'total': MonthlySummary.objects.count(),
            'avg_per_location': MonthlySummary.objects.count() / max(
                1, Location.objects.filter(monthly_summaries__isnull=False).distinct().count()
            )
        },
        'solar_potential': {
            'avg_score': Location.objects.filter(
                solar_potential_score__isnull=False
            ).aggregate(Avg('solar_potential_score'))['solar_potential_score__avg'],
            'excellent_locations': Location.objects.filter(
                solar_potential_score__gte=80
            ).count(),
            'good_locations': Location.objects.filter(
                solar_potential_score__gte=60,
                solar_potential_score__lt=80
            ).count()
        },
        'timestamp': timezone.now().isoformat()
    }
    
    # Cache for 5 minutes
    cache.set(cache_key, statistics, timeout=300)
    
    return Response(statistics)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def solar_analysis(request):
    """
    Perform advanced solar potential analysis
    """
    serializer = SolarAnalysisSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Get locations based on filters
    locations = Location.objects.all()
    
    if data.get('governorate'):
        locations = locations.filter(governorate=data['governorate'])
    
    if data.get('min_solar_potential'):
        locations = locations.filter(
            solar_potential_score__gte=data['min_solar_potential']
        )
    
    if data.get('max_solar_potential'):
        locations = locations.filter(
            solar_potential_score__lte=data['max_solar_potential']
        )
    
    # Apply analysis type
    if data['analysis_type'] == 'ranking':
        results = locations.order_by('-solar_potential_score')[:data.get('limit', 10)]
        analysis_result = {
            'type': 'ranking',
            'count': results.count(),
            'locations': LocationSerializer(results, many=True).data
        }
    
    elif data['analysis_type'] == 'statistics':
        stats = locations.aggregate(
            avg_score=Avg('solar_potential_score'),
            max_score=Max('solar_potential_score'),
            min_score=Min('solar_potential_score'),
            std_dev=Count('solar_potential_score'),  # Simplified std dev
            location_count=Count('id')
        )
        
        # Calculate distribution
        distribution = locations.values('governorate__name').annotate(
            count=Count('id'),
            avg_score=Avg('solar_potential_score')
        ).order_by('-avg_score')
        
        analysis_result = {
            'type': 'statistics',
            'overall': stats,
            'distribution': list(distribution),
            'recommendations': generate_recommendations(stats['avg_score'])
        }
    
    elif data['analysis_type'] == 'comparison':
        if not data.get('comparison_locations'):
            return Response(
                {'error': 'comparison_locations required for comparison analysis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comparison_data = []
        for loc_id in data['comparison_locations']:
            try:
                location = Location.objects.get(id=loc_id)
                comparison_data.append({
                    'location': LocationSerializer(location).data,
                    'climate_stats': get_location_climate_stats(location),
                    'monthly_stats': get_location_monthly_stats(location)
                })
            except Location.DoesNotExist:
                continue
        
        analysis_result = {
            'type': 'comparison',
            'locations': comparison_data,
            'comparison_metrics': compare_locations(comparison_data)
        }
    
    else:
        return Response(
            {'error': 'Invalid analysis type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Add metadata
    analysis_result.update({
        'parameters': data,
        'timestamp': timezone.now().isoformat(),
        'locations_analyzed': locations.count()
    })
    
    return Response(analysis_result)


@api_view(['GET'])
@permission_classes([AllowAny])
def export_data(request):
    """
    Export data in various formats
    """
    export_type = request.GET.get('type', 'locations')
    format_type = request.GET.get('format', 'json')
    
    if export_type == 'locations':
        queryset = Location.objects.all().select_related('governorate')
        filename = 'locations_export'
    
    elif export_type == 'climate_data':
        queryset = DailyClimateData.objects.all().select_related('location')
        filename = 'climate_data_export'
    
    elif export_type == 'monthly_summaries':
        queryset = MonthlySummary.objects.all().select_related('location')
        filename = 'monthly_summaries_export'
    
    else:
        return Response(
            {'error': 'Invalid export type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Apply filters
    filters = request.GET.dict()
    for key, value in filters.items():
        if key not in ['type', 'format', 'page', 'page_size'] and value:
            if '__' in key:
                queryset = queryset.filter(**{key: value})
    
    if format_type == 'csv':
        return export_to_csv(queryset, export_type, filename)
    elif format_type == 'json':
        return export_to_json(request, queryset, export_type)
    else:
        return Response(
            {'error': 'Invalid format. Use csv or json'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============================================
# HELPER FUNCTIONS
# ============================================

def export_to_csv(queryset, export_type, filename):
    """Export queryset to CSV"""
    response = Response(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    # Write headers based on export type
    if export_type == 'locations':
        headers = ['ID', 'Name', 'Governorate', 'Latitude', 'Longitude',
                  'Avg Solar Radiation', 'Avg Temperature', 'Solar Potential Score',
                  'Data Source', 'Created At', 'Updated At']
        writer.writerow(headers)
        
        for obj in queryset:
            row = [
                obj.id, obj.name, obj.governorate.name if obj.governorate else '',
                float(obj.latitude), float(obj.longitude),
                obj.avg_solar_radiation or '', obj.avg_temperature or '',
                obj.solar_potential_score or '', obj.data_source or '',
                obj.created_at, obj.updated_at
            ]
            writer.writerow(row)
    
    elif export_type == 'climate_data':
        headers = ['ID', 'Date', 'Location', 'Solar Radiation', 'Temperature',
                  'Max Temp', 'Min Temp', 'Humidity', 'Wind Speed', 'Cloud Cover',
                  'Precipitation', 'Solar Efficiency', 'Dust Risk']
        writer.writerow(headers)
        
        for obj in queryset:
            row = [
                obj.id, obj.date, obj.location.name if obj.location else '',
                obj.allsky_sfc_sw_dwn or '', obj.t2m or '',
                obj.t2m_max or '', obj.t2m_min or '', obj.rh2m or '',
                obj.ws2m or '', obj.cloud_amt or '', obj.prectotcorr or '',
                obj.solar_efficiency_factor or '', obj.dust_risk_score or ''
            ]
            writer.writerow(row)
    
    return response


def export_to_json(request, queryset, export_type):
    """Export queryset to JSON"""
    from django.core.paginator import Paginator
    from django.core.paginator import PageNotAnInteger, EmptyPage

    paginator = Paginator(queryset, 1000)  # 1000 items per page
    page_number = request.GET.get('page', 1)
    
    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)
    
    if export_type == 'locations':
        serializer = LocationSerializer(page, many=True)
    elif export_type == 'climate_data':
        serializer = DailyClimateDataSerializer(page, many=True)
    else:
        serializer = MonthlySummarySerializer(page, many=True)
    
    result = {
        'type': export_type,
        'page': page.number,
        'total_pages': paginator.num_pages,
        'total_items': paginator.count,
        'items_per_page': paginator.per_page,
        'data': serializer.data,
        'timestamp': timezone.now().isoformat()
    }
    
    return Response(result)


def generate_recommendations(avg_score):
    """Generate recommendations based on average solar score"""
    if avg_score >= 80:
        return [
            "Excellent solar potential - ideal for large-scale solar farms",
            "Consider government incentives for renewable energy",
            "High return on investment expected"
        ]
    elif avg_score >= 60:
        return [
            "Good solar potential - suitable for commercial installations",
            "Consider medium-scale systems",
            "Moderate return on investment"
        ]
    elif avg_score >= 40:
        return [
            "Moderate solar potential - suitable for residential use",
            "Consider hybrid systems with backup",
            "Evaluate local grid connection options"
        ]
    else:
        return [
            "Limited solar potential - explore alternative energy sources",
            "Consider energy efficiency improvements first",
            "Consult with solar experts for site-specific assessment"
        ]


def get_location_climate_stats(location):
    """Get climate statistics for a location"""
    climate_data = location.climate_data.all()
    
    if not climate_data.exists():
        return None
    
    stats = climate_data.aggregate(
        avg_radiation=Avg('allsky_sfc_sw_dwn'),
        avg_temperature=Avg('t2m'),
        avg_humidity=Avg('rh2m'),
        total_precipitation=Sum('prectotcorr'),
        clear_days=Count('id', filter=Q(cloud_amt__lt=20)),
        sunny_days=Count('id', filter=Q(allsky_sfc_sw_dwn__gt=5))
    )
    
    return stats


def get_location_monthly_stats(location):
    """Get monthly statistics for a location"""
    monthly_data = location.monthly_summaries.all()
    
    if not monthly_data.exists():
        return None
    
    stats = monthly_data.aggregate(
        avg_monthly_radiation=Avg('avg_radiation'),
        avg_monthly_temperature=Avg('avg_temperature'),
        total_months=Count('id')
    )
    
    return stats


def compare_locations(comparison_data):
    """Compare multiple locations"""
    if len(comparison_data) < 2:
        return None
    
    metrics = {}
    
    # Compare solar potential scores
    scores = [loc['location']['solar_potential_score'] 
              for loc in comparison_data if loc['location'].get('solar_potential_score')]
    
    if scores:
        metrics['solar_potential'] = {
            'best': max(scores),
            'worst': min(scores),
            'range': max(scores) - min(scores) if scores else 0
        }
    
    # Compare climate stats
    climate_stats = [loc['climate_stats'] for loc in comparison_data if loc.get('climate_stats')]
    
    if climate_stats:
        radiations = [s.get('avg_radiation', 0) for s in climate_stats]
        temperatures = [s.get('avg_temperature', 0) for s in climate_stats]
        
        metrics['climate'] = {
            'radiation': {
                'best': max(radiations) if radiations else 0,
                'worst': min(radiations) if radiations else 0
            },
            'temperature': {
                'highest': max(temperatures) if temperatures else 0,
                'lowest': min(temperatures) if temperatures else 0
            }
        }
    
    return metrics


# ============================================
# URL CONFIGURATION
# ============================================

# These views would be registered in urls.py like:
# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import (
#     GovernorateViewSet, LocationViewSet, 
#     DailyClimateDataViewSet, MonthlySummaryViewSet,
#     dashboard_summary, solar_analysis, export_data
# )
#
# router = DefaultRouter()
# router.register(r'governorates', GovernorateViewSet)
# router.register(r'locations', LocationViewSet)
# router.register(r'climate-data', DailyClimateDataViewSet)
# router.register(r'monthly-summaries', MonthlySummaryViewSet)
#
# urlpatterns = [
#     path('', include(router.urls)),
#     path('dashboard-summary/', dashboard_summary, name='dashboard-summary'),
#     path('solar-analysis/', solar_analysis, name='solar-analysis'),
#     path('export/', export_data, name='export-data'),
# ]