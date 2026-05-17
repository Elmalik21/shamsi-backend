# Case Study CS-02: Alexandria Commercial Factory
## AI Optimisation Improves NPV by 19% vs Manual Design

**Location:** El-Ameriya Industrial Zone, Alexandria  
**System size:** 86.8 kWp (with 3-phase commercial tariff)  
**Design time:** 14 minutes (vs 4.5 hours manual)  
**Outcome:** 19% better NPV than competing manual proposal

---

## Background

A textile factory in Alexandria's El-Ameriya Industrial Zone was consuming 22,000 kWh/month on Egypt's commercial 3-phase tariff (Tier 5–6, 1.20–1.40 EGP/kWh). The factory owner had received one quote from a local EPC company — a straightforward "maximum panels" design — and wanted a second opinion before committing 900,000 EGP.

## The Challenge

- Large industrial flat roof: 480 m²
- High consumption (22,000 kWh/month) → significant tariff savings potential
- Adjacent rooftop structure casting partial shading on northeast corner (15% of roof)
- Egyptian commercial net-metering cap: 500 kW
- Owner wanted maximum NPV, not maximum capacity

## Shamsi Smart Process

**Roof Analysis:** Shamsi CV detected the main roof boundary, adjacent structure casting shade, skylights (excluded), and 6 AC compressor units. Net usable area: 387 m².

**NSGA-II Optimisation:** With the 3-phase commercial tariff applied, the optimiser found that the maximum-panels solution (94 panels, 54.5 kWp) was not optimal — the inverter becomes undersized relative to panel capacity, increasing clipping losses. The optimal solution (150 panels × 580Wp = 86.8 kWp) with two Huawei SUN2000 inverters achieved better energy balance.

**Five Solutions Returned:**

| Option | Panels | kWp | Annual kWh | Cost (EGP) | Payback | NPV (EGP) |
|--------|--------|-----|-----------|-----------|---------|----------|
| A (max yield) | 168 | 97.4 | 128,900 | 1,020,000 | 4.9 yr | 3,210,000 |
| **B (best NPV)** | **150** | **86.8** | **114,900** | **892,000** | **4.6 yr** | **3,450,000** |
| C (min cost) | 120 | 69.6 | 92,000 | 730,000 | 4.2 yr | 2,980,000 |

The "best NPV" option (B) was selected — 7% fewer panels but 19% better NPV than Option A, because the inverter sizing is better matched.

## Head-to-Head vs Competing Proposal

| Metric | Competing EPC | Shamsi Smart (Opt B) | Difference |
|--------|--------------|----------------------|-----------|
| Design | 94 panels, 54.5 kWp | 150 panels, 86.8 kWp | — |
| Annual yield | 72,100 kWh | 114,900 kWh | +59% |
| Cost | 810,000 EGP | 892,000 EGP | +10% |
| Payback | 7.1 years | 4.6 years | −35% |
| 25-year NPV | 2,380,000 EGP | 3,450,000 EGP | **+45%** |
| Bank-ready files | No | Yes | — |

The competing EPC had under-dimensioned the system significantly (54.5 kWp for a 22,000 kWh/month factory is only ~36% self-sufficiency). Shamsi's design covers ~64% of consumption with better economic return.

## Outcome

Factory owner chose Shamsi Smart's Pareto-optimal design. The installation company won the contract (previously at risk of losing to the cheaper but poorly dimensioned competitor proposal).

---

**Time saved:** 4 hours 16 minutes  
**Additional revenue for installer:** Full contract won over competitor  
**Client outcome:** Electricity bill reduced by ~9,400 EGP/month; payback in 4.6 years
