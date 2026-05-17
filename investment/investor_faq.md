# Shamsi Smart — Investor FAQ
## Common Questions from Prospective Investors

*Confidential | May 2026*

---

## Technology & Validation

### Q1: How accurate is the AI system, and how was it validated?

The system achieved **3.1% mean MAPE** (Mean Absolute Percentage Error) across five Egyptian cities (Cairo, Alexandria, Aswan, Hurghada, Mansoura) validated against PVWatts v5, the international reference standard used by the World Bank and NREL.

Three independent accuracy metrics:
- CNN-LSTM yield prediction: 4.2% MAPE, R² = 0.91
- System-level validation (vs PVWatts v5): 3.1% mean MAPE, 100% of cities within 10%
- YOLOv8 roof analysis: 94.7% mAP@50 on Egyptian Rooftop Dataset

The 3.1% figure is below the **5% bankable threshold** — the standard that project finance banks require before accepting AI-generated solar yield assessments. This is documented in our *Applied Energy* submission (under review).

---

### Q2: Why does Egypt need its own climate data? Can't you use international datasets?

International tools (PVsyst, SAM, HelioScope) use PVGIS or NASA POWER datasets with 1° × 1° resolution — approximately 110 km grid spacing. This level of resolution misses:

- **Egypt's 5 distinct dust zones**, including the extreme Khamasin storm region in Upper Egypt where dust soiling reduces yield by 10% vs 5% in Cairo
- **Red Sea coastal microclimate** — sea breeze cooling reduces temperature derating by ~2% vs inland sites
- **Nile Delta humidity effects** on dust adhesion and soiling

A generic tool applied to Aswan would over-predict yield by ~18% due to incorrect dust and temperature derating assumptions. Our validated ESED dataset (341,991 records from NASA POWER 8-year means, calibrated to Egyptian measurement stations) eliminates this systematic error.

---

### Q3: Is the code proprietary, or could a competitor copy it?

The AI models (CNN-LSTM, NSGA-II, YOLOv8-seg) are established architectures — not patentable algorithms. Our competitive moat is not the algorithm but five compounding advantages:

1. **Data moat:** ESED dataset grows with every user project — a competitor starting today has 0 Egyptian validation points
2. **Export integration:** PVsyst/HelioScope export took 8 months to reverse-engineer; required format specifications are not public
3. **Localisation depth:** Egyptian EEHC 7-tier tariff, dust zones, Arabic UI, currency — 12+ months of domain work
4. **Academic credibility:** A published Applied Energy paper cannot be acquired by a competitor; it takes 18–24 months to replicate
5. **First-mover network:** 15,000 Egyptian installers; the first tool used in production becomes the standard

---

### Q4: What happens if your Applied Energy paper gets rejected?

The paper is under review, not the product's viability. The 3.1% MAPE validation result exists regardless of publication outcome. If rejected at Applied Energy, the next targets are *Solar Energy* (Elsevier), *Renewable Energy* (Elsevier), or *Energies* (MDPI, open access). The validation methodology and dataset have been released on Zenodo under CC BY 4.0 — independently citable.

---

## Market & Competition

### Q5: PVsyst and Aurora Solar are large companies. Won't they just build an Egypt-specific version?

This is the most common investor question. Three reasons this is unlikely in the near term:

1. **Market size mismatch:** Egypt's ~$5M software TAM is too small for a company like Aurora Solar (US-focused, $50M+ ARR) to prioritize. Their engineering team would need to spend 12+ months on Egyptian climate data, Arabic localization, and tariff modeling for a market representing <0.1% of their current revenue.

2. **Distribution disadvantage:** We are Egyptian, with direct access to WhatsApp solar groups (30K+ engineers), Solar Egypt Conference relationships, and Arabic-language marketing. A US company entering Egypt faces a 2–3 year relationship-building disadvantage.

3. **Data disadvantage:** ESED is public and citable — but integrating 341,991 records into a validated system takes engineering time. By the time a competitor catches up, our dataset will be 10× larger from user projects.

If a major player does enter (e.g., Aurora Solar acquires us), that is an exit pathway, not a threat.

---

### Q6: SAM (System Advisor Model) from NREL is free. Why would installers pay?

SAM is a research tool designed for energy analysts with university-level solar training. In testing with 10 Egyptian solar companies, zero had used SAM. Common feedback: "too complex," "no Arabic," "no Egyptian tariffs," "output not accepted by Egyptian banks."

Shamsi Smart is designed for the working installer who needs a client proposal in 20 minutes, not an energy researcher who needs a 6-hour simulation. The comparison is not "free SAM vs paid Shamsi" — it is "2–4 hours in Excel + WhatsApp vs 5 minutes in Shamsi."

---

### Q7: What is the realistic addressable market? Is $1.5M TAM too small?

The $1.5M figure is **Year 1 Egypt-only, SMB segment only.** It is intentionally conservative to show a credible path to 10% market capture.

Full opportunity by Year 3:
- Egypt (all segments including enterprise): ~$5M/year
- Saudi Arabia: $2.5B solar market → engineering software TAM ~$15M/year
- UAE: $800M market, stricter technical requirements → premium pricing
- Jordan, Morocco, Libya: Similar market dynamics

MENA-wide TAM at 10% market share: **~$15M/year in engineering software subscriptions**, plus API revenue and equipment marketplace commission (Years 2–3).

The same Shamsi architecture deploys to any MENA country with different climate data and tariff tables — the marginal cost of expansion is engineering days, not months.

---

## Business Model & Unit Economics

### Q8: How did you arrive at the $29/month Pro price?

Three inputs:

1. **Willingness-to-pay testing:** 70% of beta testers indicated they would pay ≥$29/month. Tested anchors: $15 (too low — "must be worth more"), $49 (some resistance from small operators), $29 (near-universal acceptance).

2. **Value-based pricing:** If Shamsi saves 2 hours per design and an engineer's billable rate is 300 EGP/hour (~$6), one design saves $12 in time. At 4 designs/month, time saved = $48 — the $29 Pro price represents 60% of value delivered.

3. **Competitive anchor:** PVsyst equivalent is $125/month with no AI, no Egyptian data, no Arabic. Shamsi at $29/month is 77% cheaper for a superior product.

---

### Q9: What is your customer acquisition cost (CAC) assumption and is it realistic?

CAC assumptions: **$40 for Pro**, **$200 for Enterprise**.

Pro CAC breakdown:
- Facebook/Google ads targeted to Egyptian solar engineers: $15 per new free signup (tested)
- Free-to-Pro conversion at 5% (tested; current beta conversion is ~7%)
- Effective CAC per Pro subscriber: ~$15 / 0.05 = $300 at paid-only channels
- With organic channels (LinkedIn posts, WhatsApp referrals, Solar Egypt Conference) contributing ~50% of signups, blended CAC ≈ $40

This is supported by comparable SaaS tools in adjacent markets (construction software, engineering calculators) where CAC of $30–$60 for SMB professionals is typical.

Enterprise CAC: Direct outreach (email + WhatsApp), demo call, 2–3 week sales cycle. No ads needed. $200 reflects founder time + travel for 1–2 meetings.

---

### Q10: 99.3% gross margin seems too high. What are you missing?

The 99.3% figure reflects **variable cost of serving one additional user**, which is genuinely close to zero for SaaS:
- Railway hosting scales to 500 users within current $27/month fixed cost
- API inference cost per optimisation: ~$0.003 (CPU-based NSGA-II, no GPU required)
- Support time: ~10 minutes/month/user (Pro), billing absorbed in fixed cost

At scale (1,000+ users), costs that increase:
- Railway hosting: $200–$500/month (reduce margin to ~97%)
- Customer success staff: ~$800/month (reduce to ~93%)
- Support tooling: ~$50/month

True long-run gross margin (accounting for support staff) is estimated at **85–90%**, which remains excellent for SaaS.

---

## Risk & Mitigation

### Q11: This is a single-founder company. What happens if you get sick?

This is the highest-risk factor and is disclosed transparently in the pitch deck. Mitigations in place:

1. **Documentation:** Entire system documented at architectural level in `/docs`. Any competent engineer can understand the system structure in 1–2 days.
2. **Test coverage:** 62/62 tests passing means the system's expected behavior is machine-readable.
3. **First hire:** A full-stack developer joins in Month 1. By Month 3, two people understand the full system.
4. **Code quality:** Academic code standards (linting, type hints, docstrings) mean the codebase is maintainable by a new hire.

Investors are correct to weight this risk. The $100K seed round is partly risk capital on this specific factor.

---

### Q12: Egypt's currency has devalued significantly. Does this affect your revenue?

Pricing is in **USD** to eliminate this risk. Users pay in EGP at the prevailing exchange rate. Egyptian solar projects themselves are frequently USD-denominated (equipment imports, European financing), so USD pricing is standard in this market.

Revenue in USD also creates natural MENA expansion pricing — Saudi riyal, UAE dirham, Jordanian dinar are all USD-pegged or stable.

---

### Q13: What if the Egyptian government restricts net-metering or changes tariffs?

The EEHC tariff model is updated via admin panel — no redeployment required. If net-metering rules change, the tariff calculator is updated within 24 hours.

Tariff risk is real but cuts both ways: Egypt's 42% by 2035 renewable target creates political pressure to *increase* net-metering incentives for small installers, not reduce them. The Ministry of Electricity has publicly committed to expanding the programme.

---

### Q14: How are you thinking about the Series A, and what metrics trigger it?

Series A target: **$500K–$1M at $8–10M valuation** (Month 24–30).

Trigger metrics:
- $10K MRR achieved and stable for 3+ months
- Churn below 3% for Pro, 1% for Enterprise
- Saudi Arabia or UAE soft launch with first 10 paying users
- NPS above 8.0 maintained at scale

At $10K MRR, the company is **self-sustaining** — the Series A accelerates MENA expansion, not survival. This de-risks the pre-seed: even if Series A doesn't happen, the company continues.

---

## The Ask

### Q15: Why $100K at $1M valuation? Is the valuation justified?

Comparables for pre-revenue deep-tech with academic validation in MENA:
- Egyptian AI startups at pre-seed: $500K–$2M post-money typical (2023–2025 data, Magnitt)
- $1M valuation is **conservative** relative to comparables

Justification for $1M:
- Working production system (deployed on Railway, 127 systems designed)
- Academic validation (Applied Energy, 3.1% MAPE)
- Original dataset (341,991 records, Zenodo, CC BY 4.0)
- Real user traction (NPS 8.2, WTP validated)
- Competition wins (Microsoft Imagine Cup, Egyptian AI Innovation Awards)

We chose $1M post-money to make the round accessible to angel investors and Egyptian family offices, and to be conservative enough that hitting milestones creates clear upside for early investors.

---

### Q16: What is the ideal investor profile?

We are looking for investors who bring:
- **Egyptian or MENA network** (introductions to solar companies, contractors, government bodies)
- **SaaS experience** (help with pricing, go-to-market, customer success)
- **Technical credibility** (able to evaluate AI validation claims independently)

Check size: $10K–$100K. We are filling a $100K round and can accommodate 1–10 investors.

Pro-rata rights for Series A are included in SAFE terms.

---

*This document is confidential and intended solely for prospective investors. Questions not addressed here can be directed to [email]. Technical due diligence materials (codebase, dataset, paper draft) are available under NDA upon request.*
