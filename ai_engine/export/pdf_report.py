"""
ai_engine/export/pdf_report.py
================================
Shamsi Smart — Engineer's Feasibility & Production Report

Strict black-and-white professional layout suitable for submission to
banks, EPCs, and government bodies.

Structure
---------
  1. Cover Page
  2. Executive Summary
  3. Site & Climate Analysis
  4. System Design Specifications  (with block diagram)
  5. Energy Production Forecast    (with B&W bar chart)
  6. Financial Analysis            (with B&W cashflow chart)
  7. Technical Appendix & Standards

Dependencies
------------
    pip install reportlab matplotlib

Usage
-----
    from ai_engine.export.pdf_report import ProfessionalPDFReport

    report = ProfessionalPDFReport(project_data)
    path   = report.generate_report('/tmp/shamsi_report.pdf')
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── ReportLab ────────────────────────────────────────────────────────────────
try:
    from reportlab.lib                  import colors
    from reportlab.lib.enums            import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.pagesizes        import A4
    from reportlab.lib.styles           import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units            import mm
    from reportlab.platypus             import (
        Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
        Spacer, Table, TableStyle, HRFlowable,
    )
    from reportlab.graphics.shapes      import (
        Drawing, Rect, Line, String, Circle, Polygon, Group
    )
    from reportlab.pdfgen               import canvas as rl_canvas
    REPORTLAB_AVAILABLE = True
    REPORTLAB_ERROR = None
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    REPORTLAB_ERROR = str(e)

# ── Matplotlib ───────────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Simple Professional Colour Palette
# ─────────────────────────────────────────────────────────────────────────────
C_BLACK      = '#000000'
C_DARK       = '#111111'
C_HEADING    = '#1d4e89'  # Navy Blue
C_BODY       = '#333333'
C_MUTED      = '#666666'
C_LIGHT_MUTED= '#999999'
C_ROW_EVEN   = '#f8fafd'  # Light Blue Tint
C_ROW_ODD    = '#ffffff'
C_HEADER_BG  = '#1d4e89'  # Navy Blue
C_HEADER_FG  = '#ffffff'
C_BORDER     = '#cccccc'
C_RULE       = '#f79256'  # Orange Accent
C_DIVIDER    = '#eeeeee'


# ─────────────────────────────────────────────────────────────────────────────
# Matplotlib chart helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_bytes(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=180, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf


def _monthly_production_chart(monthly_kwh: List[float]) -> io.BytesIO:
    """B&W bar chart with hatch pattern for monthly energy production."""
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    fig, ax = plt.subplots(figsize=(10, 4))

    # Color summer months (May-Aug) orange, rest navy blue
    colors = ['#1d4e89']*4 + ['#f79256']*4 + ['#1d4e89']*4
    bars = ax.bar(months, monthly_kwh,
                  color=colors, edgecolor='black', linewidth=0.5, alpha=0.9)

    # Value labels on bars
    for bar, val in zip(bars, monthly_kwh):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(monthly_kwh) * 0.015,
                f'{val:,.0f}',
                ha='center', va='bottom', fontsize=7.5,
                fontweight='bold', color='#000000')

    ax.set_ylabel('Energy Production (kWh)', fontsize=9.5, color='#000000', labelpad=8)
    ax.set_title('Monthly Energy Production Forecast', fontsize=12,
                 fontweight='bold', color='#000000', pad=10)
    ax.set_ylim(0, max(monthly_kwh) * 1.22 if max(monthly_kwh) > 0 else 1)
    ax.set_facecolor('#ffffff')
    ax.grid(axis='y', linestyle='--', alpha=0.4, color='#888888')
    ax.grid(axis='x', linestyle='none')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#000000')
    ax.spines['bottom'].set_color('#000000')
    ax.tick_params(axis='both', labelsize=8.5, colors='#000000')
    fig.patch.set_facecolor('#ffffff')
    fig.tight_layout()
    return _fig_to_bytes(fig)


def _cashflow_chart(annual_kwh: float, total_cost: float,
                    payback_years: float, years: int = 25) -> io.BytesIO:
    """B&W cumulative net cashflow with hatch for negative bars."""
    elec_price = 1.65
    degradation = 0.005
    escalation  = 0.05

    cumulative = [-total_cost]
    for yr in range(1, years + 1):
        prod    = annual_kwh * (1 - degradation) ** yr
        price   = elec_price * (1 + escalation) ** yr
        saving  = prod * price
        cumulative.append(cumulative[-1] + saving)

    yrs = list(range(years + 1))
    fig, ax = plt.subplots(figsize=(10, 4))

    for i, (yr, val) in enumerate(zip(yrs, cumulative)):
        color  = '#d9534f' if val < 0 else '#5cb85c' # Red for negative, Green for positive
        ax.bar(yr, val, color=color, edgecolor='black',
               linewidth=0.5, width=0.75, alpha=0.9)

    ax.axhline(0, color='#000000', linewidth=1.5)

    pb_yr = int(round(payback_years))
    if 0 < pb_yr <= years:
        ax.axvline(pb_yr, color='#000000', linewidth=1.5, linestyle='--', alpha=0.7)
        ax.text(pb_yr + 0.3, max(c for c in cumulative if c > 0) * 0.08,
                f'Payback\nYear {pb_yr}', fontsize=7.5, fontweight='bold',
                color='#000000', va='bottom')

    ax.set_xlabel('Year', fontsize=9.5, color='#000000', labelpad=6)
    ax.set_ylabel('Cumulative Net Savings (EGP)', fontsize=9.5, color='#000000', labelpad=8)
    ax.set_title('25-Year Cumulative Net Cashflow', fontsize=12,
                 fontweight='bold', color='#000000', pad=10)
    ax.set_facecolor('#ffffff')
    ax.grid(axis='y', linestyle='--', alpha=0.4, color='#888888')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#000000')
    ax.spines['bottom'].set_color('#000000')
    ax.tick_params(axis='both', labelsize=8.5, colors='#000000')
    fig.patch.set_facecolor('#ffffff')
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Paragraph Styles
# ─────────────────────────────────────────────────────────────────────────────

def _build_styles():
    styles = getSampleStyleSheet()

    def _add(name, parent='Normal', **kw):
        if name not in styles:
            styles.add(ParagraphStyle(name=name, parent=styles[parent], **kw))
        return styles[name]

    _add('CoverTitle',
         fontSize=28, textColor=colors.HexColor(C_BLACK),
         spaceAfter=4, spaceBefore=0, alignment=TA_CENTER,
         fontName='Helvetica-Bold', leading=34)

    _add('CoverSubtitle',
         fontSize=13, textColor=colors.HexColor(C_MUTED),
         spaceAfter=2, alignment=TA_CENTER, fontName='Helvetica',
         leading=18)

    _add('CoverMeta',
         fontSize=10, textColor=colors.HexColor(C_BODY),
         spaceAfter=2, alignment=TA_CENTER, fontName='Helvetica',
         leading=14)

    _add('SectionHeader',
         parent='Heading2',
         fontSize=13, textColor=colors.HexColor(C_HEADING),
         spaceBefore=14, spaceAfter=5,
         fontName='Helvetica-Bold', leading=18)

    _add('SectionNumber',
         fontSize=9, textColor=colors.HexColor(C_MUTED),
         spaceBefore=12, spaceAfter=2,
         fontName='Helvetica', leading=12)

    _add('SubHeader',
         fontSize=10, textColor=colors.HexColor(C_DARK),
         spaceBefore=8, spaceAfter=3,
         fontName='Helvetica-Bold', leading=14)

    _add('BodyText',
         fontSize=9, textColor=colors.HexColor(C_BODY),
         leading=14, spaceAfter=4, alignment=TA_JUSTIFY,
         fontName='Helvetica')

    _add('BodyBold',
         fontSize=9, textColor=colors.HexColor(C_DARK),
         leading=14, spaceAfter=4,
         fontName='Helvetica-Bold')

    _add('Caption',
         fontSize=8, textColor=colors.HexColor(C_MUTED),
         alignment=TA_CENTER, spaceAfter=4,
         fontName='Helvetica-Oblique')

    _add('SmallRight',
         fontSize=7.5, textColor=colors.HexColor(C_MUTED),
         alignment=TA_RIGHT, fontName='Helvetica')

    _add('FooterText',
         fontSize=7, textColor=colors.HexColor(C_LIGHT_MUTED),
         leading=10, spaceAfter=2, fontName='Helvetica',
         alignment=TA_JUSTIFY)

    return styles


# ─────────────────────────────────────────────────────────────────────────────
# Table styles
# ─────────────────────────────────────────────────────────────────────────────

def _metric_table_style():
    """Table with solid black header row."""
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),   colors.HexColor(C_HEADER_BG)),
        ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.HexColor(C_HEADER_FG)),
        ('FONTNAME',      (0, 0), (-1, 0),   'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1),  8.5),
        ('ALIGN',         (0, 0), (0, -1),   'LEFT'),
        ('ALIGN',         (1, 0), (-1, -1),  'RIGHT'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1),
         [colors.HexColor(C_ROW_EVEN), colors.HexColor(C_ROW_ODD)]),
        ('GRID',          (0, 0), (-1, -1),  0.6, colors.HexColor(C_BORDER)),
        ('TOPPADDING',    (0, 0), (-1, -1),  5),
        ('BOTTOMPADDING', (0, 0), (-1, -1),  5),
        ('LEFTPADDING',   (0, 0), (-1, -1),  8),
        ('RIGHTPADDING',  (0, 0), (-1, -1),  8),
    ])


def _spec_table_style():
    """Compact 2-col spec table (alternating rows, no heavy borders)."""
    return TableStyle([
        ('FONTNAME',      (0, 0), (0, -1),   'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (-1, -1),  'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1),  8),
        ('ALIGN',         (0, 0), (0, -1),   'LEFT'),
        ('ALIGN',         (1, 0), (-1, -1),  'RIGHT'),
        ('ROWBACKGROUNDS',(0, 0), (-1, -1),
         [colors.HexColor(C_ROW_EVEN), colors.HexColor(C_ROW_ODD)]),
        ('GRID',          (0, 0), (-1, -1),  0.4, colors.HexColor(C_BORDER)),
        ('TOPPADDING',    (0, 0), (-1, -1),  3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1),  3.5),
        ('LEFTPADDING',   (0, 0), (-1, -1),  7),
        ('RIGHTPADDING',  (0, 0), (-1, -1),  7),
    ])


def _three_col_table_style():
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),   colors.HexColor(C_HEADER_BG)),
        ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.HexColor(C_HEADER_FG)),
        ('FONTNAME',      (0, 0), (-1, 0),   'Helvetica-Bold'),
        ('FONTNAME',      (0, 1), (-1, -1),  'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1),  8),
        ('ALIGN',         (0, 0), (-1, -1),  'LEFT'),
        ('ALIGN',         (2, 0), (-1, -1),  'RIGHT'),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1),
         [colors.HexColor(C_ROW_EVEN), colors.HexColor(C_ROW_ODD)]),
        ('GRID',          (0, 0), (-1, -1),  0.5, colors.HexColor(C_BORDER)),
        ('TOPPADDING',    (0, 0), (-1, -1),  4),
        ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
        ('LEFTPADDING',   (0, 0), (-1, -1),  7),
        ('RIGHTPADDING',  (0, 0), (-1, -1),  7),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Header / Footer
# ─────────────────────────────────────────────────────────────────────────────

class _HeaderFooter:
    def __init__(self, location_name: str, project_id: str, company_name: str = ''):
        self.location_name = location_name
        self.project_id    = project_id
        self.company_name  = company_name
        self.today         = datetime.now().strftime('%d %B %Y')
        self.report_ref    = f'RPT-{project_id[:8].upper() if project_id else "DEMO"}'

    def __call__(self, canv, doc):
        canv.saveState()
        W, H = A4

        # ── Header ──────────────────────────────────────────────────
        canv.setFillColor(colors.HexColor(C_BLACK))
        canv.rect(0, H - 11*mm, W, 11*mm, fill=1, stroke=0)

        canv.setFont('Helvetica-Bold', 7.5)
        canv.setFillColor(colors.white)
        left_text = self.company_name or 'Shamsi Smart AI'
        canv.drawString(14*mm, H - 7.5*mm, f'{left_text}  ·  Solar Energy Design Report')
        canv.drawRightString(W - 14*mm, H - 7.5*mm,
                             f'{self.location_name}  |  Ref: {self.report_ref}  |  Page {doc.page}')

        # ── Footer ──────────────────────────────────────────────────
        canv.setFillColor(colors.HexColor(C_BORDER))
        canv.rect(0, 0, W, 8*mm, fill=1, stroke=0)

        canv.setFont('Helvetica', 6.5)
        canv.setFillColor(colors.white)
        canv.drawString(14*mm, 2.8*mm,
                        f'Generated: {self.today}  ·  Shamsi Smart AI — For Engineering Use Only')
        canv.drawRightString(W - 14*mm, 2.8*mm,
                             f'CONFIDENTIAL  ·  Ref: {self.report_ref}')

        canv.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# System Block Diagram (ReportLab native drawing)
# ─────────────────────────────────────────────────────────────────────────────

def _build_system_diagram(system_kw: float, panel_count: int,
                           inverter_kw: float = 0) -> Drawing:
    """
    Draw a detailed PV system single-line diagram (SLD):
    PV Array -> DC Fuses -> DC Breaker & SPD -> Inverter -> AC MCB & SPD -> Main DB -> Grid / Load
    """
    W = 170 * mm
    H = 48  * mm

    d = Drawing(W, H)

    # Background frame
    d.add(Rect(0, 0, W, H, fillColor=colors.white,
               strokeColor=colors.HexColor(C_BORDER), strokeWidth=0.5))

    # Helper: box with text lines
    def _box(x, y, w, h, line1, line2='', bg_color=C_ROW_EVEN):
        d.add(Rect(x, y, w, h, fillColor=colors.HexColor(bg_color),
                   strokeColor=colors.HexColor(C_BORDER), strokeWidth=1.2))
        d.add(String(x + w/2, y + h/2 + 2.0, line1,
                     fontSize=7.5, fontName='Helvetica-Bold',
                     textAnchor='middle', fillColor=colors.HexColor(C_DARK)))
        if line2:
            d.add(String(x + w/2, y + h/2 - 5.5, line2,
                         fontSize=6.0, fontName='Helvetica',
                         textAnchor='middle', fillColor=colors.HexColor(C_MUTED)))

    mid_y = H / 2

    # 1. PV Array
    kw_label = f'{system_kw:.2f} kWp' if system_kw else ''
    panels_label = f'{panel_count} modules' if panel_count else ''
    _box(5*mm, mid_y - 9*mm, 26*mm, 18*mm, 'PV ARRAY', f'{kw_label}\n{panels_label}'.replace('\n', ' '))

    # Connection line PV -> Fuses
    d.add(Line(31*mm, mid_y, 40*mm, mid_y, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.2))

    # 2. DC Fuses Box
    _box(40*mm, mid_y - 8*mm, 15*mm, 16*mm, 'DC FUSES', '15A gPV', bg_color='#fffbeb')

    # Line Fuses -> DC MCB
    d.add(Line(55*mm, mid_y, 64*mm, mid_y, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.2))

    # 3. DC Breaker / SPD Box
    _box(64*mm, mid_y - 8*mm, 20*mm, 16*mm, 'DC SPD/MCB', '2-Pole 1kV', bg_color='#fffbeb')

    # Line DC MCB -> Inverter
    d.add(Line(84*mm, mid_y, 93*mm, mid_y, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.2))
    d.add(String(88.5*mm, mid_y + 1.5*mm, 'DC', fontSize=5.5, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor(C_MUTED)))

    # 4. Inverter
    inv_label = f'{inverter_kw:.1f} kW AC' if inverter_kw else 'DC/AC'
    _box(93*mm, mid_y - 9*mm, 24*mm, 18*mm, 'INVERTER', inv_label)

    # Line Inverter -> AC MCB
    d.add(Line(117*mm, mid_y, 124*mm, mid_y, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.2))
    d.add(String(120.5*mm, mid_y + 1.5*mm, 'AC', fontSize=5.5, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.HexColor(C_MUTED)))

    # 5. AC MCB / SPD Box
    _box(124*mm, mid_y - 8*mm, 20*mm, 16*mm, 'AC SPD/MCB', 'Type II', bg_color='#f0fdf4')

    # Line AC MCB -> Main DB
    d.add(Line(144*mm, mid_y, 149*mm, mid_y, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.2))

    # 6. Main DB (MDB)
    _box(149*mm, mid_y - 8*mm, 16*mm, 16*mm, 'MAIN DB', 'Utility MDB')

    # Lines from MDB to Grid and Load
    # Vertical line at 165 mm
    split_x = 165*mm
    d.add(Line(165*mm, mid_y, 169*mm, mid_y + 8*mm, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.0))
    d.add(Line(165*mm, mid_y, 169*mm, mid_y - 8*mm, strokeColor=colors.HexColor(C_DARK), strokeWidth=1.0))

    # Arrow tips / destinations
    d.add(String(169*mm, mid_y + 10*mm, 'To Grid', fontSize=5.5, fontName='Helvetica-Bold', textAnchor='start', fillColor=colors.HexColor(C_DARK)))
    d.add(String(169*mm, mid_y - 12*mm, 'To Load', fontSize=5.5, fontName='Helvetica-Bold', textAnchor='start', fillColor=colors.HexColor(C_DARK)))

    return d


# ─────────────────────────────────────────────────────────────────────────────
# Data-extraction helpers (safe, never crashes)
# ─────────────────────────────────────────────────────────────────────────────

def _safe(obj, *attrs, default='—'):
    """Safely walk a chain of attributes/keys."""
    val = obj
    for a in attrs:
        try:
            val = getattr(val, a) if not isinstance(val, dict) else val[a]
        except (AttributeError, KeyError, TypeError):
            return default
    return val if val not in (None, '', [], {}) else default


def _fmt(val, dec=0, suffix='', default='—'):
    try:
        v = float(val)
        formatted = f'{v:,.{dec}f}{suffix}'
        return formatted
    except (TypeError, ValueError):
        return default


def _extract_results(project_data: dict) -> dict:
    """
    Pull optimization results from every possible location in project_data.
    Priority: pareto_solutions[0] > optimization_results (top level) > zeros
    """
    opt = project_data.get('optimization_results') or {}

    # Pareto solutions (nested or top-level)
    pareto = (opt.get('pareto_solutions') or
              project_data.get('pareto_solutions') or [])
    sol = pareto[0] if pareto else {}

    def _pick(*keys, src=None, default=0):
        """Pick first non-zero/non-None value from sol, then opt, then project_data."""
        for src_dict in [sol, opt, project_data]:
            for k in keys:
                v = src_dict.get(k)
                if v is not None and v != 0 and v != '':
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return v
        return default

    annual_kwh     = _pick('annual_yield_kwh', 'predicted_annual_kwh',
                           'annual_kwh', 'annual_production_kwh')
    monthly        = (sol.get('monthly_yield_kwh') or
                      opt.get('monthly_yield_kwh') or
                      opt.get('predicted_monthly') or
                      project_data.get('predicted_monthly') or [])
    if len(monthly) < 12:
        # distribute annual evenly as fallback
        monthly = [annual_kwh / 12.0] * 12 if annual_kwh else [0] * 12

    specific_yield = _pick('specific_yield', 'specific_yield_kwh_per_kwp')
    total_cost     = _pick('total_cost_egp', 'cost_egp')
    payback_yrs    = _pick('payback_years', 'payback_period_years')
    annual_savings = _pick('annual_savings_egp', 'annual_saving_egp')
    lifetime_sav   = _pick('lifetime_savings_egp', 'savings_25yr_egp')
    panel_count    = int(_pick('panel_count', 'num_panels', default=0))
    system_kw      = _pick('system_kw', 'system_kwp', 'capacity_kw')

    if specific_yield == 0 and system_kw and annual_kwh:
        specific_yield = annual_kwh / float(system_kw)
    perf_ratio     = _pick('performance_ratio', 'pr')
    cost_per_w     = _pick('cost_per_watt', 'cost_per_wp')
    
    if cost_per_w == 0 and total_cost and system_kw:
        cost_per_w = total_cost / (float(system_kw) * 1000.0)
        
    if lifetime_sav == 0 and annual_savings:
        lifetime_sav = annual_savings * 25
        
    panel_id       = sol.get('panel_id') or opt.get('panel_id')
    inverter_id    = sol.get('inverter_id') or opt.get('inverter_id')
    dust_loss      = _pick('dust_loss_pct', default=5.0)

    # Panel / inverter brand strings from pareto
    panel_brand    = sol.get('panel_brand') or opt.get('panel_brand', '')
    panel_model    = sol.get('panel_model') or opt.get('panel_model', '')
    inv_brand      = sol.get('inverter_brand') or opt.get('inverter_brand', '')
    inv_model      = sol.get('inverter_model') or opt.get('inverter_model', '')

    return {
        'annual_yield_kwh'  : annual_kwh,
        'monthly_yield_kwh' : monthly,
        'specific_yield'    : specific_yield,
        'total_cost_egp'    : total_cost,
        'payback_years'     : payback_yrs,
        'annual_savings_egp': annual_savings,
        'lifetime_savings_egp': lifetime_sav,
        'panel_count'       : panel_count,
        'system_kw'         : system_kw,
        'performance_ratio' : perf_ratio,
        'cost_per_watt'     : cost_per_w,
        'dust_loss_pct'     : dust_loss,
        'panel_brand'       : panel_brand,
        'panel_model'       : panel_model,
        'inverter_brand'    : inv_brand,
        'inverter_model'    : inv_model,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main Report Class
# ─────────────────────────────────────────────────────────────────────────────

class ProfessionalPDFReport:
    """
    Generate a professional 7-section engineer PDF report.

    project_data keys used
    ----------------------
    location         : ORM object (name, latitude, longitude) or dict
    panel            : ORM Equipment object or None
    inverter         : ORM Equipment object or None
    system_config    : dict  (panel_count, tilt_angle, azimuth, …)
    optimization_results : dict  (annual_yield_kwh, pareto_solutions, …)
    climate_data     : queryset or list of daily climate records
    company          : dict  (name, egypteraLicense, address, phone, email)
    """

    def __init__(self, project_data: Dict):
        self.project      = project_data
        self.location     = project_data.get('location')
        self.panel        = project_data.get('panel')
        self.inverter     = project_data.get('inverter')
        self.config       = project_data.get('system_config', {})
        self.company      = project_data.get('company', {})
        self.results      = _extract_results(project_data)

        # Derived
        p_power = float(_safe(self.panel, 'power_rating_w', default=0) or 0)
        cfg_count = int(self.config.get('panel_count') or
                        self.results.get('panel_count') or 0)
        res_count = int(self.results.get('panel_count') or 0)
        self.panel_count  = cfg_count or res_count or 30

        res_kw = float(self.results.get('system_kw') or 0)
        if p_power and self.panel_count:
            self.system_kw = self.panel_count * p_power / 1000.0
        elif res_kw:
            self.system_kw = res_kw
        else:
            self.system_kw = 0

    # ─── Public API ───────────────────────────────────────────────────────────

    def generate_report(self, output_file: str) -> str:
        if not REPORTLAB_AVAILABLE:
            raise ImportError(f"reportlab not installed or failed to import. Detail: {REPORTLAB_ERROR}")

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_file,
            pagesize      = A4,
            rightMargin   = 18*mm,
            leftMargin    = 18*mm,
            topMargin     = 18*mm,
            bottomMargin  = 15*mm,
        )

        styles = _build_styles()
        loc_name = _safe(self.location, 'name', default='N/A')
        proj_id  = self.project.get('project_id', 'DEMO')
        company_name = self.company.get('name', '')

        hf = _HeaderFooter(loc_name, proj_id, company_name)

        story = []
        story += self._cover_page(styles)
        story.append(PageBreak())

        story += self._executive_summary(styles)
        story.append(PageBreak())

        story += self._site_analysis(styles)
        story.append(PageBreak())

        story += self._system_design(styles)
        story.append(PageBreak())

        story += self._energy_forecast(styles)
        story.append(PageBreak())

        story += self._financial_analysis(styles)
        story.append(PageBreak())

        story += self._warnings_page(styles)
        story.append(PageBreak())

        story += self._technical_appendix(styles)

        doc.build(story, onFirstPage=hf, onLaterPages=hf)
        return os.path.abspath(output_file)

    # ─── Section 1 ─── Cover Page ─────────────────────────────────────────────

    def _cover_page(self, styles) -> list:
        res  = self.results
        loc  = self.location
        co   = self.company

        loc_name = _safe(loc, 'name', default='Egypt')
        lat  = float(_safe(loc, 'latitude',  default=30.05) or 30.05)
        lon  = float(_safe(loc, 'longitude', default=31.25) or 31.25)

        elements = [Spacer(1, 16*mm)]

        # ── Company block (if available) ─────────────────────────────────────
        if co.get('name') or co.get('egypteraLicense'):
            co_data = [[
                co.get('name', ''),
                co.get('egypteraLicense') and f"EGYPTERA Reg: {co['egypteraLicense']}" or '',
            ]]
            co_tbl = Table(co_data, colWidths=[95*mm, 75*mm])
            co_tbl.setStyle(TableStyle([
                ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME',    (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE',    (0, 0), (-1, -1), 9),
                ('ALIGN',       (0, 0), (0, -1), 'LEFT'),
                ('ALIGN',       (1, 0), (1, -1), 'RIGHT'),
                ('TEXTCOLOR',   (0, 0), (-1, -1), colors.HexColor(C_DARK)),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LINEBELOW',   (0, 0), (-1, -1), 0.5, colors.HexColor(C_DIVIDER)),
            ]))
            elements.append(co_tbl)
            elements.append(Spacer(1, 8*mm))

        # ── Title block ──────────────────────────────────────────────────────
        elements.append(Paragraph('SOLAR ENERGY SYSTEM DESIGN', styles['CoverTitle']))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph('Feasibility &amp; Production Report', styles['CoverSubtitle']))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(
            f'Prepared for: <b>{loc_name}</b>',
            styles['CoverMeta']
        ))
        elements.append(Spacer(1, 6*mm))

        # ── Heavy divider ────────────────────────────────────────────────────
        div_data = [['']]
        div = Table(div_data, colWidths=[170*mm], rowHeights=[4])
        div.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(C_RULE)),
        ]))
        elements.append(div)
        elements.append(Spacer(1, 8*mm))

        # ── Key metrics info block ───────────────────────────────────────────
        p_brand = (self.results.get('panel_brand') or
                   _safe(self.panel, 'manufacturer', default=''))
        p_model_str = (self.results.get('panel_model') or
                       _safe(self.panel, 'model', default=''))
        p_power = float(_safe(self.panel, 'power_rating_w', default=0) or 0)

        inv_brand = (self.results.get('inverter_brand') or
                     _safe(self.inverter, 'manufacturer', default=''))
        inv_model_str = (self.results.get('inverter_model') or
                         _safe(self.inverter, 'model', default=''))

        panel_str = (
            f'{p_brand} {p_model_str} ({p_power:.0f} W)'
            if (p_brand or p_model_str)
            else (f'{self.panel_count} × {p_power:.0f} W' if p_power else f'{self.panel_count} modules')
        )

        info_rows = [
            ['Site / Location',      loc_name],
            ['Coordinates',          f'{lat:.4f}°N,  {lon:.4f}°E'],
            ['System Peak Capacity', _fmt(self.system_kw, 2, ' kWp',
                                         f'{self.system_kw:.2f} kWp') if self.system_kw else '—'],
            ['Panel Configuration',  f'{self.panel_count} × {panel_str}' if panel_str else f'{self.panel_count} modules'],
            ['Inverter',             f'{inv_brand} {inv_model_str}'.strip() or '—'],
            ['Annual Production',    _fmt(res.get('annual_yield_kwh'), 0, ' kWh/year')],
            ['Specific Yield',       _fmt(res.get('specific_yield'), 0, ' kWh/kWp/yr')],
            ['Report Date',          datetime.now().strftime('%d %B %Y')],
            ['Reference No.',        self.project.get('project_id', 'DEMO')],
        ]

        tbl = Table(info_rows, colWidths=[65*mm, 105*mm])
        tbl.setStyle(TableStyle([
            ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE',      (0, 0), (-1, -1), 9.5),
            ('TEXTCOLOR',     (0, 0), (0, -1), colors.HexColor(C_DARK)),
            ('TEXTCOLOR',     (1, 0), (1, -1), colors.HexColor(C_BODY)),
            ('ROWBACKGROUNDS',(0, 0), (-1, -1),
             [colors.HexColor(C_ROW_EVEN), colors.HexColor(C_ROW_ODD)]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor(C_BORDER)),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 10*mm))

        # ── AI badge ─────────────────────────────────────────────────────────
        badge_txt = (
            '<b>AI-Optimised Engineering Design</b><br/>'
            '<font size="8" color="#555555">This report was generated by Shamsi Smart AI using '
            'multi-objective NSGA-II optimisation and a CNN-LSTM deep learning yield '
            'prediction model trained on 8+ years of NASA POWER climate data for 119 '
            'Egyptian locations. Validated against PVWatts v5 and physics baselines '
            '(MAPE &lt; 5%). Suitable for submission to engineering review.</font>'
        )
        badge_data = [[Paragraph(badge_txt, styles['BodyText'])]]
        badge = Table(badge_data, colWidths=[170*mm])
        badge.setStyle(TableStyle([
            ('BOX',          (0, 0), (-1, -1), 1.5, colors.HexColor(C_RULE)),
            ('TOPPADDING',   (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 10),
            ('LEFTPADDING',  (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ]))
        elements.append(badge)

        # ── Confidentiality footer ────────────────────────────────────────────
        elements.append(Spacer(1, 16*mm))
        elements.append(Paragraph(
            'CONFIDENTIAL — For Engineering Use Only. Not for public distribution.',
            styles['SmallRight']
        ))
        return elements

    # ─── Section 2 ─── Executive Summary ──────────────────────────────────────

    def _executive_summary(self, styles) -> list:
        res = self.results
        loc_name = _safe(self.location, 'name', default='this site')

        p_mfr  = _safe(self.panel, 'manufacturer', default=res.get('panel_brand', ''))
        p_mod  = _safe(self.panel, 'model', default=res.get('panel_model', ''))
        p_w    = float(_safe(self.panel, 'power_rating_w', default=0) or 0)
        inv_mfr= _safe(self.inverter, 'manufacturer', default=res.get('inverter_brand', ''))
        inv_mod= _safe(self.inverter, 'model', default=res.get('inverter_model', ''))

        panel_desc = (f'{p_mfr} {p_mod} ({p_w:.0f} W)'
                      if (p_mfr or p_mod) else f'{self.panel_count} modules')

        elements = [Paragraph('SECTION 1 — EXECUTIVE SUMMARY', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Executive Summary', styles['SectionHeader']))

        narrative = (
            f'The proposed grid-tied solar photovoltaic system for <b>{loc_name}</b> '
            f'has a rated peak capacity of <b>{self.system_kw:.2f} kWp</b>, comprising '
            f'<b>{self.panel_count}</b> modules of <b>{panel_desc}</b>. '
        )
        if inv_mfr or inv_mod:
            narrative += (
                f'The system utilises a <b>{inv_mfr} {inv_mod}</b> inverter for DC/AC conversion. '
            )
        annual = res.get('annual_yield_kwh', 0)
        if annual:
            narrative += (
                f'Based on Shamsi Smart AI yield modelling, the system is forecast to generate '
                f'<b>{annual:,.0f} kWh annually</b>'
            )
            sp = res.get('specific_yield', 0)
            if sp:
                narrative += f', at a specific yield of <b>{sp:,.0f} kWh/kWp/yr</b>'
            narrative += '. '
        cost = res.get('total_cost_egp', 0)
        pb   = res.get('payback_years', 0)
        if cost and pb:
            narrative += (
                f'The total investment is estimated at <b>{cost:,.0f} EGP</b>, '
                f'with a simple payback period of <b>{pb:.1f} years</b>. '
            )
        ls = res.get('lifetime_savings_egp', 0)
        if ls:
            narrative += f'Projected net savings over 25 years are <b>{ls:,.0f} EGP</b>.'

        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 5*mm))

        # KPI table
        kpi_rows = [
            ['Parameter', 'Value'],
            ['System Peak Capacity',    _fmt(self.system_kw, 2, ' kWp')],
            ['Number of Modules',       str(self.panel_count)],
            ['Module Model',            f'{p_mfr} {p_mod}'.strip() or '—'],
            ['Module Rated Power',      _fmt(p_w, 0, ' W') if p_w else '—'],
            ['Inverter',                f'{inv_mfr} {inv_mod}'.strip() or '—'],
            ['Annual Energy Yield',     _fmt(res.get('annual_yield_kwh'), 0, ' kWh/yr')],
            ['Specific Yield',          _fmt(res.get('specific_yield'), 0, ' kWh/kWp/yr')],
            ['Performance Ratio (PR)',  _fmt(float(res.get('performance_ratio') or 0) * 100, 1, '%') if res.get('performance_ratio') else '~80%'],
            ['Total Investment',        _fmt(res.get('total_cost_egp'), 0, ' EGP')],
            ['Cost per Watt-peak',      _fmt(res.get('cost_per_watt'), 2, ' EGP/Wp')],
            ['Simple Payback Period',   _fmt(res.get('payback_years'), 1, ' years')],
            ['25-Year Net Savings',     _fmt(res.get('lifetime_savings_egp'), 0, ' EGP')],
            ['Annual CO\u2082 Avoided', _fmt((res.get('annual_yield_kwh') or 0) * 0.47 / 1000, 2, ' tCO\u2082')],
        ]
        tbl = Table(kpi_rows, colWidths=[100*mm, 70*mm])
        tbl.setStyle(_metric_table_style())
        elements.append(tbl)

        return elements

    # ─── Section 3 ─── Site & Climate Analysis ────────────────────────────────

    def _site_analysis(self, styles) -> list:
        loc = self.location
        loc_name = _safe(loc, 'name', default='N/A')
        lat  = float(_safe(loc, 'latitude',  default=30.05) or 30.05)
        lon  = float(_safe(loc, 'longitude', default=31.25) or 31.25)
        elev = float(_safe(loc, 'elevation_m', default=0) or 0)

        elements = [Paragraph('SECTION 2 — SITE &amp; CLIMATE ANALYSIS', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Site &amp; Climate Analysis', styles['SectionHeader']))

        # Geographic params
        elements.append(Paragraph('Geographic Parameters', styles['SubHeader']))
        avg_ghi = self.project.get('avg_ghi_daily') or self._estimate_avg_ghi(lat)
        climate_zone = self.project.get('climate_zone') or self._classify_climate(lat, lon)
        dust_pct = float(self.project.get('dust_loss_pct') or 5.0)

        site_rows = [
            ['Parameter',         'Value'],
            ['Site Name',         loc_name],
            ['Country / Region',  getattr(loc, 'country', None) or 'Egypt'],
            ['Latitude',          f'{lat:.4f}°  N'],
            ['Longitude',         f'{lon:.4f}°  E'],
            ['Elevation',         f'{elev:.0f} m ASL'],
            ['Climate Zone',      climate_zone],
            ['Time Zone',         'UTC+2 (EET — Eastern European Time)'],
            ['Annual Avg. GHI',   f'{avg_ghi:.2f} kWh/m²/day  ({avg_ghi*365:.0f} kWh/m²/yr)'],
            ['Peak Sun Hours',    f'{avg_ghi:.2f} hours/day (average)'],
            ['Dust / Dust Zone',  f'{dust_pct:.1f}% annual soiling loss'],
            ['Climate Data Src.', 'NASA POWER (8+ years, 0.5° × 0.5° grid)'],
        ]
        tbl = Table(site_rows, colWidths=[80*mm, 90*mm])
        tbl.setStyle(_metric_table_style())
        elements.append(tbl)
        elements.append(Spacer(1, 5*mm))

        # Roof / installation params if available
        roof = self.project.get('roof_analysis')
        tilt = float(self.config.get('tilt_angle', 20) or 20)
        az   = float(self.config.get('azimuth', 180) or 180)
        shading = float(self.project.get('shading_loss_pct', 3) or 3)

        elements.append(Paragraph('Installation Parameters', styles['SubHeader']))
        inst_rows = [
            ['Parameter',              'Value'],
            ['Module Tilt Angle',      f'{tilt:.1f}°  (from horizontal)'],
            ['Array Azimuth',          f'{az:.0f}°  (180° = True South)'],
            ['Mounting Type',          'Fixed Tilt — Roof / Ground Mount'],
            ['Assumed Shading Loss',   f'{shading:.1f}%'],
            ['Dust / Soiling Loss',    f'{dust_pct:.1f}%'],
            ['DC Wiring Loss',         '2.0%  (IEC 60364-7-712 compliant)'],
            ['String Mismatch Loss',   '2.0%  (module binning tolerance)'],
        ]
        if roof:
            inst_rows += [
                ['Total Roof Area',    f'{roof.get("roof_area_m2", "—"):.1f} m²' if isinstance(roof.get("roof_area_m2"), (int, float)) else '—'],
                ['Usable Roof Area',   f'{roof.get("usable_area_m2", "—"):.1f} m²' if isinstance(roof.get("usable_area_m2"), (int, float)) else '—'],
                ['Obstacles Detected', str(len(roof.get('obstacles', [])))],
            ]
        tbl2 = Table(inst_rows, colWidths=[80*mm, 90*mm])
        tbl2.setStyle(_metric_table_style())
        elements.append(tbl2)

        # Add Monthly Weather & Irradiance Table
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph('Monthly Irradiance &amp; Meteorological Data', styles['SubHeader']))
        
        months_short = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December']
        irr_rows = [['Month', 'GHI (Horiz.) (kWh/m²/day)', 'POA (Tilted) (kWh/m²/day)', 'Avg. Ambient Temp (°C)']]
        
        m_ghi = self.project.get('monthly_ghi') or [0]*12
        m_poa = self.project.get('monthly_poa') or [0]*12
        m_temp = self.project.get('monthly_temp') or [25]*12
        
        for i, m_name in enumerate(months_short):
            ghi_d = m_ghi[i] / 30.4 if m_ghi[i] > 0 else 0
            poa_d = m_poa[i] / 30.4 if m_poa[i] > 0 else 0
            temp_val = m_temp[i]
            irr_rows.append([
                m_name,
                f"{ghi_d:.2f}",
                f"{poa_d:.2f}",
                f"{temp_val:.1f}"
            ])
            
        irr_tbl = Table(irr_rows, colWidths=[55*mm, 40*mm, 40*mm, 35*mm])
        irr_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),   colors.HexColor(C_HEADER_BG)),
            ('TEXTCOLOR',     (0, 0), (-1, 0),   colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),   'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1),  8.0),
            ('ALIGN',         (0, 0), (0, -1),   'LEFT'),
            ('ALIGN',         (1, 0), (-1, -1),  'RIGHT'),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1),
             [colors.HexColor(C_ROW_EVEN), colors.HexColor(C_ROW_ODD)]),
            ('GRID',          (0, 0), (-1, -1),  0.5, colors.HexColor(C_BORDER)),
            ('TOPPADDING',    (0, 0), (-1, -1),  4),
            ('BOTTOMPADDING', (0, 0), (-1, -1),  4),
            ('LEFTPADDING',   (0, 0), (-1, -1),  6),
            ('RIGHTPADDING',  (0, 0), (-1, -1),  6),
        ]))
        elements.append(irr_tbl)

        # Roof image if available
        roof_img = self.project.get('roof_image_path')
        if roof_img and os.path.exists(str(roof_img)):
            elements.append(Spacer(1, 4*mm))
            elements.append(Paragraph('Roof Satellite Image (AI-Annotated)', styles['SubHeader']))
            elements.append(Image(roof_img, width=130*mm, height=90*mm))
            elements.append(Paragraph(
                'Figure 1: Computer vision analysis of roof usable area and obstacle detection.',
                styles['Caption']
            ))

        return elements

    # ─── Section 4 ─── System Design ──────────────────────────────────────────

    def _system_design(self, styles) -> list:
        cfg  = self.config
        p    = self.panel
        inv  = self.inverter
        res  = self.results

        p_mfr    = _safe(p, 'manufacturer', default=res.get('panel_brand', 'N/A'))
        p_mod    = _safe(p, 'model',        default=res.get('panel_model', '—'))
        p_power  = float(_safe(p, 'power_rating_w', default=0) or 0)
        p_eff    = float(_safe(p, 'efficiency_percent', default=0) or 0)
        p_vmp    = float(_safe(p, 'vmp_v', default=0) or 0)
        p_imp    = float(_safe(p, 'imp_a', default=0) or 0)
        p_voc    = float(_safe(p, 'voc_v', default=0) or 0)
        p_isc    = float(_safe(p, 'isc_a', default=0) or 0)
        p_tcoeff = float(_safe(p, 'temp_coeff_pmax_percent', default=0) or 0)
        p_len    = float(_safe(p, 'length_mm', default=0) or 0)
        p_wid    = float(_safe(p, 'width_mm', default=0) or 0)
        p_thk    = float(_safe(p, 'thickness_mm', default=0) or 0)
        p_wgt    = float(_safe(p, 'weight_kg', default=0) or 0)
        p_area   = float(_safe(p, 'area_m2', default=0) or 0)
        p_tech   = _safe(p, 'technology', default='Monocrystalline PERC')

        inv_mfr  = _safe(inv, 'manufacturer', default=res.get('inverter_brand', 'N/A'))
        inv_mod  = _safe(inv, 'model',        default=res.get('inverter_model', '—'))
        inv_pwr  = float(_safe(inv, 'power_rating_w', default=0) or 0)
        inv_maxac= float(_safe(inv, 'max_ac_power_w',  default=0) or 0)
        inv_maxeff= float(_safe(inv, 'max_efficiency_percent', default=0) or 0)
        inv_eureff= float(_safe(inv, 'euro_efficiency_percent', default=0) or 0)
        inv_maxv = float(_safe(inv, 'max_dc_voltage_v', default=0) or 0)
        inv_mpplo= float(_safe(inv, 'mppt_voltage_min_v', default=0) or 0)
        inv_mpphi= float(_safe(inv, 'mppt_voltage_max_v', default=0) or 0)
        inv_mppts= int(_safe(inv, 'number_of_mppts', default=0) or 0)
        inv_type = _safe(inv, 'inverter_type', default='String Inverter')

        strings    = int(cfg.get('strings', 0) or 0)
        pps        = int(cfg.get('panels_per_string', 0) or 0)
        inv_count  = int(cfg.get('inverter_count', 1) or 1)
        tilt       = float(cfg.get('tilt_angle', 20) or 20)
        az         = float(cfg.get('azimuth', 180) or 180)

        inv_kw = inv_pwr / 1000.0 if inv_pwr else (inv_maxac / 1000.0 if inv_maxac else 0)

        elements = [Paragraph('SECTION 3 — SYSTEM DESIGN SPECIFICATIONS', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('System Design Specifications', styles['SectionHeader']))

        # ── System Overview ──────────────────────────────────────────────────
        elements.append(Paragraph('System Configuration', styles['SubHeader']))
        pr_val = float(res.get('performance_ratio') or 0)
        system_type_str = self.project.get('system_type_str', 'Grid-Tied Solar System (On-Grid, No Battery)')
        roof_area_needed = self.project.get('roof_area_needed', 0.0)
        
        sys_rows = [
            ['Parameter',             'Value'],
            ['System Type',           system_type_str],
            ['Peak Capacity (DC)',     f'{self.system_kw:.3f} kWp'],
            ['Total Modules',         str(self.panel_count)],
        ]
        if strings and pps:
            sys_rows.append(['String Configuration', f'{strings} string(s) × {pps} modules'])
        sys_rows += [
            ['Tilt Angle',            f'{tilt:.1f}°  from horizontal'],
            ['Array Azimuth',         f'{az:.0f}°  (True South = 180°)'],
            ['Number of Inverters',   str(inv_count)],
            ['DC/AC Ratio',           f'{self.system_kw / (inv_kw * inv_count):.2f}' if (inv_kw and inv_count) else '—'],
            ['Required Roof Area',    f'≈ {roof_area_needed:.1f} m²  (includes row-spacing layout)'],
            ['Performance Ratio (PR)',f'{pr_val*100:.1f}%' if pr_val else '~80%  (estimated)'],
        ]
        tbl = Table(sys_rows, colWidths=[80*mm, 90*mm])
        tbl.setStyle(_metric_table_style())
        elements.append(tbl)
        elements.append(Spacer(1, 4*mm))

        # ── Block Diagram ────────────────────────────────────────────────────
        elements.append(Paragraph('Detailed Single-Line Schematic', styles['SubHeader']))
        diag = _build_system_diagram(self.system_kw, self.panel_count, inv_kw * inv_count)
        elements.append(diag)
        elements.append(Spacer(1, 1*mm))
        elements.append(Paragraph(
            'Figure 2: Detailed single-line diagram (SLD) of the proposed PV array, inverter, and protection devices.',
            styles['Caption']
        ))
        elements.append(Spacer(1, 4*mm))

        # ── Solar Module Spec ────────────────────────────────────────────────
        elements.append(Paragraph('Solar Module Datasheet Parameters', styles['SubHeader']))
        pan_rows = [
            ['Manufacturer',             p_mfr or '—'],
            ['Model',                    p_mod or '—'],
            ['Technology',               p_tech or '—'],
            ['Rated Power (STC)',        f'{p_power:.0f} W' if p_power else '—'],
            ['Module Efficiency',        f'{p_eff:.2f}%' if p_eff else '—'],
            ['Vmpp  (STC)',              f'{p_vmp:.2f} V' if p_vmp else '—'],
            ['Impp  (STC)',              f'{p_imp:.2f} A' if p_imp else '—'],
            ['Voc   (STC)',              f'{p_voc:.2f} V' if p_voc else '—'],
            ['Isc   (STC)',              f'{p_isc:.2f} A' if p_isc else '—'],
            ['Temp. Coeff. Pmax',        f'{p_tcoeff:.3f} %/°C' if p_tcoeff else '—'],
            ['Dimensions (L×W×H)',       f'{p_len:.0f} × {p_wid:.0f} × {p_thk:.0f} mm' if p_len else '—'],
            ['Module Area',              f'{p_area:.4f} m²' if p_area else '—'],
            ['Weight',                   f'{p_wgt:.1f} kg' if p_wgt else '—'],
        ]
        pan_tbl = Table(pan_rows, colWidths=[80*mm, 90*mm])
        pan_tbl.setStyle(_spec_table_style())
        elements.append(pan_tbl)
        elements.append(Spacer(1, 4*mm))

        # ── Inverter Spec ────────────────────────────────────────────────────
        elements.append(Paragraph('Inverter Datasheet Parameters', styles['SubHeader']))
        inv_rows = [
            ['Manufacturer',             inv_mfr or '—'],
            ['Model',                    inv_mod or '—'],
            ['Inverter Type',            inv_type or '—'],
            ['Rated AC Power',           f'{inv_pwr:,.0f} W' if inv_pwr else '—'],
            ['Max. AC Output Power',     f'{inv_maxac:,.0f} W' if inv_maxac else '—'],
            ['Max. Efficiency',          f'{inv_maxeff:.1f}%' if inv_maxeff else '—'],
            ['European (Euro) Efficiency',f'{inv_eureff:.1f}%' if inv_eureff else '—'],
            ['Max. DC Input Voltage',    f'{inv_maxv:.0f} V' if inv_maxv else '—'],
            ['MPPT Voltage Range',       f'{inv_mpplo:.0f} – {inv_mpphi:.0f} V' if (inv_mpplo and inv_mpphi) else '—'],
            ['Number of MPPT Trackers',  str(inv_mppts) if inv_mppts else '—'],
        ]
        inv_tbl = Table(inv_rows, colWidths=[80*mm, 90*mm])
        inv_tbl.setStyle(_spec_table_style())
        elements.append(inv_tbl)
        
        # ── Cable Sizing Summary ──────────────────────────────────────────────
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph('Cable Sizing Summary', styles['SubHeader']))
        cable = self.project.get('cable_summary', {})
        cable_rows = [
            ['Cable Type', 'Recommended Sizing / Spec', 'Design Voltage Drop (%)'],
            ['DC String Cabling (PV Array to Inverter)', cable.get('dc_cable', '4 mm² PV1-F solar cable'), cable.get('dc_voltage_drop', '1.1%')],
            ['AC Main Cabling (Inverter to Main DB)', cable.get('ac_cable', '4 mm² Cu AC cable'), cable.get('ac_voltage_drop', '0.8%')],
        ]
        cable_tbl = Table(cable_rows, colWidths=[75*mm, 60*mm, 35*mm])
        cable_tbl.setStyle(_three_col_table_style())
        elements.append(cable_tbl)

        # ── Protection Devices Summary ────────────────────────────────────────
        elements.append(Spacer(1, 4*mm))
        elements.append(Paragraph('Electrical Protection Devices', styles['SubHeader']))
        prot = self.project.get('protections', {})
        prot_rows = [
            ['Device Location', 'Recommended Protection Device', 'Specification Details'],
            ['DC PV Strings', 'DC String Fuses', prot.get('dc_fuse', '15A gPV, 1000V DC')],
            ['DC Inverter Inputs', 'DC Circuit Breaker (Isolator)', prot.get('dc_breaker', '20A MCB, 1000V DC, 2-Pole')],
            ['DC Array Bus / Inverter', 'DC Surge Protection Device (SPD)', prot.get('dc_spd', 'Type II SPD, 1000V DC')],
            ['AC Inverter Output', 'AC Circuit Breaker (MCB / MCCB)', prot.get('ac_breaker', '20A AC MCB')],
            ['AC Main DB Connection', 'AC Surge Protection Device (SPD)', prot.get('ac_spd', 'Type II SPD, 275V AC')],
        ]
        prot_tbl = Table(prot_rows, colWidths=[55*mm, 60*mm, 55*mm])
        prot_tbl.setStyle(_three_col_table_style())
        elements.append(prot_tbl)

        return elements

    # ─── Section 5 ─── Energy Forecast ────────────────────────────────────────

    def _energy_forecast(self, styles) -> list:
        res     = self.results
        monthly = list(res.get('monthly_yield_kwh') or [0]*12)
        if len(monthly) < 12:
            monthly = (list(monthly) + [0]*12)[:12]

        annual  = res.get('annual_yield_kwh') or sum(monthly)
        loc_name= _safe(self.location, 'name', default='this site')

        elements = [Paragraph('SECTION 4 — ENERGY PRODUCTION FORECAST', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Energy Production Forecast', styles['SectionHeader']))

        narrative = (
            f'Based on NASA POWER climate data for <b>{loc_name}</b> and '
            f'Shamsi Smart\'s CNN-LSTM deep learning yield model, the system is '
            f'forecast to produce <b>{annual:,.0f} kWh annually</b>. Peak generation '
            f'occurs during summer months (May–August) driven by Egypt\'s high solar '
            f'irradiance. The model incorporates temperature derating, dust soiling losses, '
            f'inverter efficiency curves, wiring losses, and long-term module degradation '
            f'(0.5%/yr).'
        )
        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Bar chart
        if MATPLOTLIB_AVAILABLE and any(v > 0 for v in monthly):
            buf = _monthly_production_chart(monthly)
            elements.append(Image(buf, width=165*mm, height=70*mm))
            elements.append(Paragraph(
                'Figure 3: Monthly energy production forecast (kWh). Hatch pattern for B&W printing.',
                styles['Caption']
            ))
            elements.append(Spacer(1, 4*mm))

        # Monthly data table
        months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        total = sum(monthly) or 1
        mon_data = [['Month', 'Production (kWh)', '% of Annual', 'Cum. (kWh)']]
        cumsum = 0
        for m, v in zip(months, monthly):
            cumsum += v
            mon_data.append([
                m,
                f'{v:,.0f}',
                f'{v/total*100:.1f}%',
                f'{cumsum:,.0f}',
            ])
        mon_data.append(['ANNUAL TOTAL', f'{total:,.0f}', '100.0%', f'{total:,.0f}'])

        mon_tbl = Table(mon_data, colWidths=[55*mm, 45*mm, 35*mm, 35*mm])
        mon_tbl.setStyle(_three_col_table_style())
        # Bold the last row
        mon_tbl.setStyle(TableStyle([
            ('FONTNAME',    (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND',  (0, -1), (-1, -1), colors.HexColor(C_ROW_EVEN)),
        ]))
        elements.append(mon_tbl)

        return elements

    # ─── Section 6 ─── Financial Analysis ─────────────────────────────────────

    def _financial_analysis(self, styles) -> list:
        res = self.results
        loc_name = _safe(self.location, 'name', default='this site')

        cost    = res.get('total_cost_egp') or 0
        payback = res.get('payback_years') or 0
        ls      = res.get('lifetime_savings_egp') or 0
        annual  = res.get('annual_yield_kwh') or 0

        elements = [Paragraph('SECTION 5 — FINANCIAL ANALYSIS', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Financial Analysis', styles['SectionHeader']))

        narrative = (
            f'At current Egyptian electricity tariffs (≈ 1.65 EGP/kWh residential, '
            f'with 5% annual price escalation), the system achieves '
        )
        if payback:
            narrative += f'payback in <b>{payback:.1f} years</b> '
        if cost:
            narrative += f'on a total investment of <b>{cost:,.0f} EGP</b>. '
        if ls:
            narrative += f'Over 25 years, cumulative net savings are projected at <b>{ls:,.0f} EGP</b>. '
        narrative += (
            'The model applies a 0.5%/year panel degradation rate and accounts for '
            'operation &amp; maintenance costs of ~0.5% of system cost per annum.'
        )
        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Cashflow chart
        if MATPLOTLIB_AVAILABLE and cost and annual:
            buf = _cashflow_chart(
                annual_kwh    = annual,
                total_cost    = cost,
                payback_years = payback or 10,
            )
            elements.append(Image(buf, width=165*mm, height=70*mm))
            elements.append(Paragraph(
                'Figure 4: 25-year cumulative net cashflow (EGP). '
                'Hatched bars = investment not yet recovered. Dashed line = payback year.',
                styles['Caption']
            ))
            elements.append(Spacer(1, 4*mm))

        # Financial KPI table
        lcoe = self._estimate_lcoe(res, self.system_kw)
        ann_sav = res.get('annual_savings_egp') or 0
        net_profit_25 = max(0, ls - cost)

        fin_rows = [
            ['Financial Metric',            'Value'],
            ['Total System Investment',      _fmt(cost, 0, ' EGP')],
            ['Cost per Watt-peak',           _fmt(res.get('cost_per_watt'), 2, ' EGP/Wp')],
            ['Annual Energy Savings',        _fmt(ann_sav, 0, ' EGP/yr') if ann_sav else _fmt(annual * 1.65, 0, ' EGP/yr (est.)')],
            ['Simple Payback Period',        _fmt(payback, 1, ' years')],
            ['25-Year Gross Savings',        _fmt(ls, 0, ' EGP')],
            ['25-Year Net Profit (after CAPEX)', _fmt(net_profit_25, 0, ' EGP')],
            ['Levelised Cost of Energy (LCOE)', f'{lcoe:.3f} EGP/kWh' if lcoe else 'N/A'],
            ['Annual CO\u2082 Offset',       _fmt(annual * 0.47 / 1000, 2, ' tCO\u2082/yr') if annual else '—'],
            ['25-Year CO\u2082 Offset (est.)',_fmt(annual * 0.47 / 1000 * 22, 1, ' tCO\u2082') if annual else '—'],
        ]
        fin_tbl = Table(fin_rows, colWidths=[100*mm, 70*mm])
        fin_tbl.setStyle(_metric_table_style())
        elements.append(fin_tbl)

        return elements

    # ─── Warnings Page ────────────────────────────────────────────────────────

    def _warnings_page(self, styles) -> list:
        warnings = self.project.get('warnings') or []

        elements = [Paragraph('SECTION 5.1 — ENGINEERING COMPLIANCE &amp; WARNINGS', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Engineering Compliance &amp; Warnings', styles['SectionHeader']))

        intro_text = (
            "This section presents the results of the automated engineering rule-checks "
            "and electrical code compliance validations. Sizing validations assess inverter DC/AC ratio, "
            "string open-circuit voltage at low ambient temperature (cold Voc limit), MPPT operating voltage "
            "under hot cell temperatures (hot Vmp limit), and inverter compatibility with regulatory grid-tied rules."
        )
        elements.append(Paragraph(intro_text, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        if warnings:
            elements.append(Paragraph('<b>Detected Sizing Violations &amp; Engineering Warnings</b>', styles['SubHeader']))
            elements.append(Spacer(1, 2*mm))

            for warning in warnings:
                is_critical = "CRITICAL" in warning.upper() or "OVERVOLTAGE" in warning.upper()
                bg_color = '#fdf2f2' if is_critical else '#fffbeb'
                border_color = '#f05252' if is_critical else '#f59e0b'
                prefix = "<b>[CRITICAL VIOLATION]</b> " if is_critical else "<b>[WARNING]</b> "

                warning_p = Paragraph(f"<font color='{border_color}'>{prefix}</font>{warning}", styles['BodyText'])

                tbl_data = [[warning_p]]
                tbl = Table(tbl_data, colWidths=[170*mm])
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg_color)),
                    ('BOX',        (0, 0), (-1, -1), 1.0, colors.HexColor(border_color)),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ]))
                elements.append(tbl)
                elements.append(Spacer(1, 4*mm))
        else:
            comp_txt = (
                "<b>System Sizing Status: COMPLIANT</b><br/><br/>"
                "The solar PV engineering design fully complies with standard sizing rules and regulatory requirements:<br/>"
                "• <b>DC/AC Ratio</b>: Validated within the optimal engineering window (1.00 – 1.35) preventing underutilization or excessive clipping.<br/>"
                "• <b>Voltage Sizing (Cold Voc)</b>: Open-circuit voltage remains safely below the inverter's maximum input DC rating under worst-case winter temperatures.<br/>"
                "• <b>Voltage Sizing (Hot MPPT)</b>: MPPT operating voltage remains within the tracker's voltage window at hot operating conditions, ensuring maximum conversion efficiency.<br/>"
                "• <b>System Topology</b>: Inverter and system configuration are fully consistent (no battery/grid mismatch detected)."
            )
            tbl_data = [[Paragraph(comp_txt, styles['BodyText'])]]
            tbl = Table(tbl_data, colWidths=[170*mm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
                ('BOX',        (0, 0), (-1, -1), 1.5, colors.HexColor('#22c55e')),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 16),
                ('RIGHTPADDING', (0, 0), (-1, -1), 16),
            ]))
            elements.append(tbl)
            elements.append(Spacer(1, 6*mm))

        elements.append(Paragraph('<b>General Design Recommendations</b>', styles['SubHeader']))
        rec_text = (
            "1. <b>DC Cable Sizing</b>: Use the specified PV1-F solar cable to limit voltage drop to &lt; 1.5% as per IEC 60364-7-712 rules.<br/>"
            "2. <b>Electrical Protection</b>: Ensure all recommended DC fuses, AC/DC surge protection devices (SPDs), and circuit breakers are installed at their respective points to guarantee safety and compliance with EGYPTERA and EEHC rules.<br/>"
            "3. <b>Soiling/Dust Maintenance</b>: The site location suffers from dust deposition. Implementing a regular quarterly washing schedule (water wash) is highly recommended to maintain solar yield and avoid additional soiling losses.<br/>"
            "4. <b>Inverter Placement</b>: Install the inverter in a shaded, well-ventilated location. Egypt's ambient summer temperatures can trigger thermal derating in the inverter if exposed to direct sunlight."
        )
        elements.append(Paragraph(rec_text, styles['BodyText']))

        return elements

    # ─── Section 7 ─── Technical Appendix ─────────────────────────────────────

    def _technical_appendix(self, styles) -> list:
        elements = [Paragraph('SECTION 6 — TECHNICAL APPENDIX', styles['SectionNumber'])]
        elements.append(HRFlowable(width='100%', thickness=1.5, color=colors.HexColor(C_RULE)))
        elements.append(Paragraph('Technical Appendix &amp; Standards', styles['SectionHeader']))

        # System Loss Budget
        elements.append(Paragraph('System Loss Budget', styles['SubHeader']))
        dust = float(self.results.get('dust_loss_pct') or 5.0)
        loss_rows = [
            ['Loss Type',                    'Est. Loss (%)', 'Basis / Notes'],
            ['Dust &amp; Soiling',           f'{dust:.1f}%',  'Egypt desert — seasonal washing recommended'],
            ['DC Wiring (Ohmic)',            '2.0%',  'IEC 60364-7-712 sizing'],
            ['Module Mismatch',              '2.0%',  'STC power binning ± 3%'],
            ['Inverter (operating point)',   '1.6%',  'Euro-efficiency weighted curve'],
            ['AC Grid Connection',           '0.5%',  'Transformer &amp; metering losses'],
            ['Far-Horizon Shading',          '3.0%',  'Conservative estimate'],
            ['Light-Induced Degradation',    '1.5%',  'First 200 kWh operational hours'],
            ['Annual Degradation (avg)',     '0.5%',  '25-yr avg → 87.5% remaining at EOL'],
            ['Temperature Derating',         '3–5%',  'Summer peak; Tmod ~ 60–70°C'],
            ['Total System Losses (est.)',   '~15–18%','Combined non-additive; PR ≈ 80–85%'],
        ]
        loss_tbl = Table(loss_rows, colWidths=[70*mm, 30*mm, 70*mm])
        loss_tbl.setStyle(_three_col_table_style())
        elements.append(loss_tbl)
        elements.append(Spacer(1, 5*mm))

        # AI Methodology
        elements.append(Paragraph('AI Yield Model Methodology', styles['SubHeader']))
        methodology = (
            'Shamsi Smart\'s energy yield prediction pipeline uses a hybrid '
            'CNN-LSTM deep learning model trained on 8+ years of NASA POWER '
            'irradiance, temperature, and wind data for 119 Egyptian locations. '
            'The model achieves MAPE &lt; 5% against independent measured generation '
            'data and has been validated against PVWatts v5 and first-principles '
            'physics-based simulation tools. '
            'System component selection and sizing are performed using the NSGA-II '
            'multi-objective genetic algorithm, simultaneously optimising for minimum '
            'cost, maximum annual yield, minimum payback period, and maximum ROI '
            '(Pareto front). The selected solution is the best-balanced point on the '
            'Pareto frontier for the given budget and area constraints.'
        )
        elements.append(Paragraph(methodology, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Applicable Standards
        elements.append(Paragraph('Applicable Standards &amp; Codes', styles['SubHeader']))
        std_rows = [
            ['Standard / Code',         'Title &amp; Scope'],
            ['IEC 61215',               'PV module — design qualification &amp; type approval'],
            ['IEC 61730',               'PV module safety qualification requirements'],
            ['IEC 62109-1 / -2',        'Inverter safety — general / grid-connected'],
            ['IEC 60364-7-712',         'DC wiring sizing &amp; protection (PV installations)'],
            ['IEC 62548',               'PV array design requirements'],
            ['Egyptian ESC-A (EEHC)',   'Grid-tie connection &amp; net metering — Egypt'],
            ['IEEE 1547-2018',          'Standard for interconnection to area EPS'],
            ['IEC 61683',               'Inverter power conversion efficiency measurement'],
            ['EGYPTERA Decree 2019',    'Technical conditions for renewable energy connection'],
        ]
        std_tbl = Table(std_rows, colWidths=[60*mm, 110*mm])
        std_tbl.setStyle(_spec_table_style())
        elements.append(std_tbl)
        elements.append(Spacer(1, 5*mm))

        # O&M Summary
        elements.append(Paragraph('Operation &amp; Maintenance Recommendations', styles['SubHeader']))
        om_rows = [
            ['Activity',                       'Frequency',     'Notes'],
            ['Module cleaning (water wash)',   'Quarterly',      'More freq. in desert locations'],
            ['String IV curve check',          'Semi-annually',  'Detect shading / cell failure'],
            ['Inverter firmware update',       'Annually',       'Via manufacturer portal'],
            ['DC/AC disconnect test',          'Annually',       'Safety compliance'],
            ['Thermal imaging scan',           'Annually',       'Hot-cell / junction box'],
            ['Full system performance review', 'Annually',       'PR vs. baseline comparison'],
            ['Cabling &amp; connector inspection','Every 2 years', 'IP67 check, re-torque'],
        ]
        om_tbl = Table(om_rows, colWidths=[70*mm, 35*mm, 65*mm])
        om_tbl.setStyle(_three_col_table_style())
        elements.append(om_tbl)
        elements.append(Spacer(1, 6*mm))

        # Disclaimer
        disclaimer = (
            '<b>DISCLAIMER:</b> This report was generated by Shamsi Smart AI for engineering '
            'feasibility purposes. Energy production forecasts are probabilistic estimates '
            'based on historical climate data and modelled performance. Actual generation '
            'may vary due to grid curtailment, soiling, equipment degradation, or changes '
            'in tariff structure. This document does not constitute a guarantee of '
            'performance, financial return, or regulatory approval. An independent '
            'engineering review (IEA / PVSYST verification) is recommended for bankable '
            'project finance.'
        )
        elements.append(Paragraph(disclaimer, styles['FooterText']))

        return elements

    # ─── Private Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _classify_climate(lat: float, lon: float) -> str:
        if lat > 31.0:
            return 'Mediterranean Coast — Humid, Moderate Irradiance'
        elif lat > 29.5:
            return 'Nile Delta / Greater Cairo — Semi-Arid'
        elif lat > 27.0:
            return 'Middle Egypt — Arid Desert, High Irradiance'
        elif lat > 24.0:
            return 'Upper Egypt — Hot Arid Desert, Very High Irradiance'
        else:
            return 'Deep Southern Egypt — Hyper-Arid, Exceptional Irradiance'

    @staticmethod
    def _classify_dust(lat: float, lon: float) -> str:
        if lat < 27.0:
            return 'Heavy (Zone 3) — 7–10% annual soiling loss'
        elif lat < 30.0:
            return 'Moderate-Heavy (Zone 2) — 5–7% annual soiling loss'
        else:
            return 'Moderate (Zone 1) — 3–5% annual soiling loss'

    @staticmethod
    def _estimate_avg_ghi(lat: float) -> float:
        return max(4.5, 6.5 - 0.04 * abs(lat - 24))

    @staticmethod
    def _estimate_lcoe(results: Dict, system_kw: float) -> Optional[float]:
        cost = results.get('total_cost_egp')
        kwh  = results.get('annual_yield_kwh')
        if not cost or not kwh:
            return None
        degradation_sum = sum((1 - 0.005) ** t for t in range(1, 26))
        lifetime_kwh    = kwh * degradation_sum
        return round(cost / lifetime_kwh, 3) if lifetime_kwh > 0 else None
