# Shamsi Smart — Real Data Training Guide
## Windows 11 + NVIDIA GPU + Railway PostgreSQL + Sentinel-2 GeoTIFF

---

## Overview

This guide covers training all four Shamsi Smart AI models using **real production data**:

| Model | Data source | Expected time (RTX 3090) |
|-------|-------------|--------------------------|
| Random Forest (yield predictor) | Railway PostgreSQL — 341,991 records | ~2 min |
| K-Means (dust zones) | Railway PostgreSQL — same dataset | ~1 min |
| CNN-LSTM (monthly yield) | Railway PostgreSQL — time-series | ~45 min |
| YOLOv8-seg (roof detector) | Sentinel-2 GeoTIFF satellite images | ~2 hours |

For a no-database smoke test, see the synthetic flag: `--synthetic`.

---

## Prerequisites

### Hardware
- NVIDIA GPU (GTX 1060 minimum, RTX 3080+ recommended)
- RAM: 16 GB minimum, 32 GB recommended
- Disk: 20 GB free (GeoTIFF files are large)

### Software — install once

#### 1. CUDA toolkit (match your GPU driver)

Check your driver version:
```
nvidia-smi
```

Install CUDA 11.8 (for PyTorch 2.x):
- Download from https://developer.nvidia.com/cuda-11-8-0-download-archive
- Select: Windows → x86_64 → 11 → exe (local)
- Run installer, choose "Custom" and select CUDA components

Verify:
```powershell
nvcc --version
```

#### 2. Python 3.10 (recommended)

Download from https://www.python.org/downloads/release/python-31012/ — use the Windows installer and check "Add Python to PATH".

#### 3. Create a virtual environment

```powershell
# In the project root
python -m venv .venv
.venv\Scripts\activate
```

#### 4. Install PyTorch with CUDA support

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

Verify GPU is visible:
```python
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

#### 5. Install project dependencies

```powershell
pip install -r requirements.txt
```

#### 6. Install geospatial stack (for GeoTIFF / SAM pipeline)

```powershell
# rasterio on Windows requires the binary wheel from Christoph Gohlke
pip install rasterio --extra-index-url https://wheelhouse.openquake.org/windows/
# OR use conda (easiest on Windows):
conda install -c conda-forge rasterio geopandas shapely pyproj

# OpenCV
pip install opencv-python

# Segment Anything Model
pip install git+https://github.com/facebookresearch/segment-anything.git
```

---

## Part 1: ML Models from Railway PostgreSQL

### 1.1 Configure the database connection

Railway provides two connection strings:

**Internal hostname** (only works inside Railway's private network):
```
postgresql://postgres:<password>@postgres.railway.internal:5432/railway
```

**Public proxy URL** (works from your local Windows machine):
```
postgresql://postgres:<password>@<region>.railway.app:<port>/railway
```

Get the public URL from: Railway Dashboard → your PostgreSQL service → **Connect** tab → **Public URL**.

Set the environment variable before running any training script:

```powershell
# Windows PowerShell
$env:DATABASE_URL = "postgresql://postgres:<password>@<region>.railway.app:<port>/railway"

# Or add it to your .env file (requires python-dotenv):
# DATABASE_URL=postgresql://postgres:<password>@<region>.railway.app:<port>/railway
```

If you see the warning:
```
⚠️  Railway Internal Hostname Detected — External Warning
```
you need to switch to the public proxy URL above.

### 1.2 Django setup

```powershell
# Make sure Django can connect to the Railway DB
$env:DJANGO_SETTINGS_MODULE = "shamsi_smart.settings"
python manage.py check --database default
```

### 1.3 Train Random Forest + K-Means

```powershell
python scripts/train_all_models.py --only rf kmeans --gpu
```

Expected output:
```
✅  Random Forest trained — MAPE: 4.2%  R²: 0.973
✅  K-Means trained — Silhouette: 0.681  Clusters: 4
```

Models saved to `ai_engine/models/`:
- `yield_predictor.pkl`
- `dust_clusterer.pkl`

### 1.4 Train CNN-LSTM

```powershell
python scripts/train_all_models.py --only cnn_lstm --gpu --epochs-lstm 100
```

With the RTX 3090 this takes ~45 minutes for 341,991 records (3 years × 119 locations). Early stopping (patience=15) typically triggers around epoch 60–75.

Expected metrics:
- Test MAPE: < 5%
- Test R²: > 0.96
- Test MAE: < 8 kWh/kWp

Model saved to: `ai_engine/models/cnn_lstm_best.pth`

---

## Part 2: YOLOv8 from Sentinel-2 Satellite Imagery

This is a three-step pipeline: **Download → Extract → Annotate → Train**.

### 2.1 Download Sentinel-2 GeoTIFF files

```powershell
# Print the full download guide:
python scripts/download_sentinel2.py --guide

# List recommended tiles for Egypt:
python scripts/download_sentinel2.py --tiles
```

Manual steps (free, no API key needed):
1. Go to https://browser.dataspace.copernicus.eu/
2. Register (free) and log in
3. Search for Egyptian tiles: Cairo, Alexandria, Aswan, Luxor
4. Filter: Sentinel-2 L2A, cloud cover 0–10%, 2022–2024
5. Download TCI GeoTIFF (10 m/pixel, RGB)
6. Save to: `datasets/sentinel2/raw/`

Validate your downloads:
```powershell
python scripts/download_sentinel2.py --validate datasets/sentinel2/raw/ --verbose
```

A healthy file shows:
```
✅  cairo_TCI.tif                    312.4 MB  10m  3b
     Bounds : 31.100°E – 31.600°E,  29.900°N – 30.300°N
```

### 2.2 Extract 640×640 tiles

```powershell
python scripts/extract_roofs_from_geotiff.py ^
    --input  datasets/sentinel2/raw/ ^
    --output datasets/egyptian_roofs/ ^
    --tile-size 640 ^
    --stride 320 ^
    --split 0.8
```

This creates:
```
datasets/egyptian_roofs/
├── images/
│   ├── train/   (80% of tiles)
│   └── val/     (20% of tiles)
```

Typical yield: ~200–800 tiles per GeoTIFF file.

Dry run first to estimate tile count:
```powershell
python scripts/extract_roofs_from_geotiff.py --input datasets/sentinel2/raw/ --output . --dry-run
```

### 2.3 Download SAM checkpoint

```powershell
# ViT-H (best quality, 2.5 GB):
python scripts/semi_auto_annotate.py --download-sam --sam-model-type vit_h

# ViT-B (faster, 375 MB) — good for testing:
python scripts/semi_auto_annotate.py --download-sam --sam-model-type vit_b
```

Saved to: `ai_engine/models/sam_vit_h.pth`

### 2.4 Run SAM auto-annotation (GPU strongly recommended)

```powershell
python scripts/semi_auto_annotate.py ^
    --images  datasets/egyptian_roofs/images/train/ ^
    --output  datasets/egyptian_roofs/labels/train/ ^
    --sam-checkpoint ai_engine/models/sam_vit_h.pth ^
    --device cuda ^
    --review
```

For the validation set:
```powershell
python scripts/semi_auto_annotate.py ^
    --images  datasets/egyptian_roofs/images/val/ ^
    --output  datasets/egyptian_roofs/labels/val/ ^
    --sam-checkpoint ai_engine/models/sam_vit_h.pth ^
    --device cuda
```

On CPU (slow but works — ~5 minutes per image with ViT-H):
```powershell
python scripts/semi_auto_annotate.py ^
    --images  datasets/egyptian_roofs/images/train/ ^
    --output  datasets/egyptian_roofs/labels/train/ ^
    --sam-checkpoint ai_engine/models/sam_vit_b.pth ^
    --sam-model-type vit_b ^
    --device cpu ^
    --points-per-side 16
```

### 2.5 Manual review (recommended)

SAM is not perfect. After auto-annotation, review a sample of labels:

Option A — LabelMe (free, local):
```powershell
pip install labelme
labelme datasets/egyptian_roofs/images/train/ --labels roof chimney ac_unit water_tank satellite_dish tree_shadow vent shade_structure
```

Option B — Roboflow (online, free tier):
1. Go to https://roboflow.com
2. Create a project: Segmentation
3. Upload `datasets/egyptian_roofs/` (images + labels)
4. Review and correct annotations in the web UI
5. Export back as YOLO format

### 2.6 Create data.yaml

```powershell
# data.yaml is auto-created by the training script when running --synthetic.
# For real data, verify or create it manually:
```

`datasets/egyptian_roofs/data.yaml`:
```yaml
path: datasets/egyptian_roofs
train: images/train
val: images/val

nc: 8
names:
  - roof
  - chimney
  - ac_unit
  - water_tank
  - satellite_dish
  - tree_shadow
  - vent
  - shade_structure
```

### 2.7 Train YOLOv8

```powershell
python scripts/train_yolov8_roof.py ^
    --device 0 ^
    --epochs 100 ^
    --batch 16 ^
    --copy-best
```

On CPU (not recommended for >100 images — extremely slow):
```powershell
python scripts/train_yolov8_roof.py --device cpu --epochs 30 --batch 4
```

Resume interrupted training:
```powershell
python scripts/train_yolov8_roof.py --resume runs/segment/egyptian_roofs/weights/last.pt
```

Expected metrics (200+ real images):
- mAP50 (roof): ~94%
- mAP50 (obstacles): ~87%
- Mask mAP50: ~91%

---

## Part 3: Train Everything at Once

```powershell
# Real data, GPU, all models:
python scripts/train_all_models.py --gpu

# With Railway public URL already set in DATABASE_URL:
python scripts/train_all_models.py --gpu --epochs-lstm 100 --epochs-yolo 100
```

---

## Part 4: Verify Trained Models

```powershell
python scripts/verify_trained_models.py --verbose
```

Expected output:
```
✅  Random Forest   — MAPE=4.2%  R²=0.97  (1428 predictions all in range)
✅  K-Means         — 4 clusters  Silhouette=0.68
✅  CNN-LSTM        — output shape (1,12)  all finite  MAPE=4.8%
✅  YOLOv8          — inference OK  640×640  8 classes
ALL 4 MODELS PASS
```

---

## Troubleshooting

### CUDA out of memory
```powershell
# Reduce batch sizes:
python scripts/train_all_models.py --gpu --batch-size 16 --epochs-lstm 100
python scripts/train_yolov8_roof.py --device 0 --batch 8
```

### rasterio installation fails on Windows
```powershell
# Use conda:
conda install -c conda-forge rasterio
# Or use the unofficial Windows wheel:
pip install rasterio --extra-index-url https://wheelhouse.openquake.org/windows/
```

### Railway connection times out
The internal hostname `postgres.railway.internal` is not reachable from outside Railway. Use the public proxy URL from the Railway dashboard.

### SAM is very slow on CPU
Use the smaller `vit_b` model and reduce `--points-per-side 16`. Alternatively, run on Google Colab (free T4 GPU): see `notebooks/train_all_colab.ipynb`.

### YOLOv8 "dataset not found"
Make sure `data.yaml` exists at `datasets/egyptian_roofs/data.yaml` and that the `path`, `train`, and `val` keys point to existing directories with images.

### Windows path issues with long paths
Enable long paths in Windows 11:
- Run: `gpedit.msc`
- Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
- Enable: "Enable Win32 long paths"

---

## Expected Final File Structure

```
shamsi-backend-main/
├── ai_engine/
│   └── models/
│       ├── yield_predictor.pkl         ← Random Forest
│       ├── dust_clusterer.pkl          ← K-Means
│       ├── cnn_lstm_best.pth           ← CNN-LSTM
│       ├── roof_detector_best.pt       ← YOLOv8
│       └── sam_vit_h.pth              ← SAM (annotation only)
├── datasets/
│   ├── sentinel2/
│   │   └── raw/                       ← Downloaded GeoTIFFs
│   └── egyptian_roofs/
│       ├── data.yaml
│       ├── images/train/  (640×640 tiles)
│       ├── images/val/
│       ├── labels/train/  (YOLO .txt)
│       └── labels/val/
└── results/
    ├── training_report.json
    └── step1/
        ├── models/
        ├── metrics/
        └── plots/
```

---

## Performance Benchmarks

| Model | Training time | Inference time |
|-------|--------------|----------------|
| Random Forest | 2 min (CPU) | < 1 ms |
| K-Means | 1 min (CPU) | < 1 ms |
| CNN-LSTM | 45 min (RTX 3090) | 12 ms GPU / 45 ms CPU |
| YOLOv8n-seg | 2 hours (RTX 3090) | 45 ms GPU / 180 ms CPU |

*Training times are for the full real dataset (341,991 DB records / 200 GeoTIFF tiles).*
