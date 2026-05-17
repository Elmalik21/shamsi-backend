"""
ai_engine/export/excel_exporter.py
=====================================
Export Shamsi Smart design results to a formatted Excel workbook.

Sheets produced
---------------
  1. Summary              — key KPIs with conditional formatting
  2. System Design        — full equipment specifications
  3. Monthly Production   — 12-month table + embedded bar chart
  4. Financial Analysis   — 25-year cashflow table + summary
  5. Equipment Specs      — panel and inverter data in detail
  6. Climate Data         — monthly climate summary (if available)

Dependencies
------------
    pip install openpyxl

Usage
-----
    from ai_engine.export.excel_exporter import ExcelExporter
    from ai_engine.export.pvsyst_exporter import make_synthetic_project

    project = make_synthetic_project()
    exp     = ExcelExporter(project)
    path    = exp.export_workbook('/tmp/shamsi_project.xlsx')
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.chart.series import SeriesLabel
    from openpyxl.styles import (
        Alignment, Border, Fill, Font, GradientFill, PatternFill, Side,
    )
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import ColorScaleRule, DataBarRule
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Colour constants (hex, no leading #)
# ─────────────────────────────────────────────────────────────────────────────

C_BLUE_DARK  = '1e3a8a'
C_BLUE_MID   = '2563eb'
C_BLUE_LIGHT = 'dbeafe'
C_ORANGE     = 'f97316'
C_GREEN      = '16a34a'
C_RED        = 'dc2626'
C_GREY       = 'f3f4f6'
C_WHITE      = 'ffffff'
C_BLACK      = '111827'
C_GREY_TXT   = '6b7280'


# ─────────────────────────────────────────────────────────────────────────────
# Style helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fill(hex_colour: str) -> PatternFill:
    return PatternFill(fill_type='solid', fgColor=hex_colour)


def _font(bold=False, size=11, colour=C_BLACK, italic=False) -> Font:
    return Font(bold=bold, size=size, color=colour, italic=italic,
                name='Calibri')


def _align(horiz='left', vert='center', wrap=False) -> Alignment:
    return Alignment(horizontal=horiz, vertical=vert, wrap_text=wrap)


def _thin_border() -> Border:
    s = Side(style='thin', color='D1D5DB')
    return Border(left=s, right=s, top=s, bottom=s)


def _header_style(ws, row: int, cols: int,
                  hex_bg: str = C_BLUE_MID, text_col: str = C_WHITE,
                  font_size: int = 11) -> None:
    """Apply header row styling across *cols* columns starting at column 1."""
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill      = _fill(hex_bg)
        cell.font      = _font(bold=True, size=font_size, colour=text_col)
        cell.alignment = _align('center')
        cell.border    = _thin_border()


def _data_row_style(ws, row: int, cols: int, even: bool) -> None:
    bg = C_GREY if even else C_WHITE
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill      = _fill(bg)
        cell.font      = _font(size=10)
        cell.alignment = _align()
        cell.border    = _thin_border()


def _kpi_block(ws, start_row: int, label: str, value: str,
               bg: str = C_BLUE_LIGHT, label_col: int = 1) -> None:
    """Write a two-cell KPI block (label | value)."""
    lc = ws.cell(row=start_row, column=label_col, value=label)
    lc.font      = _font(bold=True, size=10, colour=C_BLUE_DARK)
    lc.fill      = _fill(bg)
    lc.alignment = _align()
    lc.border    = _thin_border()

    vc = ws.cell(row=start_row, column=label_col + 1, value=value)
    vc.font      = _font(size=10, colour=C_BLACK)
    vc.fill      = _fill(C_WHITE)
    vc.alignment = _align('right')
    vc.border    = _thin_border()


def _set_col_widths(ws, widths: Dict[int, float]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w


def _merge_title(ws, row: int, start_col: int, end_col: int,
                 text: str, bg: str = C_BLUE_DARK, font_size: int = 14) -> None:
    ws.merge_cells(
        start_row=row, start_column=start_col,
        end_row=row,   end_column=end_col,
    )
    cell = ws.cell(row=row, column=start_col, value=text)
    cell.font      = _font(bold=True, size=font_size, colour=C_WHITE)
    cell.fill      = _fill(bg)
    cell.alignment = _align('center')


# ─────────────────────────────────────────────────────────────────────────────
# Main exporter
# ─────────────────────────────────────────────────────────────────────────────

class ExcelExporter:
    """
    Export a Shamsi Smart project to a formatted multi-sheet Excel workbook.

    Parameters
    ----------
    project_data : dict
        Same schema as PVsystExporter.
    """

    MONTHS = ['January','February','March','April','May','June',
              'July','August','September','October','November','December']
    MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun',
                    'Jul','Aug','Sep','Oct','Nov','Dec']

    def __init__(self, project_data: Dict):
        self.project  = project_data
        self.location = project_data['location']
        self.panel    = project_data['panel']
        self.inverter = project_data['inverter']
        self.config   = project_data['system_config']
        self.results  = project_data.get('optimization_results', {})

    # ── Public API ────────────────────────────────────────────────────────────

    def export_workbook(self, output_file: str) -> str:
        """
        Write formatted Excel workbook to *output_file*.

        Returns
        -------
        str   Absolute path of the written file.
        """
        if not OPENPYXL_AVAILABLE:
            raise ImportError(
                'openpyxl is required for Excel export. '
                'Install with: pip install openpyxl'
            )

        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        wb.remove(wb.active)   # remove default blank sheet

        self._sheet_summary(wb)
        self._sheet_system_design(wb)
        self._sheet_monthly_production(wb)
        self._sheet_financial_analysis(wb)
        self._sheet_equipment_specs(wb)
        self._sheet_climate_summary(wb)

        # Workbook properties
        wb.properties.title   = f"Shamsi Smart — {self.location.name}"
        wb.properties.creator = "Shamsi Smart AI"
        wb.properties.subject = "Solar PV Design Export"

        wb.save(output_file)
        return os.path.abspath(output_file)

    def export_csv(self, output_file: str) -> str:
        """
        Export a simple CSV with monthly production data.

        Returns
        -------
        str  Absolute path of the written file.
        """
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        monthly = self.results.get('monthly_yield_kwh', [0]*12)
        if len(monthly) < 12:
            monthly = (monthly + [0]*12)[:12]

        lines = ['Month,Production_kWh,Percentage']
        total = sum(monthly)
        for i, (m, v) in enumerate(zip(self.MONTHS, monthly)):
            pct = f"{v/total*100:.1f}" if total > 0 else '0.0'
            lines.append(f"{m},{v:.1f},{pct}")
        lines.append(f"Annual,{total:.1f},100.0")

        with open(output_file, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(lines))
        return os.path.abspath(output_file)

    # ── Sheet 1: Summary ─────────────────────────────────────────────────────

    def _sheet_summary(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('Summary', 0)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 30, 2: 24, 3: 4, 4: 30, 5: 24})

        res = self.results
        cfg = self.config
        p   = self.panel
        loc = self.location
        sys_kwp = cfg['panel_count'] * p.power_rating_w / 1000

        # Title block
        _merge_title(ws, 1, 1, 5, 'SHAMSI SMART AI — SOLAR DESIGN SUMMARY')
        _merge_title(ws, 2, 1, 5,
                     f"{loc.name}  |  {sys_kwp:.2f} kWp  |  "
                     f"Generated {datetime.now().strftime('%d %B %Y')}",
                     bg=C_BLUE_LIGHT, font_size=11)
        ws.cell(row=2, column=1).font = _font(size=11, colour=C_BLUE_DARK, italic=True)

        row = 4
        # Left column KPIs
        left_kpis = [
            ('Location',              loc.name),
            ('Latitude / Longitude',  f"{loc.latitude:.3f}°N, {loc.longitude:.3f}°E"),
            ('System Capacity',       f"{sys_kwp:.3f} kWp"),
            ('Number of Panels',      str(cfg['panel_count'])),
            ('Panel Model',           f"{p.manufacturer} {p.model}"),
            ('Inverter Model',        f"{self.inverter.manufacturer} {self.inverter.model}"),
            ('Tilt / Azimuth',        f"{cfg['tilt_angle']}° / {cfg.get('azimuth', 180)}°"),
        ]
        for label, value in left_kpis:
            _kpi_block(ws, row, label, value, label_col=1)
            row += 1

        row = 4
        # Right column KPIs
        right_kpis = [
            ('Annual Production',     f"{res.get('annual_yield_kwh', 0):,.0f} kWh"),
            ('Specific Yield',        f"{res.get('specific_yield', 0):,.0f} kWh/kWp/yr"),
            ('Total Investment',      f"{res.get('total_cost_egp', 0):,.0f} EGP"),
            ('Cost per Watt',         f"{res.get('cost_per_watt', 0):.2f} EGP/W"),
            ('Simple Payback',        f"{res.get('payback_years', 0):.1f} years"),
            ('25-Year Net Savings',   f"{res.get('lifetime_savings_egp', 0):,.0f} EGP"),
            ('CO₂ Avoided / Year',    f"{res.get('annual_yield_kwh', 0) * 0.47 / 1000:.1f} tonnes"),
        ]
        for label, value in right_kpis:
            _kpi_block(ws, row, label, value, label_col=4)
            row += 1

        # Footer
        row += 2
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
        cell = ws.cell(row=row, column=1,
                       value='Generated by Shamsi Smart AI — NSGA-II Multi-Objective Optimisation '
                             'with CNN-LSTM Yield Prediction')
        cell.font      = _font(size=9, colour=C_GREY_TXT, italic=True)
        cell.alignment = _align('center')

    # ── Sheet 2: System Design ────────────────────────────────────────────────

    def _sheet_system_design(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('System Design', 1)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 32, 2: 28})

        _merge_title(ws, 1, 1, 2, 'System Design Parameters')

        rows = [
            ('SYSTEM CONFIGURATION', None),
            ('System Type',         'Grid-Tied (No Battery)'),
            ('Peak DC Capacity',    f"{self.config['panel_count'] * self.panel.power_rating_w / 1000:.3f} kWp"),
            ('Number of Strings',   str(self.config.get('strings', 'N/A'))),
            ('Modules / String',    str(self.config.get('panels_per_string', 'N/A'))),
            ('Tilt Angle',          f"{self.config['tilt_angle']:.1f}°"),
            ('Azimuth',             f"{self.config.get('azimuth', 180):.0f}° (South=180°)"),
            ('Inverter Count',      str(self.config.get('inverter_count', 1))),
            (None, None),
            ('LOSS ASSUMPTIONS', None),
            ('Dust / Soiling',      '5.0%'),
            ('DC Wiring',           '2.0%'),
            ('Mismatch',            '2.0%'),
            ('Inverter',            '~1.6%'),
            ('Shading',             f"{self.project.get('shading_loss_pct', 3.0):.1f}%"),
            ('Light-Induced Degradation', '1.5%'),
            ('Annual Degradation',  '0.5%/year'),
        ]

        for r, (label, value) in enumerate(rows, start=3):
            if label is None:
                continue
            if value is None:
                # Section header
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
                cell = ws.cell(row=r, column=1, value=label)
                cell.font = _font(bold=True, size=10, colour=C_WHITE)
                cell.fill = _fill(C_BLUE_DARK)
                cell.alignment = _align()
            else:
                lc = ws.cell(row=r, column=1, value=label)
                vc = ws.cell(row=r, column=2, value=value)
                even = (r % 2 == 0)
                for c in [lc, vc]:
                    c.fill      = _fill(C_GREY if even else C_WHITE)
                    c.font      = _font(size=10)
                    c.alignment = _align()
                    c.border    = _thin_border()

    # ── Sheet 3: Monthly Production ───────────────────────────────────────────

    def _sheet_monthly_production(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('Monthly Production', 2)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 16, 2: 20, 3: 16, 4: 16})

        monthly = self.results.get('monthly_yield_kwh', [0]*12)
        if len(monthly) < 12:
            monthly = (monthly + [0]*12)[:12]
        annual  = sum(monthly)

        _merge_title(ws, 1, 1, 4, 'Monthly Energy Production Forecast')

        # Header row
        headers = ['Month', 'Production (kWh)', '% of Annual', 'Cumulative (kWh)']
        for c, h in enumerate(headers, 1):
            ws.cell(row=2, column=c, value=h)
        _header_style(ws, 2, 4)

        cumulative = 0.0
        for i, (m, v) in enumerate(zip(self.MONTHS, monthly)):
            row    = i + 3
            cumulative += v
            pct    = v / annual * 100 if annual > 0 else 0
            data   = [m, round(v, 1), round(pct, 1), round(cumulative, 1)]
            for c, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=c, value=val)
                _data_row_style(ws, row, 4, even=(i % 2 == 0))
                if c >= 2:
                    cell.number_format = '#,##0.0'
                    cell.alignment = _align('right')

        # Annual total row
        tot_row = 15
        ws.cell(row=tot_row, column=1, value='Annual Total').font = _font(bold=True, size=10)
        ws.cell(row=tot_row, column=2, value=round(annual, 1)).font = _font(bold=True)
        ws.cell(row=tot_row, column=3, value=100.0).font = _font(bold=True)
        ws.cell(row=tot_row, column=4, value=round(annual, 1)).font = _font(bold=True)
        for c in range(1, 5):
            ws.cell(row=tot_row, column=c).fill   = _fill(C_BLUE_LIGHT)
            ws.cell(row=tot_row, column=c).border = _thin_border()
            if c >= 2:
                ws.cell(row=tot_row, column=c).number_format = '#,##0.0'
                ws.cell(row=tot_row, column=c).alignment = _align('right')

        # Bar chart
        data_ref   = Reference(ws, min_col=2, min_row=2, max_row=14)
        cats_ref   = Reference(ws, min_col=1, min_row=3, max_row=14)
        chart      = BarChart()
        chart.type = 'col'
        chart.title            = 'Monthly Energy Production (kWh)'
        chart.y_axis.title     = 'Energy (kWh)'
        chart.x_axis.title     = 'Month'
        chart.style            = 10
        chart.grouping         = 'clustered'
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        chart.width  = 22
        chart.height = 12
        chart.series[0].graphicalProperties.solidFill = C_BLUE_MID
        ws.add_chart(chart, 'F2')

    # ── Sheet 4: Financial Analysis ───────────────────────────────────────────

    def _sheet_financial_analysis(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('Financial Analysis', 3)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 10, 2: 22, 3: 20, 4: 20, 5: 20, 6: 20})

        _merge_title(ws, 1, 1, 6, '25-Year Financial Cashflow Model')

        # Parameters
        annual_kwh  = self.results.get('annual_yield_kwh', 0) or 0
        total_cost  = self.results.get('total_cost_egp', 0) or 0
        payback_yrs = self.results.get('payback_years', 0) or 0
        elec_price  = 1.65    # EGP/kWh
        degradation = 0.005   # 0.5%/yr
        escalation  = 0.05    # 5%/yr

        # Column headers
        headers = ['Year','Production (kWh)','Price (EGP/kWh)',
                   'Annual Saving (EGP)','Net Cashflow (EGP)','Cumulative (EGP)']
        for c, h in enumerate(headers, 1):
            ws.cell(row=3, column=c, value=h)
        _header_style(ws, 3, 6)

        cumulative = -total_cost
        ws.cell(row=4, column=1, value=0)
        ws.cell(row=4, column=5, value=round(-total_cost, 0))
        ws.cell(row=4, column=6, value=round(-total_cost, 0))
        _data_row_style(ws, 4, 6, even=False)
        for c in [5, 6]:
            ws.cell(row=4, column=c).number_format = '#,##0'
            ws.cell(row=4, column=c).alignment = _align('right')

        for yr in range(1, 26):
            row        = yr + 4
            production = annual_kwh * (1 - degradation) ** yr
            price      = elec_price * (1 + escalation) ** yr
            saving     = production * price
            cumulative += saving

            data = [yr, round(production, 0), round(price, 3),
                    round(saving, 0), round(saving, 0), round(cumulative, 0)]
            for c, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=c, value=val)
                _data_row_style(ws, row, 6, even=(yr % 2 == 0))
                if c >= 2:
                    cell.alignment = _align('right')
                    if c in (2, 4, 5, 6):
                        cell.number_format = '#,##0'
                    elif c == 3:
                        cell.number_format = '0.000'

                # Colour cumulative column: red = not paid back, green = profit
                if c == 6:
                    cell.font = _font(
                        size=10,
                        colour=C_RED if val < 0 else C_GREEN,
                    )

        # Summary KPIs below table
        kpi_row = 31
        ws.merge_cells(start_row=kpi_row, start_column=1, end_row=kpi_row, end_column=6)
        ws.cell(row=kpi_row, column=1, value='Financial Summary').font = _font(bold=True, size=11, colour=C_BLUE_DARK)

        kpis = [
            ('Total Investment',        f"{total_cost:,.0f} EGP"),
            ('Simple Payback',          f"{payback_yrs:.1f} years"),
            ('25-Year Gross Savings',   f"{self.results.get('lifetime_savings_egp', 0):,.0f} EGP"),
            ('CO₂ Offset (25 yr)',      f"{annual_kwh * 25 * 0.47 / 1000:.0f} tonnes"),
        ]
        for i, (label, value) in enumerate(kpis):
            r = kpi_row + 1 + i
            _kpi_block(ws, r, label, value)

        # Line chart: cumulative cashflow
        cum_ref  = Reference(ws, min_col=6, min_row=3, max_row=29)
        yr_ref   = Reference(ws, min_col=1, min_row=5, max_row=29)
        lc       = LineChart()
        lc.title = 'Cumulative Net Cashflow (EGP)'
        lc.y_axis.title = 'EGP'
        lc.x_axis.title = 'Year'
        lc.style   = 10
        lc.add_data(cum_ref, titles_from_data=True)
        lc.set_categories(yr_ref)
        lc.width   = 22
        lc.height  = 12
        lc.series[0].graphicalProperties.line.solidFill = C_BLUE_MID
        lc.series[0].graphicalProperties.line.width = 20000   # 2pt
        ws.add_chart(lc, 'H3')

    # ── Sheet 5: Equipment Specs ──────────────────────────────────────────────

    def _sheet_equipment_specs(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('Equipment Specs', 4)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 30, 2: 28, 3: 4, 4: 30, 5: 28})

        _merge_title(ws, 1, 1, 5, 'Equipment Specifications')

        p   = self.panel
        inv = self.inverter

        panel_rows = [
            ('SOLAR PANEL', None),
            ('Manufacturer',            p.manufacturer),
            ('Model',                   p.model),
            ('Technology',              p.technology),
            ('Rated Power (Pnom)',      f"{p.power_rating_w:.0f} W"),
            ('Efficiency',              f"{p.efficiency_percent:.1f}%"),
            ('Vmpp',                    f"{p.vmp_v:.2f} V"),
            ('Impp',                    f"{p.imp_a:.2f} A"),
            ('Voc',                     f"{p.voc_v:.2f} V"),
            ('Isc',                     f"{p.isc_a:.2f} A"),
            ('Temp. Coeff. Pmax',       f"{p.temp_coeff_pmax_percent:.3f} %/°C"),
            ('Temp. Coeff. Voc',        f"{p.temp_coeff_voc_percent:.3f} %/°C"),
            ('Temp. Coeff. Isc',        f"{p.temp_coeff_isc_percent:.3f} %/°C"),
            ('NOCT',                    f"{getattr(p, 'noct_celsius', 45):.0f} °C"),
            ('Dimensions (L×W×H)',      f"{p.length_mm:.0f} × {p.width_mm:.0f} × {p.thickness_mm:.0f} mm"),
            ('Weight',                  f"{p.weight_kg:.1f} kg"),
            ('Cell Area',               f"{p.area_m2:.4f} m²"),
        ]

        inv_rows = [
            ('INVERTER', None),
            ('Manufacturer',            inv.manufacturer),
            ('Model',                   inv.model),
            ('Type',                    inv.inverter_type),
            ('Rated AC Power',          f"{inv.power_rating_w:,.0f} W"),
            ('Max AC Power',            f"{inv.max_ac_power_w:,.0f} W"),
            ('AC Voltage',              f"{inv.output_voltage_v:.0f} V"),
            ('Max Efficiency',          f"{inv.max_efficiency_percent:.1f}%"),
            ('Euro Efficiency',         f"{inv.euro_efficiency_percent:.1f}%"),
            ('Max DC Voltage',          f"{inv.max_dc_voltage_v:.0f} V"),
            ('Min DC Voltage',          f"{inv.min_dc_voltage_v:.0f} V"),
            ('MPPT Range',              f"{inv.mppt_voltage_min_v:.0f} – {inv.mppt_voltage_max_v:.0f} V"),
            ('Max DC Current',          f"{inv.max_dc_current_a:.1f} A"),
            ('Number of MPPTs',         str(inv.number_of_mppts)),
            ('Number of DC Inputs',     str(inv.number_of_inputs)),
            ('Weight',                  f"{inv.weight_kg:.1f} kg"),
            ('Dimensions',              str(getattr(inv, 'dimensions_mm', 'N/A'))),
        ]

        def _write_col(rows, col_offset):
            for r_idx, (label, value) in enumerate(rows, start=3):
                row = r_idx
                if value is None:
                    ws.merge_cells(start_row=row, start_column=col_offset,
                                   end_row=row, end_column=col_offset + 1)
                    cell = ws.cell(row=row, column=col_offset, value=label)
                    cell.fill      = _fill(C_BLUE_DARK)
                    cell.font      = _font(bold=True, colour=C_WHITE, size=10)
                    cell.alignment = _align()
                else:
                    lc = ws.cell(row=row, column=col_offset,   value=label)
                    vc = ws.cell(row=row, column=col_offset+1, value=value)
                    even = (r_idx % 2 == 0)
                    for c in [lc, vc]:
                        c.fill      = _fill(C_GREY if even else C_WHITE)
                        c.font      = _font(size=10)
                        c.border    = _thin_border()
                        c.alignment = _align()

        _write_col(panel_rows, col_offset=1)
        # Spacer column 3 intentionally blank
        _write_col(inv_rows,   col_offset=4)

    # ── Sheet 6: Climate Summary ──────────────────────────────────────────────

    def _sheet_climate_summary(self, wb: 'Workbook') -> None:
        ws = wb.create_sheet('Climate Data', 5)
        ws.sheet_view.showGridLines = False
        _set_col_widths(ws, {1: 14, 2: 18, 3: 16, 4: 14, 5: 14, 6: 14})

        _merge_title(ws, 1, 1, 6,
                     f'Monthly Climate Summary — {self.location.name}')

        # Build monthly climate aggregates from climate_data if available
        monthly_ghi  = [0.0] * 12
        monthly_temp = [0.0] * 12
        monthly_cnt  = [0]   * 12

        try:
            for record in self.project['climate_data']:
                m = record.date.month - 1   # 0-indexed
                monthly_ghi[m]  += float(record.allsky_sfc_sw_dwn)
                monthly_temp[m] += float(record.t2m)
                monthly_cnt[m]  += 1
        except (TypeError, AttributeError, KeyError):
            # climate_data not iterable or missing — use latitude-based defaults
            import math
            for m in range(12):
                phase = 2 * math.pi * (m - 5) / 12   # peak June
                monthly_ghi[m]  = 5.5 + 2.0 * math.cos(phase)
                monthly_temp[m] = 22.0 + 10.0 * math.cos(phase)
                monthly_cnt[m]  = 30

        headers = ['Month','Avg GHI (kWh/m²/day)','Avg Temp (°C)',
                   'Monthly GHI (kWh/m²)','Radiation Index','Category']
        for c, h in enumerate(headers, 1):
            ws.cell(row=3, column=c, value=h)
        _header_style(ws, 3, 6)

        for i, m_name in enumerate(self.MONTHS):
            row     = i + 4
            n       = max(1, monthly_cnt[i])
            avg_ghi = monthly_ghi[i]  / n
            avg_t   = monthly_temp[i] / n
            mon_ghi = avg_ghi * 30.4   # approximate days/month
            ri      = avg_ghi / 6.5    # relative to max achievable

            if ri >= 0.85:
                cat = 'Excellent'
                cat_col = C_GREEN
            elif ri >= 0.65:
                cat = 'Good'
                cat_col = '16a34a'
            elif ri >= 0.45:
                cat = 'Moderate'
                cat_col = 'ca8a04'
            else:
                cat = 'Low'
                cat_col = C_RED

            data = [m_name, round(avg_ghi, 2), round(avg_t, 1),
                    round(mon_ghi, 0), round(ri, 3), cat]
            for c, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=c, value=val)
                _data_row_style(ws, row, 6, even=(i % 2 == 0))
                if c >= 2:
                    cell.alignment = _align('right')
                if c == 6:
                    cell.font = _font(size=10, colour=cat_col, bold=True)
