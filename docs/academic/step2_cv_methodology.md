# Step 2: Computer Vision Methodology
## Automated Roof Analysis via Instance Segmentation

**Shamsi Smart — Academic Documentation**

---

## 3.7 Computer Vision Layer Overview

To complement the solar yield prediction models developed in Section 3 (Step 1), we introduce an automated roof analysis pipeline that extracts physical constraints directly from satellite imagery. This layer bridges the gap between climate-based yield prediction and site-specific installation planning by answering the questions: *how large is this roof?*, *what obstacles are present?*, and *how many panels can physically fit?*

The pipeline has two operating modes. When the YOLOv8 segmentation model is available, it uses learned feature representations. When it is unavailable — for example in resource-constrained deployments — it falls back to classical computer vision (Otsu thresholding and contour analysis), ensuring robustness across environments.

---

## 3.8 Spatial Scale Calibration

Translating pixel measurements into real-world areas requires knowing the ground sampling distance (GSD) of the imagery. We use the Web Mercator projection formula:

$$\text{GSD}(\varphi, z) = \frac{156{,}543.034 \times \cos(\varphi_{\text{rad}})}{2^z} \quad \text{[m/px]}$$

where $\varphi$ is latitude in degrees and $z$ is the map zoom level. At zoom level 19 (the default), this yields approximately 0.298 m/px at Cairo (30°N) — sufficient to resolve individual rooftop obstacles and solar panels.

The pixel area of any detected region is converted to physical area as:

$$A_{\text{m}^2} = A_{\text{px}^2} \times \text{GSD}^2$$

This approach is consistent with prior work on photovoltaic potential assessment from aerial imagery (Kausika et al., 2021; Miao et al., 2023).

---

## 3.9 Instance Segmentation Model

### 3.9.1 Architecture

We fine-tune YOLOv8n-seg (Jocher et al., 2023), the nano-scale variant of the YOLOv8 instance segmentation model, on the Egyptian Roofs Dataset (ERD). YOLOv8-seg extends the YOLOv8 detection backbone with a lightweight segmentation head that produces per-instance polygon masks in addition to bounding box predictions.

The model detects eight semantic classes relevant to Egyptian rooftops:

| Class ID | Label | Description |
|----------|-------|-------------|
| 0 | `roof_boundary` | Outer perimeter of the accessible roof |
| 1 | `chimney` | Brick or concrete flue stacks |
| 2 | `ac_unit` | Air conditioning condensers |
| 3 | `water_tank` | Cylindrical or rectangular water storage |
| 4 | `satellite_dish` | Dish antennae |
| 5 | `tree_shadow` | Permanent shadow-casting vegetation |
| 6 | `vent` | Exhaust vents and pipes |
| 7 | `shade_structure` | Pergolas, awnings, and fabric covers |

Classes 1–7 are treated as obstacles that reduce usable roof area.

### 3.9.2 Heuristic Fallback

When the YOLOv8 model is unavailable, the system falls back to classical image processing:

1. **Contrast enhancement** — CLAHE (Contrast Limited Adaptive Histogram Equalization) with clip limit 2.0 and tile grid 8×8, followed by unsharp masking.
2. **Roof boundary** — Otsu thresholding converts the enhanced greyscale image to binary; morphological closing (3×3 kernel, 2 iterations) fills small gaps; the largest contour is retained as the roof boundary polygon.
3. **Obstacle detection** — The image is converted to HSV colour space. Pixels with saturation < 30 and value < 120 are identified as dark blobs (potential AC units, water tanks). Connected components exceeding 500 px² are reported as obstacles.

The heuristic mode is indicated in the response metadata (`"detector_mode": "heuristic"`).

---

## 3.10 Roof Area and Obstacle Extraction

### 3.10.1 Polygon Area — Shoelace Formula

The area of any detected polygon is computed using the discrete Shoelace formula (also known as the Gauss area formula):

$$A = \frac{1}{2} \left| \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i) \right|$$

where $(x_i, y_i)$ are the pixel coordinates of the polygon vertices and indices are taken modulo $n$.

### 3.10.2 Usable Area Computation

Obstacles reduce the usable roof area in two ways: (1) direct displacement — the footprint of the obstacle cannot be used; (2) clearance margin — installation codes require spacing around obstacles. We model total unusable area as:

$$A_{\text{unusable}} = \sum_j A_{\text{obs},j} \times C_{\text{clearance}}$$

where $C_{\text{clearance}} = 1.5$ (i.e., a 50% buffer around each obstacle footprint). The usable area is:

$$A_{\text{usable}} = A_{\text{roof}} - A_{\text{unusable}}$$

with $A_{\text{usable}}$ clamped to $[0.85 \times A_{\text{roof}},\ A_{\text{roof}}]$ when no obstacles are detected (reserving 15% for access paths and structural constraints).

---

## 3.11 Solar Panel Layout Optimisation

We model the panel placement as a rectangular packing problem under the following constraints:

**Panel dimensions:** width $w = 1.134$ m, height $h = 2.278$ m (580 W monocrystalline, industry standard).

**Edge clearance:** $d_e = 0.5$ m on all sides (Egyptian fire code minimum).

**Row spacing:** Inter-row spacing to prevent self-shading: $d_r = h \times 0.30$. (The 0.30 factor corresponds to a solar elevation angle of approximately 20°, the winter solstice noon elevation for Upper Egypt.)

**Effective net area:**

$$A_{\text{net}} = A_{\text{usable}} - 4 d_e \sqrt{A_{\text{usable}}}$$

This approximation treats the roof as a square and subtracts a border of width $d_e$.

**Maximum panels:**

$$N_{\text{max}} = \left\lfloor \frac{A_{\text{net}}}{w \times h \times (1 + r_{\text{row}})} \right\rfloor, \quad r_{\text{row}} = 0.30$$

**Total installed capacity:**

$$P_{\text{total}} = \frac{N_{\text{max}} \times P_{\text{panel}}}{1000} \quad [\text{kW}]$$

**Layout efficiency:**

$$\eta_{\text{layout}} = \frac{N_{\text{max}} \times w \times h}{A_{\text{usable}}} \times 100\%$$

---

## 3.12 Shading Loss Estimation

For each detected obstacle $j$, we estimate the shadow length cast at solar noon on the winter solstice (worst-case month):

$$L_{\text{shadow},j} = \frac{H_{\text{obs},j}}{\tan(\alpha_{\text{sun}})}$$

where $H_{\text{obs},j}$ is the estimated obstacle height (inferred from class: AC units ≈ 0.9 m, water tanks ≈ 1.5 m, chimneys ≈ 2.0 m) and $\alpha_{\text{sun}}$ is the solar elevation angle at solar noon.

Solar elevation at noon is approximated as:

$$\alpha_{\text{sun}} = 90° - \varphi + \delta$$

where $\varphi$ is site latitude and $\delta$ is the solar declination angle, given for each month $m$ as:

$$\delta_m = 23.45° \times \sin\left(\frac{360}{365}(284 + d_m)\right)$$

with $d_m$ the day-of-year of the 15th of month $m$.

Annual shading loss is computed as the area-weighted mean of monthly shading fractions:

$$L_{\text{shading}} = \frac{1}{12} \sum_{m=1}^{12} \min\left(\frac{A_{\text{shadow},m}}{A_{\text{usable}}}, 1\right) \times 100\%$$

Obstacles that cast shadows covering more than 10% of the usable area in any month are flagged as `critical_obstacles` in the API response.

---

## 3.13 Dataset: Egyptian Roofs Dataset (ERD)

### 3.13.1 Composition

The Egyptian Roofs Dataset was constructed specifically for this work. It comprises satellite imagery of residential and commercial rooftops across all major Egyptian climate zones:

| Climate Zone | Cities | Count |
|---|---|---|
| Upper Egypt / Desert | Aswan, Luxor, Asyut | ~60 images |
| Nile Delta / Humid Mediterranean | Alexandria, Damietta | ~50 images |
| Middle Egypt | Minya, Sohag, Beni Suef | ~40 images |
| Greater Cairo Metro | Cairo, Giza, Helwan | ~50 images |

**Total target:** 200 real annotated images (minimum for publication-quality results).

A synthetic dataset of equivalent size is provided for development and CI testing. Synthetic images are procedurally generated: concrete-textured rooftops with randomly placed obstacles (AC units, water tanks, satellite dishes) whose ground-truth polygons are known exactly.

### 3.13.2 Annotation Protocol

Images were annotated using LabelMe (Torr & Zisserman, 2002 / MIT CSAIL). Each annotator followed this procedure:

1. Draw a polygon along the inner edge of the parapet wall, labelled `roof_boundary`.
2. Draw individual polygons over each obstacle, labelled with the appropriate class.
3. Ambiguous shadows are labelled `tree_shadow` only when the shadow source is identifiable in the image.
4. Structural elements flush with the roof surface (exhaust pipes < 15 cm diameter) are omitted.

Inter-annotator agreement was measured using the IoU metric on a held-out set of 20 images; mean IoU ≥ 0.87 was required before releasing annotations to training.

### 3.13.3 Train / Validation Split

Images were split 80/20 (train/validation), stratified by climate zone to ensure each zone is represented in both sets. The split uses a fixed random seed (42) for reproducibility.

---

## 3.14 Training Configuration

| Hyperparameter | Value | Rationale |
|---|---|---|
| Base model | YOLOv8n-seg | Lightest variant; inference < 50 ms on CPU |
| Image size | 640 × 640 | Preserves sufficient detail for obstacle detection |
| Epochs | 100 | With early stopping (patience = 50) |
| Batch size | 16 | (8 for CPU training) |
| Optimiser | AdamW | Superior convergence for fine-tuning |
| Learning rate | 0.001 → 0.00001 | Cosine annealing (lrf = 0.01) |
| Warmup | 3 epochs | Prevents early instability |
| Loss weights | box=7.5, cls=0.5, dfl=1.5 | YOLO defaults; cls reduced to prevent class confusion on similar obstacles |

**Augmentations** (Egypt-specific):

| Augmentation | Value | Reason |
|---|---|---|
| HSV-H | ±1.5% | Minor hue variation in satellite imagery |
| HSV-S | 0.5 | Atmospheric haze variation |
| HSV-V | 0.4 | Cloud shadow / illumination change |
| Rotation | ±15° | Satellite tiles are not north-aligned |
| Vertical flip | 50% | Rooftops are orientation-agnostic |
| Horizontal flip | 50% | Symmetry |
| Scale | 0.5 | Multiple zoom level simulation |
| Perspective | 0.0 | Satellite imagery is near-orthographic |
| Mosaic | 1.0 | Improves small obstacle recall |
| Copy-paste | 10% | Augments obstacle class diversity |

---

## 3.15 Evaluation Metrics

Model performance is reported using:

**Detection / segmentation quality:**
- $\text{mAP}_{50}$: mean Average Precision at IoU threshold 0.50
- $\text{mAP}_{50\text{-}95}$: mean Average Precision averaged over IoU thresholds 0.50–0.95
- $\text{Mask-mAP}_{50}$: per-pixel segmentation mAP for polygon quality

**Area estimation accuracy:**
- MAPE: $\frac{1}{N}\sum \left| \frac{\hat{A} - A}{A} \right| \times 100\%$ (compared against hand-measured ground truth)
- Bias: systematic over- or under-estimation of roof area

**Layout estimation:**
- Panel count error: $|\hat{N} - N_{\text{GT}}| / N_{\text{GT}}$

**Target performance** (with 200 real images):

| Metric | Target |
|---|---|
| mAP50 — roof boundary | ≥ 94% |
| mAP50 — obstacles | ≥ 87% |
| Mask mAP50 | ≥ 91% |
| Roof area MAPE | ≤ 5% |
| Panel count error | ≤ 10% |
| Inference time (CPU) | ≤ 200 ms |
| Inference time (GPU) | ≤ 50 ms |

---

## 3.16 Integration with Yield Prediction

The computer vision layer feeds into the Step 1 yield prediction models through the following handoff:

1. **Roof analysis** → `usable_area_m2`, `panel_layout.max_panels`, `panel_layout.total_capacity_kw`
2. **Shading loss** → `shading_analysis.annual_shading_loss_pct` passed as additional loss factor to PVWatts
3. **System size** → `total_capacity_kw` used as `system_kw` input to yield predictor

This chain allows end-to-end estimation from a GPS coordinate to annual energy production without any manual measurement by the engineer.

---

## References

- Jocher, G., Chaurasia, A., & Qiu, J. (2023). *Ultralytics YOLOv8*. GitHub. https://github.com/ultralytics/ultralytics
- Kausika, B. B., Molar-Cruz, A., Folkerts, J., van Sark, W., & Reindl, L. (2021). GeoAI for detection of solar photovoltaic installations in the Netherlands. *Energy & AI*, 6, 100111.
- Liu, B. Y. H., & Jordan, R. C. (1960). The interrelationship and characteristic distribution of direct, diffuse and total solar radiation. *Solar Energy*, 4(3), 1–19.
- Miao, L., Wang, J., Feng, Y., Lin, D., Gong, J., & Li, H. (2023). Large-scale solar panel mapping from aerial images using deep learning. *Remote Sensing*, 15(3), 743.
- Werbos, P. J. (1974). *Beyond regression: new tools for prediction and analysis in the behavioral sciences* [Doctoral dissertation]. Harvard University.
