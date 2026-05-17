# Case Study CS-03: Aswan Agricultural Pump
## Off-Grid Solar for Irrigation — Egypt's Highest-Irradiance Zone

**Location:** Agricultural land, Kom Ombo district, Aswan  
**System:** 7.5 kWp off-grid for irrigation pump  
**Design time:** 6 minutes  
**Irradiance:** 7.2 kWh/m²/day (Egypt's highest)  
**Dust zone:** Extreme (Zone 3)

---

## Background

A date palm farmer in the Kom Ombo district needed a solar pumping system to replace a diesel generator running his 5.5 kW irrigation pump. The diesel cost was approximately 3,200 EGP/month during the 8-month irrigation season. There was no grid connection at the field location.

The farmer's nephew, a junior electrical engineer, used Shamsi Smart to design the system — his first solar design ever.

## The Unique Challenge of Aswan's Climate

Aswan presents both opportunity and complexity:
- **Opportunity:** 7.2 kWh/m²/day GHI — Egypt's highest irradiance
- **Challenge 1:** Extreme heat — average summer temperature 40°C, peak 47°C
- **Challenge 2:** Extreme dust — Zone 3 (Khamasin storms, daily wind-blown sand)
- **Challenge 3:** Temperature derating — cell temperatures regularly exceed 65°C at NOCT

Shamsi Smart applies Aswan-specific parameters automatically:
- GHI: 7.2 kWh/m²/day (from NASA POWER 8-year mean)
- Dust zone: 3 (extreme) → soiling loss 10% vs 5% for Cairo
- Temperature derating: 14.3% at typical cell temperature vs STC
- NOCT model calibrated for Aswan's 24h-average conditions

## Design Process

**Roof analysis skipped** (open field installation — user entered dimensions manually: 25 m × 10 m available)

**System configuration selected:**
The farmer needed an off-grid system (no net-metering available), so Shamsi's optimiser applied off-grid sizing constraints: battery bank sizing for 2-day autonomy, oversized PV array to compensate for dust.

**Optimal design:**
- 13 panels × 580Wp = 7.54 kWp
- Growatt 10000-TL3 inverter (modified for off-grid with battery)
- Battery bank: 24V × 400Ah (LiFePO4)
- Dust management: monthly cleaning scheduled in maintenance plan
- Annual yield (with 10% dust loss): 18,200 kWh

**Cost and Economics:**
- Total system cost: 145,000 EGP
- Diesel avoided: 3,200 EGP/month × 8 months = 25,600 EGP/year
- Simple payback: 5.7 years
- 20-year NPV (vs continued diesel): 382,000 EGP

## Shamsi vs Generic Design Tool

A generic tool (not Egypt-specific) would have applied:
- Default dust soiling: 2% (vs 10% for Aswan Zone 3)
- Default temperature derating: 5% flat (vs 14.3% NOCT-calculated)
- Result: over-prediction of yield by ~18%
- Result: under-sizing by ~2 panels
- Result: system delivers less than 80% of expected yield in summer peak

Shamsi's Aswan-calibrated design avoids this systematic error.

## Outcome

System installed. First irrigation season (summer 2026): pump ran continuously during daylight hours, diesel generator used only 3 days during an extended Khamasin dust storm. Diesel savings: ~3,000 EGP/month vs 3,200 projected (actual dust loss slightly higher than model during Khamasin — within expected range).

The engineer who designed it:
> "أول تصميم حقيقي عملته في حياتي كان على Shamsi Smart.
> كنت خايف من الموضوع بس الذكاء الاصطناعي حسب كل حاجة —
> حتى الغبار الشديد في أسوان. الجهاز شغال تمام."
>
> "My first real solar design was on Shamsi Smart.
> I was nervous but the AI calculated everything —
> even Aswan's extreme dust. The system works perfectly."

---

**Time saved:** First-time designer completed in 6 minutes (vs unknown hours of research)  
**Client outcome:** Diesel cost eliminated (estimated 25,000 EGP/year saved)  
**Environmental:** ~9.6 tonnes CO₂/year avoided (vs diesel generator)
