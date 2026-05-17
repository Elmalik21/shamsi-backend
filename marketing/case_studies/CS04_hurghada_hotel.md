# Case Study CS-04: Hurghada Hotel Complex
## Largest Case — 180 kWp Resort System, Enterprise Export

**Location:** Hurghada, Red Sea Governorate  
**System size:** 180 kWp (310 panels across 3 roof zones)  
**Design time:** 22 minutes (including 3 roof zone analysis)  
**Outcome:** PVsyst report accepted by European development bank

---

## Background

A 4-star hotel resort in Hurghada was seeking financing from a European development finance institution (DFI) for a rooftop PV system. The DFI's term sheet required a PVsyst simulation by an independent engineer as a condition for the $800K loan.

The hotel's Egyptian engineering consultant had never used PVsyst. Hiring a specialist PVsyst engineer would have cost 25,000 EGP and taken 2 weeks. Instead, they used Shamsi Smart Enterprise tier to generate PVsyst-ready files, then had a local engineer verify in PVsyst.

## The Multi-Zone Challenge

The hotel complex had three separate roof zones:
- **Zone A** (Main building): 280 m², flat, south-facing
- **Zone B** (Restaurant wing): 120 m², slight slope, 15° south-southeast
- **Zone C** (Pool area canopy): 180 m² (south-facing shade structure)

Shamsi Smart Enterprise supports multi-zone analysis: three separate roof images were processed, then the results combined into a single system optimisation.

**Hurghada Climate (from ESED dataset):**
- GHI: 6.7 kWh/m²/day
- Avg temperature: 28.5°C (year-round)
- Dust zone: 3 (extreme — near Red Sea coast)
- Temperature derating: 12.8% (slightly less extreme than Aswan due to sea breeze cooling)

## Design Output

**Zone A:** 120 panels × 580Wp = 69.6 kWp  
**Zone B:** 80 panels × 580Wp = 46.4 kWp  
**Zone C:** 110 panels × 580Wp = 63.8 kWp  
**Total:** 310 panels = 179.8 kWp (≈180 kWp)

**System performance:**
- Annual yield: 232,400 kWh
- Specific yield: 1,720 kWh/kWp/year (matches CS-04 validation case exactly)
- Performance Ratio: 0.77
- Self-consumption ratio: ~65% (hotel load profile: 18–22 hours/day AC, kitchen, pool)
- Grid export: ~35% → sold at net-metering commercial rate

**Financial (commercial tariff, EEHC August 2024):**
- Annual savings: 186,000 EGP (self-consumption) + 28,000 EGP (export) = 214,000 EGP
- Total cost: 1,620,000 EGP
- Simple payback: 7.6 years
- 25-year NPV: 4,850,000 EGP
- IRR: 18.2%

## DFI Financing Process

1. Shamsi generated PVsyst bundle (4 files) for each zone → 3 ZIP archives
2. Egyptian engineer imported all three into PVsyst 7.2
3. PVsyst simulation ran with hourly TMY data
4. PVsyst result: 228,100 kWh/year (1.9% below Shamsi — within expected discrepancy)
5. Independent engineer signed off on PVsyst report
6. DFI accepted the PVsyst report → loan approved

**Cost comparison:**
- Specialist PVsyst engineer: 25,000 EGP + 2-week delay
- Shamsi Smart Enterprise (3 months): 1,497 EGP ($499 × 3) + 22-minute design session
- **Saving: 23,500 EGP and 2 weeks**

## Testimonial

> "Shamsi Smart made PVsyst accessible to our team for the first time.
> We generated all the files, our engineer verified them in PVsyst,
> and the bank accepted the report. The loan was approved in 3 weeks
> instead of the usual 2–3 months for similar projects."
>
> *— Project Director, [Hotel Group], Hurghada*

---

**Time saved:** 2 weeks timeline compression + 23,500 EGP specialist fees  
**Financing unlocked:** $800K DFI loan  
**System capacity:** 180 kWp (largest Shamsi case study)  
**Annual CO₂ avoided:** ~110 tonnes/year
