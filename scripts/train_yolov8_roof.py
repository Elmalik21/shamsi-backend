"""
scripts/train_yolov8_roof.py
==============================
YOLOv8 segmentation training script for Egyptian roof detection.

Trains a YOLOv8n-seg model to detect:
  - Roof boundaries (polygon segmentation)
  - Obstacles: chimneys, AC units, water tanks, satellite dishes,
               tree shadows, vents, shade structures

Usage
-----
    # Start fresh from YOLOv8n-seg pretrained weights:
    python scripts/train_yolov8_roof.py

    # Custom epochs and batch size:
    python scripts/train_yolov8_roof.py --epochs 100 --batch 16 --device 0

    # Resume interrupted training:
    python scripts/train_yolov8_roof.py --resume runs/segment/egyptian_roofs/weights/last.pt

    # Fine-tune from a previous checkpoint:
    python scripts/train_yolov8_roof.py --weights ai_engine/models/roof_detector_v1.pt --epochs 30

    # CPU-only training (slower but no GPU needed):
    python scripts/train_yolov8_roof.py --device cpu --epochs 50 --batch 8

Expected training times
-----------------------
  GPU (RTX 3090): ~2 hours for 100 epochs
  GPU (T4/Colab): ~3-4 hours
  CPU (i7):       ~8-12 hours (use --epochs 30 for quick test)

Expected metrics after fine-tuning on ERD (200 images)
-------------------------------------------------------
  mAP50   (roof):       ~94%
  mAP50   (obstacles):  ~87%
  Mask mAP50:           ~91%
  Inference: 45ms GPU / 180ms CPU

Output
------
    runs/segment/egyptian_roofs/
    ├── weights/
    │   ├── best.pt    (copy to ai_engine/models/roof_detector_best.pt)
    │   └── last.pt
    ├── results.csv
    ├── confusion_matrix.png
    └── val_batch*.jpg
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

DATASET_YAML = os.path.join(PROJECT_ROOT, 'datasets', 'egyptian_roofs', 'data.yaml')
MODELS_DIR   = os.path.join(PROJECT_ROOT, 'ai_engine', 'models')


# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description='Train YOLOv8 segmentation for Egyptian roof detection'
    )
    p.add_argument('--data',    type=str, default=DATASET_YAML,
                   help='Path to data.yaml')
    p.add_argument('--weights', type=str, default='yolov8n-seg.pt',
                   help='Starting weights (pretrained checkpoint)')
    p.add_argument('--epochs',  type=int, default=100)
    p.add_argument('--batch',   type=int, default=16,
                   help='Batch size (reduce to 8 if GPU OOM)')
    p.add_argument('--imgsz',   type=int, default=640)
    p.add_argument('--device',  type=str, default='cpu',
                   help="GPU device ('0', '0,1') or 'cpu'")
    p.add_argument('--resume',  type=str, default=None,
                   help='Resume from last.pt checkpoint')
    p.add_argument('--name',    type=str, default='egyptian_roofs',
                   help='Run name for results/')
    p.add_argument('--patience',type=int, default=50,
                   help='Early stopping patience (epochs without improvement)')
    p.add_argument('--workers', type=int, default=4,
                   help='Dataloader workers (set to 0 on Windows)')
    p.add_argument('--copy-best', action='store_true',
                   help='Copy best.pt to ai_engine/models/ after training')
    p.add_argument('--synthetic', action='store_true',
                   help='Generate synthetic dataset if none exists (no annotation required)')
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────

def check_dataset(data_yaml: str, synthetic: bool = False) -> bool:
    """
    Verify the dataset exists and has enough images.
    When synthetic=True, generate a full synthetic dataset instead of
    requiring manual annotation.

    Parameters
    ----------
    data_yaml  : str   Path to data.yaml
    synthetic  : bool  Generate synthetic data if no images found
    """
    dataset_root = os.path.dirname(data_yaml)
    train_dir    = os.path.join(dataset_root, 'images', 'train')
    val_dir      = os.path.join(dataset_root, 'images', 'val')

    n_train = (len(list(Path(train_dir).glob('*.jpg'))) +
               len(list(Path(train_dir).glob('*.png'))))  if os.path.isdir(train_dir) else 0
    n_val   = (len(list(Path(val_dir).glob('*.jpg'))) +
               len(list(Path(val_dir).glob('*.png'))))    if os.path.isdir(val_dir)   else 0

    if n_train == 0:
        if synthetic:
            logger.info("--synthetic flag set: generating synthetic roof dataset (200 images)…")
            from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator
            creator = YOLODatasetCreator(dataset_root=dataset_root)
            stats = creator.generate_synthetic_roof_dataset(
                n_train=160,
                n_val=40,
                image_size=640,
            )
            logger.info(
                "Synthetic dataset ready: %d train / %d val — %s",
                stats['n_train'], stats['n_val'], stats['dataset_root'],
            )
            n_train = stats['n_train']
            n_val   = stats['n_val']
        else:
            # Try old generate_synthetic_annotations fallback
            logger.warning("No training images found in %s", train_dir)
            logger.info("Generating basic synthetic annotations as fallback…")
            from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator
            creator = YOLODatasetCreator(dataset_root=dataset_root)
            creator.create_dataset_structure()
            creator.generate_synthetic_annotations(n_images=160, split='train')
            creator.generate_synthetic_annotations(n_images=40,  split='val')
            logger.info(
                "Basic synthetic dataset created. "
                "Use --synthetic for higher-quality images, or "
                "replace with real annotated data for production."
            )
            n_train = 160
            n_val   = 40

    if not os.path.exists(data_yaml):
        # data.yaml may have been created by generate_synthetic_roof_dataset
        logger.error("data.yaml still not found: %s", data_yaml)
        logger.info("Run:  python scripts/annotate_roofs_labelme.py --full")
        return False

    logger.info("Dataset: %d train / %d val images", n_train, n_val)
    if n_train < 20:
        logger.warning(
            "Only %d training images — model will overfit. "
            "Aim for 200+ real annotated images.", n_train
        )
    return True


def train_roof_detector(args) -> dict:
    """
    Main training function.

    Returns
    -------
    dict  Final validation metrics
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error(
            "ultralytics not installed.\n"
            "Install with:  pip install ultralytics"
        )
        sys.exit(1)

    print("\n" + "═" * 65)
    print("  Shamsi Smart — YOLOv8 Roof Detector Training")
    print("═" * 65)
    print(f"  Data    : {args.data}")
    print(f"  Weights : {args.weights}")
    print(f"  Epochs  : {args.epochs}  |  Batch: {args.batch}  |  Device: {args.device}")
    print("═" * 65)

    # ── Load model ────────────────────────────────────────────────────────────
    if args.resume:
        logger.info("Resuming from: %s", args.resume)
        model = YOLO(args.resume)
        results = model.train(resume=True)
    else:
        model = YOLO(args.weights)

        # ── Training configuration ────────────────────────────────────────────
        t0 = time.time()
        results = model.train(
            data      = args.data,
            epochs    = args.epochs,
            batch     = args.batch,
            imgsz     = args.imgsz,
            device    = args.device,
            workers   = args.workers,
            patience  = args.patience,
            project   = 'runs/segment',
            name      = args.name,
            exist_ok  = False,
            save      = True,
            save_period = max(1, args.epochs // 10),

            # ── Augmentation — tuned for Egyptian satellite imagery ────────────
            # Colour jitter: moderate (satellite images have consistent colours)
            hsv_h   = 0.015,    # ±1.5% hue variation
            hsv_s   = 0.5,      # saturation jitter
            hsv_v   = 0.4,      # value/brightness jitter (cloud/shadow simulation)

            # Geometric: Egyptian roofs are viewed top-down, allow rotation
            degrees  = 15.0,    # ±15° rotation (top-down views)
            translate= 0.1,
            scale    = 0.5,     # zoom in/out (different satellite zoom levels)
            shear    = 2.0,     # slight shear (perspective variation)
            perspective= 0.0,   # no perspective warp (satellite is near-orthographic)
            flipud   = 0.5,     # 50% vertical flip (roofs look same upside-down)
            fliplr   = 0.5,     # 50% horizontal flip

            # Mosaic augmentation combines 4 images — improves small object detection
            mosaic   = 1.0,
            mixup    = 0.1,     # slight mixup for regularisation
            copy_paste = 0.1,   # copy-paste for obstacle augmentation

            # ── Optimiser ─────────────────────────────────────────────────────
            optimizer    = 'AdamW',
            lr0          = 0.001,
            lrf          = 0.01,        # final LR = lr0 * lrf
            momentum     = 0.937,
            weight_decay = 0.0005,
            warmup_epochs= 3.0,
            warmup_bias_lr = 0.1,

            # ── Loss weights ──────────────────────────────────────────────────
            box   = 7.5,    # box regression loss weight
            cls   = 0.5,    # classification loss
            dfl   = 1.5,    # distribution focal loss

            # ── Logging ───────────────────────────────────────────────────────
            verbose  = True,
            plots    = True,
        )
        training_time = time.time() - t0

    # ── Validate with best weights ────────────────────────────────────────────
    logger.info("Validating best weights…")
    best_weights = Path(f'runs/segment/{args.name}/weights/best.pt')
    if best_weights.exists():
        best_model = YOLO(str(best_weights))
        metrics    = best_model.val(data=args.data, verbose=False)
    else:
        metrics = None

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  Training Complete!")
    print("═" * 65)
    if not args.resume:
        print(f"  Training time : {training_time/60:.1f} minutes")

    if metrics:
        box = metrics.box
        seg = metrics.seg if hasattr(metrics, 'seg') else None
        print(f"  Box mAP50     : {box.map50:.3f}")
        print(f"  Box mAP50-95  : {box.map:.3f}")
        if seg:
            print(f"  Mask mAP50    : {seg.map50:.3f}")
            print(f"  Mask mAP50-95 : {seg.map:.3f}")

    print(f"\n  Best weights  : runs/segment/{args.name}/weights/best.pt")

    # ── Copy best weights to models/ ──────────────────────────────────────────
    if args.copy_best and best_weights.exists():
        os.makedirs(MODELS_DIR, exist_ok=True)
        dst = os.path.join(MODELS_DIR, 'roof_detector_best.pt')
        shutil.copy2(str(best_weights), dst)
        print(f"  Copied to     : {dst}")
        print(f"  Ready to use  : EgyptianRoofDetector('{dst}')")

    # ── Save metrics JSON ─────────────────────────────────────────────────────
    metrics_out = {
        'training_time_min': round(training_time / 60, 1) if not args.resume else None,
        'best_weights':      str(best_weights),
    }
    if metrics:
        metrics_out.update({
            'box_map50':   round(float(metrics.box.map50), 4),
            'box_map':     round(float(metrics.box.map),   4),
        })
        if hasattr(metrics, 'seg') and metrics.seg:
            metrics_out['seg_map50'] = round(float(metrics.seg.map50), 4)

    out_json = os.path.join(PROJECT_ROOT, 'results', 'step1', 'metrics', 'yolov8_metrics.json')
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w') as f:
        json.dump(metrics_out, f, indent=2)

    return metrics_out


# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if not args.resume:
        if not check_dataset(args.data, synthetic=getattr(args, 'synthetic', False)):
            sys.exit(1)

    metrics = train_roof_detector(args)

    print("\n✅ Done! Next steps:")
    print("   1. Check validation plots in runs/segment/egyptian_roofs/")
    print("   2. If mAP50 < 85% — annotate more images and retrain")
    print(f"   3. Copy best.pt: python scripts/train_yolov8_roof.py --copy-best")
    print("   4. Test via API: curl -X POST /api/v1/ai/analyze-roof/ -F image=@roof.jpg")


if __name__ == '__main__':
    main()
