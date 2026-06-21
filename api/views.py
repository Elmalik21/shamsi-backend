# [file name]: api/views.py
from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Avg

# Import models and serializers from the main solar_data app
from solar_data.models import Governorate, Location, DailyClimateData, MonthlySummary
from solar_data.serializers import (
    GovernorateSerializer, LocationSerializer,
    DailyClimateDataSerializer, MonthlySummarySerializer,
)

# Import local API management models
from .models import APIConfig, APILog, APIAnalytics
from .serializers import APIConfigSerializer, APILogSerializer, APIAnalyticsSerializer

# ============================================
# Solar Data ViewSets
# ============================================

class GovernorateViewSet(viewsets.ReadOnlyModelViewSet):
    """Governorates — annotated with location_count and avg stats for serializer."""
    serializer_class = GovernorateSerializer
    permission_classes = [AllowAny]  # Read-only public data

    def get_queryset(self):
        return Governorate.objects.annotate(
            location_count=Count('locations', distinct=True),
            avg_solar_radiation=Avg('locations__avg_solar_radiation'),
            avg_solar_potential=Avg('locations__solar_potential_score'),
        ).order_by('name')


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """Locations — public read-only with governorate filter."""
    queryset = Location.objects.select_related('governorate').order_by('name')
    serializer_class = LocationSerializer
    permission_classes = [AllowAny]
    filterset_fields = ['governorate', 'solar_potential_category']


class DailyClimateDataViewSet(viewsets.ReadOnlyModelViewSet):
    """Daily climate data — public read-only."""
    queryset = DailyClimateData.objects.select_related('location__governorate').order_by('-date')
    serializer_class = DailyClimateDataSerializer
    permission_classes = [AllowAny]
    filterset_fields = ['location', 'date']


class MonthlySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """Monthly summaries — public read-only."""
    queryset = MonthlySummary.objects.select_related('location__governorate').order_by('-year', '-month')
    serializer_class = MonthlySummarySerializer
    permission_classes = [AllowAny]
    filterset_fields = ['location', 'year', 'month']

# ============================================
# API Management ViewSets
# ============================================

class APIConfigViewSet(viewsets.ModelViewSet):
    queryset = APIConfig.objects.all()
    serializer_class = APIConfigSerializer
    permission_classes = [IsAdminUser]

class APILogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = APILog.objects.all()
    serializer_class = APILogSerializer
    permission_classes = [IsAdminUser]

class APIAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = APIAnalytics.objects.all()
    serializer_class = APIAnalyticsSerializer
    permission_classes = [IsAdminUser]

# ============================================
# Additional Views (Required by urls.py)
# ============================================

@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    return Response({
        'solar_data': {
            'governorates': '/api/v1/governorates/',
            'locations': '/api/v1/locations/',
            'climate_daily': '/api/v1/climate/daily/',
            'climate_monthly': '/api/v1/climate/monthly/',
        },
        'management': {
            'config': '/api/v1/config/',
            'logs': '/api/v1/logs/',
        }
    })

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({
            'username': request.user.username,
            'email': request.user.email,
            'is_staff': request.user.is_staff
        })

class SolarPotentialAnalysisView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'message': 'Analysis endpoint active'})

class TopSolarLocationsView(generics.ListAPIView):
    queryset = Location.objects.filter(solar_potential_score__gte=80)
    serializer_class = LocationSerializer
    permission_classes = [AllowAny]

class SolarRecommendationsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'message': 'Recommendations endpoint active'})

# Export Views Placeholders
class ClimateDataCSVExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return HttpResponse("CSV Export", content_type="text/csv")

class ClimateDataJSONExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return JsonResponse({'message': 'JSON Export'})

class LocationsCSVExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return HttpResponse("Locations CSV", content_type="text/csv")

# Stats Views Placeholders
class APIStatsSummaryView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({'status': 'ok'})

class APIUsageStatsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({'status': 'ok'})

class APIPerformanceStatsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({'status': 'ok'})

# Health Check Views
class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'status': 'healthy'})

class DetailedHealthCheckView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({'status': 'healthy', 'details': 'All systems operational'})

# Documentation Views Placeholders
class APISchemaView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'message': 'Schema'})

class SwaggerUIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return HttpResponse("Swagger UI")

class RedocView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return HttpResponse("Redoc")

# ============================================================
# NEW VIEWS: Tariffs, Equipment, AI, Projects
# ============================================================
from solar_data.models import (
    ElectricityTariff, SolarPanel, Inverter,
    InstallationCost, DesignProject,
)
from solar_data.serializers import (
    ElectricityTariffSerializer, SolarPanelSerializer,
    InverterSerializer, InstallationCostSerializer,
    DesignProjectSerializer,
)
from solar_data.utils import calculate_monthly_bill, calculate_annual_savings
import logging

logger = logging.getLogger(__name__)

# ── 5A: Tariff endpoints ──────────────────────────────────────────────────────

class TariffListView(generics.ListAPIView):
    queryset = ElectricityTariff.objects.all()
    serializer_class = ElectricityTariffSerializer
    permission_classes = [AllowAny]

class TariffByTypeView(generics.ListAPIView):
    serializer_class = ElectricityTariffSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        return ElectricityTariff.objects.filter(
            usage_type=self.kwargs['usage_type'].upper()
        )

class CalculateBillView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        monthly_kwh = request.data.get('monthly_kwh')
        usage_type  = request.data.get('usage_type', 'RESIDENTIAL')
        if monthly_kwh is None:
            return Response({'error': 'monthly_kwh is required'}, status=400)
        try:
            result = calculate_monthly_bill(float(monthly_kwh), usage_type)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class CalculateSavingsView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        annual_solar_kwh        = request.data.get('annual_solar_kwh')
        usage_type              = request.data.get('usage_type', 'RESIDENTIAL')
        monthly_kwh_without     = request.data.get('monthly_kwh_without_solar')
        if None in (annual_solar_kwh, monthly_kwh_without):
            return Response({'error': 'annual_solar_kwh and monthly_kwh_without_solar required'}, status=400)
        try:
            result = calculate_annual_savings(
                float(annual_solar_kwh), usage_type, float(monthly_kwh_without)
            )
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

# ── 5B: Equipment endpoints ───────────────────────────────────────────────────

class SolarPanelListView(generics.ListAPIView):
    serializer_class = SolarPanelSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        qs = SolarPanel.objects.filter(in_stock=True)
        brand = self.request.query_params.get('brand')
        min_cap = self.request.query_params.get('min_capacity')
        max_ppw = self.request.query_params.get('max_price_per_watt')
        if brand:
            qs = qs.filter(brand__icontains=brand)
        if min_cap:
            qs = qs.filter(capacity_w__gte=int(min_cap))
        if max_ppw:
            qs = qs.filter(price_per_watt_egp__lte=float(max_ppw))
        return qs

class InverterListView(generics.ListAPIView):
    serializer_class = InverterSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        qs = Inverter.objects.filter(in_stock=True)
        inv_type = self.request.query_params.get('type')
        min_kw   = self.request.query_params.get('min_kw')
        max_kw   = self.request.query_params.get('max_kw')
        if inv_type:
            qs = qs.filter(inverter_type=inv_type.upper())
        if min_kw:
            qs = qs.filter(capacity_kw__gte=float(min_kw))
        if max_kw:
            qs = qs.filter(capacity_kw__lte=float(max_kw))
        return qs

class InstallationCostListView(generics.ListAPIView):
    queryset = InstallationCost.objects.all()
    serializer_class = InstallationCostSerializer
    permission_classes = [AllowAny]

# ── 5C: AI endpoints (require auth) ──────────────────────────────────────────

class OptimizeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        from ai_engine.optimizer       import EgyptianSolarOptimizer
        from ai_engine.decision_support import EgyptianDecisionSupport

        # Required fields (usage_type is optional — default RESIDENTIAL)
        required = ['location_id', 'available_area_m2', 'monthly_consumption_kwh', 'budget_egp']
        for field in required:
            if field not in request.data:
                return Response({'error': f'{field} is required'}, status=400)

        # Inject usage_type default so optimizer always has it
        data = dict(request.data)
        data.setdefault('usage_type', 'RESIDENTIAL')

        try:
            optimizer = EgyptianSolarOptimizer()
            result    = optimizer.run(data)

            # ── Normalise field names for frontend compatibility ──────────────
            for sol in result.get('pareto_solutions', []):
                # Frontend reads space_utilization (not space_utilisation_pct)
                sol['space_utilization'] = round(
                    sol.get('space_utilisation_pct', 0) / 100.0, 3
                )
                # Frontend reads performance_ratio (PR = yield / peak_theoretical)
                sys_kw = sol.get('system_kw', 1)
                annual_yield = sol.get('annual_yield_kwh', 0)
                # PR estimate: actual / (irradiance_hours * installed_kw) — use 1825 h/yr Egypt avg
                sol['performance_ratio'] = round(
                    annual_yield / (sys_kw * 1825) if sys_kw > 0 else 0, 3
                )
                # Add panel_id / inverter_id hints (brand+model as slug)
                sol['panel_id']   = f"{sol.get('panel_brand','')}-{sol.get('panel_model','')}".lower().replace(' ', '-')
                sol['inverter_id']= f"{sol.get('inverter_brand','')}-{sol.get('inverter_model','')}".lower().replace(' ', '-')

            # ── Integrate Decision Support System ────────────────────────────
            try:
                dss = EgyptianDecisionSupport()
                site_context = {
                    'location_id':       data.get('location_id'),
                    'budget_egp':        float(data.get('budget_egp', 0)),
                    'available_area_m2': float(data.get('available_area_m2', 0)),
                    'usage_type':        data.get('usage_type', 'RESIDENTIAL'),
                    'shading_loss_pct':  float(data.get('shading_loss_pct', 5)),
                    'include_battery':   data.get('include_battery', False),
                    'system_type':       data.get('system_type', 'ON_GRID'),
                }
                dust_zone = result.get('dust_zone_info', {})
                recommendation = dss.generate_recommendation(
                    result.get('pareto_solutions', []),
                    site_context,
                    dust_zone,
                )
                result['recommendation'] = recommendation
            except Exception as dss_err:
                logger.warning("DSS failed (non-fatal): %s", dss_err)
                result['recommendation'] = None

            return Response(result)
        except Exception as e:
            logger.exception("Optimization error")
            return Response({'error': str(e)}, status=500)

class PredictYieldView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        from ai_engine.yield_predictor  import EgyptianYieldPredictor
        from ai_engine.dust_clustering  import EgyptianDustClusterer
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg, Max

        loc_id = request.data.get('location_id', 1)
        sys_kw = float(request.data.get('system_kw', 10.0))
        eff    = float(request.data.get('panel_efficiency', 0.22))
        tilt   = float(request.data.get('tilt_angle', 30.0))
        shade  = float(request.data.get('shading_loss_pct', 5.0))

        try:
            loc = Location.objects.get(location_id=loc_id)
        except Location.DoesNotExist:
            return Response({'error': f'Location {loc_id} not found'}, status=404)

        agg = DailyClimateData.objects.filter(location=loc).aggregate(
            avg_ghi=Avg('allsky_sfc_sw_dwn'), avg_temp=Avg('t2m'),
            max_temp=Max('t2m_max'), avg_hum=Avg('rh2m'), avg_wind=Avg('ws2m'),
        )
        dust_zone = EgyptianDustClusterer().predict_zone(loc_id)

        predictor = EgyptianYieldPredictor()
        result = predictor.predict({
            'avg_ghi':           agg['avg_ghi'] or 5.5,
            'avg_temperature':   agg['avg_temp'] or 28.0,
            'max_temperature':   agg['max_temp'] or 40.0,
            'avg_humidity':      agg['avg_hum'] or 40.0,
            'avg_wind_speed':    agg['avg_wind'] or 3.5,
            'dust_risk_score':   dust_zone['factor'],
            'latitude':          loc.latitude,
            'tilt_angle':        tilt,
            'panel_efficiency':  eff,
            'temp_coefficient':  -0.30,
            'system_kw':         sys_kw,
        })
        # Apply shading
        shade_factor = 1 - shade / 100
        result['predicted_annual_kwh'] = round(result['predicted_annual_kwh'] * shade_factor, 1)
        result['predicted_monthly']    = [round(v * shade_factor, 1) for v in result['predicted_monthly']]
        return Response(result)

class DustZonesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        from ai_engine.dust_clustering import EgyptianDustClusterer
        clusterer = EgyptianDustClusterer()
        zones = clusterer.get_all_zones()
        return Response(zones)

class ROIRangeView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_params(self, request):
        """Accept params from both GET query string and POST body."""
        if request.method == 'GET':
            return request.query_params
        return request.data

    def get(self, request):
        return self._calculate(request)

    def post(self, request):
        return self._calculate(request)

    def _calculate(self, request):
        from ai_engine.roi_calculator import EgyptianROICalculator
        params  = self._get_params(request)
        cost    = params.get('system_cost_egp')
        savings = params.get('annual_savings_egp')
        usage   = params.get('usage_type', 'RESIDENTIAL')
        if None in (cost, savings):
            return Response({'error': 'system_cost_egp and annual_savings_egp required'}, status=400)
        try:
            calc   = EgyptianROICalculator()
            result = calc.calculate_roi_range(float(cost), float(savings), usage)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

# ── 5D: Project endpoints ────────────────────────────────────────────────────

class DesignProjectViewSet(viewsets.ModelViewSet):
    serializer_class    = DesignProjectSerializer
    permission_classes  = [IsAuthenticated]

    def get_queryset(self):
        return DesignProject.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class SelectDesignView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, pk):
        return self._select(request, pk)

    def patch(self, request, pk):
        return self._select(request, pk)

    def _select(self, request, pk):
        try:
            project = DesignProject.objects.get(project_id=pk, user=request.user)
        except DesignProject.DoesNotExist:
            return Response({'error': 'Project not found'}, status=404)
        rank = request.data.get('solution_rank')
        if rank is None:
            return Response({'error': 'solution_rank required'}, status=400)
        solutions = project.pareto_solutions
        matching  = [s for s in solutions if s.get('rank') == int(rank)]
        if not matching:
            return Response({'error': f'No solution with rank {rank}'}, status=400)
        project.selected_design = matching[0]
        project.status = 'COMPLETED'
        project.save()
        return Response({'status': 'selected', 'design': project.selected_design})


# ── User Registration ─────────────────────────────────────────────────────────

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        email    = request.data.get('email',    '').strip()
        password = request.data.get('password', '')

        # Basic validation
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=400)

        if User.objects.filter(username=username).exists():
            return Response({'username': ['A user with that username already exists.']}, status=400)

        if email and User.objects.filter(email=email).exists():
            return Response({'email': ['A user with that email already exists.']}, status=400)

        # Password strength
        try:
            validate_password(password)
        except DjangoValidationError as e:
            return Response({'password': list(e.messages)}, status=400)

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'token':    token.key,
            'user_id':  user.pk,
            'username': user.username,
            'email':    user.email,
        }, status=201)
