# Shamsi Smart — User Testing Protocol v1.0

**Programme:** Beta Validation  
**Duration:** 4 weeks (Week 1–2: Sessions, Week 3–4: Analysis & Follow-up)  
**Target:** 10 Egyptian solar companies, 3 real projects each  
**Goal:** Validate usability, accuracy, and willingness-to-pay before public launch

---

## 1. Objectives

| # | Objective | Success Criterion |
|---|-----------|------------------|
| 1 | Usability | ≥8/10 users rate experience ≥7/10 |
| 2 | Time savings | Mean time saved ≥60 min per project |
| 3 | Accuracy | ≥7/10 users find results "accurate or better" vs their manual estimate |
| 4 | WTP | ≥6/10 willing to pay $10–50/month |
| 5 | Bugs | Zero critical bugs (data loss, wrong output, crash) |

---

## 2. Participant Selection

### Tier 1 — Large Companies (3 participants)

These companies provide credibility and high-volume feedback. They are most likely to become Enterprise customers.

| Company | Location | Projects/Month | Contact |
|---------|----------|----------------|---------|
| Solar Arabia Egypt | Cairo | 50+ | [email] |
| Infinity Solar | Cairo / Alexandria | 30+ | [email] |
| Enertec Egypt | Cairo | 25+ | [email] |

**Recruitment script:** "We're inviting you as a founding partner to test our AI solar design tool before launch. You'll get free Pro access for 6 months in exchange for structured feedback. Your company will be featured as a reference customer."

### Tier 2 — Medium SMEs (4 participants)

Core market. Representing Cairo, Alexandria, Upper Egypt, and the Delta.

| Governorate | Company Size | Monthly Projects |
|-------------|-------------|-----------------|
| Cairo | 5–15 employees | 10–25 |
| Alexandria | 3–10 employees | 8–20 |
| Aswan / Luxor | 3–8 employees | 5–15 |
| Mansoura | 3–10 employees | 8–20 |

### Tier 3 — Freelance Engineers (3 participants)

Early adopters and word-of-mouth multipliers. Typically active in engineering Facebook groups and forums.

**Profiles:** 2–8 years experience, 5–15 projects/month, primarily residential.

---

## 3. Three Test Projects

Each participant completes all three project types in a 90-minute session:

### Project A — Residential Villa

```
Location:     Provided by participant (their real next project or typical case)
Roof:         120–150 m²
Consumption:  800 kWh/month (bills provided by participant)
Budget:       150,000–200,000 EGP
Goal:         Maximum self-consumption
```

### Project B — Commercial Building

```
Location:     Participant provides (factory, office, school)
Roof:         300–500 m²
Consumption:  2,000–5,000 kWh/month
Budget:       500,000–800,000 EGP
Goal:         Minimum payback period
```

### Project C — Agricultural Pump

```
Location:     Agricultural land (Delta or Upper Egypt)
System:       5–10 kW off-grid or net-metered irrigation pump
Consumption:  Seasonal (summer peak)
Budget:       80,000–120,000 EGP
Goal:         Minimum cost per kWh
```

---

## 4. Session Protocol

### Pre-session (Day before — 15 min)

1. Send participant their login credentials
2. Share one-page quick-start guide (Arabic)
3. Confirm they have their project details ready
4. Send Zoom/Teams link for observed session

### Observed Session (90 min)

**Facilitator script:**

> "Thank you for joining our testing programme. Today you'll complete three solar design projects using Shamsi Smart. Please think out loud — tell us what you're doing and why, what confuses you, and what you like. We're testing the software, not you. There are no wrong answers. We'll record the session for internal analysis only."

**Session structure:**

| Time | Activity |
|------|----------|
| 0:00–0:10 | Pre-test survey (current tools, baseline time) |
| 0:10–0:40 | Project A — Residential villa |
| 0:40–1:05 | Project B — Commercial building |
| 1:05–1:20 | Project C — Agricultural pump |
| 1:20–1:30 | Post-test survey + open debrief |

**Facilitator notes:**
- Do not assist unless participant is truly stuck after 5 minutes
- Note every moment of hesitation, confusion, or delight
- Record time from project start to first result display
- Note whether participant tries to export to PVsyst

### Post-session follow-up (1 week later — 15 min call)

- Did they use Shamsi on a real project since the session?
- Any issues encountered independently?
- Has their opinion changed?
- Final NPS score?

---

## 5. Metrics and Measurement

### Quantitative Metrics

| Metric | How Measured | Target |
|--------|-------------|--------|
| Task completion rate | % of 3 projects completed without abandoning | 100% |
| Time to first result | Clock from "start" to Pareto solutions appearing | <5 min |
| Total session time | Actual time for all 3 projects | <90 min |
| Error count | Facilitator notes — UI errors, wrong results | 0 critical |
| NPS score | Post-survey question 11 (0–10) | ≥7 mean |
| WTP | Post-survey question 9 | ≥60% willing |

### Qualitative Data

- Think-aloud transcripts (5–10 key quotes per session)
- Usability issues classified by severity (Critical / Major / Minor / Cosmetic)
- Feature requests ranked by frequency
- Verbatim testimonials (with written permission)

### Comparison Baseline

Before the session, ask each participant:

> "For your last residential project, how long did the system design calculation take (not site visit, just the optimisation/sizing calculation)?"

Record this as their **personal baseline**. Compare against Shamsi time in the session.

---

## 6. Survey Questions

### Pre-Test Survey (10 questions, 10 min)

1. What tools do you currently use for solar system design? (Multi-select: Excel / PVsyst / HelioScope / SAM / Other / Manual calculation)
2. How long does a typical residential system design take you? (Hours)
3. What is your biggest pain point in the current design process? (Open text)
4. How many projects do you design per month on average?
5. What percentage of projects do you verify in PVsyst or similar simulation software?
6. How would you rate your confidence in the accuracy of your current designs? (1–10)
7. Have you ever lost a client because your quote took too long? (Yes / No / Not sure)
8. What features would a "dream" solar design tool have? (Open text)
9. How much would you pay monthly for a tool that cuts design time by 90%? (Free / $10 / $20 / $30 / $50 / >$50 / Wouldn't pay)
10. Which features are most important to you? (Rank: Speed / Accuracy / Egyptian tariffs / PVsyst export / Roof CV / Arabic interface / Price)

### Post-Test Survey (11 questions, 10 min)

1. Overall, how would you rate your experience with Shamsi Smart? (1–10)
2. How does Shamsi Smart compare to your current design method? (Much worse / Worse / Same / Better / Much better)
3. How much time did Shamsi Smart save you per project? (Minutes/hours estimate)
4. How accurate did the AI results seem compared to your expectations? (1–10)
5. How confident are you that the Pareto-optimal solutions are genuinely better than what you'd design manually? (1–10)
6. What was the most confusing part of the interface? (Open text)
7. What feature did you like most? (Open text)
8. What feature was most missing? (Open text)
9. Would you use Shamsi Smart for real client projects? (Yes / No / Only with verification)
10. Would you recommend Shamsi Smart to a colleague? (1–10, NPS)
11. If Shamsi Smart were available at Pro tier ($29/month), would you subscribe? (Definitely yes / Probably yes / Unsure / Probably no / Definitely no)

### Testimonial Consent (end of session)

> "We'd love to feature your experience in our website and marketing materials. Would you be willing to provide a written testimonial or appear in a short video quote (30 seconds)?  
> Written only: ☐ Yes ☐ No  
> Video quote: ☐ Yes ☐ No  
> Company name and logo visible: ☐ Yes ☐ No (anonymous OK)"

---

## 7. Deliverables from Testing Programme

1. **Testing Report** (`user_testing/results/testing_report.md`) — aggregated findings
2. **Bug List** (`user_testing/results/bugs.csv`) — prioritised by severity
3. **Feature Requests** (`user_testing/results/feature_requests.csv`) — ranked by frequency
4. **Testimonials** (`user_testing/results/testimonials.md`) — 5+ quotes with consent
5. **NPS Report** — per-segment breakdown
6. **WTP Analysis** — pricing sensitivity curve
7. **Decision Brief** — go/no-go for public launch + pricing finalisation

---

## 8. Success Criteria and Go/No-Go Decision

| Criterion | Threshold | Go | No-Go Action |
|-----------|-----------|-----|-------------|
| Mean NPS | ≥7.0/10 | ✅ | Fix top 3 UX issues, re-test |
| Task completion | 100% | ✅ | Fix blocking bugs immediately |
| Time saved | ≥60 min | ✅ | Investigate bottlenecks |
| WTP ≥$10/month | ≥60% | ✅ | Revisit value prop |
| Critical bugs | 0 | ✅ | Fix before launch |
| Accuracy confidence | ≥7.0/10 | ✅ | Improve explanations/validation UI |

**Launch decision:** All 6 criteria met → Proceed to soft launch. Any criterion failed → Address and re-test with 5 new participants.
