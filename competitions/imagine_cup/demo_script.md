# Shamsi Smart — Demo Video Script
## Microsoft Imagine Cup 2026 | 90-Second Pitch

---

## Shot-by-Shot Breakdown

### Scene 1 — The Problem (0:00–0:18)

**Visual:** Split screen. Left: installer in Cairo, shirt sleeves, surrounded by printouts, typing in Excel. Clock in corner: 10:47 AM.  
**Right:** Same installer, same clock: 1:23 PM. Still in Excel. Customer waiting.

**Voiceover (Arabic, subtitled in English):**
> "In Egypt, we have one of the best solar resources in the world. 7 hours of sunshine a day. But most installers still design systems by hand. It takes hours. And the systems we build? They could be 20% better."

**Text overlay:** "90% of Egyptian solar installers use Excel for system design. (ESIA, 2023)"

---

### Scene 2 — Open Shamsi Smart (0:18–0:30)

**Visual:** Installer closes Excel in frustration. Opens browser. Shamsi Smart loads — clean, Arabic/English interface. Logo animates: ☀️ Shamsi Smart.

**Voiceover:**
> "We built Shamsi Smart. An AI platform that does in five minutes what takes hours by hand — and does it better."

**Action (screen recording):**
- Type address: "15 El-Tahrir Street, Dokki, Giza"
- Drop pin on map. Click "Analyze Roof".

---

### Scene 3 — Computer Vision (0:30–0:42)

**Visual:** Satellite view of roof appears. YOLOv8 processes in real time — bounding boxes appear: green=usable roof, yellow=water tank, orange=AC unit.

**Text overlay:**
> "AI roof analysis: 2.3 seconds"  
> "Usable area: 48.2 m²"  
> "Obstacles detected: 2"  
> "Panel capacity: up to 21 panels"

**Voiceover:**
> "Computer vision maps the roof, finds every obstacle, and calculates exactly how many panels fit. In two seconds."

---

### Scene 4 — Optimisation Results (0:42–0:58)

**Visual:** Dashboard loads with 5 side-by-side cards. Each shows: system size, yield, cost, payback. One card highlighted: "Best ROI".

**Voiceover:**
> "Our AI tests two million possible designs and returns five Pareto-optimal solutions. The engineer chooses what fits the customer best."

**Installer clicks "Best ROI" card — detail view:**
- 14 kWp system (24 panels × Jinko 580 Wp)
- Huawei 17 kW inverter
- Annual yield: 19,600 kWh
- 25-year NPV: 185,000 EGP
- Payback: 4.9 years
- CO₂ avoided: 9.3 tonnes/year

**Text overlay:** "4.9 years payback. 94% accuracy. 30 seconds."

---

### Scene 5 — Export (0:58–1:10)

**Visual:** Click "Download All". Progress bar. ZIP opens to reveal: PDF report, Excel workbook, PVsyst files.

**Installer opens PDF on screen — professional cover page, charts, financial tables.**

**Voiceover:**
> "One click — a full professional report. PVsyst files for bank financing. Excel financials for the customer."

**Text overlay:** "Bank-ready. PVsyst-importable. Under 20 seconds."

---

### Scene 6 — Customer Meeting (1:10–1:22)

**Visual:** Installer presents iPad to customer. Customer leafs through PDF. Sees 25-year cashflow chart going positive at year 5. Nods. Signs.

**Voiceover:**
> "The installer walks in with a professional report backed by AI. The customer signs in confidence."

**Cut to:** Clock shows 11:03 AM. Elapsed since opening Shamsi Smart: 12 minutes. (Excel still open in background — closed.)

---

### Scene 7 — Impact (1:22–1:30)

**Visuals:** Fast cuts — solar panels on Cairo rooftop, Aswan riverside, Alexandria coast. Map of Egypt with glowing dots.

**Text overlays (one per cut):**
> "400,000 hours saved per year"  
> "45,000 tonnes CO₂ avoided"  
> "Free for every installer in Egypt"

**Final frame:**
```
☀️ Shamsi Smart
Multi-model AI for solar optimization
Designed for Egypt. Built for the world.
github.com/shamsi-smart/ai-engine
```

**Music:** Upbeat instrumental, fades out.

---

## Technical Demo Talking Points (for Q&A)

### "How accurate is it?"
> "We validated against PVWatts v5 — the US DOE standard — across five Egyptian cities. Mean error: 3.1%. Industry standard for bankable predictions is 5%. We're at 3.1%."

### "What data does it use?"
> "Our Egyptian Solar Energy Dataset — 341,991 daily records across 119 Egyptian locations, 8 years of NASA satellite data. Released publicly for reproducibility."

### "What's the business model?"
> "Free for small installers. $20/month Pro for exports and unlimited projects. $500/month Enterprise for companies and banks. Freemium drives adoption; Pro converts power users."

### "Can it scale to other countries?"
> "Yes. The architecture is country-agnostic. Change the climate dataset, tariff schedule, and equipment catalogue — same AI pipeline works for Morocco, Saudi Arabia, any sun-rich country."

### "Is the code open source?"
> "Fully open source, MIT licence. ESED dataset is CC BY 4.0 on Zenodo. The paper is submitted to Applied Energy. Everything reproducible."

---

## Demo Checklist (pre-presentation)

- [ ] Shamsi Smart live at shamsi-smart.railway.app
- [ ] Demo project pre-loaded (Cairo, 14 kWp)
- [ ] PDF report downloaded and ready
- [ ] PVsyst 7.2 open with Cairo.SIT pre-imported
- [ ] Validation script ready: `python scripts/validate_with_case_studies.py`
- [ ] GitHub repo public with README
- [ ] ESED on Zenodo with DOI
- [ ] Backup: offline demo video (in case internet fails)
