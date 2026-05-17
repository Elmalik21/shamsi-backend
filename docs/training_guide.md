# Shamsi Smart — AI Training Guide

Complete guide for training all four AI models that power the Shamsi Smart solar energy platform.

---

## Models Overview

| Model | File | Purpose | Size |
|-------|------|---------|------|
| Random Forest | `yield_predictor.pkl` | Annual solar yield prediction | ~5 MB |
| K-Means | `dust_clusterer.pkl` | Dust zone classification | ~1 MB |
| CNN-LSTM | `cnn_lstm_best.pth` | Deep learning yield time-series | ~15 MB |
| YOLOv8 | `roof_detector_best.pt` | Satellite roof segmentation | ~6 MB |

All models live in `ai_engine/models/` and are loaded automatically when the Django server starts.

---

## Prerequisites

### Python & OS

- Python 3.10 or 3.11
- Linux/macOS recommended (Windows works but may need `--workers 0` for YOLOv8)

### Install dependencies

```bash
pip install -r requirements.txt
```

Required packages (added to requirements.txt):

```
torch==2.0.1
ultralytics==8.0.200
reportlab>=4.0.0
tqdm
matplotlib
Pillow
scipy
```

### Directory structure

Ensure the following directories exist (they are created automatically during training):

```
ai_engine/models/          ← trained model files saved here
datasets/egyptian_roofs/   ← YOLO dataset
results/                   ← metrics, plots, report
```

---

## Local Training

### Option A — All models with synthetic data (recommended for first run)

No database required. Uses realistic synthetic Egyptian climate data.

```bash
python scripts/train_all_models.py --synthetic
```

This takes approximately:
- Random Forest: 30–60 seconds
- K-Means: 5–10 seconds
- CNN-LSTM: 15–30 min (CPU) / 3–5 min (GPU)
- YOLOv8: 20–40 min (CPU) / 5–10 min (GPU)

### Option B — Train with real database

Requires a populated PostgreSQL database with `DailyClimateData` records.

```bash
# Set up Django environment first
export DJANGO_SETTINGS_MODULE=shamsi_smart.settings
python manage.py migrate
python manage.py import_all_data  # or use the management command

# Then train
python scripts/train_all_models.py
```

### Option C — Train individual models

```bash
# Random Forest only
python scripts/train_all_models.py --synthetic --only rf

# K-Means only
python scripts/train_all_models.py --synthetic --only kmeans

# CNN-LSTM only
python scripts/train_all_models.py --synthetic --only cnn_lstm

# YOLOv8 only
python scripts/train_all_models.py --synthetic --only yolo
```

### Option D — GPU training

```bash
python scripts/train_all_models.py --synthetic --gpu
```

### Option E — Quick smoke test (5 epochs, ~2 min total)

```bash
python scripts/train_all_models.py --synthetic --quick
```

---

## Google Colab Training

For GPU-accelerated training using Google's free T4 GPUs:

1. Open `notebooks/train_all_colab.ipynb` in Google Colab
2. Set runtime to **GPU**: *Runtime → Change runtime type → T4 GPU*
3. Update `REPO_URL` in Cell 1 to your GitHub repository URL
4. Run all cells in order (Shift+Enter or *Runtime → Run all*)
5. Cell 5 will automatically download a ZIP file containing all trained models

### Expected Colab training times

| Model | T4 GPU | Free T4 (throttled) |
|-------|--------|---------------------|
| Random Forest | ~45s | ~1 min |
| K-Means | ~5s | ~10s |
| CNN-LSTM (100 epochs) | ~8 min | ~15 min |
| YOLOv8 (50 epochs) | ~12 min | ~20 min |
| **Total** | **~21 min** | **~36 min** |

---

## Expected Outputs

After successful training, you should see:

```
ai_engine/models/
├── yield_predictor.pkl      (~5 MB)
├── dust_clusterer.pkl       (~1 MB)
├── cnn_lstm_best.pth        (~15 MB)
└── roof_detector_best.pt    (~6 MB)

results/
├── training_report.json
├── step1/
│   ├── models/cnn_lstm_best.pth
│   ├── plots/cnn_lstm_loss_curve.png
│   └── plots/cnn_lstm_predictions_vs_actual.png

datasets/egyptian_roofs/
├── images/train/   (160 images)
├── images/val/     (40 images)
├── labels/train/   (160 .txt files)
├── labels/val/     (40 .txt files)
└── data.yaml
```

### Expected model performance (synthetic data)

| Model | Metric | Expected Range |
|-------|--------|----------------|
| Random Forest | Test R² | 0.85 – 0.95 |
| Random Forest | Test MAPE | 3 – 7% |
| K-Means | Silhouette | 0.55 – 0.85 |
| CNN-LSTM | Test MAPE | 4 – 9% |
| CNN-LSTM | Test R² | 0.80 – 0.92 |
| YOLOv8 | Box mAP50 | 0.75 – 0.95 (synthetic) |

> Real annotated data will achieve higher YOLOv8 mAP50 (typically 0.90+).

---

## Verifying Models

After training, run the verification script to confirm all models load and predict correctly:

```bash
python scripts/verify_trained_models.py
```

Expected output:

```
  ✅ PASS  Random Forest   — Prediction = 1492.3 kWh/kWp (within expected range)
  ✅ PASS  K-Means         — 4/4 test locations assigned to plausible dust zones
  ✅ PASS  CNN-LSTM        — Shape (1,12) ✓  Annual sum = 94.21  All finite ✓
  ✅ PASS  YOLOv8          — Inference successful
```

If a model fails, retrain it:

```bash
python scripts/train_all_models.py --synthetic --only <rf|kmeans|cnn_lstm|yolo>
```

---

## Deploying to Railway

After training locally or in Colab, copy the model files to your project and deploy:

```bash
# 1. Copy models to project (if trained in Colab, extract ZIP first)
cp /path/to/downloaded/models/*.pkl  ai_engine/models/
cp /path/to/downloaded/models/*.pth  ai_engine/models/
cp /path/to/downloaded/models/*.pt   ai_engine/models/

# 2. Verify models
python scripts/verify_trained_models.py

# 3. Commit and push
git add ai_engine/models/
git commit -m "Add trained AI models v1.0"
git push origin main

# 4. Deploy to Railway
railway up
```

> **Note**: The `ai_engine/models/` directory is included in `.gitignore` by default
> to prevent large model files from bloating the repository. Use Git LFS or upload
> models separately as Railway volume attachments for production.

### Railway environment variables required

```bash
DJANGO_SETTINGS_MODULE=shamsi_smart.settings.production
DATABASE_URL=postgresql://...
SECRET_KEY=...
ALLOWED_HOSTS=your-railway-domain.up.railway.app
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'torch'`

```bash
pip install torch==2.0.1 torchvision==0.15.2
```

### `ModuleNotFoundError: No module named 'ultralytics'`

```bash
pip install ultralytics==8.0.200
```

### CNN-LSTM training crashes with CUDA OOM

Reduce batch size:

```bash
python scripts/train_all_models.py --synthetic --gpu --batch-size 16
```

### YOLOv8 training crashes on Windows with workers error

Add `--workers 0` to avoid multiprocessing issues:

```bash
# In train_yolov8_roof.py, set workers=0
python scripts/train_yolov8_roof.py --synthetic --workers 0
```

### `django.core.exceptions.ImproperlyConfigured`

This happens when training without `--synthetic` and Django settings are not configured.
Either use `--synthetic` or set up Django:

```bash
export DJANGO_SETTINGS_MODULE=shamsi_smart.settings.local
python scripts/train_all_models.py
```

### Model file not found after training

Check the training report to see if training succeeded:

```bash
cat results/training_report.json | python -m json.tool
```

Look for `"status": "success"` for each model. If any show `"failed"`, re-run that model.

### YOLOv8 mAP50 < 50%

This is expected when training on purely synthetic data. To improve:

1. Collect 200+ real satellite roof images using Google Maps or Mapbox
2. Annotate them with LabelMe: `python scripts/annotate_roofs_labelme.py`
3. Retrain: `python scripts/train_yolov8_roof.py --epochs 100`

---

## Training Data Details

### Random Forest (119 synthetic locations × 12 parameter combos = 1,428 samples)

Features: GHI, temperature, max_temperature, humidity, wind_speed, dust_risk,
latitude, tilt_angle, panel_efficiency, temp_coefficient

Target: specific_yield (kWh/kWp/year) — scale-independent, comparable across system sizes

Locations cover all Egyptian climate bands:
- Nile Delta (lat 31–31.5°): low dust, humid
- Cairo belt (lat 29.5–31°): moderate
- Middle Egypt (lat 27–29.5°): drier, higher dust
- Upper Egypt (lat 24–27°): very sunny, dusty
- Deep south (lat 22–24°): extreme dust/sun

### CNN-LSTM (119 locations × 3 years = 357 sequences of 365 days × 5 features)

Each sequence: daily [GHI, Temperature, Humidity, Wind, Dust_Risk_Score]
Target: monthly specific yield [kWh/kWp] × 12

### YOLOv8 (160 train + 40 val synthetic images)

Each image: 640×640 px synthetic concrete roof with YOLO segmentation labels
Classes: roof_boundary, chimney, ac_unit, water_tank, satellite_dish, tree_shadow, vent, shade_structure

---

*For questions or issues, open a GitHub issue or contact the Shamsi Smart AI Team.*
