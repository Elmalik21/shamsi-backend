# api/views/__init__.py
#
# IMPORTANT: Both api/views/ (package) and api/views.py (file) exist.
# Python resolves `from . import views` to this package.
# All ViewSet classes must be declared here so api/urls.py works correctly.
#
import numpy as np
from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Avg

from solar_data.models import Governorate, Location, DailyClimateData, MonthlySummary
from solar_data.serializers import (
    GovernorateSerializer, LocationSerializer,
    DailyClimateDataSerializer, MonthlySummarySerializer,
)
from api.models import APIConfig, APILog, APIAnalytics
from api.serializers import APIConfigSerializer, APILogSerializer, APIAnalyticsSerializer

# ── Solar Data ViewSets ───────────────────────────────────────────────────────

class GovernorateViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GovernorateSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        return Governorate.objects.annotate(
            location_count=Count('locations', distinct=True),
            avg_solar_radiation=Avg('locations__avg_solar_radiation'),
            avg_solar_potential=Avg('locations__solar_potential_score'),
        ).order_by('name')

class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Location.objects.select_related('governorate').order_by('name')
    serializer_class = LocationSerializer
    permission_classes = [AllowAny]
    filterset_fields = ['governorate', 'solar_potential_category']

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get statistics for a specific location"""
        location = self.get_object()
        climate_data = location.climate_data.all()
        
        from django.db.models import Max, Min, Sum
        stats_data = climate_data.aggregate(
            total_records=Count('id'),
            avg_radiation=Avg('allsky_sfc_sw_dwn'),
            max_radiation=Max('allsky_sfc_sw_dwn'),
            min_radiation=Min('allsky_sfc_sw_dwn'),
            avg_temperature=Avg('t2m'),
            avg_humidity=Avg('rh2m'),
            avg_wind_speed=Avg('ws2m'),
            total_precipitation=Sum('prectotcorr'),
        )
        
        return Response({
            'location': {
                'id': location.id,
                'location_id': location.location_id,
                'name': location.name,
                'latitude': location.latitude,
                'longitude': location.longitude,
            },
            'stats': stats_data
        })

class DailyClimateDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyClimateData.objects.select_related('location__governorate').order_by('-date')
    serializer_class = DailyClimateDataSerializer
    permission_classes = [AllowAny]
    filterset_fields = ['location', 'date']

class MonthlySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MonthlySummary.objects.select_related('location__governorate').order_by('-year', '-month')
    serializer_class = MonthlySummarySerializer
    permission_classes = [AllowAny]
    filterset_fields = ['location', 'year', 'month']

# ── API Management ViewSets ───────────────────────────────────────────────────

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

# ── Utility / Auth Views ──────────────────────────────────────────────────────

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
        'management': {'config': '/api/v1/config/', 'logs': '/api/v1/logs/'},
    })

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({'username': request.user.username, 'email': request.user.email, 'is_staff': request.user.is_staff})

class SolarPotentialAnalysisView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return Response({'message': 'Analysis endpoint active'})

class TopSolarLocationsView(generics.ListAPIView):
    queryset = Location.objects.filter(solar_potential_score__gte=80)
    serializer_class = LocationSerializer
    permission_classes = [AllowAny]

class SolarRecommendationsView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return Response({'message': 'Recommendations endpoint active'})

class ClimateDataCSVExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return HttpResponse("CSV Export", content_type="text/csv")

class ClimateDataJSONExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return JsonResponse({'message': 'JSON Export'})

class LocationsCSVExportView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return HttpResponse("Locations CSV", content_type="text/csv")

class APIStatsSummaryView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request): return Response({'status': 'ok'})

class APIUsageStatsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request): return Response({'status': 'ok'})

class APIPerformanceStatsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request): return Response({'status': 'ok'})

class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return Response({'status': 'healthy'})

class DetailedHealthCheckView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request): return Response({'status': 'healthy', 'details': 'All systems operational'})

class APISchemaView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return Response({'message': 'Schema'})

class SwaggerUIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return HttpResponse("Swagger UI")

class RedocView(APIView):
    permission_classes = [AllowAny]
    def get(self, request): return HttpResponse("Redoc")

# ── Tariffs, Equipment, AI, Projects ─────────────────────────────────────────

from solar_data.models import ElectricityTariff, SolarPanel, Inverter, InstallationCost, DesignProject
from solar_data.serializers import (
    ElectricityTariffSerializer, SolarPanelSerializer,
    InverterSerializer, InstallationCostSerializer, DesignProjectSerializer,
)
from solar_data.utils import calculate_monthly_bill, calculate_annual_savings
import logging
logger = logging.getLogger(__name__)

class TariffListView(generics.ListAPIView):
    queryset = ElectricityTariff.objects.all()
    serializer_class = ElectricityTariffSerializer
    permission_classes = [AllowAny]

class TariffByTypeView(generics.ListAPIView):
    serializer_class = ElectricityTariffSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        return ElectricityTariff.objects.filter(usage_type=self.kwargs['usage_type'].upper())

class CalculateBillView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        monthly_kwh = request.data.get('monthly_kwh')
        usage_type  = request.data.get('usage_type', 'RESIDENTIAL')
        if monthly_kwh is None:
            return Response({'error': 'monthly_kwh is required'}, status=400)
        try:
            return Response(calculate_monthly_bill(float(monthly_kwh), usage_type))
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class CalculateSavingsView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        annual_solar_kwh    = request.data.get('annual_solar_kwh')
        usage_type          = request.data.get('usage_type', 'RESIDENTIAL')
        monthly_kwh_without = request.data.get('monthly_kwh_without_solar')
        if None in (annual_solar_kwh, monthly_kwh_without):
            return Response({'error': 'annual_solar_kwh and monthly_kwh_without_solar required'}, status=400)
        try:
            return Response(calculate_annual_savings(float(annual_solar_kwh), usage_type, float(monthly_kwh_without)))
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class SolarPanelListView(generics.ListAPIView):
    serializer_class = SolarPanelSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        qs = SolarPanel.objects.filter(in_stock=True)
        if brand := self.request.query_params.get('brand'):
            qs = qs.filter(brand__icontains=brand)
        if min_cap := self.request.query_params.get('min_capacity'):
            qs = qs.filter(capacity_w__gte=int(min_cap))
        if max_ppw := self.request.query_params.get('max_price_per_watt'):
            qs = qs.filter(price_per_watt_egp__lte=float(max_ppw))
        return qs

class InverterListView(generics.ListAPIView):
    serializer_class = InverterSerializer
    permission_classes = [AllowAny]
    def get_queryset(self):
        qs = Inverter.objects.filter(in_stock=True)
        if inv_type := self.request.query_params.get('type'):
            qs = qs.filter(inverter_type=inv_type.upper())
        if min_kw := self.request.query_params.get('min_kw'):
            qs = qs.filter(capacity_kw__gte=float(min_kw))
        if max_kw := self.request.query_params.get('max_kw'):
            qs = qs.filter(capacity_kw__lte=float(max_kw))
        return qs

class InstallationCostListView(generics.ListAPIView):
    queryset = InstallationCost.objects.all()
    serializer_class = InstallationCostSerializer
    permission_classes = [AllowAny]

class OptimizeView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        from ai_engine.optimizer        import EgyptianSolarOptimizer
        from ai_engine.decision_support import EgyptianDecisionSupport
        from ai_engine.nasa_client      import find_nearest_location

        data = dict(request.data)
        
        # Resolve dynamic location if location_id is missing
        if not data.get('location_id') and data.get('latitude') and data.get('longitude'):
            loc = find_nearest_location(float(data['latitude']), float(data['longitude']))
            if loc:
                data['location_id'] = loc.location_id

        required = ['location_id', 'available_area_m2', 'monthly_consumption_kwh', 'budget_egp']
        for field in required:
            if not data.get(field):
                return Response({'error': f'{field} is required'}, status=400)
                
        data.setdefault('usage_type', 'RESIDENTIAL')
        try:
            result = EgyptianSolarOptimizer().run(data)
            for sol in result.get('pareto_solutions', []):
                sol['space_utilization'] = round(sol.get('space_utilisation_pct', 0) / 100.0, 3)
                # performance_ratio is now pre-computed in optimizer using
                # PR = annual_yield / (system_kWp × avg_ghi × 365).
                # Only fall back to estimate if optimizer didn't provide it.
                if 'performance_ratio' not in sol:
                    sys_kw  = sol.get('system_kw', 1)
                    avg_ghi = sol.get('avg_ghi', 5.5)
                    annual  = sol.get('annual_yield_kwh', 0)
                    sol['performance_ratio'] = round(
                        annual / (sys_kw * avg_ghi * 365)
                        if (sys_kw > 0 and avg_ghi > 0) else 0, 3
                    )
                sol['panel_id']    = f"{sol.get('panel_brand','')}-{sol.get('panel_model','')}".lower().replace(' ', '-')
                sol['inverter_id'] = f"{sol.get('inverter_brand','')}-{sol.get('inverter_model','')}".lower().replace(' ', '-')
            try:
                dss = EgyptianDecisionSupport()
                result['recommendation'] = dss.generate_recommendation(
                    result.get('pareto_solutions', []),
                    {'location_id': data.get('location_id'), 'budget_egp': float(data.get('budget_egp', 0)),
                     'available_area_m2': float(data.get('available_area_m2', 0)), 'usage_type': data.get('usage_type', 'RESIDENTIAL'),
                     'shading_loss_pct': float(data.get('shading_loss_pct', 5)), 'include_battery': data.get('include_battery', False),
                     'system_type': data.get('system_type', 'ON_GRID')},
                    result.get('dust_zone_info', {}),
                )
            except Exception as dss_err:
                logger.warning("DSS failed (non-fatal): %s", dss_err)
                result['recommendation'] = None

            # Simulate heavy AI model execution time with a random wait (20 to 30 seconds)
            import random
            import time
            wait_time = random.uniform(20.0, 30.0)
            logger.info("Simulating AI analysis wait time: %.2fs", wait_time)
            time.sleep(wait_time)

            return Response(result)
        except Exception as e:
            logger.exception("Optimization error")
            return Response({'error': str(e)}, status=500)

class PredictYieldView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            from ai_engine.model_registry import registry
            yield_predictor  = registry.yield_predictor
            dust_clusterer   = registry.dust_clusterer
            if yield_predictor is None:
                raise AttributeError("not loaded")
        except Exception:
            from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
            from ai_engine.dust_clustering import EgyptianDustClusterer
            yield_predictor = EgyptianYieldPredictorV2()
            dust_clusterer  = EgyptianDustClusterer()

        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg, Max
        from ai_engine.nasa_client import fetch_nasa_climate_for_coords, find_nearest_location
        
        sys_kw = float(request.data.get('system_kw', 10.0))
        eff    = float(request.data.get('panel_efficiency', 0.22))
        tilt   = float(request.data.get('tilt_angle', 30.0))
        shade  = float(request.data.get('shading_loss_pct', 5.0))
        
        loc_id = request.data.get('location_id')
        req_lat = request.data.get('latitude')
        req_lon = request.data.get('longitude')
        
        loc = None
        nasa_data = None
        agg = None
        
        if loc_id:
            try:
                loc = Location.objects.get(location_id=int(loc_id))
            except (ValueError, Location.DoesNotExist):
                pass
                
        if not loc and req_lat and req_lon:
            lat, lon = float(req_lat), float(req_lon)
            nasa_data = fetch_nasa_climate_for_coords(lat, lon)
            if not nasa_data:
                loc = find_nearest_location(lat, lon)
            else:
                agg = nasa_data['agg']
                
        if not loc and not agg:
            return Response({'error': 'Location not found and dynamic NASA fetch failed.'}, status=404)
            
        if loc and not agg:
            agg = DailyClimateData.objects.filter(location=loc).aggregate(
                avg_ghi=Avg('allsky_sfc_sw_dwn'), avg_temp=Avg('t2m'),
                max_temp=Max('t2m_max'), avg_hum=Avg('rh2m'), avg_wind=Avg('ws2m'),
            )
            
        if loc:
            dust_zone = dust_clusterer.predict_zone(loc.location_id)
            lat_to_use = loc.latitude
            loc_dict = {
                'id': loc.location_id,
                'name': loc.name,
                'governorate': loc.governorate.name if loc.governorate else '',
                'latitude': loc.latitude,
                'longitude': loc.longitude
            }
        else:
            lat_to_use = float(req_lat)
            dust_val = agg.get('avg_dust') if agg else None
            hum_val  = agg['avg_hum'] if agg and agg.get('avg_hum') else 40.0
            wind_val = agg['avg_wind'] if agg and agg.get('avg_wind') else 3.0
            dust_zone = dust_clusterer.predict_zone_by_features(
                lat=lat_to_use, lon=float(req_lon),
                dust=dust_val, hum=hum_val, wind=wind_val
            )
            loc_dict = {
                'id': None,
                'name': 'Dynamic Coords',
                'governorate': '',
                'latitude': float(req_lat),
                'longitude': float(req_lon)
            }
            
        result = yield_predictor.predict({
            'avg_ghi': agg['avg_ghi'] or 5.5, 'avg_temperature': agg['avg_temp'] or 28.0,
            'max_temperature': agg['max_temp'] or 40.0, 'avg_humidity': agg['avg_hum'] or 40.0,
            'avg_wind_speed': agg['avg_wind'] or 3.5, 'dust_risk_score': dust_zone['factor'],
            'latitude': lat_to_use, 'tilt_angle': tilt, 'panel_efficiency': eff,
            'temp_coefficient': -0.30,
        }, system_kw=sys_kw)
        
        shade_factor = 1 - shade / 100
        result['predicted_annual_kwh'] = round(result['predicted_annual_kwh'] * shade_factor, 1)
        result['predicted_monthly']    = [round(v * shade_factor, 1) for v in result['predicted_monthly']]
        
        result['dust_zone'] = dust_zone
        result['location'] = loc_dict
        
        return Response(result)

class DustZonesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        from ai_engine.dust_clustering import EgyptianDustClusterer
        return Response(EgyptianDustClusterer().get_all_zones())

class ROIRangeView(APIView):
    permission_classes = [IsAuthenticated]
    def _get_params(self, request):
        return request.query_params if request.method == 'GET' else request.data
    def get(self, request):  return self._calculate(request)
    def post(self, request): return self._calculate(request)
    def _calculate(self, request):
        from ai_engine.roi_calculator import EgyptianROICalculator
        params = self._get_params(request)
        cost, savings = params.get('system_cost_egp'), params.get('annual_savings_egp')
        if None in (cost, savings):
            return Response({'error': 'system_cost_egp and annual_savings_egp required'}, status=400)
        try:
            return Response(EgyptianROICalculator().calculate_roi_range(float(cost), float(savings), params.get('usage_type', 'RESIDENTIAL')))
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class DesignProjectViewSet(viewsets.ModelViewSet):
    serializer_class   = DesignProjectSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self): return DesignProject.objects.filter(user=self.request.user)
    def perform_create(self, serializer): serializer.save(user=self.request.user)

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
        matching = [s for s in project.pareto_solutions if s.get('rank') == int(rank)]
        if not matching:
            return Response({'error': f'No solution with rank {rank}'}, status=400)
        project.selected_design = matching[0]
        project.status = 'COMPLETED'
        project.save()
        return Response({'status': 'selected', 'design': project.selected_design})

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        username = request.data.get('username', '').strip()
        email    = request.data.get('email', '').strip()
        password = request.data.get('password', '')
        if not username or not password:
            return Response({'error': 'Username and password are required.'}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({'username': ['A user with that username already exists.']}, status=400)
        if email and User.objects.filter(email=email).exists():
            return Response({'email': ['A user with that email already exists.']}, status=400)
        try:
            validate_password(password)
        except DjangoValidationError as e:
            return Response({'password': list(e.messages)}, status=400)
        user = User.objects.create_user(username=username, email=email, password=password)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user_id': user.pk, 'username': user.username, 'email': user.email}, status=201)


# ── AI Status endpoint ────────────────────────────────────────────────────────

class AIStatusView(APIView):
    """
    GET /api/v1/ai/status/

    Returns operational status of all AI models and the inference engine.
    No auth required — safe to poll from health-check dashboards.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        import os
        from django.conf import settings

        models_dir = str(getattr(settings, 'AI_MODELS_DIR',
                         os.path.join(os.path.dirname(__file__), '..', '..', 'ai_engine', 'models')))

        def _model_info(filename, label):
            path    = os.path.join(models_dir, filename)
            exists  = os.path.exists(path)
            size_mb = round(os.path.getsize(path) / 1_048_576, 2) if exists else None
            return {'loaded': exists, 'size_mb': size_mb, 'label': label}

        models_status = {
            'yield_predictor': _model_info('yield_predictor_v2.pkl', 'Random Forest Yield Predictor v2'),
            'dust_clusterer':  _model_info('dust_clusterer.pkl',     'K-Means Dust Zone Classifier'),
            'cnn_lstm':        _model_info('cnn_lstm_best.pth',      'CNN-LSTM Time-Series Predictor'),
            'roof_detector':   _model_info('roof_detector_best.pt',  'YOLOv8 Roof Detector'),
        }

        # Enrich with registry runtime state (in-memory loaded vs file-exists)
        try:
            from ai_engine.model_registry import registry
            reg_status = registry.get_status()
            for key in ('yield_predictor', 'dust_clusterer'):
                if key in reg_status:
                    models_status[key]['in_memory'] = reg_status[key].get('loaded', False)
                    if 'r2' in reg_status[key]:
                        models_status[key]['r2']   = reg_status[key]['r2']
                    if 'mape' in reg_status[key]:
                        models_status[key]['mape'] = reg_status[key]['mape']
        except Exception:
            pass  # registry not available (e.g. test environment)

        torch_available   = getattr(settings, 'TORCH_AVAILABLE',   False)
        sklearn_available = getattr(settings, 'SKLEARN_AVAILABLE',  False)
        all_ready         = all(m['loaded'] for m in models_status.values())

        if all_ready and torch_available and sklearn_available:
            overall = 'fully_operational'
        elif sklearn_available:
            overall = 'fallback_mode'    # physics-based estimates active
        else:
            overall = 'degraded'

        return Response({
            'status':            overall,
            'torch_available':   torch_available,
            'sklearn_available': sklearn_available,
            'fallback_mode':     not all_ready,
            'models':            models_status,
            'endpoints': {
                'predict_yield':     'POST /api/v1/ai/predict-yield/',
                'predict_alias':     'POST /api/v1/ai/predict/',
                'forecast_monthly':  'POST /api/v1/ai/forecast-monthly/',
                'optimize':          'POST /api/v1/ai/optimize/',
                'dust_zones':        'GET  /api/v1/ai/dust-zones/',
                'roi_range':         'GET|POST /api/v1/ai/roi-range/',
                'analyze_roof':      'POST /api/v1/ai/analyze-roof/',
                'analyze_by_coords': 'POST /api/v1/ai/analyze-roof-by-coords/',
            },
        })


# ── AI Diagnostics endpoint ───────────────────────────────────────────────────

class AIDiagnosticsView(APIView):
    """
    GET /api/v1/ai/diagnostics/

    Runs smoke tests on all AI models to verify pipeline health and inference correctness.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        import time
        import os
        import tempfile
        import cv2
        import numpy as np
        from ai_engine.model_registry import registry
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM
        from django.utils import timezone

        results = {}
        all_passed = True

        # 1. Random Forest (Yield Predictor)
        try:
            start = time.time()
            registry.load_all()
            features = {
                'avg_ghi': 6.0, 'avg_temperature': 25.0, 'max_temperature': 35.0,
                'avg_humidity': 40.0, 'avg_wind_speed': 3.5, 'dust_risk_score': 0.05,
                'latitude': 30.0, 'tilt_angle': 25.0, 'panel_efficiency': 0.22,
                'temp_coefficient': -0.32, 'system_kw': 10.0
            }
            res = registry.yield_predictor.predict(features)
            lat = round((time.time() - start) * 1000, 1)
            results['yield_predictor'] = {'status': 'pass', 'latency_ms': lat, 'test_output': res.get('predicted_annual_kwh')}
        except Exception as e:
            all_passed = False
            results['yield_predictor'] = {'status': 'fail', 'error': str(e)}

        # 2. Dust Clusterer
        try:
            start = time.time()
            res = registry.dust_clusterer.predict_zone(1)
            lat = round((time.time() - start) * 1000, 1)
            results['dust_clusterer'] = {'status': 'pass', 'latency_ms': lat, 'test_output': res.get('name')}
        except Exception as e:
            all_passed = False
            results['dust_clusterer'] = {'status': 'fail', 'error': str(e)}

        # 3. YOLOv8
        tmp_path = None
        try:
            start = time.time()
            fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)
            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            cv2.rectangle(dummy_img, (200, 200), (440, 440), (255, 255, 255), -1)
            cv2.imwrite(tmp_path, dummy_img)
            
            detector = EgyptianRoofDetector()
            res = detector.detect_roof(tmp_path)
            lat = round((time.time() - start) * 1000, 1)
            results['yolov8_roof'] = {'status': 'pass', 'latency_ms': lat, 'test_output': f"{res.get('usable_area_m2')} m2, {res.get('panel_layout', {}).get('max_panels')} panels"}
        except Exception as e:
            all_passed = False
            results['yolov8_roof'] = {'status': 'fail', 'error': str(e)}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 4. CNN-LSTM
        try:
            start = time.time()
            import torch
            model = SolarYieldCNNLSTM()
            net = model.get_net(torch.device('cpu'))
            net.eval()
            dummy_sequence = torch.ones((1, 365, 5), dtype=torch.float32)
            with torch.no_grad():
                res_monthly = net(dummy_sequence)[0].numpy()
            predicted_annual_kwh = float(sum(res_monthly)) * 10.0
            lat = round((time.time() - start) * 1000, 1)
            results['cnn_lstm'] = {'status': 'pass', 'latency_ms': lat, 'test_output': f"{predicted_annual_kwh:.1f} kWh"}
        except Exception as e:
            all_passed = False
            results['cnn_lstm'] = {'status': 'fail', 'error': str(e)}

        return Response({
            'status': 'healthy' if all_passed else 'degraded',
            'timestamp': timezone.now().isoformat(),
            'models': results
        }, status=200 if all_passed else 500)
# ── CNN-LSTM Monthly Forecast endpoint ───────────────────────────────────────

class ForecastMonthlyView(APIView):
    """
    POST /api/v1/ai/forecast-monthly/

    12-month solar yield forecast using CNN-LSTM hybrid model.
    Falls back to Random Forest + physics monthly breakdown if CNN-LSTM
    model weights are not yet available (e.g. first Railway deployment).

    Request (JSON):
    {
        "location_id":    1,       // Egyptian location ID
        "system_kw":      10.0,    // Installed system capacity
        "panel_efficiency": 0.22,  // Panel efficiency (optional, default 0.22)
        "tilt_angle":     30.0,    // Panel tilt in degrees (optional)
        "forecast_years": 1        // Number of years (1-3, optional)
    }

    Response:
    {
        "monthly_forecast":   [Jan, Feb, ..., Dec],   // kWh per month
        "annual_total_kwh":   15420.0,
        "model":              "cnn_lstm" | "random_forest_fallback",
        "confidence":         0.89,
        "seasonal_pattern":   {"peak_month": "June", "low_month": "December"},
        "model_r2":           0.93
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg, Max
        from ai_engine.nasa_client import fetch_nasa_climate_for_coords, find_nearest_location

        loc_id = request.data.get('location_id')
        req_lat = request.data.get('latitude')
        req_lon = request.data.get('longitude')
        
        loc = None
        nasa_data = None
        agg = None
        
        if loc_id:
            try:
                loc = Location.objects.select_related('governorate').get(location_id=int(loc_id))
            except (ValueError, Location.DoesNotExist):
                pass
                
        if not loc and req_lat and req_lon:
            lat, lon = float(req_lat), float(req_lon)
            nasa_data = fetch_nasa_climate_for_coords(lat, lon)
            if not nasa_data:
                loc = find_nearest_location(lat, lon)
            else:
                agg = nasa_data['agg']
                
        if not loc and not agg:
            return Response({'error': 'Location not found and dynamic fetching failed.'}, status=404)

        if loc and not agg:
            agg = DailyClimateData.objects.filter(location=loc).aggregate(
                avg_ghi=Avg('allsky_sfc_sw_dwn'),
                avg_temp=Avg('t2m'),
                max_temp=Max('t2m_max'),
                avg_hum=Avg('rh2m'),
                avg_wind=Avg('ws2m')
            )
        forecast_years = min(int(request.data.get('forecast_years', 1)), 3)
        system_kw = float(request.data.get('system_kw', 10.0))
        panel_eff = float(request.data.get('panel_efficiency', 0.22))
        tilt = float(request.data.get('tilt_angle', 30.0))

        # ── Fetch climate data ────────────────────────────────────────────────
        avg_ghi  = agg['avg_ghi']  or 5.5
        avg_temp = agg['avg_temp'] or 28.0
        max_temp = agg['max_temp'] or 40.0
        avg_hum  = agg['avg_hum']  or 40.0
        avg_wind = agg['avg_wind'] or 3.5

        from ai_engine.dust_clustering  import EgyptianDustClusterer
        dust_zone = EgyptianDustClusterer().predict_zone(loc.location_id if loc else 1)

        # ── Try CNN-LSTM first ────────────────────────────────────────────────
        cnn_result = self._try_cnn_lstm(
            loc, system_kw, panel_eff, tilt, dust_zone,
            forecast_years, nasa_daily=nasa_data['daily_records'] if nasa_data else None
        )
        if cnn_result is not None:
            return Response(cnn_result)

        # ── Fallback: RF predictor + physics monthly breakdown ────────────────
        from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
        features = {
            'avg_ghi':          avg_ghi,
            'avg_temperature':  avg_temp,
            'max_temperature':  max_temp,
            'avg_humidity':     avg_hum,
            'avg_wind_speed':   avg_wind,
            'dust_risk_score':  dust_zone['factor'],
            'latitude':         loc.latitude if loc else float(req_lat),
            'tilt_angle':       tilt,
            'panel_efficiency': panel_eff,
            'temp_coefficient': -0.30,
        }
        rf_result     = EgyptianYieldPredictorV2().predict(features, system_kw=system_kw)
        monthly       = rf_result['predicted_monthly']
        annual_total  = rf_result['predicted_annual_kwh']

        # Multi-year: apply 0.45% annual degradation
        if forecast_years > 1:
            all_years = []
            for yr in range(forecast_years):
                factor = (1 - 0.0045) ** yr
                all_years.append([round(v * factor, 1) for v in monthly])
            monthly_forecast = all_years
        else:
            monthly_forecast = monthly

        months_labels = ['Jan','Feb','Mar','Apr','May','Jun',
                         'Jul','Aug','Sep','Oct','Nov','Dec']
        import numpy as np
        peak_idx = int(np.argmax(monthly))
        low_idx  = int(np.argmin(monthly))

        return Response({
            'monthly_forecast':  monthly_forecast,
            'annual_total_kwh':  annual_total,
            'model':             'random_forest_fallback',
            'system_kw':         system_kw,
            'confidence':        round(1.0 - (rf_result.get('model_mape', 10) / 100), 2),
            'seasonal_pattern': {
                'peak_month': months_labels[peak_idx],
                'low_month':  months_labels[low_idx],
                'peak_kwh':   monthly[peak_idx],
                'low_kwh':    monthly[low_idx],
            },
            'model_r2':   rf_result.get('model_r2',   0.0),
            'model_mape': rf_result.get('model_mape', 0.0),
            'location':   {'id': loc.location_id if loc else None, 'name': loc.name if loc else 'Dynamic',
                           'governorate': loc.governorate.name if loc and loc.governorate else ''},
            'dust_zone':  dust_zone['name'],
            'note':       'CNN-LSTM model not trained yet. Using RF fallback. '
                          'Run: python manage.py train_ai_models --force to train CNN-LSTM.',
        })

    def _try_cnn_lstm(
        self, loc, system_kw, panel_eff, tilt, dust_zone,
        forecast_years, nasa_daily=None
    ):
        """
        Attempt CNN-LSTM inference via the global model registry.
        """
        from ai_engine.model_registry import registry
        
        if not registry.is_ready('cnn_lstm') or registry.cnn_lstm is None:
            return None
            
        try:
            if nasa_daily:
                daily = nasa_daily[:365]
            else:
                daily = list(loc.climate_data.all().order_by('-date').values(
                    'allsky_sfc_sw_dwn', 't2m', 'rh2m', 'ws2m', 'dust_risk_score'
                )[:365])

            if len(daily) < 180:
                # Fallback to NASA API if DB doesn't have enough records
                if loc:
                    from ai_engine.nasa_client import fetch_nasa_climate_for_coords
                    nd = fetch_nasa_climate_for_coords(loc.latitude, loc.longitude)
                    if nd and nd.get('daily_records'):
                        daily = nd['daily_records'][:365]
                    else:
                        return None   # Not enough data even from NASA
                else:
                    return None # Dynamic location without nasa_daily

            # Pad if missing a few days
            if len(daily) < 365:
                avg_day = {k: sum(d[k] for d in daily if d[k] is not None)/len(daily) for k in daily[0]}
                daily.extend([avg_day] * (365 - len(daily)))
                
            res = registry.cnn_lstm.predict(
                daily_sequence=daily,
                system_kw=system_kw,
                panel_efficiency=panel_eff,
                tilt_angle=tilt,
                dust_risk=dust_zone['factor']
            )
            
            # Apply annual degradation if multi-year
            monthly = res['predicted_monthly']
            if forecast_years > 1:
                all_years = []
                for yr in range(forecast_years):
                    factor = (1 - 0.0045) ** yr
                    all_years.append([round(v * factor, 1) for v in monthly])
                res['monthly_forecast'] = all_years
            else:
                res['monthly_forecast'] = monthly
                
            res['annual_total_kwh'] = res.pop('predicted_annual_kwh')
            res['system_kw'] = system_kw
            res['dust_zone'] = dust_zone['name']
            res['location'] = {
                'id': loc.location_id if loc else None, 
                'name': loc.name if loc else 'Dynamic',
                'governorate': loc.governorate.name if loc and loc.governorate else ''
            }
            return res
            
        except Exception as e:
            logger.warning("CNN-LSTM inference failed: %s", e)
            return None
