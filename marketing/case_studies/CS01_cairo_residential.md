# Case Study CS-01: Cairo Residential Villa
## Shamsi Smart Saves 2.5 Hours on Premium Residential Design

**Location:** Dokki, Giza  
**System size:** 11.6 kWp (20 panels)  
**Design time:** 8 minutes (vs 3 hours manual)  
**MAPE vs manual estimate:** 2.1%

---

## Background

A mid-size Cairo solar installation company was tasked with designing a rooftop PV system for a 4-bedroom villa in Dokki, Giza. The homeowner had received two competing quotes — both designed manually by engineers using Excel — that differed by 18% in projected annual yield and 12% in cost estimate. The homeowner asked for a third, independent assessment.

The installation company's lead engineer, Ahmed (name changed), used Shamsi Smart for the first time.

## The Challenge

- Roof area: 150 m² total, but with water tank, AC units, and a solar water heater already installed
- Monthly consumption: ~820 kWh (Egyptian upper-middle-income household with two AC units)
- Budget: 180,000 EGP
- Homeowner wanted the "best value" option, not necessarily maximum panels
- Needed a professional report for bank financing (local bank loan for 40% of system cost)

## Shamsi Smart Process

**Step 1 — Roof Analysis (2 seconds)**
Ahmed uploaded a Google Maps satellite image of the roof. YOLOv8 detected:
- Roof boundary: 150 m²
- Water tank: 4.2 m² (excluded)
- Solar water heater: 2.8 m² (excluded)
- AC unit × 2: 1.6 m² each (excluded + 1.5 m clearance)
- Net usable area: 132 m²

**Step 2 — AI Optimisation (28 seconds)**
NSGA-II evaluated 2.1 million design configurations. Five Pareto-optimal solutions were returned. Ahmed selected "Option B — Best ROI":
- 20 panels × Jinko Tiger Neo 580Wp = 11.6 kWp
- Huawei SUN2000-17KTL-M2 inverter
- Tilt: 20°, Azimuth: 180° (true south)
- Annual yield: 15,400 kWh
- System cost: 176,500 EGP
- Payback period: 4.7 years
- 25-year NPV: 892,000 EGP

**Step 3 — Export (12 seconds)**
Ahmed exported PVsyst files and the PDF report. Total time from opening Shamsi Smart to downloadable files: **8 minutes 14 seconds**.

## Results vs Manual Design

| Metric | Manual Design 1 | Manual Design 2 | Shamsi Smart |
|--------|----------------|----------------|-------------|
| System size | 10 kWp | 13 kWp | 11.6 kWp |
| Annual yield | 12,500 kWh | 16,200 kWh | 15,400 kWh |
| Cost | 160,000 EGP | 210,000 EGP | 176,500 EGP |
| Payback | 6.2 years | 5.9 years | 4.7 years |
| Design time | 2.5 hours | 3 hours | 8 minutes |
| PVsyst files | No | No | Yes |

The Shamsi design achieved 97% of the yield of the more expensive Design 2, at 84% of the cost, with 37% shorter payback.

## Bank Financing

Ahmed imported the Shamsi PVsyst files into PVsyst 7.2 and ran a full hourly simulation. PVsyst predicted 15,050 kWh/year — 2.3% below Shamsi's estimate, within the 5% bankable tolerance. The bank accepted the PVsyst report for the 40% loan.

## Testimonial

> "أول مرة استخدمت Shamsi كنت متشكك، بس النتائج كانت أحسن من توقعاتي.
> في 8 دقائق عندي تصميم محسّن وتقرير احترافي وملفات PVsyst.
> العميل وافق على الفور وأخذنا القرض من البنك."
>
> *— Ahmed K., Lead Engineer, [Company Name], Cairo*

> "I was skeptical the first time I used Shamsi, but the results exceeded my expectations.
> In 8 minutes I had an optimised design, professional report, and PVsyst files.
> The client approved immediately and we got the bank loan."

---

**Time saved:** 2 hours 42 minutes  
**Revenue preserved:** Full project (competitor with faster quote might have won otherwise)  
**Outcome:** System installed, homeowner saving ~1,400 EGP/month on electricity bills
