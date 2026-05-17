# Professional Export Layer — Developer Guide

**Shamsi Smart | Step 3: Integration & Exports**

---

## Overview

The export layer transforms Shamsi Smart from an internal AI tool into a **professional solar design platform** compatible with the industry's two dominant simulation tools — PVsyst and HelioScope.

The workflow this enables:

```
Shamsi Smart (AI-optimised design)
  │
  ├──→ PVsyst (.SIT + .MET + .PAN + .OND)   ← bankable simulation
  ├──→ HelioScope JSON                         ← US/international review
  ├──→ PDF Report (client-facing)              ← sales + financing
  └──→ Excel Workbook (full financials)        ← investor analysis
```

This workflow does not exist in any other product. PVsyst cannot optimise; Shamsi can. Shamsi cannot generate bankable yield reports; PVsyst can. Together they cover the entire design-to-finance pipeline.

---

## Quick Start

### Install dependencies

```bash
# Core (always required)
pip install django djangorestframework numpy

# PDF reports
pip install reportlab matplotlib

# Excel workbooks
pip install openpyxl

# All at once
pip install reportlab matplotlib openpyxl
```

### Generate exports programmatically

```python
from ai_engine.export.pvsyst_exporter    import PVsystExporter, make_synthetic_project
from ai_engine.export.helioscope_exporter import HelioScopeExporter
from ai_engine.export.pdf_report          import ProfessionalPDFReport
from ai_engine.export.excel_exporter      import ExcelExporter

# Use synthetic data (works without Django/DB)
project = make_synthetic_project('Cairo')

# PVsyst
PVsystExporter(project).export_all('/tmp/cairo_export/')
# → Cairo.SIT, Cairo.MET, JA_Solar_JAM72D40-580.PAN, Huawei_SUN2000.OND

# HelioScope
HelioScopeExporter(project).export_project('/tmp/cairo_helioscope.json')

# PDF Report
ProfessionalPDFReport(project).generate_report('/tmp/cairo_report.pdf')

# Excel
ExcelExporter(project).export_workbook('/tmp/cairo_design.xlsx')

# CSV (no dependencies)
ExcelExporter(project).export_csv('/tmp/cairo_monthly.csv')
```

### Call the REST API

```bash
# Demo mode (no DB needed)
curl http://localhost:8000/api/v1/export/demo/pvsyst/     -o pvsyst.zip
curl http://localhost:8000/api/v1/export/demo/helioscope/ -o design.json
curl http://localhost:8000/api/v1/export/demo/pdf/        -o report.pdf
curl http://localhost:8000/api/v1/export/demo/excel/      -o design.xlsx
curl http://localhost:8000/api/v1/export/demo/all/        -o all_formats.zip

# Real project
curl http://localhost:8000/api/v1/export/{project_id}/pdf/

# With overrides
curl "http://localhost:8000/api/v1/export/demo/pdf/?tilt_angle=25&azimuth=175&panel_power_w=600"
```

---

## API Reference

### GET `/api/v1/export/{project_id}/{format}/`

| Format       | Content-Type | File |
|---|---|---|
| `pvsyst`     | `application/zip` | ZIP of 4 PVsyst files |
| `helioscope` | `application/json` | HelioScope JSON project |
| `pdf`        | `application/pdf` | 7-section PDF report |
| `excel`      | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | XLSX workbook |
| `csv`        | `text/csv` | Monthly production CSV |
| `all`        | `application/zip` | ZIP of every format |

**Query parameters** (all optional):

| Parameter | Default | Description |
|---|---|---|
| `panel_power_w` | 580 | Override panel wattage |
| `tilt_angle` | 20 | Override tilt angle (degrees) |
| `azimuth` | 180 | Override azimuth (180 = South) |
| `format` | file | For helioscope: `json` returns inline JSON |

**Special project_id: `demo`** — generates synthetic output without any database access. Use this for testing and integration.

**Error responses:**

| Code | Reason |
|---|---|
| 404 | Project not found |
| 400 | Missing required project data |
| 500 | Export library not installed (see `detail` and `install` fields) |

---

## File Formats

### PVsyst (`.SIT`, `.MET`, `.PAN`, `.OND`)

PVsyst is the industry standard for bankable solar yield assessments. Banks and project finance institutions require PVsyst simulations for loans above ~$500K.

**To import into PVsyst:**
1. Open PVsyst → Project → New Project
2. Site → Import → Select `<location>.SIT`
3. Meteo → Import → Select `<location>.MET`
4. Equipment → Panel database → Import → Select `<panel>.PAN`
5. Equipment → Inverter database → Import → Select `<inverter>.OND`
6. Run simulation and compare with Shamsi's predicted yield

**`.SIT` file** — ASCII text, site definition:
```
PVsyst Site data
****
Country             Egypt
Latitude            30.044 °N
Longitude           31.236 °E
Altitude            23 m
Time zone           UT+2.0
Meteo file          Cairo.MET
Albedo              0.20
...
```

**`.MET` file** — NASA SSE CSV format:
```
# Shamsi Smart meteo export
-31.236,30.044,23,2.0
date,GHI,DNI,DHI,Tdry,Wspd,RH
2023-01-01,3.821,4.912,1.203,15.2,2.3,62
...
```

DNI and DHI are decomposed from GHI using the Erbs (1982) correlation.

**`.PAN` file** — panel electrical + physical specs in PVsyst database format.

**`.OND` file** — inverter specs (OND = Onduleur, French for inverter).

---

### HelioScope JSON

HelioScope (Aurora Solar) is widely used in the US and internationally. The JSON follows the HelioScope API v1 project schema.

**Schema structure:**
```json
{
  "project": {
    "name": "Shamsi_Cairo_20240115",
    "location": { "latitude": 30.044, ... },
    "design": {
      "system_type": "grid_tied",
      "arrays": [{
        "tilt": 20, "azimuth": 180,
        "modules": { "count": 30, "specifications": {...} },
        "inverters": [{ "specifications": {...} }]
      }],
      "losses": { "soiling": 0.05, "shading": 0.03, ... }
    },
    "energy_production": { "annual_kwh": 24800, ... },
    "economics": { "payback_years": 5.8, ... },
    "shamsi_metadata": { "optimiser": "NSGA-II", ... }
  }
}
```

---

### PDF Report Structure

The 7-section report is generated with ReportLab and is designed to be client-facing — professional quality, no developer aesthetics.

| Section | Content |
|---|---|
| 1. Cover Page | Project summary, location, system size, AI badge |
| 2. Executive Summary | Key KPI table, project narrative |
| 3. Site Analysis | Geographic parameters, climate zone, roof CV analysis if available |
| 4. System Design | Configuration, panel specs table, inverter specs table |
| 5. Energy Forecast | Monthly bar chart, monthly data table |
| 6. Financial Analysis | 25-year cashflow chart, financial summary table, LCOE |
| 7. Technical Appendix | Loss budget, AI methodology, standards compliance, disclaimer |

---

### Excel Workbook Sheets

| Sheet | Contents |
|---|---|
| Summary | KPI block × 2 columns (location + production on left, financials on right) |
| System Design | Configuration + loss assumptions with section headers |
| Monthly Production | Monthly table + embedded bar chart |
| Financial Analysis | 25-year cashflow table (colour coded) + line chart + KPI summary |
| Equipment Specs | Panel and inverter specs side by side |
| Climate Data | Monthly GHI + temperature aggregates with radiation category |

---

## Module Reference

### `PVsystExporter`

```python
class PVsystExporter:
    def __init__(self, project_data: Dict): ...
    def export_all(self, output_dir: str) -> Dict[str, str]: ...
    # Returns {'sit_file': ..., 'met_file': ..., 'pan_file': ..., 'ond_file': ...}
```

**`project_data` schema:**

| Key | Type | Description |
|---|---|---|
| `location` | object | `.name`, `.country`, `.latitude`, `.longitude`, `.elevation_m` |
| `panel` | object | Electrical + physical specs (see `make_synthetic_project()`) |
| `inverter` | object | Inverter specs |
| `system_config` | dict | `panel_count`, `tilt_angle`, `azimuth`, `strings`, `panels_per_string`, `inverter_count` |
| `climate_data` | iterable | Daily records with `.date`, `.allsky_sfc_sw_dwn`, `.t2m`, `.ws2m`, `.rh2m` |
| `optimization_results` | dict | `annual_yield_kwh`, `monthly_yield_kwh`, `specific_yield`, `total_cost_egp`, … |
| `project_id` | str | Optional project identifier |
| `dust_loss_pct` | float | Optional, default 5.0 |
| `shading_loss_pct` | float | Optional, default 3.0 |

Use `make_synthetic_project(location_name)` for testing without Django.

---

### `HelioScopeExporter`

```python
class HelioScopeExporter:
    def export_project(self, output_file: str) -> str: ...
    def to_dict(self) -> Dict: ...  # Returns dict without file I/O
```

---

### `ProfessionalPDFReport`

```python
class ProfessionalPDFReport:
    def generate_report(self, output_file: str) -> str: ...
```

Optional: include `'roof_image_path'` and `'roof_analysis'` in project_data to add CV results to Section 3.

---

### `ExcelExporter`

```python
class ExcelExporter:
    def export_workbook(self, output_file: str) -> str: ...  # requires openpyxl
    def export_csv(self, output_file: str) -> str: ...       # no dependencies
```

---

## Running Tests

```bash
python -m pytest tests/test_exports.py -v
python -m pytest tests/test_exports.py::TestPVsystExporter -v
python -m pytest tests/test_exports.py::TestCaseStudyValidation -v
```

---

## Case Study Validation

Run the 5-city Egyptian validation:

```bash
python scripts/validate_with_case_studies.py

# With PVsyst file generation per case
python scripts/validate_with_case_studies.py --export-files

# Single case
python scripts/validate_with_case_studies.py --case CS-03   # Aswan

# Machine-readable output
python scripts/validate_with_case_studies.py --json > results.json
```

Results are saved to `results/step3/validation/case_study_results.json`.

**Validation targets:**

| Metric | Target | Achieved |
|---|---|---|
| Mean MAPE (specific yield) | < 10% | ✅ |
| All cases within 10% MAPE | 5/5 | ✅ |
| Mean monthly RMSE | < 200 kWh | ✅ |
| Performance Ratio diff | < 5% | ✅ |

---

## File Index

| File | Purpose |
|---|---|
| `ai_engine/export/__init__.py` | Package with exports for all 4 classes |
| `ai_engine/export/pvsyst_exporter.py` | .SIT/.MET/.PAN/.OND generation |
| `ai_engine/export/helioscope_exporter.py` | HelioScope JSON |
| `ai_engine/export/pdf_report.py` | 7-section ReportLab PDF |
| `ai_engine/export/excel_exporter.py` | Multi-sheet openpyxl workbook + CSV |
| `api/views/export_view.py` | Django REST endpoints |
| `api/urls.py` | Updated URL routing |
| `scripts/validate_with_case_studies.py` | 5-city validation script |
| `tests/test_exports.py` | 50+ unit tests |
| `docs/export_guide.md` | This file |
| `docs/academic/step3_validation.md` | Paper Section 5 |
| `case_studies/` | Per-city export files (generated by --export-files) |
| `results/step3/validation/` | Validation JSON output |
