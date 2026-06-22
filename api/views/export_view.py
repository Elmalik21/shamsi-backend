"""
api/views/export_view.py
=========================
Django REST Framework endpoints for professional design exports.

Endpoints
---------
  GET  /api/v1/export/{project_id}/pvsyst/      → ZIP of .SIT/.MET/.PAN/.OND
  GET  /api/v1/export/{project_id}/helioscope/  → JSON file
  GET  /api/v1/export/{project_id}/pdf/         → PDF report
  GET  /api/v1/export/{project_id}/excel/       → XLSX workbook
  GET  /api/v1/export/{project_id}/csv/         → CSV (monthly production)
  GET  /api/v1/export/{project_id}/all/         → ZIP of every format

All endpoints accept the optional query parameters:
  ?panel_power_w=580     Override panel wattage
  ?tilt_angle=20         Override tilt angle
  ?azimuth=180           Override azimuth

Error responses
---------------
  404  Project not found
  400  Missing required project data
  500  Export generation error

Demo mode (no DB)
-----------------
  GET /api/v1/export/demo/pdf/     — generates a synthetic demo report
  GET /api/v1/export/demo/pvsyst/ — generates synthetic PVsyst files
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)

EXPORT_SUBDIR = 'exports'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _export_dir(project_id: str) -> str:
    """Return (and create) the export directory for a project."""
    base = os.path.join(getattr(settings, 'MEDIA_ROOT', 'media'),
                        EXPORT_SUBDIR, project_id)
    os.makedirs(base, exist_ok=True)
    return base


def _file_response(path: str, content_type: str,
                   filename: str) -> FileResponse:
    """Return a FileResponse that triggers browser download."""
    fh = open(path, 'rb')
    response = FileResponse(fh, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


class SolarPanelWrapper:
    def __init__(self, panel):
        self._panel = panel

    def __getattr__(self, name):
        return getattr(self._panel, name, None)

    def get(self, name, default=None):
        return getattr(self, name, default)

    @property
    def manufacturer(self):
        return getattr(self._panel, 'brand', 'JA Solar') or 'JA Solar'

    @property
    def model(self):
        return getattr(self._panel, 'model', 'JAM72D40-580') or 'JAM72D40-580'

    @property
    def power_rating_w(self):
        val = getattr(self._panel, 'capacity_w', None)
        return float(val) if val is not None else 580.0

    @property
    def efficiency_percent(self):
        val = getattr(self._panel, 'efficiency_pct', None)
        return float(val) if val is not None else 22.5

    @property
    def temp_coeff_pmax_percent(self):
        val = getattr(self._panel, 'temp_coefficient_pct', None)
        return float(val) if val is not None else -0.350

    @property
    def noct_celsius(self):
        val = getattr(self._panel, 'noct_celsius', None)
        return float(val) if val is not None else 45.0

    @property
    def technology(self):
        return getattr(self._panel, 'panel_type', 'mono-Si') or 'mono-Si'

    @property
    def vmp_v(self):
        w = self.power_rating_w
        if w >= 600: return 45.0
        elif w >= 500: return 42.0
        elif w >= 400: return 38.0
        return 34.0

    @property
    def imp_a(self):
        return round(self.power_rating_w / self.vmp_v, 2)

    @property
    def voc_v(self):
        return round(self.vmp_v * 1.2, 2)

    @property
    def isc_a(self):
        return round(self.imp_a * 1.05, 2)

    @property
    def temp_coeff_voc_percent(self):
        return round(self.temp_coeff_pmax_percent * 0.77, 3)

    @property
    def temp_coeff_isc_percent(self):
        return 0.045

    @property
    def length_mm(self):
        w = self.power_rating_w
        if w >= 600: return 2300
        elif w >= 500: return 2200
        elif w >= 400: return 2000
        return 1700

    @property
    def width_mm(self):
        w = self.power_rating_w
        if w >= 600: return 1200
        elif w >= 500: return 1134
        elif w >= 400: return 1000
        return 1000

    @property
    def thickness_mm(self):
        return 30

    @property
    def weight_kg(self):
        w = self.power_rating_w
        if w >= 600: return 32.0
        elif w >= 500: return 28.5
        elif w >= 400: return 22.0
        return 19.0

    @property
    def area_m2(self):
        return (self.length_mm * self.width_mm) / 1e6

    def __str__(self):
        return f"{self.manufacturer} {self.model}"


class InverterWrapper:
    def __init__(self, inverter):
        self._inverter = inverter

    def __getattr__(self, name):
        return getattr(self._inverter, name, None)

    def get(self, name, default=None):
        return getattr(self, name, default)

    @property
    def manufacturer(self):
        return getattr(self._inverter, 'brand', 'Huawei') or 'Huawei'

    @property
    def model(self):
        return getattr(self._inverter, 'model', 'SUN2000-10KTL-M1') or 'SUN2000-10KTL-M1'

    @property
    def inverter_type(self):
        return getattr(self._inverter, 'inverter_type', 'ON_GRID') or 'ON_GRID'

    @property
    def power_rating_w(self):
        val = getattr(self._inverter, 'capacity_kw', None)
        return float(val * 1000.0) if val is not None else 10000.0

    @property
    def output_voltage_v(self):
        return 230.0

    @property
    def max_ac_power_w(self):
        return self.power_rating_w * 1.1

    @property
    def max_efficiency_percent(self):
        val = getattr(self._inverter, 'efficiency_pct', None)
        return float(val) if val is not None else 98.4

    @property
    def euro_efficiency_percent(self):
        return self.max_efficiency_percent * 0.995

    @property
    def max_dc_voltage_v(self):
        val = getattr(self._inverter, 'max_dc_voltage_v', None)
        return float(val) if val is not None else 1000.0

    @property
    def min_dc_voltage_v(self):
        val = getattr(self._inverter, 'mppt_min_v', None)
        return float(val) if val is not None else 200.0

    @property
    def mppt_voltage_min_v(self):
        return self.min_dc_voltage_v

    @property
    def mppt_voltage_max_v(self):
        val = getattr(self._inverter, 'mppt_max_v', None)
        return float(val) if val is not None else 950.0

    @property
    def max_dc_current_a(self):
        val = getattr(self._inverter, 'max_dc_current_a', None)
        return float(val) if val is not None else 25.0

    @property
    def number_of_inputs(self):
        val = getattr(self._inverter, 'max_strings', None)
        return int(val) if val is not None else 2

    @property
    def number_of_mppts(self):
        val = getattr(self._inverter, 'mppt_channels', None)
        return int(val) if val is not None else 2

    @property
    def weight_kg(self):
        kw = self.power_rating_w / 1000.0
        if kw >= 100: return 75.0
        elif kw >= 50: return 43.0
        elif kw >= 20: return 25.0
        return 12.0

    @property
    def dimensions_mm(self):
        return '525x470x182 mm'

    def __str__(self):
        return f"{self.manufacturer} {self.model}"


class MockPanel:
    brand = 'JA Solar'
    model = 'JAM72D40-580'
    panel_type = 'mono-Si'
    capacity_w = 580.0
    efficiency_pct = 22.5
    temp_coefficient_pct = -0.350
    vmp_v = 41.88
    imp_a = 13.86
    voc_v = 50.26
    isc_a = 14.50
    length_mm = 2278
    width_mm = 1134
    thickness_mm = 30
    weight_kg = 28.5


class MockInverter:
    brand = 'Huawei'
    model = 'SUN2000-10KTL-M1'
    inverter_type = 'ON_GRID'
    capacity_kw = 10.0
    efficiency_pct = 98.4
    max_dc_voltage_v = 1100.0
    mppt_min_v = 200.0
    mppt_max_v = 950.0
    max_dc_current_a = 22.0
    max_strings = 2
    mppt_channels = 2



def _load_project(project_id: str, request: Request) -> dict | None:
    """
    Attempt to load a DesignProject from the database and assemble the
    project_data dict expected by the exporters.

    Falls back to synthetic data when:
      - project_id == 'demo'
      - The Django models are not yet migrated (ImportError / no table)
      - The project does not exist

    Returns None only on genuine database errors.
    """
    if project_id == 'demo':
        return _synthetic_project(request)

    # 1. Isolate the main project/climate query.
    # Fallback to synthetic ONLY if models are not migrated or project doesn't exist.
    try:
        from solar_data.models import DesignProject, DailyClimateData, SolarPanel, Inverter  # noqa: PLC0415
        project = DesignProject.objects.select_related('location').get(pk=project_id)
        climate = DailyClimateData.objects.filter(location=project.location).order_by('date')
    except (ImportError, DesignProject.DoesNotExist) as exc:
        logger.warning("Cannot load project %s from DB (%s) — using synthetic data.", project_id, exc)
        return _synthetic_project(request)
    except Exception as exc:
        logger.exception("Database error loading project %s", project_id)
        return None

    # From here on, we do NOT fall back to synthetic data.
    # We load project details and recover gracefully from missing data/equipment.
    pareto = project.pareto_solutions or []
    selected = project.selected_design or (pareto[0] if pareto else {})

    opt = {
        'pareto_solutions': pareto,
        'selected_design': selected,
        'run_id': project.optimization_run_id,
    }

    # Load panel and inverter equipments from DB if IDs are present in the selected solution
    panel = None
    inverter = None
    
    # Standardize query param fetching to support both DRF Request and standard Django HttpRequest
    qparams = getattr(request, 'query_params', getattr(request, 'GET', {}))

    # Helper to safely lookup SolarPanel
    panel_id = selected.get('panel_id')
    panel_brand = selected.get('panel_brand')
    panel_model = selected.get('panel_model')
    
    if panel_id:
        # A) Try by primary key if it is numeric
        if isinstance(panel_id, int) or (isinstance(panel_id, str) and panel_id.isdigit()):
            try:
                panel = SolarPanel.objects.filter(pk=int(panel_id)).first()
            except Exception as e:
                logger.warning("Failed to query SolarPanel by pk=%s: %s", panel_id, e)
        
        # B) Try by brand and model
        if not panel and panel_brand and panel_model:
            try:
                panel = SolarPanel.objects.filter(
                    brand__iexact=panel_brand,
                    model__iexact=panel_model
                ).first()
            except Exception as e:
                logger.warning("Failed to query SolarPanel by brand/model (%s/%s): %s", panel_brand, panel_model, e)
                
        # C) Try by matching slug
        if not panel and isinstance(panel_id, str):
            try:
                for p in SolarPanel.objects.all():
                    slug = f"{p.brand}-{p.model}".lower().replace(' ', '-')
                    if slug == panel_id:
                        panel = p
                        break
            except Exception as e:
                logger.warning("Failed to query SolarPanel by slug %s: %s", panel_id, e)

    # D) Fallback 1: Query first available panel in DB if still not resolved
    if not panel:
        try:
            panel = SolarPanel.objects.first()
        except Exception as e:
            logger.warning("Failed to fallback to first SolarPanel in DB: %s", e)

    # E) Fallback 2: If DB is empty, use mock panel
    if not panel:
        panel = MockPanel()

    panel = SolarPanelWrapper(panel)

    # Helper to safely lookup Inverter
    inverter_id = selected.get('inverter_id')
    inverter_brand = selected.get('inverter_brand')
    inverter_model = selected.get('inverter_model')
    
    if inverter_id:
        # A) Try by primary key if it is numeric
        if isinstance(inverter_id, int) or (isinstance(inverter_id, str) and inverter_id.isdigit()):
            try:
                inverter = Inverter.objects.filter(pk=int(inverter_id)).first()
            except Exception as e:
                logger.warning("Failed to query Inverter by pk=%s: %s", inverter_id, e)
        
        # B) Try by brand and model
        if not inverter and inverter_brand and inverter_model:
            try:
                inverter = Inverter.objects.filter(
                    brand__iexact=inverter_brand,
                    model__iexact=inverter_model
                ).first()
            except Exception as e:
                logger.warning("Failed to query Inverter by brand/model (%s/%s): %s", inverter_brand, inverter_model, e)
                
        # C) Try by matching slug
        if not inverter and isinstance(inverter_id, str):
            try:
                for inv in Inverter.objects.all():
                    slug = f"{inv.brand}-{inv.model}".lower().replace(' ', '-')
                    if slug == inverter_id:
                        inverter = inv
                        break
            except Exception as e:
                logger.warning("Failed to query Inverter by slug %s: %s", inverter_id, e)

    # D) Fallback 1: Query first available inverter in DB if still not resolved
    if not inverter:
        try:
            inverter = Inverter.objects.first()
        except Exception as e:
            logger.warning("Failed to fallback to first Inverter in DB: %s", e)

    # E) Fallback 2: If DB is empty, use mock inverter
    if not inverter:
        inverter = MockInverter()

    inverter = InverterWrapper(inverter)

    # Build company dict from query params
    company = {
        'name'           : qparams.get('company_name', ''),
        'address'        : qparams.get('company_address', ''),
        'phone'          : qparams.get('company_phone', ''),
        'email'          : qparams.get('company_email', ''),
        'egypteraLicense': qparams.get('company_egyptera', ''),
    }

    # Safe float parsing helper
    def _get_float_param(key, default_val):
        val = qparams.get(key)
        if val is not None and val != '':
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
        try:
            return float(default_val)
        except (ValueError, TypeError):
            return 20.0

    panel_count = selected.get('panel_count')
    if not panel_count:
        panel_count = 30

    tilt_angle = _get_float_param('tilt_angle', selected.get('tilt_angle', getattr(project, 'tilt_angle', 20)))
    azimuth = _get_float_param('azimuth', selected.get('azimuth', getattr(project, 'azimuth', 180)))

    res_dict = {
        'project_id'          : str(project.pk),
        'location'            : project.location,
        'panel'               : panel,
        'inverter'            : inverter,
        'system_config'       : {
            'panel_count'       : panel_count,
            'tilt_angle'        : tilt_angle,
            'azimuth'           : azimuth,
            'strings'           : selected.get('string_count', getattr(project, 'string_count', 3)) or 3,
            'panels_per_string' : selected.get('panels_per_string', getattr(project, 'panels_per_string', 10)) or 10,
            'inverter_count'    : selected.get('inverter_count', getattr(project, 'inverter_count', 1)) or 1,
        },
        'climate_data'        : climate,
        'dust_loss_pct'       : float(getattr(project, 'dust_loss_pct', 5.0)),
        'shading_loss_pct'    : float(getattr(project, 'shading_loss_pct', 3.0)),
        'optimization_results': opt,
        # Also expose pareto solutions at top-level for the PDF engine
        'pareto_solutions'    : pareto,
        'roof_image_path'     : getattr(project, 'annotated_roof_image_path', None),
        'company'             : company,
    }
    from ai_engine.export.calc_engine import normalize_and_validate_project
    return normalize_and_validate_project(res_dict)


def _synthetic_project(request: Request) -> dict:
    """Return a synthetic demo project (no DB required)."""
    from ai_engine.export.pvsyst_exporter import make_synthetic_project
    project = make_synthetic_project('Cairo')
    # Allow query param overrides
    qparams = getattr(request, 'query_params', getattr(request, 'GET', {}))
    panel_w = int(qparams.get('panel_power_w', 580))
    tilt    = float(qparams.get('tilt_angle', 20))
    az      = float(qparams.get('azimuth', 180))
    project['panel'].power_rating_w         = panel_w
    project['system_config']['tilt_angle']  = tilt
    project['system_config']['azimuth']     = az
    
    from ai_engine.export.calc_engine import normalize_and_validate_project
    return normalize_and_validate_project(project)


# ─────────────────────────────────────────────────────────────────────────────
# PVsyst export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def export_pvsyst(request: Request, project_id: str) -> Response:
    """
    GET /api/v1/export/{project_id}/pvsyst/

    Returns a ZIP archive containing:
      <location>.SIT  — site definition
      <location>.MET  — meteo data (NASA SSE format)
      <panel>.PAN     — panel specs
      <inverter>.OND  — inverter specs
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    try:
        from ai_engine.export.pvsyst_exporter import PVsystExporter

        out_dir  = _export_dir(project_id)
        exporter = PVsystExporter(project)
        files    = exporter.export_all(out_dir)

        # Pack into ZIP in memory
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for label, path in files.items():
                zf.write(path, arcname=os.path.basename(path))
        zip_buf.seek(0)

        loc_safe = project['location'].name.replace(' ', '_')
        response = HttpResponse(zip_buf.read(), content_type='application/zip')
        response['Content-Disposition'] = (
            f'attachment; filename="Shamsi_{loc_safe}_PVsyst.zip"'
        )
        logger.info("PVsyst export for project %s: %d files",
                    project_id, len(files))
        return response

    except Exception as exc:
        logger.exception("PVsyst export failed for project %s", project_id)
        return Response({'error': str(exc)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# HelioScope export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def export_helioscope(request: Request, project_id: str) -> Response:
    """
    GET /api/v1/export/{project_id}/helioscope/

    Returns HelioScope API v1 JSON project file.
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    try:
        from ai_engine.export.helioscope_exporter import HelioScopeExporter

        exporter = HelioScopeExporter(project)

        # Option A: return as inline JSON (for API consumption)
        if request.query_params.get('format') == 'json':
            return Response(exporter.to_dict())

        # Option B: return as downloadable .json file
        out_dir  = _export_dir(project_id)
        loc_safe = project['location'].name.replace(' ', '_')
        out_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_HelioScope.json')
        exporter.export_project(out_path)

        response = HttpResponse(
            open(out_path, 'rb').read(),
            content_type='application/json',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Shamsi_{loc_safe}_HelioScope.json"'
        )
        return response

    except Exception as exc:
        logger.exception("HelioScope export failed for project %s", project_id)
        return Response({'error': str(exc)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# PDF export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def export_pdf(request: Request, project_id: str) -> Response:
    """
    GET or POST /api/v1/export/{project_id}/pdf/

    On POST: accepts JSON body with:
      ai_result  — the full AI result object from the frontend (pareto_solutions, etc.)
      form       — form params (tilt_angle, azimuth, ...)
      company_*  — company branding fields
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    # ── Merge live POST payload (always wins over DB data) ─────────────────
    if request.method == 'POST' and request.data:
        body = request.data

        # Company info from POST body
        company_override = {}
        for key in ('company_name', 'company_address', 'company_phone',
                    'company_email', 'company_egyptera'):
            val = body.get(key, '')
            if val:
                short = key.replace('company_', '')
                company_override[short if short != 'egyptera' else 'egypteraLicense'] = val
        if company_override:
            project['company'] = {**project.get('company', {}), **company_override}

        # Live AI result from frontend overrides everything
        ai_result = body.get('ai_result')
        if ai_result and isinstance(ai_result, dict):
            # Merge pareto_solutions at top level for _extract_results()
            pareto = (ai_result.get('pareto_solutions') or [])
            project['pareto_solutions']     = pareto
            project['optimization_results'] = ai_result
            logger.info("PDF export project %s: using live ai_result from POST "
                        "(%d pareto solutions)", project_id, len(pareto))

            if pareto:
                sol = pareto[0]
                # Override panel if sol has it
                if sol.get('panel_name'):
                    if hasattr(project.get('panel'), 'model'):
                        project['panel'].model = sol['panel_name']
                        project['panel'].manufacturer = ''
                    if hasattr(project.get('panel'), 'power_rating_w'):
                        project['panel'].power_rating_w = sol.get('panel_power_w', 580)
                
                # Override inverter if sol has it
                if sol.get('inverter_name'):
                    if hasattr(project.get('inverter'), 'model'):
                        project['inverter'].model = sol['inverter_name']
                        project['inverter'].manufacturer = ''
                    if hasattr(project.get('inverter'), 'power_rating_w'):
                        project['inverter'].power_rating_w = sol.get('inverter_power_w', 10000)

        # Form overrides for system_config and location
        form_data = body.get('form', {})
        if form_data:
            cfg = project.get('system_config', {})
            if form_data.get('tilt_angle'):
                cfg['tilt_angle'] = float(form_data['tilt_angle'])
            if form_data.get('azimuth'):
                cfg['azimuth'] = float(form_data['azimuth'])
            project['system_config'] = cfg

            loc_name = form_data.get('location_name')
            if loc_name:
                loc = project.get('location')
                if isinstance(loc, dict):
                    loc['name'] = loc_name
                elif hasattr(loc, 'name'):
                    loc.name = loc_name

        # Re-run engineering validation on updated project dict
        from ai_engine.export.calc_engine import normalize_and_validate_project
        project = normalize_and_validate_project(project)

    try:
        from ai_engine.export.pdf_report import ProfessionalPDFReport

        out_dir  = _export_dir(project_id)
        loc      = project.get('location')
        loc_name = getattr(loc, 'name', None) or (loc.get('name') if isinstance(loc, dict) else None) or 'Report'
        loc_safe = loc_name.replace(' ', '_')
        out_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_Report.pdf')

        report = ProfessionalPDFReport(project)
        report.generate_report(out_path)

        with open(out_path, 'rb') as f:
            pdf_bytes = f.read()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="Shamsi_{loc_safe}_Report.pdf"'
        )
        logger.info("PDF export for project %s: %s", project_id, out_path)
        return response

    except ImportError as exc:
        return Response(
            {'error': 'PDF generation requires reportlab.',
             'detail': str(exc),
             'install': 'pip install reportlab matplotlib'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        logger.exception("PDF export failed for project %s", project_id)
        return Response({
            'error': str(exc),
            'traceback': tb
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# Excel export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def export_excel(request: Request, project_id: str) -> Response:
    """
    GET /api/v1/export/{project_id}/excel/

    Returns a formatted .xlsx workbook.
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    try:
        from ai_engine.export.excel_exporter import ExcelExporter

        out_dir  = _export_dir(project_id)
        loc_safe = project['location'].name.replace(' ', '_')
        out_path = os.path.join(out_dir, f'Shamsi_{loc_safe}.xlsx')

        ExcelExporter(project).export_workbook(out_path)

        response = HttpResponse(
            open(out_path, 'rb').read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Shamsi_{loc_safe}.xlsx"'
        )
        return response

    except ImportError as exc:
        return Response(
            {'error': 'Excel export requires openpyxl.',
             'detail': str(exc),
             'install': 'pip install openpyxl'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:
        logger.exception("Excel export failed for project %s", project_id)
        return Response({'error': str(exc)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# CSV export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def export_csv(request: Request, project_id: str) -> Response:
    """
    GET /api/v1/export/{project_id}/csv/

    Returns monthly production data as CSV (lightweight, no dependencies).
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    try:
        from ai_engine.export.excel_exporter import ExcelExporter

        out_dir  = _export_dir(project_id)
        loc_safe = project['location'].name.replace(' ', '_')
        out_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_production.csv')

        ExcelExporter(project).export_csv(out_path)

        response = HttpResponse(
            open(out_path, 'rb').read(),
            content_type='text/csv',
        )
        response['Content-Disposition'] = (
            f'attachment; filename="Shamsi_{loc_safe}_production.csv"'
        )
        return response

    except Exception as exc:
        logger.exception("CSV export failed for project %s", project_id)
        return Response({'error': str(exc)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────────────────
# All-in-one export
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def export_all(request: Request, project_id: str) -> Response:
    """
    GET /api/v1/export/{project_id}/all/

    Generate every export format and return a single ZIP archive.
    Skips formats whose dependencies are not installed.
    """
    project = _load_project(project_id, request)
    if project is None:
        return Response({'error': 'Project not found.'},
                        status=status.HTTP_404_NOT_FOUND)

    out_dir  = _export_dir(project_id)
    loc_safe = project['location'].name.replace(' ', '_')
    generated: list[str] = []
    skipped:   list[str] = []

    # PVsyst
    try:
        from ai_engine.export.pvsyst_exporter import PVsystExporter
        files = PVsystExporter(project).export_all(out_dir)
        generated.extend(files.values())
    except Exception as exc:
        skipped.append(f"PVsyst: {exc}")

    # HelioScope
    try:
        from ai_engine.export.helioscope_exporter import HelioScopeExporter
        hs_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_HelioScope.json')
        HelioScopeExporter(project).export_project(hs_path)
        generated.append(hs_path)
    except Exception as exc:
        skipped.append(f"HelioScope: {exc}")

    # PDF
    try:
        from ai_engine.export.pdf_report import ProfessionalPDFReport
        pdf_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_Report.pdf')
        ProfessionalPDFReport(project).generate_report(pdf_path)
        generated.append(pdf_path)
    except Exception as exc:
        skipped.append(f"PDF: {exc}")

    # Excel
    try:
        from ai_engine.export.excel_exporter import ExcelExporter
        xlsx_path = os.path.join(out_dir, f'Shamsi_{loc_safe}.xlsx')
        ExcelExporter(project).export_workbook(xlsx_path)
        generated.append(xlsx_path)
    except Exception as exc:
        skipped.append(f"Excel: {exc}")

    # CSV (always works)
    try:
        from ai_engine.export.excel_exporter import ExcelExporter
        csv_path = os.path.join(out_dir, f'Shamsi_{loc_safe}_production.csv')
        ExcelExporter(project).export_csv(csv_path)
        generated.append(csv_path)
    except Exception as exc:
        skipped.append(f"CSV: {exc}")

    if not generated:
        return Response(
            {'error': 'No files generated.', 'details': skipped},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Pack into ZIP
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in generated:
            if os.path.exists(path):
                zf.write(path, arcname=os.path.basename(path))
        if skipped:
            zf.writestr('SKIPPED.txt', '\n'.join(skipped))
    zip_buf.seek(0)

    response = HttpResponse(zip_buf.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="Shamsi_{loc_safe}_AllExports.zip"'
    )
    logger.info("All-formats export for %s: %d files, %d skipped",
                project_id, len(generated), len(skipped))
    return response
