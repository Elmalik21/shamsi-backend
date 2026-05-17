# Shamsi Smart — Business Model Canvas

**Version:** 1.0 — Pre-Launch  
**Date:** May 2026  
**Status:** Validated through 10 beta users (testing programme)

---

## 1. Value Propositions

### For Solar Engineers and Installation Companies

| Pain Today | Shamsi Smart Solution | Quantified Benefit |
|-----------|----------------------|-------------------|
| 2–4 hours manual design | AI optimisation in <5 minutes | 97% time reduction |
| Suboptimal systems | NSGA-II Pareto-optimal design | 15–20% NPV improvement |
| No Egyptian data | 8 years NASA POWER + EEHC tariffs | Zero manual data lookup |
| Expensive tools (PVsyst: $1,500/yr) | Free tier + $29/month Pro | 77% cheaper with more features |
| No Arabic support | Arabic UI, Egyptian tariff model | Zero language barrier |
| Roof measurement takes hours | YOLOv8 automated analysis | 3 hours → 2 seconds |
| Can't afford bankable reports | PVsyst export built-in | Bank-ready output from day 1 |

### For End Customers (Homeowners and Businesses)

- Faster quotes (same day vs 1 week)
- Transparent comparison (5 design options vs 1 take-it-or-leave-it quote)
- AI-optimised performance (15–20% better than industry average)
- Professional documentation for financing applications

---

## 2. Customer Segments

### Segment A — Small Solar Installation Companies (Primary, 60% revenue)

**Profile:** 3–15 employees, 10–30 projects/month, primarily residential and SME commercial  
**Geography:** Greater Cairo (40%), Alexandria (20%), Upper Egypt (20%), Delta (20%)  
**Current tooling:** Excel (80%), PVsyst occasionally (15%), pen and paper (5%)  
**Key buyer:** Owner/technical director  
**Budget:** $20–50/month  
**Market size:** ~800 companies in Egypt (200 active online)

### Segment B — Freelance Solar Engineers (Primary, 25% revenue)

**Profile:** Solo consultants, 5–20 projects/month, strong word-of-mouth networks  
**Geography:** All governorates  
**Current tooling:** Excel, manual calculation  
**Budget:** $10–30/month  
**Market size:** ~1,500 individuals in Egypt (500 active online)

### Segment C — Large EPC and Developer Companies (Secondary, 15% revenue)

**Profile:** 50+ employees, 50–200+ projects/year, need API integration and white-label reports  
**Geography:** Cairo, multi-governorate operations  
**Budget:** $300–500/month  
**Market size:** ~30 companies in Egypt

### Future Segments (Year 2+)

- Saudi Arabia, UAE, Jordan — identical climate and methodology challenges
- Banks and DFIs — portfolio-level feasibility screening
- NGOs and development agencies — rural electrification programmes

---

## 3. Revenue Streams

### 3.1 SaaS Subscriptions (80% of revenue)

| Tier | Price | Optimisations | Exports | CV | Support | Users |
|------|-------|--------------|---------|-----|---------|-------|
| **Free** | $0/month | 3/month | PDF only | No | Community | Unlimited |
| **Pro** | $29/month | Unlimited | All formats | Yes | Email | 1 |
| **Enterprise** | $499/month | Unlimited | All + White-label | Yes + bulk | Priority + calls | 10 |

**Annual discounts:** 20% (Pro: $278/year; Enterprise: $4,790/year)

### 3.2 Pay-Per-Use API (15% of revenue, Year 2)

Targets software integrators and platforms that want to embed Shamsi's AI:

| Call Type | Price |
|-----------|-------|
| System optimisation | $2.00 |
| Roof CV analysis | $5.00 |
| Complete project (optimise + CV + all exports) | $10.00 |
| Bulk (100+ calls/month) | 30% discount |

### 3.3 Equipment Marketplace Commission (5% of revenue, Year 3)

Partner with Egyptian solar equipment importers and distributors:
- Manufacturer lists products with market prices in Shamsi's catalogue
- When a design is exported with specific equipment, a referral link is included
- Commission: 2–5% of equipment value for verified purchases
- No change to user experience — equipment recommendations already present

---

## 4. Cost Structure

### Fixed Costs (Monthly)

| Item | Cost |
|------|------|
| Railway hosting (2 vCPU, 4 GB) | $25 |
| PostgreSQL (Railway managed) | $0 (included) |
| Netlify (frontend hosting) | $0 (free tier → $19 at scale) |
| Domain (shamsi.ai) | $2 |
| Transactional email (Resend) | $0 (free tier → $20 at scale) |
| Error monitoring (Sentry) | $0 (free tier) |
| **Total fixed** | **~$27/month** |

### Variable Costs (Per Active User/Month)

| Item | Cost |
|------|------|
| NASA POWER API calls | $0 (free API) |
| Google Maps Static API (CV) | ~$0.05 |
| AI inference (CPU) | ~$0.10 |
| Storage (per user data) | ~$0.02 |
| Email sends | ~$0.03 |
| **Total variable** | **~$0.20/user/month** |

### Unit Economics

| Tier | Price | Variable Cost | Contribution | Margin |
|------|-------|--------------|-------------|--------|
| Free | $0 | $0.20 | -$0.20 | — |
| Pro | $29 | $0.20 | $28.80 | 99.3% |
| Enterprise | $499 | $0.20 | $498.80 | 99.9% |

**Break-even:** 1 Pro user covers 1.1 months of fixed costs. 2 Pro users = profitable.

### Payroll (When Funded)

| Role | Monthly Cost (Egypt) |
|------|---------------------|
| Full-stack developer | $800 |
| Sales/Marketing | $600 |
| Part-time support | $300 |
| **Total payroll** | **$1,700/month** |

---

## 5. Financial Projections

### Monthly MRR Build (18-Month Model)

| Month | Free | Pro | Enterprise | MRR | Cumulative Revenue |
|-------|------|-----|-----------|-----|------------------|
| 0 (Beta) | 10 | 0 | 0 | $0 | $0 |
| 1 | 30 | 5 | 0 | $145 | $145 |
| 2 | 60 | 12 | 0 | $348 | $493 |
| 3 | 100 | 25 | 1 | $1,224 | $1,717 |
| 6 | 250 | 70 | 3 | $3,527 | ~$10K |
| 9 | 450 | 130 | 6 | $6,764 | ~$35K |
| 12 | 700 | 200 | 10 | $10,790 | ~$80K |
| 18 | 1,500 | 400 | 25 | $24,075 | ~$210K |

**Revenue mix at Month 12:**
- Pro (200 × $29): $5,800 (54%)
- Enterprise (10 × $499): $4,990 (46%)
- API: $0 (not yet launched)

**Path to profitability:**
- Fixed + payroll costs at Month 12: ~$1,727/month
- MRR at Month 12: ~$10,790
- **Operating margin at Month 12: ~84%**

### Key Assumptions

- Free-to-Pro conversion: 5% (industry SaaS average: 2–8%)
- Monthly churn: 3% Pro, 1% Enterprise
- CAC via content + community: $40 (Pro), $200 (Enterprise)
- LTV (Pro): $29 / 3% churn = $967 (LTV/CAC = 24x)
- LTV (Enterprise): $499 / 1% churn = $49,900 (LTV/CAC = 250x)

---

## 6. Go-to-Market Strategy

### Phase 1: Beta Validation (Month 0–2)

**Goal:** 10 paying-quality users, 0 critical bugs, validated value prop

- Personal outreach to 10 solar companies for free beta
- Collect testimonials and case studies
- Fix bugs, refine UX based on feedback
- Finalise pricing model

### Phase 2: Soft Launch (Month 3–4)

**Goal:** 100 registered users, first $500 MRR

**Channels:**
- Egyptian Solar Energy Facebook groups (3 groups, 30K+ combined members)
- LinkedIn posts by founder + supervisor
- Engineering WhatsApp networks
- Direct DMs to companies identified via Instagram/Facebook ads
- Guest post in Renewable Energy Egypt newsletter

**Offer:** "Founder Pricing — 40% off forever for first 50 Pro subscribers"

### Phase 3: Public Launch (Month 5–6)

**Goal:** 250 users, $3,500 MRR

**Channels:**
- Google Ads (solar + Egypt + PVsyst keywords)
- Facebook/Instagram ads targeting solar engineers
- YouTube demo video (3 min product tour)
- Press release to Mubasher, Amwal, Tech Arabia
- Conference presence: Solar Egypt, RECONF, Energy Africa

### Phase 4: Scale (Month 7–12)

**Goal:** 700 users, $10,000 MRR

- Double down on top 2 acquisition channels
- Enterprise sales outreach (30 target companies by name)
- Partner with solar equipment distributors for co-marketing
- Launch affiliate programme (installers refer colleagues)
- Begin Saudi Arabia/UAE landing page + waitlist

---

## 7. Competitive Moats

| Moat | Description | Durability |
|------|-------------|-----------|
| Data moat | ESED dataset (8 years, 119 locations) grows with every API call | High — grows over time |
| Integration moat | Only tool exporting AI designs directly to PVsyst | Medium — competitors could add |
| Localisation | Egyptian tariffs, Arabic UI, dust zones, local equipment | Medium |
| Academic credibility | Published in Applied Energy, peer-reviewed methodology | High — takes years to replicate |
| Network effects | More users → more anonymised data → better model | Medium-high |
| Switching costs | Projects stored, team trained, reports branded | Medium |

---

## 8. Key Metrics Dashboard (North Stars)

| Metric | Month 3 Target | Month 12 Target |
|--------|---------------|----------------|
| Weekly Active Users (WAU) | 50 | 300 |
| Monthly Recurring Revenue (MRR) | $1,000 | $10,000 |
| Free → Pro conversion rate | 5% | 8% |
| Monthly churn (Pro) | <5% | <3% |
| CAC (blended) | <$60 | <$40 |
| NPS score | ≥40 | ≥50 |
| API response time (p95) | <3s | <2s |
| Support tickets/user/month | <0.5 | <0.2 |
