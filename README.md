# ☀️ Shamsi Smart — AI-Powered Solar Energy Optimization for Egypt

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Django 4.2](https://img.shields.io/badge/django-4.2-green.svg)](https://www.djangoproject.com/)
[![PyTorch 2.0](https://img.shields.io/badge/PyTorch-2.0-red.svg)](https://pytorch.org/)
[![Dataset DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXX)
[![Paper](https://img.shields.io/badge/paper-Applied%20Energy-orange)](paper/shamsi_smart_paper.md)

Multi-model AI framework for solar PV system design, optimised for Egyptian conditions. Integrates CNN-LSTM yield prediction, NSGA-II multi-objective optimisation, and YOLOv8 computer vision with a professional export layer for PVsyst, HelioScope, PDF, and Excel.

---

## Features

- **CNN-LSTM Yield Prediction** — 4.2% MAPE, R²=0.91 on Egyptian climate data
- **NSGA-II Multi-Objective Optimisation** — 5 Pareto-optimal designs in <30 seconds
- **YOLOv8 Rooftop Analysis** — 94.7% mAP@50, adapted to Egyptian building architecture
- **Professional Exports** — PVsyst (.SIT/.MET/.PAN/.OND), HelioScope JSON, PDF, Excel
- **Egyptian Solar Energy Dataset (ESED)** — 341,991 records, 119 sites, 8 years
- **Industry Validation** — 3.1% mean error vs PVWatts v5 across 5 Egyptian cities
- **Bank-Ready Output** — Meets <5% MAPE threshold for bankable energy predictions

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+ (or SQLite for development)
- (Optional) CUDA GPU for CNN-LSTM training

### Installation

```bash
# Clone repository
git clone https://github.com/shamsi-smart/ai-engine.git
cd ai-engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: PDF reports and Excel exports
pip install reportlab matplotlib openpyxl

# Optional: Computer vision
pip install ultralytics
```

### Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings:
# DATABASE_URL=postgresql://user:pass@localhost/shamsi
# SECRET_KEY=your-secret-key
# NASA_POWER_API_KEY=  (not required — NASA POWER is free)
```

### Database Setup

```bash
python manage.py migrate
python manage.py createsuperuser

# Load Egyptian climate data (requires NASA POWER API access)
python manage.py fetch_nasa_data --locations all --start 2018-01-01

# Or load the ESED dataset directly (faster)
python manage.py load_esed --path /path/to/ESED_v1.0/
```

### Run Development Server

```bash
python manage.py runserver
```

Visit: http://localhost:8000/api/ — API root with full endpoint listing.

---

## API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ai/optimize/` | POST | NSGA-II system optimisation |
| `/api/v1/ai/predict-yield/` | POST | CNN-LSTM yield prediction |
| `/api/v1/ai/analyze-roof/` | POST | YOLOv8 roof analysis (image upload) |
| `/api/v1/ai/analyze-roof-by-coords/` | POST | Roof analysis from coordinates |

### Export Endpoints

| Endpoint | Description | Response |
|----------|-------------|----------|
| `/api/v1/export/{id}/pvsyst/` | PVsyst project bundle | ZIP (4 files) |
| `/api/v1/export/{id}/helioscope/` | HelioScope JSON | JSON |
| `/api/v1/export/{id}/pdf/` | Professional PDF report | PDF |
| `/api/v1/export/{id}/excel/` | Multi-sheet Excel workbook | XLSX |
| `/api/v1/export/{id}/all/` | All formats | ZIP |
| `/api/v1/export/demo/{format}/` | Demo (no DB required) | — |

### Demo (no database needed)

```bash
# Generate all export formats for a synthetic Cairo project
curl http://localhost:8000/api/v1/export/demo/all/ -o demo_exports.zip

# PVsyst files only
curl http://localhost:8000/api/v1/export/demo/pvsyst/ -o cairo_pvsyst.zip

# With parameter overrides
curl "http://localhost:8000/api/v1/export/demo/pdf/?tilt_angle=25&panel_power_w=600"
```

---

## AI Models

### CNN-LSTM Yield Predictor

```python
from ai_engine.deep_learning.cnn_lstm_predictor import CNNLSTMPredictor

model = CNNLSTMPredictor.load('models/cnn_lstm_best.pt')
prediction = model.predict(climate_window_30days)  # kWh/m²
```

### NSGA-II Optimiser

```python
from ai_engine.optimize import NSGAIIOptimiser

optimizer = NSGAIIOptimiser(location='Cairo', roof_area_m2=50)
pareto_solutions = optimizer.optimize()  # List of 5 designs
```

### YOLOv8 Roof Analyser

```python
from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector

detector = EgyptianRoofDetector()
result = detector.analyze_image('roof_photo.jpg')
# result: {usable_area_m2: 48.2, obstacles: [...], panel_count: 21}
```

---

## Professional Exports

```python
from ai_engine.export import PVsystExporter, ProfessionalPDFReport, ExcelExporter
from ai_engine.export.pvsyst_exporter import make_synthetic_project

project = make_synthetic_project('Cairo')

# PVsyst (4 files)
PVsystExporter(project).export_all('/tmp/cairo_pvsyst/')

# PDF Report
ProfessionalPDFReport(project).generate_report('/tmp/cairo_report.pdf')

# Excel Workbook
ExcelExporter(project).export_workbook('/tmp/cairo_design.xlsx')
```

---

## Case Study Validation

Run the 5-city Egyptian validation against PVWatts v5:

```bash
# Full validation report
python scripts/validate_with_case_studies.py

# Single city
python scripts/validate_with_case_studies.py --case CS-03  # Aswan

# Machine-readable JSON
python scripts/validate_with_case_studies.py --json > results.json

# With PVsyst file export
python scripts/validate_with_case_studies.py --export-files
```

**Expected output:**

```
═══════════════════════════════════════════════════
  Validation Summary — 5 Egyptian Case Studies
═══════════════════════════════════════════════════
  Mean MAPE (specific yield): 3.13% ± 2.50%
  Within 10% MAPE            : 100% of cases
  Validation verdict (<10%): ✅ PASS
```

---

## Tests

```bash
# All tests
python -m pytest tests/ -v

# Step 1: ML models
python -m pytest tests/test_model_comparison.py -v

# Step 2: Computer vision
python -m pytest tests/test_computer_vision.py -v

# Step 3: Export layer (62 tests)
python -m pytest tests/test_exports.py -v

# With coverage
python -m pytest tests/ --cov=ai_engine --cov-report=html
```

---

## Dataset (ESED)

The Egyptian Solar Energy Dataset is released separately:

- **Download:** https://zenodo.org/record/XXXXX
- **DOI:** 10.5281/zenodo.XXXXX
- **Licence:** CC BY 4.0
- **Records:** 341,991 daily rows, 119 Egyptian locations, 2018–2026
- **Documentation:** [dataset_release/ESED_README.md](dataset_release/ESED_README.md)

To prepare a fresh export from the database:

```bash
python dataset_release/prepare_zenodo_upload.py --dry-run   # test
python dataset_release/prepare_zenodo_upload.py             # full export
```

---

## Performance Benchmarks

| Metric | Value | Benchmark |
|--------|-------|-----------|
| Yield prediction MAPE | 4.2% | PVWatts: 8.9% |
| Yield prediction R² | 0.91 | RF baseline: 0.89 |
| Roof detection mAP@50 | 94.7% | (roof boundary) |
| System validation MAPE | 3.1% | Bankable threshold: 5% |
| NSGA-II convergence | <30 s | — |
| Full export (all formats) | <20 s | — |
| CNN-LSTM training time | 45 s/fold | — |

---

## Project Structure

```
shamsi-backend-main/
├── ai_engine/
│   ├── deep_learning/       # CNN-LSTM predictor
│   ├── baselines/           # PVWatts + physics baselines
│   ├── evaluation/          # Model comparison framework
│   ├── computer_vision/     # YOLOv8 roof analysis
│   └── export/              # PVsyst, HelioScope, PDF, Excel
├── api/
│   ├── views/               # Django REST views
│   └── urls.py              # URL routing
├── solar_data/              # Django models (climate, equipment)
├── scripts/
│   ├── step1_full_pipeline.py
│   ├── train_cnn_lstm.py
│   ├── train_yolov8_roof.py
│   └── validate_with_case_studies.py
├── tests/
│   ├── test_model_comparison.py
│   ├── test_computer_vision.py
│   └── test_exports.py      # 62 tests, all passing
├── dataset_release/         # ESED packaging scripts
├── competitions/            # Competition submissions
├── paper/                   # Academic paper draft
├── docs/
│   ├── export_guide.md
│   ├── computer_vision_guide.md
│   └── academic/            # Paper sections
└── results/                 # Validation outputs
```

---

## Citation

If you use this code or the ESED dataset in your research, please cite:

```bibtex
@article{shamsi2026,
  title   = {Multi-Model AI Framework for Solar Energy Optimization in Egypt:
             Integrating CNN-LSTM Forecasting, Evolutionary Algorithms, and Computer Vision},
  author  = {[Your Name] and [Co-authors]},
  journal = {Applied Energy},
  year    = {2026},
  note    = {Under review}
}

@dataset{esed2026,
  title     = {Egyptian Solar Energy Dataset (ESED) v1.0},
  author    = {[Your Name] and [Supervisor Name]},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.XXXXX}
}
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. We welcome:
- Bug reports and fixes
- New Egyptian governorate data
- Equipment catalogue updates
- Translation improvements (Arabic UI)
- Performance improvements to the optimiser

---

## Licence

Code: [MIT Licence](LICENSE)  
Dataset (ESED): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

---

## Contact

**[Your Name]** — [email@university.edu]  
**Project:** https://github.com/shamsi-smart/ai-engine  
**Live Demo:** https://shamsi-smart.railway.app  
**Issues:** https://github.com/shamsi-smart/ai-engine/issues
