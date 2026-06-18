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

    try:
        from solar_data.models import DesignProject, DailyClimateData  # noqa: PLC0415

        project = DesignProject.objects.select_related(
            'location', 'panel', 'inverter'
        ).get(pk=project_id)

        climate = DailyClimateData.objects.filter(
            location=project.location
        ).order_by('date')

        opt = project.optimization_results or {}

        panel = project.panel
        inverter = project.inverter

        if not panel and opt.get('pareto_solutions'):
            sol = opt['pareto_solutions'][0]
            if sol.get('panel_id'):
                from solar_data.models import Equipment
                panel = Equipment.objects.filter(pk=sol['panel_id']).first()

        if not inverter and opt.get('pareto_solutions'):
            sol = opt['pareto_solutions'][0]
            if sol.get('inverter_id'):
                from solar_data.models import Equipment
                inverter = Equipment.objects.filter(pk=sol['inverter_id']).first()

        panel_count = getattr(project, 'panel_count', None)
        if not panel_count and opt.get('pareto_solutions'):
            panel_count = opt['pareto_solutions'][0].get('panel_count')
        if not panel_count:
            panel_count = 30

        # Build company dict from query params
        company = {
            'name'           : request.query_params.get('company_name', ''),
            'address'        : request.query_params.get('company_address', ''),
            'phone'          : request.query_params.get('company_phone', ''),
            'email'          : request.query_params.get('company_email', ''),
            'egypteraLicense': request.query_params.get('company_egyptera', ''),
        }

        return {
            'project_id'          : str(project.pk),
            'location'            : project.location,
            'panel'               : panel,
            'inverter'            : inverter,
            'system_config'       : {
                'panel_count'       : panel_count,
                'tilt_angle'        : float(request.query_params.get(
                                          'tilt_angle',
                                          getattr(project, 'tilt_angle', 20))),
                'azimuth'           : float(request.query_params.get(
                                          'azimuth',
                                          getattr(project, 'azimuth', 180))),
                'strings'           : getattr(project, 'string_count', 3),
                'panels_per_string' : getattr(project, 'panels_per_string', 10),
                'inverter_count'    : getattr(project, 'inverter_count', 1),
            },
            'climate_data'        : climate,
            'dust_loss_pct'       : float(getattr(project, 'dust_loss_pct', 5.0)),
            'shading_loss_pct'    : float(getattr(project, 'shading_loss_pct', 3.0)),
            'optimization_results': opt,
            # Also expose pareto solutions at top-level for the PDF engine
            'pareto_solutions'    : opt.get('pareto_solutions', []),
            'roof_image_path'     : getattr(project, 'annotated_roof_image_path', None),
            'company'             : company,
        }

    except Exception as exc:                        # noqa: BLE001
        logger.warning("Cannot load project %s from DB (%s) — using synthetic data.",
                       project_id, exc)
        return _synthetic_project(request)


def _synthetic_project(request: Request) -> dict:
    """Return a synthetic demo project (no DB required)."""
    from ai_engine.export.pvsyst_exporter import make_synthetic_project
    project = make_synthetic_project('Cairo')
    # Allow query param overrides
    panel_w = int(request.query_params.get('panel_power_w', 580))
    tilt    = float(request.query_params.get('tilt_angle', 20))
    az      = float(request.query_params.get('azimuth', 180))
    project['panel'].power_rating_w         = panel_w
    project['system_config']['tilt_angle']  = tilt
    project['system_config']['azimuth']     = az
    return project


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
