# Section 3: Methodology

**Paper:** AI-Powered Solar Energy Yield Prediction for Egyptian Conditions:
A Comparative Study of Random Forest, CNN-LSTM, and Physics-Based Models

**Target Journals:** Applied Energy · Solar Energy · Renewable and Sustainable Energy Reviews

---

## 3.1 Problem Formulation

Let $\mathcal{L} = \{l_1, l_2, \ldots, l_N\}$ denote the set of $N = 119$ geographic locations across Egypt, each characterised by a feature vector $\mathbf{x}_l \in \mathbb{R}^{10}$ of annual-aggregate climate and panel parameters.

The **specific yield** (scale-independent output) is defined as:

$$y_l = \frac{E_{l,\text{annual}}}{P_{\text{peak}}} \quad [\text{kWh/kWp/year}]$$

where $E_{l,\text{annual}}$ is the annual AC energy production [kWh] and $P_{\text{peak}}$ is the system nameplate capacity [kWp]. Using specific yield removes the trivial linear dependence on system size, forcing models to learn genuine climate-production relationships.

The regression objective is to learn a mapping $f: \mathbb{R}^{10} \to \mathbb{R}$ minimising the expected absolute percentage error:

$$\mathcal{L}(f) = \mathbb{E}_l \left[ \left| \frac{y_l - \hat{y}_l}{y_l} \right| \right] \times 100\%$$

---

## 3.2 Dataset Description

### 3.2.1 NASA POWER Climate Data

Daily climate records were retrieved from the NASA Prediction of Worldwide Energy Resources (POWER) database [Stackhouse et al., 2018] for 119 Egyptian locations spanning latitudes 22°N–31.5°N and longitudes 25°E–36°E. The dataset covers 8 years (2015–2022), yielding 341,991 daily records.

Variables extracted per day per location:

| Variable | Description | Units |
|---|---|---|
| ALLSKY_SFC_SW_DWN | Global Horizontal Irradiance | kWh/m²/day |
| T2M | Air temperature at 2 m | °C |
| T2M_MAX | Maximum daily temperature | °C |
| RH2M | Relative humidity at 2 m | % |
| WS2M | Wind speed at 2 m | m/s |
| PRECTOTCORR | Corrected precipitation | mm/day |

### 3.2.2 Train/Test Split Strategy

A critical methodological decision is the train/test split strategy. We employ a **location-based split** rather than a random row split, for the following reason: random row splitting allows data from the same location to appear in both train and test sets. This means the model is never tested on a truly unseen location — it has seen the climate patterns of that site during training. For a deployment system that must generalise to new Egyptian sites, this constitutes evaluation data leakage.

Our split:
- **Train**: 80 unique locations (80%), randomly selected with seed 42
- **Test**: 24 unique locations (20%), geographically distributed across all Egyptian climate zones

All cross-validation is performed using `GroupKFold(n_splits=5)` grouped by `location_id`, ensuring no same-location leakage across folds.

### 3.2.3 Data Preprocessing and Feature Engineering

Annual-aggregate features per location are computed from 8-year daily records:

| Feature | Engineering | Justification |
|---|---|---|
| `avg_ghi` | $\frac{1}{N_d}\sum_d \text{GHI}_d$ | Primary driver of energy yield |
| `avg_temperature` | $\frac{1}{N_d}\sum_d T_{2m,d}$ | Temperature derating |
| `max_temperature` | $\max_d(T_{2m,d})$ | Worst-case thermal stress |
| `avg_humidity` | $\frac{1}{N_d}\sum_d \text{RH}_{2m,d}$ | Soiling and cloud correlation |
| `avg_wind_speed` | $\frac{1}{N_d}\sum_d \text{WS}_{2m,d}$ | Convective cooling |
| `dust_risk_score` | K-Means cluster centre | Egypt dust micro-zones |
| `latitude` | Location attribute | Solar geometry (tilt optimisation) |
| `tilt_angle` | $= \text{latitude} \pm 5°$ | Panel inclination |
| `panel_efficiency` | Equipment database | STC conversion efficiency |
| `temp_coefficient` | Equipment database | Thermal power derating |

**Critically excluded**: `system_kw` is **not** a feature, since it would create a direct linear relationship with the absolute yield target, enabling trivial model memorisation (as demonstrated in Section 4.1).

All features are normalised with `StandardScaler` (zero mean, unit variance) before input to tree-based and neural network models.

---

## 3.3 Random Forest V2 (Fixed Approach)

### 3.3.1 Feature Engineering Rationale

The Random Forest uses the 10 features enumerated in Table 3.2. The exclusion of `system_kw` is the critical fix over the V1 model. The specific yield target:

$$y = \text{GHI} \times 365 \times \eta_{\text{panel}} \times (1 - \delta_{\text{temp}}) \times (1 - \delta_{\text{dust}})$$

is a complex non-linear function of climate variables, making it genuinely learnable only through the 10 input features.

### 3.3.2 Hyperparameters

Selected via 5-fold GroupKFold cross-validation:

| Hyperparameter | Value |
|---|---|
| n_estimators | 300 |
| max_depth | 12 |
| min_samples_split | 8 |
| min_samples_leaf | 4 |
| max_features | sqrt |
| random_state | 42 |

### 3.3.3 Cross-Validation

`GroupKFold(n_splits=5)` is used with `groups=location_id`. This ensures each validation fold contains locations not seen during that fold's training, providing an unbiased estimate of generalisation to new sites. Standard k-fold would allow same-location data to leak across folds, inflating CV scores.

---

## 3.4 CNN-LSTM Deep Learning Architecture

### 3.4.1 Motivation

Random Forest operates on annual-aggregate features, discarding all temporal structure. Real solar production is determined by seasonal patterns, inter-day variability, and event-level phenomena (dust storms, cloud events). A sequence model can explicitly capture:
- Weekly and fortnightly seasonality → captured by CNN kernels
- Long-range dependencies (summer vs. winter regimes) → captured by LSTM
- Critical production periods (peak irradiance days) → captured by attention

### 3.4.2 Architecture

The CNN-LSTM takes daily time-series input of shape $(B, 365, 5)$ where $B$ is batch size, 365 is days per year, and 5 are the daily climate features $[\text{GHI}, T, \text{RH}, \text{WS}, \delta_{\text{dust}}]$.

**Stage 1 — Temporal CNN:**
Two 1D convolutional layers extract local temporal patterns:
- `Conv1D(in=5, out=64, kernel=7, padding=3)` — captures weekly patterns
- `Conv1D(in=64, out=128, kernel=14, padding=7)` — fortnightly patterns
- `MaxPool1D(2)` reduces sequence length from 365 to 182
- `BatchNorm1D + GELU + Dropout(0.3)`

**Stage 2 — Bidirectional LSTM:**
$$\overrightarrow{h}_t = \text{LSTM}(\mathbf{c}_t, \overrightarrow{h}_{t-1}), \quad \overleftarrow{h}_t = \text{LSTM}(\mathbf{c}_t, \overleftarrow{h}_{t+1})$$
$$h_t = [\overrightarrow{h}_t; \overleftarrow{h}_t] \in \mathbb{R}^{256}$$

Bidirectionality allows the model to incorporate both past (e.g., accumulated dust) and future (e.g., approaching rainy season) context.

**Stage 3 — Multi-Head Attention:**
$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right)V$$

4 attention heads over the LSTM output sequence identify which time-steps are most informative for yield prediction. Global average pooling over the attended sequence produces a fixed-size representation.

**Stage 4 — Regression Head:**
$$\hat{y} = W_2 \cdot \text{GELU}(W_1 \cdot h_{\text{pooled}}) \in \mathbb{R}^{12}$$

Output: 12-month specific yield vector.

**Total parameters**: ~850,000 (appropriate for dataset size; prevents overfitting).

### 3.4.3 Training Procedure

| Setting | Value |
|---|---|
| Loss function | Huber Loss ($\delta=1.0$) |
| Optimizer | AdamW (lr=1e-3, weight_decay=1e-4) |
| LR Schedule | CosineAnnealingLR (T_max=100) |
| Dropout | 0.3 (all stages) |
| Gradient clipping | max_norm=1.0 |
| Early stopping | patience=15 (on val loss) |
| Batch size | 32 |
| Max epochs | 100 |

**Huber loss** is chosen over MSE because solar yield data contains occasional outliers (extreme dust storms, equipment failures) that would excessively penalise MSE and distort gradient updates.

### 3.4.4 Attention Mechanism and Interpretability

The multi-head attention weights provide visual interpretability: high-weight time-steps correspond to periods the model considers most critical for annual yield prediction (typically summer peak irradiance periods and post-rain recovery periods). This is visualised in Figure X (attention weight heatmap over 365 days).

---

## 3.5 Baseline Methods

### 3.5.1 PVWatts Baseline (Industry Standard)

We implement the NREL PVWatts v5 DC/AC model [Dobos, 2014], the most widely used solar yield estimation tool in the industry. It uses deterministic physics equations with Egypt-specific default losses:

$$E_{\text{ac}} = P_{\text{dc0}} \cdot \frac{\text{POA}}{1000} \cdot [1 + \gamma_{\text{pdc}}(T_c - 25)] \cdot \eta_{\text{inv}} \cdot \prod_i (1 - L_i)$$

Loss factors for Egypt: soiling $L_s = 5\%$, wiring $2\%$, mismatch $2\%$, availability $3\%$, shading $3\%$.

The PVWatts model serves as the **industry competitiveness threshold**: any AI model that cannot beat PVWatts by a statistically significant margin provides no practical value.

### 3.5.2 Physics-Based Baseline (First Principles)

A simplified first-principles model implements the complete solar geometry chain:
1. Solar declination (Spencer, 1971)
2. Plane-of-array irradiance (Liu & Jordan isotropic model, 1963)
3. Cell temperature (Sandia NOCT model)
4. DC power with temperature derating
5. Dust accumulation and rain cleaning

This model uses no empirical calibration and represents the minimal achievable accuracy from physical knowledge alone. It provides a lower bound below which no reasonable ML model should fall.

---

## 3.6 Evaluation Metrics

All metrics are computed on the held-out 24-location test set on the **specific yield** target (kWh/kWp/year):

| Metric | Formula | Interpretation |
|---|---|---|
| MAE | $\frac{1}{N}\sum|y_i - \hat{y}_i|$ | Average absolute error [kWh/kWp] |
| RMSE | $\sqrt{\frac{1}{N}\sum(y_i-\hat{y}_i)^2}$ | Penalises large errors |
| MAPE | $\frac{1}{N}\sum\frac{|y_i-\hat{y}_i|}{y_i}\times 100$ | Scale-independent [%] |
| R² | $1 - \frac{\sum(y_i-\hat{y}_i)^2}{\sum(y_i-\bar{y})^2}$ | Variance explained |

MAPE is the primary metric because it is:
(a) scale-independent — comparable across locations with different system sizes,
(b) industry-standard — NREL reports PVWatts accuracy in MAPE,
(c) interpretable — directly translates to financial uncertainty in ROI calculations.

---

## 3.7 Experimental Setup

- **Hardware**: CPU-only experiments (Intel Core i7); GPU acceleration available via CUDA
- **Software**: Python 3.11, PyTorch 2.1, scikit-learn 1.4, Django 4.2, NumPy 1.26
- **Reproducibility**: All experiments use `random_state=42` / `torch.manual_seed(42)`
- **Code**: Available at [GitHub URL — to be filled]
- **Data**: NASA POWER (https://power.larc.nasa.gov/), publicly available
- **Training time**: RF V2 < 10s · CNN-LSTM < 3 min (CPU), < 30s (GPU)
