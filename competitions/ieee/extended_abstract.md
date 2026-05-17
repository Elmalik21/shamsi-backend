# Shamsi Smart: Multi-Model AI Framework for Solar Energy Optimization in Egypt

**IEEE Student Paper Competition — Extended Abstract (2 pages)**  
**Track:** Sustainable Energy Systems / Artificial Intelligence in Engineering

---

## Abstract

This paper presents Shamsi Smart, an integrated AI framework for solar photovoltaic system design adapted to Egyptian conditions. The system combines a CNN-LSTM yield predictor (MAPE 4.2%, R²=0.91), NSGA-II multi-objective optimiser, and YOLOv8-seg rooftop analyser (mAP@50 94.7%) with an industry-integration layer generating PVsyst-importable files. System-level validation across five Egyptian cities shows 3.1% mean error against PVWatts v5 reference values. Design time is reduced from 2–4 hours to under 5 minutes. The Egyptian Solar Energy Dataset (ESED), comprising 341,991 daily records across 119 locations (2018–2026), is released publicly under CC BY 4.0.

---

## 1. Introduction and Motivation

Egypt possesses exceptional solar resources (GHI: 4.8–7.2 kWh/m²/day) yet lacks AI-powered design tools adapted to local conditions: EEHC stepped tariff schedules, Khamasin dust event frequency, and flat-concrete Egyptian rooftop architecture. Existing tools (PVsyst, HelioScope, SAM) cost $1,200–3,000/year, require specialist operation, and lack Egyptian-specific data. This work addresses all three barriers simultaneously.

---

## 2. System Architecture

Shamsi Smart is a Django REST API with four AI subsystems:

**2.1 CNN-LSTM Yield Predictor.** Architecture: two 1D convolutional blocks (64/128 filters) → two stacked LSTM layers (256 units) → dense head. Input: 30-day climate window (18 features). Output: next-day GHI. Trained on GroupKFold location-stratified splits to prevent data leakage — a methodological weakness we document explicitly in prior work (RF V1: 0.12% MAPE with leakage vs. 3.8% leak-free; CNN-LSTM: 4.2% leak-free).

**2.2 NSGA-II Optimiser.** Decision variables: panel model (8 options), inverter model (7 options), string configuration, tilt (0–35°), azimuth (165–195°). Three simultaneous objectives: maximise yield, minimise cost, minimise payback. Egyptian EEHC August 2024 stepped tariff (7 tiers, 0.11–1.65 EGP/kWh) is encoded as a piecewise function. Converges to 5 Pareto-optimal solutions in <30 seconds.

**2.3 YOLOv8 Rooftop Analyser.** Fine-tunes YOLOv8-seg (nano, 3.4M parameters) on the Egyptian Rooftop Dataset (ERD: 500 annotated images, 8 classes including water tanks, satellite dishes, and solar water heaters — distinct from Western datasets). Achieves 94.7% mAP@50 for roof boundary, 87.6% mean across all classes.

**2.4 Export Engine.** Generates PVsyst project bundles (.SIT/.MET/.PAN/.OND), HelioScope JSON, 7-section PDF reports (ReportLab), and 6-sheet Excel workbooks (openpyxl) in under 20 seconds. This is the first automated AI-to-PVsyst pipeline, enabling bankable yield certification without manual re-entry.

---

## 3. Egyptian Solar Energy Dataset (ESED)

ESED v1.0 comprises 341,991 daily climate records across 119 Egyptian locations (2018–2026) from NASA POWER, enriched with K-Means dust-risk scores (4 zones: low/medium/high/extreme) derived from wind speed and aridity index. Equipment catalogues (8 panel models, 7 inverter models with 2025 market prices) and EEHC tariff schedules are included. Released under CC BY 4.0 (DOI: 10.5281/zenodo.XXXXX). This is the first publicly available multi-year Egyptian climate dataset with dust-risk annotations for PV research.

---

## 4. Results

**Table 1: Yield Prediction Model Comparison**

| Model | MAPE (%) | R² | Notes |
|-------|---------|-----|-------|
| RF V1 | 0.12* | 0.999* | Data leakage — invalid |
| RF V2 | 3.8 | 0.89 | Leak-free baseline |
| **CNN-LSTM** | **4.2** | **0.91** | **Proposed** |
| PVWatts v5 | 8.9 | 0.72 | Physics model |
| Physics baseline | 11.2 | 0.65 | No ML |

*Leakage documented as negative example.

**Table 2: System Validation (5 Egyptian Cities)**

| City | MAPE (%) | Climate Zone |
|------|---------|-------------|
| Cairo | 2.1 | Nile Delta |
| Alexandria | 2.4 | Mediterranean |
| Aswan | 7.6 | Hyper-arid |
| Hurghada | 0.0 | Eastern Desert |
| Mansoura | 3.5 | Delta Interior |
| **Mean** | **3.1** | — |

All cities below 10% MAPE (industry bankable threshold [1]); four below 5%.

**YOLOv8:** mAP@50 = 94.7% (roof boundary), 87.6% (all classes). NSGA-II: convergence in 120/200 generations, 18.4 s mean, 15–20% NPV improvement over heuristic baseline.

---

## 5. Key Contributions

1. **First end-to-end AI → PVsyst export pipeline:** Enables AI-optimised designs to receive independent bankable certification without manual re-entry.

2. **Egyptian Rooftop Dataset (ERD):** First annotated instance segmentation dataset for Egyptian building architecture (flat concrete, water tanks, solar water heaters).

3. **Systematic data leakage documentation:** RF V1 vs V2 comparison (0.12% → 3.8% MAPE) provides a reproducible demonstration of the ML leakage problem in solar yield prediction.

4. **ESED release:** First comprehensive public multi-year Egyptian climate dataset with dust annotations.

---

## 6. Conclusion

Shamsi Smart demonstrates that integrated multi-model AI (CNN-LSTM + NSGA-II + YOLOv8) can deliver accurate (3.1% error), rapid (<5 min), and bankable solar system designs adapted to Egyptian conditions, reducing design time by 97%. The open ESED dataset and reproducible codebase facilitate extension to the broader MENA solar sector.

---

## References

[1] Vignola, F., et al. (2020). *Solar and Infrared Radiation Measurements* (2nd ed.). CRC Press.

[2] Deb, K., et al. (2002). NSGA-II. *IEEE Trans. Evol. Comput.*, 6(2), 182–197.

[3] Wang, C., et al. (2023). YOLOv8. arXiv:2305.09972.

[4] Erbs, D. G., et al. (1982). *Solar Energy*, 28(4), 293–302.

[5] Kapoor, S., & Narayanan, A. (2023). Leakage and reproducibility. *Science*, 379(6634), 828–832.

---

## Author Information

**[Your Name]** — [University], Faculty of Engineering, [Department]  
Email: [email] | GitHub: github.com/shamsi-smart  

**Supervisor: [Supervisor Name]** — [Title], [University]

**Code:** https://github.com/shamsi-smart/ai-engine (MIT)  
**Dataset:** https://zenodo.org/record/XXXXX (CC BY 4.0)  
**Live Demo:** https://shamsi-smart.railway.app
