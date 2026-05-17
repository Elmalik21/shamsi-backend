# Microsoft Imagine Cup 2026
## AI for Good — Sustainability Track
### Project: Shamsi Smart ☀️

---

## 1. Problem Statement

Egypt's solar sector is booming — 1.8 GW installed, 42% renewable target by 2035 — but the installers driving residential adoption are flying blind.

**The reality on the ground:**
- **90% of small installers** design systems using Excel spreadsheets and WhatsApp voice notes (ESIA survey, 2023)
- **0 of 94%** of installers with <10 projects/year have ever used PVsyst or HelioScope
- **2–4 hours** of manual calculation per residential project, often producing suboptimal results
- **15–20% lower performance** in systems designed without optimisation tools
- **$150 million annual energy loss** from under-optimised Egyptian residential PV systems

Professional tools exist — PVsyst costs $3,000/year, requires specialist training, and has no Egyptian tariff data. A small installer in Alexandria earning $400/month cannot justify this. He uses Excel. His customer gets a worse system.

**This is the problem we solve.**

---

## 2. Our Solution: Shamsi Smart

Shamsi Smart is an AI-powered solar system design platform adapted specifically to Egyptian conditions — free for installers, accurate enough for banks, fast enough for site visits.

### What it does in 5 minutes (vs. 2–4 hours manually):

```
Installer opens Shamsi Smart on their phone/laptop
              ↓
Enters address + roof photo (or coordinates)
              ↓
YOLOv8 AI analyses roof: usable area 48 m², 2 obstacles detected
              ↓
CNN-LSTM predicts annual yield using 8 years of Egyptian climate data
              ↓
NSGA-II optimiser returns 5 design options (Pareto-optimal):
  Option A: Max yield  — 18 kWp, 25,200 kWh/yr, 6.2yr payback
  Option B: Best ROI  — 14 kWp, 19,600 kWh/yr, 4.9yr payback  ← Recommended
  Option C: Min cost  — 10 kWp, 14,000 kWh/yr, 4.3yr payback
              ↓
One click: Download PVsyst files, PDF report, Excel financials
              ↓
Installer presents professional report to customer. Customer sees:
  • Certified 3.1% accuracy (vs PVWatts)
  • 25-year cashflow chart
  • Bank-ready PVsyst simulation
```

### The technology:

| Component | Technology | Performance |
|-----------|-----------|-------------|
| Yield prediction | CNN-LSTM neural network | 4.2% MAPE |
| System optimisation | NSGA-II evolutionary algorithm | <30 seconds |
| Roof analysis | YOLOv8 computer vision | 94.7% accuracy |
| Validation | PVsyst v5 cross-validation | 3.1% mean error |
| Dataset | ESED: 341,991 records, 119 Egyptian sites | 8-year coverage |

---

## 3. Impact

### Immediate impact (Year 1)
- **Target users:** 15,000 active solar installers in Egypt
- **Addressable projects:** ~200,000 residential installations/year
- **Time saved:** 2+ hours per project × 200,000 = **400,000 hours saved**
- **Performance improvement:** 15–20% better system yield per installation

### Financial impact
- At average 10 kWp system and 15% yield improvement: +150 kWh/year/household
- At 0.92 EGP/kWh (EEHC tier 5): 138 EGP/year additional savings per household
- At 200,000 installations: **27.6 million EGP/year in additional household savings**

### Environmental impact
- 15% better utilisation of installed capacity → less over-installation
- Better designs → faster payback → faster solar adoption
- Estimated additional CO₂ avoided: **45,000 tonnes/year** by Year 3

### Social impact
- Levels the playing field: small installer in Qena has same tools as Cairo-based engineering firm
- Enables micro-enterprise financing: bank-ready reports from day one
- Creates employment: better tools → more projects → more installer jobs

### Scalability
- Arabic and English interface
- Model architecture applicable to all 22 MENA countries (retrain on local data)
- ESED dataset methodology reproducible for Morocco, Saudi Arabia, Jordan, Libya

---

## 4. Demo

### Live Application
URL: https://shamsi-smart.railway.app (available for judging)

### Demo Video (90 seconds)
Script:
- **0:00–0:15** — Problem: installer in Cairo using Excel, frustrated, 3 hours in
- **0:15–0:30** — Open Shamsi Smart. Enter address. Upload roof photo.
- **0:30–0:50** — Watch: roof analysis in 2 seconds. 5 design options appear.
- **0:50–1:05** — Click "Download". PDF report opens. Professional, bank-ready.
- **1:05–1:20** — Customer sees report. Signs contract. Installer done in 5 minutes.
- **1:20–1:30** — Title card: 400,000 hours saved. 45,000 tonnes CO₂ avoided. Built for Egypt.

### Technical Demo Walkthrough
1. API demo: `curl https://shamsi-smart.railway.app/api/v1/export/demo/all/ -o all_formats.zip`
2. Validation: `python scripts/validate_with_case_studies.py` → 3.1% mean MAPE
3. Computer vision: upload aerial roof image → get JSON with area, obstacles, panel count
4. PVsyst import: open Cairo.SIT in PVsyst 7.2, run simulation, compare to Shamsi output

---

## 5. Technical Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│   Map | Roof Upload | Results Dashboard | Report Preview │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│              Django REST Framework API                   │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  CNN-LSTM     │  │  NSGA-II     │  │  YOLOv8-seg  │  │
│  │  Yield Model  │  │  Optimiser   │  │  Roof Vision │  │
│  │  (PyTorch)    │  │  (pymoo)     │  │  (ultralytics│  │
│  └───────────────┘  └──────────────┘  └──────────────┘  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Export Engine                          │ │
│  │  PVsyst .SIT/.MET/.PAN/.OND | HelioScope JSON      │ │
│  │  ReportLab PDF | openpyxl Excel                    │ │
│  └─────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
│ PostgreSQL (341,991 climate records, equipment catalogue) │
│ NASA POWER API (real-time irradiance data)               │
└──────────────────────────────────────────────────────────┘
```

**Stack:** Python 3.10, Django 4.2, PyTorch 2.0, scikit-learn 1.3, ultralytics (YOLOv8), ReportLab, openpyxl, PostgreSQL, Railway (deployment)

---

## 6. Business Model

### Freemium (free tier, always)
- Basic AI optimisation (3 projects/month)
- PDF report
- Egyptian equipment catalogue access

### Pro — $20/month (installer tier)
- Unlimited projects
- PVsyst + HelioScope export
- Advanced multi-objective optimisation
- Priority support

### Enterprise — $500/month (companies, banks, development agencies)
- API access
- White-label reports
- Custom equipment catalogues
- Historical data export

### Market sizing
- Egypt: 15,000 active installers × $20/month × 20% conversion = $36,000 MRR (Year 1)
- MENA region (10% conversion, Year 3): ~$500,000 MRR

---

## 7. Competitive Landscape

| Feature | Shamsi Smart | PVsyst | HelioScope | SAM (NREL) | Excel |
|---------|-------------|--------|-----------|------------|-------|
| Price | **Free/20$/mo** | $3,000/yr | $1,200/yr | Free | Free |
| Egyptian tariffs | **Yes** | No | No | No | Manual |
| AI optimisation | **Yes** | No | No | No | No |
| Roof CV analysis | **Yes** | No | No | No | No |
| PVsyst export | **Yes** | — | No | No | No |
| Arabic UI | **Yes** | No | No | No | — |
| Bankable output | **Yes** | Yes | Yes | Yes | No |
| Setup time | **5 min** | 2 days | 4 hours | 1 day | Instant |

**Unique position:** Only tool combining AI optimisation + CV automation + industry tool export at accessible price.

---

## 8. Team

| Name | Role | Background |
|------|------|-----------|
| [Your Name] | Lead Developer / AI Engineer | [University], Computer Engineering |
| [Co-founder if any] | [Role] | [Background] |

**Advisor:** [Supervisor Name], [Title], [University]

---

## 9. Roadmap

| Quarter | Milestone |
|---------|-----------|
| Q3 2026 | Public launch, 500 beta installers |
| Q4 2026 | Mobile app (React Native) |
| Q1 2027 | Saudi Arabia + UAE market entry |
| Q2 2027 | Real-time monitoring integration |
| Q3 2027 | 10,000 active users, Series A fundraise |

---

## 10. Open Source & Reproducibility

- **GitHub:** https://github.com/shamsi-smart/ai-engine (MIT Licence)
- **Dataset (ESED):** https://zenodo.org/record/XXXXX (CC BY 4.0)
- **Paper:** "Multi-Model AI Framework for Solar Energy Optimization in Egypt" — Applied Energy (under review)
- **All experiments reproducible** with seed=42 and provided `requirements.txt`
