# Computer Vision Layer — Developer Guide

**Shamsi Smart | Step 2: Automated Roof Analysis**

---

## Overview

The computer vision layer automates roof analysis from satellite imagery. It replaces 3+ hours of manual measurement with a single API call, returning:

- Detected roof boundary and total area (m²)
- Obstacle inventory (AC units, water tanks, chimneys, satellite dishes, vents, tree shadows)
- Usable roof area after obstacle clearance
- Optimal solar panel grid layout
- Monthly shading loss estimates
- Annotated visualisation images

**Business value:** $5–10/analysis as a standalone API; eliminates manual take-off work for solar installers.

---

## Architecture

```
Satellite Image (JPEG/PNG)
        │
        ▼
┌──────────────────────────────────────┐
│  EgyptianRoofDetector                │
│  ┌────────────────────────────────┐  │
│  │ YOLOv8-seg (ultralytics)       │  │  ← primary path
│  │ roof_detector_best.pt          │  │
│  └────────────────────────────────┘  │
│           OR (fallback)              │
│  ┌────────────────────────────────┐  │
│  │ Heuristic detector             │  │  ← always available
│  │ Otsu threshold + contours      │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  ImageProcessor                      │
│  • Panel layout visualisation        │
│  • Annotated image rendering         │
│  • Satellite image fetching          │
└──────────────────────────────────────┘
        │
        ▼
 Django REST API  →  JSON response + media URLs
```

---

## Quick Start

### 1. Install dependencies

```bash
# Core (always required)
pip install numpy opencv-python-headless pillow

# Optional: YOLOv8 for accurate segmentation
pip install ultralytics

# Optional: dataset annotation
pip install labelme
```

### 2. Generate a synthetic dataset and train

```bash
# Full pipeline with synthetic data (no API key needed)
python scripts/annotate_roofs_labelme.py --full

# Train YOLOv8n-seg for 50 epochs on CPU
python scripts/train_yolov8_roof.py --epochs 50 --device cpu --copy-best

# Expected output:
#   runs/segment/egyptian_roofs/weights/best.pt
#   ai_engine/models/roof_detector_best.pt  (copied by --copy-best)
```

### 3. Test the detector directly

```python
from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
from ai_engine.computer_vision.image_utils   import ImageProcessor

detector = EgyptianRoofDetector(
    model_path='ai_engine/models/roof_detector_best.pt'  # or None for heuristic
)

result = detector.detect_roof(
    image_path='path/to/roof.jpg',
    latitude=30.0,
    zoom=19,
)

print(f"Roof area:    {result['roof_area_m2']:.1f} m²")
print(f"Usable area:  {result['usable_area_m2']:.1f} m²")
print(f"Obstacles:    {len(result['obstacles'])}")
print(f"Max panels:   {result['panel_layout']['max_panels']}")
```

### 4. Call the REST API

```bash
# Analyse an uploaded image
curl -X POST http://localhost:8000/api/v1/ai/analyze-roof/ \
     -F image=@roof.jpg \
     -F latitude=30.0444 \
     -F longitude=31.2357 \
     -F zoom_level=19 \
     -F panel_power_w=580

# Analyse by coordinates (fetches satellite image automatically)
curl -X POST http://localhost:8000/api/v1/ai/analyze-roof-by-coords/ \
     -H 'Content-Type: application/json' \
     -d '{"latitude":30.0444,"longitude":31.2357,"zoom_level":19,"source":"synthetic"}'
```

---

## API Reference

### POST `/api/v1/ai/analyze-roof/`

**Request** — `multipart/form-data`

| Field           | Type    | Default | Description                                      |
|----------------|---------|---------|--------------------------------------------------|
| `image`         | file    | —       | Satellite/aerial roof image (JPEG, PNG, TIFF)    |
| `latitude`      | float   | 30.0    | Site latitude (-90 to 90)                        |
| `longitude`     | float   | 31.0    | Site longitude (-180 to 180)                     |
| `zoom_level`    | int     | 19      | Map zoom level (15–21); 19 ≈ 0.30 m/px           |
| `panel_power_w` | int     | 580     | Panel wattage (e.g. 400, 580, 600)               |

**Response 200 OK**

```json
{
  "analysis_id":         "a3f9c2b1e04d",
  "roof_area_m2":        156.3,
  "usable_area_m2":      142.1,
  "usable_percentage":   90.9,
  "obstacles": [
    {
      "class":      "ac_unit",
      "area_m2":    3.2,
      "location":   [320, 215],
      "confidence": 0.92,
      "bbox":       [300.0, 200.0, 340.0, 230.0]
    }
  ],
  "panel_layout": {
    "max_panels":        42,
    "rows":               6,
    "columns":            7,
    "total_capacity_kw": 24.36,
    "total_coverage_m2": 108.4,
    "efficiency_pct":    76.3,
    "spacing_requirements": {
      "row_spacing_m":    0.68,
      "edge_clearance_m": 0.5
    }
  },
  "shading_analysis": {
    "annual_shading_loss_pct": 5.2,
    "monthly_shading": [3.1, 2.8, 4.0, 5.1, 6.2, 7.0, 7.8, 7.1, 5.9, 4.8, 3.5, 2.9],
    "critical_obstacles": []
  },
  "metadata": {
    "meters_per_pixel": 0.298,
    "orientation":      "flat",
    "roof_type":        "concrete",
    "detector_mode":    "yolov8"
  },
  "annotated_image_url":  "/media/roof_analysis/a3f9c2b1e04d_annotated.jpg",
  "layout_image_url":     "/media/roof_analysis/a3f9c2b1e04d_layout.jpg",
  "processing_time_sec":  1.24
}
```

**Error responses**

| Code | Reason                                              |
|------|-----------------------------------------------------|
| 400  | Missing `image` field                               |
| 400  | Invalid `latitude` / `longitude` / `zoom_level`     |
| 400  | Unsupported file extension                          |
| 413  | Image exceeds 10 MB                                 |
| 500  | Internal analysis error (check server logs)         |

---

### POST `/api/v1/ai/analyze-roof-by-coords/`

**Request** — JSON

```json
{
  "latitude":     30.0444,
  "longitude":    31.2357,
  "zoom_level":   19,
  "source":       "synthetic",
  "panel_power_w": 580
}
```

`source` options: `"google"` (requires `GOOGLE_MAPS_API_KEY`), `"mapbox"` (requires `MAPBOX_TOKEN`), `"osm"`, `"synthetic"`.

**Response** — same schema as the image upload endpoint (minus `layout_image_url`).

---

## Modules

### `ai_engine/computer_vision/image_utils.py` — `ImageProcessor`

| Method | Description |
|--------|-------------|
| `estimate_meters_per_pixel(latitude, zoom)` | Web Mercator scale formula |
| `pixel_area_to_meters(pixel_area, mpp)` | Convert pixel² → m² |
| `fetch_satellite_image(lat, lon, zoom, size, source)` | Download or synthesise satellite image |
| `enhance_roof_contrast(image)` | CLAHE + unsharp mask |
| `draw_panel_layout(image, roof_polygon, panel_positions, panel_size_px, mpp, panel_power_w)` | Render blue panel grid |
| `draw_detection_results(image, roof_polygon, obstacles, usable_area_m2, roof_area_m2)` | Render bounding boxes + summary banner |
| `save_image(image, path)` | Save BGR numpy array to disk |

**Scale formula** (Web Mercator):

```
meters_per_pixel = 156543.03392 × cos(latitude_rad) / 2^zoom_level
```

| Zoom | Cairo (30°N) m/px |
|------|-------------------|
| 17   | 1.194             |
| 18   | 0.597             |
| 19   | 0.298  ← default  |
| 20   | 0.149             |
| 21   | 0.075             |

---

### `ai_engine/computer_vision/roof_detector.py` — `EgyptianRoofDetector`

**Initialisation:**

```python
detector = EgyptianRoofDetector(
    model_path='ai_engine/models/roof_detector_best.pt',  # None → heuristic fallback
    confidence_threshold=0.5,
)
```

**Class index mapping** (YOLO label IDs):

| ID | Class             |
|----|-------------------|
| 0  | `roof_boundary`   |
| 1  | `chimney`         |
| 2  | `ac_unit`         |
| 3  | `water_tank`      |
| 4  | `satellite_dish`  |
| 5  | `tree_shadow`     |
| 6  | `vent`            |
| 7  | `shade_structure` |

**Key methods:**

- `detect_roof(image_path, confidence_threshold, latitude, zoom)` → full analysis dict
- `calculate_panel_layout(usable_area_m2, panel_specs, orientation)` → layout dict
- `get_panel_positions_px(roof_polygon, panel_layout, meters_per_pixel)` → list of (x, y) pixel positions
- `estimate_shading_loss(obstacles, roof_polygon, latitude, mpp)` → shading dict
- `_polygon_area(polygon)` → float (pixel²), using the shoelace formula

**Panel layout algorithm:**

```
net_area = usable_area_m2 − 4 × edge_clearance_m × √usable_area_m2
panel_area_with_spacing = width_m × height_m × (1 + ROW_SPACING_FACTOR)
max_panels = floor(net_area / panel_area_with_spacing)
```

Constants: `ROW_SPACING_FACTOR = 0.30`, `EDGE_CLEARANCE_M = 0.50`

---

### `ai_engine/computer_vision/dataset_creator.py` — `YOLODatasetCreator`

**Dataset structure** (YOLO format):

```
datasets/egyptian_roofs/
├── data.yaml
├── images/
│   ├── train/   ← JPEG images
│   └── val/
├── labels/
│   ├── train/   ← .txt files (one per image)
│   └── val/
└── raw_images/  ← unlabelled downloads
```

**Label file format** (YOLO segmentation):

```
<class_id> <x1_norm> <y1_norm> <x2_norm> <y2_norm> ...
```

All coordinates are normalised to [0, 1] relative to image width/height.

---

## Dataset Annotation Workflow

### Option A — Fully synthetic (no API key, quickest)

```bash
python scripts/annotate_roofs_labelme.py --full
# Generates 200 synthetic labelled images ready for training
```

### Option B — Real satellite images with manual labels

```bash
# 1. Download unlabelled satellite images
python scripts/annotate_roofs_labelme.py --download --n 200 --source synthetic

# 2. Open LabelMe GUI and annotate
python scripts/annotate_roofs_labelme.py --annotate
# In LabelMe: press 'a' to draw polygons, label as roof_boundary / ac_unit / etc.
# Save with Ctrl+S before moving to the next image

# 3. Export to YOLO format
python scripts/annotate_roofs_labelme.py --export

# 4. Check dataset statistics
python scripts/annotate_roofs_labelme.py --stats
```

**Recommended annotation target:** 200+ images (at least 50 for initial testing).

---

## Training

```bash
# Synthetic dataset, CPU, 50 epochs (for testing)
python scripts/train_yolov8_roof.py --epochs 50 --device cpu --batch 8 --copy-best

# GPU training (production)
python scripts/train_yolov8_roof.py --epochs 100 --device 0 --batch 16 --copy-best

# Resume interrupted run
python scripts/train_yolov8_roof.py --resume runs/segment/egyptian_roofs/weights/last.pt
```

**Egypt-specific augmentations used:**

| Parameter      | Value | Rationale                                      |
|----------------|-------|------------------------------------------------|
| `degrees`      | 15    | Satellite images can be rotated               |
| `flipud`       | 0.5   | Roofs look the same upside-down               |
| `fliplr`       | 0.5   | Horizontal symmetry                            |
| `hsv_v`        | 0.4   | Simulates cloud shadows and haze              |
| `mosaic`       | 1.0   | Helps detect small obstacles                  |
| `copy_paste`   | 0.1   | Augments obstacle variety                     |
| `perspective`  | 0.0   | Satellite is near-orthographic                |

**Expected training metrics** (200 real images):

| Metric        | Target  |
|---------------|---------|
| mAP50 (roof)  | ≥ 94%   |
| mAP50 (obstacles) | ≥ 87% |
| Mask mAP50    | ≥ 91%   |

---

## Running Tests

```bash
# All CV tests
python -m pytest tests/test_computer_vision.py -v

# Specific class
python -m pytest tests/test_computer_vision.py::TestRoofDetector -v

# Quick smoke test
python -m pytest tests/test_computer_vision.py::TestEndToEndSmoke -v

# With coverage
pip install pytest-cov
python -m pytest tests/test_computer_vision.py --cov=ai_engine.computer_vision --cov-report=term-missing
```

---

## Configuration

### Django settings

```python
# settings.py
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL  = '/media/'

# Optional: set path to trained model
ROOF_DETECTOR_MODEL = BASE_DIR / 'ai_engine' / 'models' / 'roof_detector_best.pt'
```

### URL configuration

Ensure `api/urls.py` includes the roof analysis routes (already added):

```python
from .views.roof_analysis_view import analyze_roof_image, analyze_roof_by_coordinates

path('ai/analyze-roof/',           analyze_roof_image,           name='analyze-roof'),
path('ai/analyze-roof-by-coords/', analyze_roof_by_coordinates,  name='analyze-roof-by-coords'),
```

### Media files in development

```python
# urls.py (project-level)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## Troubleshooting

**`ultralytics` not installed — falling back to heuristic detection**
Install with `pip install ultralytics`. The heuristic fallback still works but is less accurate on complex rooftops.

**`cv2` not installed**
Install with `pip install opencv-python-headless` (server) or `pip install opencv-python` (desktop).

**Image too dark / bad contour detection**
The heuristic uses Otsu thresholding. Pass high-contrast satellite imagery. Enhance contrast first:
```python
from ai_engine.computer_vision.image_utils import ImageProcessor
import cv2
img = cv2.imread('dark_roof.jpg')
enhanced = ImageProcessor.enhance_roof_contrast(img)
cv2.imwrite('enhanced.jpg', enhanced)
```

**Google Maps / Mapbox satellite fetch fails**
Set `GOOGLE_MAPS_API_KEY` or `MAPBOX_TOKEN` in your environment, or use `source='synthetic'` for testing.

**Training: CUDA OOM**
Reduce batch size: `--batch 8` or `--batch 4`. Or run `--device cpu` with `--epochs 30` for a quick test.

---

## File Index

| File | Purpose |
|------|---------|
| `ai_engine/computer_vision/__init__.py` | Package init with `EgyptianRoofDetector`, `ImageProcessor` |
| `ai_engine/computer_vision/roof_detector.py` | Main detector class (YOLOv8 + heuristic fallback) |
| `ai_engine/computer_vision/image_utils.py` | Scale maths, image fetch, visualisation helpers |
| `ai_engine/computer_vision/dataset_creator.py` | Dataset structure, annotation export, synthetic generation |
| `scripts/annotate_roofs_labelme.py` | Dataset download + LabelMe annotation pipeline |
| `scripts/train_yolov8_roof.py` | YOLOv8 training with Egypt-specific augmentations |
| `api/views/roof_analysis_view.py` | Django REST endpoints (`/analyze-roof/`, `/analyze-roof-by-coords/`) |
| `tests/test_computer_vision.py` | Unit + integration tests (no API key or GPU needed) |
| `docs/computer_vision_guide.md` | This file |
| `docs/academic/step2_cv_methodology.md` | Academic methodology section |
