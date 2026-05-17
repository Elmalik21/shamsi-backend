# Shamsi Smart — Social Media & Content Marketing Plan

**Goal:** 500 registered users within 3 months of public launch  
**Budget:** $500/month paid ads + organic content  
**Primary language:** Arabic (Egyptian dialect) + English subtitles

---

## 1. Platform Strategy

| Platform | Priority | Target Audience | Content Type | Posting Frequency |
|----------|----------|----------------|-------------|------------------|
| Facebook | 🔴 High | Solar engineers, companies | Video demos, case studies, ads | 5x/week |
| LinkedIn | 🔴 High | Engineers, investors, B2B | Technical articles, achievements | 3x/week |
| YouTube | 🟡 Medium | All segments | Tutorial videos, demos, webinars | 1x/week |
| Instagram | 🟡 Medium | Visual content, awareness | Before/after, infographics | 4x/week |
| WhatsApp | 🟡 Medium | Direct referrals | Broadcast groups, case studies | As needed |
| Twitter/X | 🟢 Low | Tech community, academia | Paper announcements, updates | 2x/week |

---

## 2. Facebook Strategy (Primary Channel)

### Target Groups (Organic)

| Group | Members | Strategy |
|-------|---------|---------|
| Renewable Energy Engineers — Egypt (هندسة الطاقة المتجددة — مصر) | 45,000+ | Post case studies, answer technical questions |
| Solar Energy Egypt (الطاقة الشمسية في مصر) | 32,000+ | Demo videos, free tool announcements |
| Egyptian Solar Installers | 18,000+ | Practical tutorials, time-saving content |
| Engineers Egypt | 120,000+ | Technical articles, competition announcements |

**Approach:** Genuine value-first. Never spam. Answer questions, then mention Shamsi as the tool you built.

### Facebook Ads Strategy

**Campaign 1 — Awareness (Month 1–2): $200/month**
- **Objective:** Video views / Reach
- **Audience:** Egypt, age 22–45, interests: Solar energy, renewable energy, engineering
- **Creative:** 90-second demo video with Arabic voiceover
- **CTA:** "شاهد كيف يعمل — Watch how it works"
- **Expected:** 50,000 impressions, 2,000 video views

**Campaign 2 — Conversion (Month 3+): $300/month**
- **Objective:** Website registrations
- **Audience:** Retarget video viewers + Lookalike from email list
- **Creative:** "المهندسون الذين جربوا Shamsi وفّروا 2+ ساعة في كل مشروع" (testimonial ad)
- **CTA:** "ابدأ مجاناً الآن — Start Free Now"
- **Expected:** 200 clicks, 50 registrations at $6 CAC

---

## 3. Content Calendar (Monthly Themes)

### Month 1: Launch & Awareness
*Goal: Build awareness, first 100 registrations*

| Week | Content | Platform | Format |
|------|---------|---------|--------|
| 1 | "Why Egyptian solar design is broken" | FB, LinkedIn | Article + infographic |
| 1 | Product launch announcement | All | Video + post |
| 2 | "5 minutes vs 3 hours" comparison demo | FB, YouTube | Screen recording video |
| 2 | ESED dataset release announcement | LinkedIn, Twitter | Article |
| 3 | Case study: Cairo villa design (before/after) | FB, Instagram | Carousel |
| 3 | "How Shamsi calculates dust zones" | LinkedIn, YouTube | Educational video |
| 4 | User testimonial (beta tester) | FB, Instagram | Video quote |
| 4 | "What is PVsyst? And why Shamsi exports to it" | FB, YouTube | Explainer |

### Month 2: Education & Trust
*Goal: 250 registrations, first 25 Pro subscribers*

| Week | Content | Platform | Format |
|------|---------|---------|--------|
| 1 | Tutorial: "Design your first system in 5 minutes" | YouTube, FB | Full walkthrough |
| 2 | Case study: Alexandria commercial building | FB, LinkedIn | Video + article |
| 3 | "CNN-LSTM vs PVWatts — what's the difference?" | LinkedIn | Technical article |
| 4 | Webinar: "AI-Powered Solar Design in Egypt" | YouTube Live, FB | Live event |

### Month 3: Conversion & Referral
*Goal: 500 registrations, $1,000 MRR*

| Week | Content | Platform | Format |
|------|---------|---------|--------|
| 1 | "Founder Pricing ends soon" | All | Urgency post |
| 2 | Referral programme launch | FB, WhatsApp | Announcement |
| 3 | Case study: Aswan agricultural system | FB, YouTube | Video |
| 4 | Month 3 milestone celebration | All | Stats + thank you |

---

## 4. Content Templates

### Facebook Post — Case Study
```
📊 [مشروع حقيقي] فيلا سكنية في القاهرة — كيف وفّر المهندس 2.5 ساعة

المشكلة: مهندس طاقة شمسية لديه مشروع فيلا 150 م² في المعادي.
المعادل اليدوي: 3 ساعات في Excel، بدون تحسين.

مع Shamsi Smart:
✅ تحليل السطح: 2 ثانية (YOLOv8 اكتشف خزان مياه وطبقة تدفئة)
✅ مساحة قابلة للاستخدام: 98 م²
✅ التحسين: 5 حلول في 30 ثانية
✅ الحل المختار: 20 لوح × Jinko 580Wp، 11.6 كيلووات
✅ العائد السنوي: 14,800 كيلوواط ساعة
✅ فترة الاسترداد: 4.7 سنوات
✅ التصدير: PDF + ملفات PVsyst في 15 ثانية

إجمالي الوقت: 8 دقائق بدلاً من 3 ساعات.

جرّب مجاناً: shamsi.ai
#طاقة_شمسية #مصر #ذكاء_اصطناعي
```

### LinkedIn Post — Technical
```
We documented a critical problem in solar yield prediction that affects
nearly every published ML paper in the field: temporal data leakage.

When we trained Random Forest V1 on Egyptian solar data without
proper temporal validation, we got MAPE = 0.12%, R² = 0.999.
Physically implausible. The model had "seen the future."

After fixing the validation to use GroupKFold by location and
expanding windows (not rolling windows) across temporal boundaries:
MAPE = 3.8%, R² = 0.89. Much more realistic.

Our CNN-LSTM with the corrected protocol: MAPE = 4.2%, R² = 0.91.

The lesson: always check that your rolling statistics respect the
train-test boundary. The paper documents this explicitly as a cautionary
example.

Full methodology: [link to paper]
Dataset (ESED): [Zenodo link]

#MachineLearning #SolarEnergy #DataScience #Egypt
```

### Instagram — Visual (Caption)
```
⏱️ قبل Shamsi: 3 ساعات ← → 5 دقائق بعد Shamsi ✅

🔴 Excel + حاسبة يدوية
🔴 لا تحسين حقيقي
🔴 لا تصدير احترافي

🟢 ذكاء اصطناعي CNN-LSTM
🟢 5 خيارات مثلى في 30 ثانية
🟢 PDF + PVsyst جاهز للبنوك

ابدأ مجاناً 👇 shamsi.ai

#طاقة_شمسية #مصر #ذكاء_اصطناعي #تكنولوجيا
#SolarEnergy #Egypt #AI #CleanEnergy
```

---

## 5. YouTube Channel Plan

### Channel Name: Shamsi Smart — طاقة شمسية ذكية

### Video Series

**Series 1: "تعلم Shamsi Smart" (Learn Shamsi Smart)**
1. "تركيب وأول تصميم في 15 دقيقة" (Setup and first design)
2. "كيف تقرأ نتائج Pareto؟" (Reading Pareto results)
3. "التصدير إلى PVsyst — خطوة بخطوة" (PVsyst export walkthrough)
4. "رؤية الكمبيوتر — كيف تحلّل Shamsi السطح؟" (CV explainer)

**Series 2: "حالات دراسية" (Case Studies)**
1. فيلا سكنية — القاهرة (Residential villa — Cairo)
2. مصنع تجاري — الإسكندرية (Commercial factory — Alexandria)
3. مزرعة — أسوان (Agricultural — Aswan)
4. مبنى مكاتب — المنصورة (Office building — Mansoura)
5. فندق — الغردقة (Hotel — Hurghada)

**Series 3: "وراء الكواليس" (Behind the Scenes)**
1. "كيف بنينا CNN-LSTM لمصر؟" (How we built CNN-LSTM)
2. "قاعدة بيانات ESED — 341,991 سجل" (ESED dataset)
3. "NSGA-II — تحسين مليوني تصميم في 30 ثانية" (NSGA-II explainer)

---

## 6. WhatsApp Broadcast Strategy

**Group list (build during beta):**
- Beta testers group (10 companies)
- Early adopters group (50 first subscribers)
- Referral network (active users who refer others)

**Broadcast content:**
- New feature announcements
- Case studies (PDF attachments)
- Maintenance notifications
- Founder pricing reminders

**Anti-spam rule:** Maximum 2 broadcasts/week. Always valuable content only.

---

## 7. Referral Programme

**Structure:** "Refer a colleague, get 1 month Pro free"

- User shares unique referral link
- Referee signs up → user gets 1 month Pro credit
- No limit on referrals
- Tracked via UTM parameters in Django

**Expected CAC from referral:** ~$5 (vs $40–60 paid ads)
**Target:** 30% of new registrations from referral by Month 6

---

## 8. KPIs

| Metric | Month 1 | Month 3 | Month 6 |
|--------|---------|---------|---------|
| Facebook followers | 200 | 800 | 2,500 |
| LinkedIn followers | 100 | 400 | 1,200 |
| YouTube subscribers | 50 | 200 | 600 |
| Monthly website visitors | 500 | 2,000 | 6,000 |
| Registrations from social | 30 | 120 | 400 |
| Paid ad CAC | — | $50 | $35 |
| Organic CAC | — | $15 | $10 |
