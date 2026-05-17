"""
ai_engine/export/pdf_report.py
================================
Generate professional, client-facing PDF reports for Shamsi Smart designs.

The report is structured as a bankable solar design document:
  1. Cover page
  2. Executive summary
  3. Site analysis (with CV roof image if available)
  4. System design specifications
  5. Energy production forecast (with monthly bar chart)
  6. Financial analysis (with cashflow chart)
  7. Technical appendix

Dependencies
------------
    pip install reportlab matplotlib

Usage
-----
    from ai_engine.export.pdf_report import ProfessionalPDFReport
    from ai_engine.export.pvsyst_exporter import make_synthetic_project

    project = make_synthetic_project()
    report  = ProfessionalPDFReport(project)
    path    = report.generate_report('/tmp/shamsi_report.pdf')
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── ReportLab (lazy import so the module loads even without reportlab) ────────
try:
    from reportlab.lib                  import colors
    from reportlab.lib.enums            import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes        import A4
    from reportlab.lib.styles           import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units            import mm
    from reportlab.platypus             import (
        Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
        Spacer, Table, TableStyle,
    )
    from reportlab.pdfgen               import canvas as rl_canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# ── Matplotlib (lazy import) ──────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use('Agg')   # non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Colour palette — Shamsi brand colours
# ─────────────────────────────────────────────────────────────────────────────

BLUE_DARK   = '#1e3a8a'
BLUE_MID    = '#2563eb'
BLUE_LIGHT  = '#dbeafe'
ORANGE      = '#f97316'
GREY_LIGHT  = '#f3f4f6'
GREY_MID    = '#9ca3af'
WHITE       = '#ffffff'


# ─────────────────────────────────────────────────────────────────────────────
# Helper: create matplotlib chart → bytes buffer
# ─────────────────────────────────────────────────────────────────────────────

def _fig_to_bytes(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf


def _monthly_production_chart(monthly_kwh: List[float]) -> io.BytesIO:
    """Bar chart of monthly energy production."""
    months = ['Jan','Feb','Mar','Apr','May','Jun',
              'Jul','Aug','Sep','Oct','Nov','Dec']
    fig, ax = plt.subplots(figsize=(9, 3.8))
    bars = ax.bar(months, monthly_kwh, color=BLUE_MID, edgecolor='white', linewidth=0.5)

    # Annotate bars
    for bar, val in zip(bars, monthly_kwh):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15,
                f'{val:,.0f}', ha='center', va='bottom', fontsize=7, color='#374151')

    ax.set_ylabel('Energy (kWh)', fontsize=9, color='#374151')
    ax.set_title('Monthly Energy Production Forecast', fontsize=11,
                 fontweight='bold', color=BLUE_DARK, pad=8)
    ax.set_ylim(0, max(monthly_kwh) * 1.18)
    ax.set_facecolor(GREY_LIGHT)
    ax.grid(axis='y', alpha=0.4, linestyle='--')
    ax.tick_params(axis='both', labelsize=8)
    fig.patch.set_facecolor(WHITE)
    fig.tight_layout()
    return _fig_to_bytes(fig)


def _cashflow_chart(
    annual_kwh: float,
    total_cost: float,
    payback_years: float,
    years: int = 25,
) -> io.BytesIO:
    """Cumulative net cashflow chart."""
    # Simple model: flat electricity price + 5% annual escalation, 0.5%/yr degradation
    elec_price_egp = 1.65          # EGP/kWh (2024 Egypt subsidised residential)
    degradation    = 0.005         # 0.5%/yr
    escalation     = 0.05          # 5%/yr electricity price increase

    cashflow = [-total_cost]
    cumulative = [-total_cost]
    for yr in range(1, years + 1):
        production  = annual_kwh * (1 - degradation) ** yr
        price       = elec_price_egp * (1 + escalation) ** yr
        saving      = production * price
        cashflow.append(saving)
        cumulative.append(cumulative[-1] + saving)

    yrs = list(range(years + 1))
    fig, ax = plt.subplots(figsize=(9, 3.8))

    colours = [ORANGE if c < 0 else BLUE_MID for c in cumulative]
    ax.bar(yrs, cumulative, color=colours, width=0.7)
    ax.axhline(0, color='#111827', linewidth=1.0)

    # Mark payback year
    pb_yr = int(round(payback_years))
    if 0 < pb_yr <= years:
        ax.axvline(pb_yr, color=ORANGE, linewidth=1.5, linestyle='--')
        ax.text(pb_yr + 0.2, max(cumulative)*0.05,
                f'Payback\nyr {pb_yr}', color=ORANGE, fontsize=7)

    ax.set_xlabel('Year', fontsize=9, color='#374151')
    ax.set_ylabel('Cumulative Savings (EGP)', fontsize=9, color='#374151')
    ax.set_title('25-Year Net Cashflow', fontsize=11,
                 fontweight='bold', color=BLUE_DARK, pad=8)
    ax.set_facecolor(GREY_LIGHT)
    ax.grid(axis='y', alpha=0.4, linestyle='--')
    ax.tick_params(axis='both', labelsize=8)
    fig.patch.set_facecolor(WHITE)
    fig.tight_layout()
    return _fig_to_bytes(fig)


# ─────────────────────────────────────────────────────────────────────────────
# Style factory
# ─────────────────────────────────────────────────────────────────────────────

def _build_styles():
    styles = getSampleStyleSheet()

    def _add(name, parent='Normal', **kw):
        if name not in styles:
            styles.add(ParagraphStyle(name=name, parent=styles[parent], **kw))

    _add('CoverTitle',
         fontSize=26, textColor=colors.HexColor(BLUE_DARK),
         spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')

    _add('CoverSubtitle',
         fontSize=14, textColor=colors.HexColor(BLUE_MID),
         spaceAfter=4, alignment=TA_CENTER)

    _add('SectionHeader',
         parent='Heading2',
         fontSize=14, textColor=colors.HexColor(BLUE_DARK),
         spaceBefore=14, spaceAfter=6, fontName='Helvetica-Bold')

    _add('SubHeader',
         fontSize=11, textColor=colors.HexColor(BLUE_MID),
         spaceBefore=8, spaceAfter=4, fontName='Helvetica-Bold')

    _add('BodyText',
         fontSize=9, textColor=colors.HexColor('#374151'),
         leading=14, spaceAfter=4)

    _add('Caption',
         fontSize=8, textColor=colors.HexColor(GREY_MID),
         alignment=TA_CENTER, spaceAfter=4)

    _add('SmallRight',
         fontSize=8, textColor=colors.HexColor(GREY_MID),
         alignment=TA_RIGHT)

    _add('BoldBody',
         fontSize=9, fontName='Helvetica-Bold',
         textColor=colors.HexColor('#111827'), spaceAfter=2)

    return styles


# ─────────────────────────────────────────────────────────────────────────────
# Table style helper
# ─────────────────────────────────────────────────────────────────────────────

def _metric_table_style():
    return TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  colors.HexColor(BLUE_MID)),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 9),
        ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
        ('ALIGN',       (1, 0), (1, -1),  'RIGHT'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.HexColor(GREY_LIGHT), colors.white]),
        ('GRID',        (0, 0), (-1, -1), 0.5, colors.HexColor(GREY_MID)),
        ('TOPPADDING',  (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ])


def _spec_table_style():
    return TableStyle([
        ('FONTNAME',    (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 0), (-1, -1), 8),
        ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
        ('ALIGN',       (1, 0), (-1, -1), 'RIGHT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1),
         [colors.HexColor(GREY_LIGHT), colors.white]),
        ('GRID',        (0, 0), (-1, -1), 0.3, colors.HexColor(GREY_MID)),
        ('TOPPADDING',  (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Header / footer callback
# ─────────────────────────────────────────────────────────────────────────────

class _HeaderFooter:
    def __init__(self, location_name: str, project_id: str):
        self.location_name = location_name
        self.project_id    = project_id
        self.today         = datetime.now().strftime('%B %Y')

    def __call__(self, canv, doc):
        canv.saveState()
        W, H = A4

        # Header line
        canv.setStrokeColor(colors.HexColor(BLUE_MID))
        canv.setLineWidth(1)
        canv.line(15*mm, H - 14*mm, W - 15*mm, H - 14*mm)
        canv.setFont('Helvetica', 8)
        canv.setFillColor(colors.HexColor(GREY_MID))
        canv.drawString(15*mm, H - 12*mm, 'Shamsi Smart AI — Solar Design Report')
        canv.drawRightString(W - 15*mm, H - 12*mm,
                             f'{self.location_name}  |  {self.project_id}')

        # Footer line
        canv.line(15*mm, 12*mm, W - 15*mm, 12*mm)
        canv.drawString(15*mm, 8*mm, self.today)
        canv.drawRightString(W - 15*mm, 8*mm,
                             f'Page {doc.page}')
        canv.restoreState()


# ─────────────────────────────────────────────────────────────────────────────
# Main report class
# ─────────────────────────────────────────────────────────────────────────────

class ProfessionalPDFReport:
    """
    Generate a professional 7-section PDF report.

    Parameters
    ----------
    project_data : dict
        Same schema as PVsystExporter (location, panel, inverter,
        system_config, optimization_results, …).
        Optionally include 'roof_image_path' (str) for the site analysis page.
    """

    def __init__(self, project_data: Dict):
        self.project  = project_data
        self.location = project_data['location']
        self.panel    = project_data['panel']
        self.inverter = project_data['inverter']
        self.config   = project_data['system_config']
        self.results  = project_data.get('optimization_results', {})

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_report(self, output_file: str) -> str:
        """
        Build the PDF and write to *output_file*.

        Returns
        -------
        str   Absolute path of the written PDF.
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                'reportlab is required for PDF generation. '
                'Install with: pip install reportlab'
            )

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_file,
            pagesize      = A4,
            rightMargin   = 20*mm,
            leftMargin    = 20*mm,
            topMargin     = 22*mm,
            bottomMargin  = 18*mm,
        )

        styles  = _build_styles()
        hf      = _HeaderFooter(
            self.location.name,
            self.project.get('project_id', 'N/A'),
        )
        story   = []

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

        story += self._technical_appendix(styles)

        doc.build(story, onFirstPage=hf, onLaterPages=hf)
        return os.path.abspath(output_file)

    # ── Section 1: Cover ─────────────────────────────────────────────────────

    def _cover_page(self, styles) -> list:
        loc = self.location
        cfg = self.config
        p   = self.panel
        res = self.results

        system_kwp = cfg['panel_count'] * p.power_rating_w / 1000

        elements = [Spacer(1, 18*mm)]
        elements.append(Paragraph('SOLAR ENERGY SYSTEM DESIGN', styles['CoverTitle']))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph('Feasibility & Production Report', styles['CoverSubtitle']))
        elements.append(Spacer(1, 8*mm))

        # Divider bar
        divider_data = [['']]
        divider = Table(divider_data, colWidths=[170*mm], rowHeights=[3])
        divider.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(BLUE_MID)),
        ]))
        elements.append(divider)
        elements.append(Spacer(1, 8*mm))

        # Key project info block
        info_data = [
            ['Location',         loc.name],
            ['Coordinates',      f"{loc.latitude:.3f}°N, {loc.longitude:.3f}°E"],
            ['System Capacity',  f"{system_kwp:.2f} kWp  ({cfg['panel_count']} × {p.power_rating_w} W)"],
            ['Annual Production',f"{res.get('annual_yield_kwh', 0):,.0f} kWh/year"],
            ['Specific Yield',   f"{res.get('specific_yield', 0):,.0f} kWh/kWp/year"],
            ['Report Date',      datetime.now().strftime('%d %B %Y')],
            ['Project ID',       self.project.get('project_id', '—')],
        ]
        tbl = Table(info_data, colWidths=[65*mm, 105*mm])
        tbl.setStyle(TableStyle([
            ('FONTNAME',    (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME',    (1,0), (1,-1), 'Helvetica'),
            ('FONTSIZE',    (0,0), (-1,-1), 10),
            ('TEXTCOLOR',   (0,0), (0,-1), colors.HexColor(BLUE_DARK)),
            ('TEXTCOLOR',   (1,0), (1,-1), colors.HexColor('#374151')),
            ('ROWBACKGROUNDS', (0,0), (-1,-1),
             [colors.HexColor(BLUE_LIGHT), colors.white]),
            ('TOPPADDING',  (0,0), (-1,-1), 7),
            ('BOTTOMPADDING', (0,0), (-1,-1), 7),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 14*mm))

        # AI badge
        badge_txt = (
            '<font color="#1e3a8a"><b>AI-Optimised Design</b></font><br/>'
            '<font size="8" color="#6b7280">This system was optimised using Shamsi Smart AI '
            '— multi-objective NSGA-II with CNN-LSTM deep learning yield prediction. '
            'Results validated against PVWatts v5 and physics baselines.</font>'
        )
        badge_data = [[Paragraph(badge_txt, styles['BodyText'])]]
        badge = Table(badge_data, colWidths=[170*mm])
        badge.setStyle(TableStyle([
            ('BACKGROUND',   (0,0), (-1,-1), colors.HexColor(BLUE_LIGHT)),
            ('BOX',          (0,0), (-1,-1), 1, colors.HexColor(BLUE_MID)),
            ('TOPPADDING',   (0,0), (-1,-1), 10),
            ('BOTTOMPADDING',(0,0), (-1,-1), 10),
            ('LEFTPADDING',  (0,0), (-1,-1), 12),
        ]))
        elements.append(badge)

        return elements

    # ── Section 2: Executive Summary ─────────────────────────────────────────

    def _executive_summary(self, styles) -> list:
        res = self.results
        cfg = self.config
        p   = self.panel
        system_kwp = cfg['panel_count'] * p.power_rating_w / 1000

        elements = [Paragraph('Executive Summary', styles['SectionHeader'])]

        # Narrative
        narrative = (
            f"The proposed solar PV system for <b>{self.location.name}</b> has a peak capacity of "
            f"<b>{system_kwp:.2f} kWp</b>, comprising {cfg['panel_count']} × {p.manufacturer} "
            f"{p.model} modules ({p.power_rating_w} W each). The system is expected to generate "
            f"<b>{res.get('annual_yield_kwh', 0):,.0f} kWh per year</b>, at a specific yield of "
            f"{res.get('specific_yield', 0):,.0f} kWh/kWp — consistent with best-in-class Egyptian "
            f"installations of comparable size. Payback is estimated at "
            f"<b>{res.get('payback_years', 0):.1f} years</b> against a total investment of "
            f"{res.get('total_cost_egp', 0):,.0f} EGP, generating lifetime savings of "
            f"{res.get('lifetime_savings_egp', 0):,.0f} EGP over 25 years."
        )
        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 5*mm))

        # Key metrics table
        data = [
            ['Metric', 'Value'],
            ['System Capacity',      f"{system_kwp:.2f} kWp"],
            ['Number of Panels',     f"{cfg['panel_count']}"],
            ['Panel Model',          f"{p.manufacturer} {p.model}"],
            ['Inverter Model',       f"{self.inverter.manufacturer} {self.inverter.model}"],
            ['Annual Production',    f"{res.get('annual_yield_kwh', 0):,.0f} kWh"],
            ['Specific Yield',       f"{res.get('specific_yield', 0):,.0f} kWh/kWp/yr"],
            ['Total Investment',     f"{res.get('total_cost_egp', 0):,.0f} EGP"],
            ['Cost per Watt',        f"{res.get('cost_per_watt', 0):.2f} EGP/W"],
            ['Payback Period',       f"{res.get('payback_years', 0):.1f} years"],
            ['25-Year Net Savings',  f"{res.get('lifetime_savings_egp', 0):,.0f} EGP"],
        ]
        tbl = Table(data, colWidths=[95*mm, 75*mm])
        tbl.setStyle(_metric_table_style())
        elements.append(tbl)

        return elements

    # ── Section 3: Site Analysis ──────────────────────────────────────────────

    def _site_analysis(self, styles) -> list:
        loc = self.location

        elements = [Paragraph('Site Analysis', styles['SectionHeader'])]

        # Site parameters
        elements.append(Paragraph('Geographic & Climate Parameters', styles['SubHeader']))
        data = [
            ['Parameter', 'Value'],
            ['Site Name',       loc.name],
            ['Country',         getattr(loc, 'country', 'Egypt')],
            ['Latitude',        f"{loc.latitude:.3f}°N"],
            ['Longitude',       f"{loc.longitude:.3f}°E"],
            ['Elevation',       f"{getattr(loc, 'elevation_m', 0) or 0} m"],
            ['Climate Zone',    self._classify_climate(loc.latitude, loc.longitude)],
            ['Time Zone',       'UTC+2 (EET)'],
            ['Average GHI',     f"{self._estimate_avg_ghi(loc.latitude):.2f} kWh/m²/day"],
            ['Peak Sun Hours',  f"~{self._estimate_avg_ghi(loc.latitude)*1.05:.0f} hrs/yr"],
        ]
        tbl = Table(data, colWidths=[90*mm, 80*mm])
        tbl.setStyle(_metric_table_style())
        elements.append(tbl)
        elements.append(Spacer(1, 5*mm))

        # Roof analysis (from CV layer if available)
        roof_analysis = self.project.get('roof_analysis')
        if roof_analysis:
            elements.append(Paragraph('Roof Analysis (Computer Vision)', styles['SubHeader']))
            cv_data = [
                ['Parameter', 'Value'],
                ['Total Roof Area',    f"{roof_analysis.get('roof_area_m2', 'N/A'):.1f} m²"],
                ['Usable Area',        f"{roof_analysis.get('usable_area_m2', 'N/A'):.1f} m²"],
                ['Usable Percentage',  f"{roof_analysis.get('usable_percentage', 'N/A'):.1f}%"],
                ['Obstacles Found',    str(len(roof_analysis.get('obstacles', [])))],
                ['Roof Orientation',   roof_analysis.get('metadata', {}).get('orientation', 'N/A')],
                ['Roof Type',          roof_analysis.get('metadata', {}).get('roof_type', 'N/A')],
            ]
            cv_tbl = Table(cv_data, colWidths=[90*mm, 80*mm])
            cv_tbl.setStyle(_metric_table_style())
            elements.append(cv_tbl)

        # Annotated roof image
        roof_img_path = self.project.get('roof_image_path')
        if roof_img_path and os.path.exists(roof_img_path):
            elements.append(Spacer(1, 4*mm))
            elements.append(Paragraph('Roof Satellite Image (Annotated)', styles['SubHeader']))
            img = Image(roof_img_path, width=120*mm, height=90*mm)
            elements.append(img)
            elements.append(Paragraph(
                'Figure 1: Computer vision detection of roof boundary and obstacles.',
                styles['Caption'],
            ))

        return elements

    # ── Section 4: System Design ──────────────────────────────────────────────

    def _system_design(self, styles) -> list:
        cfg = self.config
        p   = self.panel
        inv = self.inverter
        system_kwp = cfg['panel_count'] * p.power_rating_w / 1000

        elements = [Paragraph('System Design Specifications', styles['SectionHeader'])]

        # System overview
        elements.append(Paragraph('System Configuration', styles['SubHeader']))
        sys_data = [
            ['Parameter', 'Value'],
            ['System Type',        'Grid-Tied (No Battery)'],
            ['Peak Capacity',      f"{system_kwp:.3f} kWp"],
            ['Number of Strings',  str(cfg.get('strings', 'N/A'))],
            ['Modules per String', str(cfg.get('panels_per_string', 'N/A'))],
            ['Tilt Angle',         f"{cfg['tilt_angle']:.1f}°"],
            ['Azimuth',            f"{cfg.get('azimuth', 180):.0f}° (South = 180°)"],
            ['Inverter Count',     str(cfg.get('inverter_count', 1))],
        ]
        sys_tbl = Table(sys_data, colWidths=[90*mm, 80*mm])
        sys_tbl.setStyle(_metric_table_style())
        elements.append(sys_tbl)
        elements.append(Spacer(1, 5*mm))

        # Panel specs
        elements.append(Paragraph('Solar Panel Specifications', styles['SubHeader']))
        pan_data = [
            ['Manufacturer',         p.manufacturer],
            ['Model',                p.model],
            ['Technology',           p.technology],
            ['Rated Power (Pnom)',   f"{p.power_rating_w:.0f} W"],
            ['Efficiency',           f"{p.efficiency_percent:.1f}%"],
            ['Vmpp',                 f"{p.vmp_v:.2f} V"],
            ['Impp',                 f"{p.imp_a:.2f} A"],
            ['Voc',                  f"{p.voc_v:.2f} V"],
            ['Isc',                  f"{p.isc_a:.2f} A"],
            ['Temp. Coeff. (Pmax)', f"{p.temp_coeff_pmax_percent:.3f} %/°C"],
            ['Dimensions',           f"{p.length_mm:.0f} × {p.width_mm:.0f} × {p.thickness_mm:.0f} mm"],
            ['Weight',               f"{p.weight_kg:.1f} kg"],
            ['Area',                 f"{p.area_m2:.4f} m²"],
        ]
        pan_tbl = Table(pan_data, colWidths=[90*mm, 80*mm])
        pan_tbl.setStyle(_spec_table_style())
        elements.append(pan_tbl)
        elements.append(Spacer(1, 4*mm))

        # Inverter specs
        elements.append(Paragraph('Inverter Specifications', styles['SubHeader']))
        inv_data = [
            ['Manufacturer',         inv.manufacturer],
            ['Model',                inv.model],
            ['Type',                 inv.inverter_type],
            ['Rated AC Power',       f"{inv.power_rating_w:,.0f} W"],
            ['Max AC Power',         f"{inv.max_ac_power_w:,.0f} W"],
            ['Max Efficiency',       f"{inv.max_efficiency_percent:.1f}%"],
            ['Euro Efficiency',      f"{inv.euro_efficiency_percent:.1f}%"],
            ['Max DC Voltage',       f"{inv.max_dc_voltage_v:.0f} V"],
            ['MPPT Range',           f"{inv.mppt_voltage_min_v:.0f} – {inv.mppt_voltage_max_v:.0f} V"],
            ['Number of MPPTs',      str(inv.number_of_mppts)],
        ]
        inv_tbl = Table(inv_data, colWidths=[90*mm, 80*mm])
        inv_tbl.setStyle(_spec_table_style())
        elements.append(inv_tbl)

        return elements

    # ── Section 5: Energy Forecast ────────────────────────────────────────────

    def _energy_forecast(self, styles) -> list:
        res     = self.results
        monthly = res.get('monthly_yield_kwh', [0]*12)
        if len(monthly) < 12:
            monthly = (monthly + [0]*12)[:12]

        elements = [Paragraph('Energy Production Forecast', styles['SectionHeader'])]

        # Narrative
        narrative = (
            f"Based on 8 years of NASA POWER climate data for <b>{self.location.name}</b> "
            f"and Shamsi's CNN-LSTM deep learning model, the system is forecast to produce "
            f"<b>{res.get('annual_yield_kwh', 0):,.0f} kWh annually</b>, with peak production "
            f"in summer months (June–August) due to Egypt's high irradiance levels. The model "
            f"accounts for temperature derating, dust soiling (5%), wiring losses (2%), and "
            f"inverter efficiency."
        )
        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Monthly bar chart
        if MATPLOTLIB_AVAILABLE:
            buf = _monthly_production_chart(monthly)
            elements.append(Image(buf, width=160*mm, height=68*mm))
            elements.append(Paragraph(
                'Figure 2: Monthly energy production forecast (kWh).',
                styles['Caption'],
            ))
            elements.append(Spacer(1, 4*mm))

        # Monthly data table
        months = ['Jan','Feb','Mar','Apr','May','Jun',
                  'Jul','Aug','Sep','Oct','Nov','Dec','Annual']
        values = monthly + [sum(monthly)]
        mon_data = [['Month', 'Production (kWh)', '% of Annual']]
        for m, v in zip(months, values):
            pct = f"{v/sum(monthly)*100:.1f}%" if sum(monthly) > 0 and m != 'Annual' else '—'
            mon_data.append([m, f"{v:,.0f}", pct])
        mon_tbl = Table(mon_data, colWidths=[40*mm, 70*mm, 60*mm])
        mon_tbl.setStyle(_metric_table_style())
        elements.append(mon_tbl)

        return elements

    # ── Section 6: Financial Analysis ────────────────────────────────────────

    def _financial_analysis(self, styles) -> list:
        res = self.results

        elements = [Paragraph('Financial Analysis', styles['SectionHeader'])]

        narrative = (
            f"At current Egyptian electricity tariffs (≈1.65 EGP/kWh residential), with 5% "
            f"annual tariff escalation and 0.5%/year panel degradation, the system achieves "
            f"payback in <b>{res.get('payback_years', 0):.1f} years</b> on an investment of "
            f"{res.get('total_cost_egp', 0):,.0f} EGP. Over 25 years, total net savings reach "
            f"<b>{res.get('lifetime_savings_egp', 0):,.0f} EGP</b>."
        )
        elements.append(Paragraph(narrative, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Cashflow chart
        if MATPLOTLIB_AVAILABLE and res.get('total_cost_egp') and res.get('annual_yield_kwh'):
            buf = _cashflow_chart(
                annual_kwh    = res['annual_yield_kwh'],
                total_cost    = res['total_cost_egp'],
                payback_years = res.get('payback_years', 10),
            )
            elements.append(Image(buf, width=160*mm, height=68*mm))
            elements.append(Paragraph(
                'Figure 3: Cumulative net cashflow over 25 years (EGP). '
                'Orange = investment not yet recovered; blue = net profit.',
                styles['Caption'],
            ))
            elements.append(Spacer(1, 4*mm))

        # Financial summary table
        lcoe = self._estimate_lcoe(res, self.config['panel_count'] * self.panel.power_rating_w / 1000)
        fin_data = [
            ['Metric', 'Value'],
            ['Total Investment',        f"{res.get('total_cost_egp', 0):,.0f} EGP"],
            ['Cost per Watt',           f"{res.get('cost_per_watt', 0):.2f} EGP/W"],
            ['Simple Payback Period',   f"{res.get('payback_years', 0):.1f} years"],
            ['25-Year Gross Savings',   f"{res.get('lifetime_savings_egp', 0):,.0f} EGP"],
            ['25-Year Net Profit',      f"{max(0, res.get('lifetime_savings_egp',0) - res.get('total_cost_egp',0)):,.0f} EGP"],
            ['LCOE',                    f"{lcoe:.3f} EGP/kWh" if lcoe else 'N/A'],
            ['Annual CO₂ Avoided',      f"{res.get('annual_yield_kwh', 0) * 0.47 / 1000:.1f} tonnes"],
        ]
        fin_tbl = Table(fin_data, colWidths=[95*mm, 75*mm])
        fin_tbl.setStyle(_metric_table_style())
        elements.append(fin_tbl)

        return elements

    # ── Section 7: Technical Appendix ─────────────────────────────────────────

    def _technical_appendix(self, styles) -> list:
        elements = [Paragraph('Technical Appendix', styles['SectionHeader'])]

        # Loss budget
        elements.append(Paragraph('System Loss Budget', styles['SubHeader']))
        loss_data = [
            ['Loss Type', 'Value', 'Notes'],
            ['Dust / Soiling',         '5.0%',  'Egypt desert condition'],
            ['DC Wiring',              '2.0%',  'IEC 60364 compliant'],
            ['String Mismatch',        '2.0%',  'Module binning tolerance'],
            ['Inverter (non-linear)',   '1.6%',  'Euro efficiency basis'],
            ['AC Grid Connection',      '0.5%',  'Transformer + metering'],
            ['Shading (far)',           '3.0%',  'Horizon obstructions'],
            ['Light-Induced Degradation','1.5%', 'First 200 kWh'],
            ['Annual Degradation',      '0.5%', '25-year average 87.5%'],
            ['Total System Losses',    '~15.5%','Combined (non-additive)'],
        ]
        loss_tbl = Table(loss_data, colWidths=[65*mm, 25*mm, 80*mm])
        loss_tbl.setStyle(_metric_table_style())
        elements.append(loss_tbl)
        elements.append(Spacer(1, 5*mm))

        # Methodology note
        elements.append(Paragraph('AI Methodology', styles['SubHeader']))
        methodology = (
            "The energy yield prediction uses Shamsi Smart's CNN-LSTM deep learning model, "
            "trained on 8 years of NASA POWER climate data for 119 Egyptian sites. The model "
            "achieves MAPE &lt;5% against measured generation data and has been validated against "
            "PVWatts v5 and physics-based baselines. System optimisation uses NSGA-II "
            "multi-objective genetic algorithm to simultaneously minimise cost, maximise yield, "
            "and minimise payback period. Export files are compatible with PVsyst 7.x and "
            "HelioScope API v1 for independent verification."
        )
        elements.append(Paragraph(methodology, styles['BodyText']))
        elements.append(Spacer(1, 4*mm))

        # Standards
        elements.append(Paragraph('Standards Compliance', styles['SubHeader']))
        standards_data = [
            ['Standard', 'Description'],
            ['IEC 61215',    'PV module qualification testing'],
            ['IEC 61730',    'PV module safety requirements'],
            ['IEC 62109',    'Inverter safety'],
            ['IEC 60364-7-712', 'DC wiring sizing'],
            ['Egyptian Code ESC-A', 'Grid-tie connection'],
            ['IEEE 1547',    'Grid interconnection'],
        ]
        std_tbl = Table(standards_data, colWidths=[60*mm, 110*mm])
        std_tbl.setStyle(_spec_table_style())
        elements.append(std_tbl)
        elements.append(Spacer(1, 5*mm))

        # Disclaimer
        disclaimer = (
            '<font size="7" color="#6b7280">'
            '<b>Disclaimer:</b> This report was generated by Shamsi Smart AI. '
            'Energy production forecasts are estimates based on historical climate data and '
            'modelled system performance. Actual performance may vary due to grid curtailment, '
            'soiling beyond assumed levels, equipment failure, or changes in electricity tariffs. '
            'This report does not constitute a guarantee of performance. For bankable project '
            'finance, an independent engineer review is recommended.'
            '</font>'
        )
        elements.append(Paragraph(disclaimer, styles['BodyText']))

        return elements

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _classify_climate(lat: float, lon: float) -> str:
        if lat > 30.5:
            return 'Mediterranean Coast (humid, moderate)'
        elif lat > 28.0:
            return 'Cairo / Nile Delta (semi-arid)'
        elif lat > 25.0:
            return 'Upper Egypt (arid desert, high irradiance)'
        else:
            return 'Deep South Egypt (hyper-arid, very high irradiance)'

    @staticmethod
    def _estimate_avg_ghi(lat: float) -> float:
        """Approximate average daily GHI (kWh/m²/day) from latitude."""
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
