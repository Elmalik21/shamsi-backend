"""
scripts/semi_auto_annotate.py
==============================
Semi-automatic roof annotation pipeline using Meta's Segment Anything
Model (SAM) for Shamsi Smart YOLOv8 training data preparation.

Given a folder of 640×640 satellite image tiles, SAM generates candidate
roof boundary masks. A lightweight heuristic filter selects roof-shaped
polygons (large, roughly rectangular, high internal contrast).

The output is YOLO segmentation format (.txt) label files, one per image.

Usage
-----
    # Download SAM checkpoint first (once):
    python scripts/semi_auto_annotate.py --download-sam

    # Annotate all images in a folder (GPU recommended):
    python scripts/semi_auto_annotate.py \\
        --images  datasets/egyptian_roofs/images/train/ \\
        --output  datasets/egyptian_roofs/labels/train/ \\
        --sam-checkpoint ai_engine/models/sam_vit_h.pth \\
        --device cuda

    # CPU-only (slow but works):
    python scripts/semi_auto_annotate.py \\
        --images  datasets/egyptian_roofs/images/train/ \\
        --output  datasets/egyptian_roofs/labels/train/ \\
        --sam-checkpoint ai_engine/models/sam_vit_h.pth \\
        --device cpu

    # Use smaller SAM model (faster):
    python scripts/semi_auto_annotate.py \\
        --images  datasets/egyptian_roofs/images/train/ \\
        --output  datasets/egyptian_roofs/labels/train/ \\
        --sam-checkpoint ai_engine/models/sam_vit_b.pth \\
        --sam-model-type vit_b

    # Review: generate overlay PNG files for manual quality check:
    python scripts/semi_auto_annotate.py \\
        --images  datasets/egyptian_roofs/images/train/ \\
        --output  datasets/egyptian_roofs/labels/train/ \\
        --sam-checkpoint ai_engine/models/sam_vit_h.pth \\
        --review

SAM Model Download URLs
-----------------------
    vit_h (best, 2.5 GB):
        https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth

    vit_l (balanced, 1.2 GB):
        https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth

    vit_b (fastest, 375 MB):
        https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth

YOLO label format (class 0 = roof boundary)
-------------------------------------------
    0  x1 y1 x2 y2 ... xN yN      (normalised 0.0–1.0, polygon vertices)

After annotation
----------------
    1. Manually review labels with LabelMe or Roboflow.
    2. Train:  python scripts/train_yolov8_roof.py --device 0 --epochs 100
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

# SAM checkpoint download URLs
SAM_URLS = {
    'vit_h': 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth',
    'vit_l': 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth',
    'vit_b': 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth',
}

SAM_FILENAMES = {
    'vit_h': 'sam_vit_h.pth',
    'vit_l': 'sam_vit_l.pth',
    'vit_b': 'sam_vit_b.pth',
}

# YOLO class IDs
CLASS_ROOF     = 0
CLASS_CHIMNEY  = 1
CLASS_AC       = 2
CLASS_TANK     = 3
CLASS_SATELLITE = 4
CLASS_SHADOW   = 5
CLASS_VENT     = 6
CLASS_SHADE    = 7


# ─────────────────────────────────────────────────────────────────────────────

def download_sam_model(
    model_type: str = 'vit_h',
    save_dir: str = 'ai_engine/models/',
) -> str:
    """
    Download SAM checkpoint from Meta's servers.

    Parameters
    ----------
    model_type : str  'vit_h', 'vit_l', or 'vit_b'
    save_dir   : str  Directory to save the checkpoint.

    Returns
    -------
    str  Path to the downloaded checkpoint.
    """
    if model_type not in SAM_URLS:
        raise ValueError(f"Unknown SAM model type '{model_type}'. "
                         f"Choose from: {list(SAM_URLS.keys())}")

    url      = SAM_URLS[model_type]
    filename = SAM_FILENAMES[model_type]
    save_path = Path(save_dir) / filename
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if save_path.exists():
        size_mb = save_path.stat().st_size / 1_048_576
        logger.info("SAM checkpoint already exists: %s  (%.0f MB)", save_path, size_mb)
        return str(save_path)

    logger.info("Downloading SAM %s from Meta servers…", model_type.upper())
    logger.info("URL: %s", url)
    logger.info("Destination: %s", save_path)

    def _progress(count, block_size, total_size):
        pct = min(100, count * block_size * 100 // total_size)
        mb  = count * block_size / 1_048_576
        print(f"\r  [{pct:3d}%]  {mb:.0f} MB downloaded", end='', flush=True)

    try:
        urllib.request.urlretrieve(url, str(save_path), reporthook=_progress)
        print()
        size_mb = save_path.stat().st_size / 1_048_576
        logger.info("Downloaded: %s  (%.0f MB)", save_path, size_mb)
    except Exception as exc:
        logger.error("Download failed: %s", exc)
        logger.info(
            "Manual download:\n"
            "  1. Open:  %s\n"
            "  2. Save to:  %s", url, save_path,
        )
        raise

    return str(save_path)


# ─────────────────────────────────────────────────────────────────────────────

def filter_roof_masks(
    masks: list,
    image_size: int = 640,
    min_area_ratio: float = 0.005,
    max_area_ratio: float = 0.85,
    min_solidity: float = 0.55,
) -> list:
    """
    Filter SAM-generated masks to keep likely roof boundaries.

    Heuristics for rooftop masks (top-down satellite view):
      - Area: 0.5%–85% of image area (not too small/large)
      - Solidity: mask area / convex hull area ≥ 0.55 (approximately convex)

    Parameters
    ----------
    masks          : list  List of SAM mask dicts with keys 'segmentation', 'area', etc.
    image_size     : int   Width/height of the square image (default 640).
    min_area_ratio : float Minimum mask area as fraction of image (default 0.005).
    max_area_ratio : float Maximum mask area as fraction of image (default 0.85).
    min_solidity   : float Minimum solidity threshold (default 0.55).

    Returns
    -------
    list  Filtered list of mask dicts, sorted by area descending.
    """
    try:
        import cv2
    except ImportError:
        logger.warning("OpenCV not available — skipping solidity filter")
        cv2 = None

    img_area    = image_size * image_size
    min_px      = int(img_area * min_area_ratio)
    max_px      = int(img_area * max_area_ratio)

    good_masks = []
    for m in masks:
        area = m.get('area', 0)
        if area < min_px or area > max_px:
            continue

        # Solidity check using OpenCV convex hull
        if cv2 is not None:
            seg = m['segmentation'].astype(np.uint8)
            contours, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL,
                                            cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                continue
            cnt = max(contours, key=cv2.contourArea)
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            if hull_area <= 0:
                continue
            solidity = cv2.contourArea(cnt) / hull_area
            if solidity < min_solidity:
                continue

        good_masks.append(m)

    # Sort by area descending (largest roof first)
    good_masks.sort(key=lambda m: m.get('area', 0), reverse=True)
    return good_masks


def mask_to_yolo_polygon(
    mask: np.ndarray,
    image_size: int = 640,
    n_points: int = 20,
) -> Optional[str]:
    """
    Convert a binary segmentation mask to a YOLO polygon annotation string.

    Traces the mask contour, samples *n_points* evenly spaced vertices, and
    returns a YOLO segmentation line:
        "CLASS_ID  x1 y1 x2 y2 … xN yN"

    Parameters
    ----------
    mask       : np.ndarray  Binary mask, shape (H, W), dtype bool or uint8.
    image_size : int         Image width = height (pixels).
    n_points   : int         Number of polygon vertices (default 20).

    Returns
    -------
    str or None   YOLO annotation line, or None if contour extraction failed.
    """
    try:
        import cv2
    except ImportError:
        logger.error("OpenCV required for mask_to_yolo_polygon.  "
                     "Install:  pip install opencv-python")
        return None

    seg = mask.astype(np.uint8)
    contours, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Use the largest contour
    cnt = max(contours, key=cv2.contourArea)

    # Sample n_points evenly around the contour
    total = len(cnt)
    if total < 3:
        return None
    step = max(1, total // n_points)
    sampled = cnt[::step].reshape(-1, 2)[:n_points]
    if len(sampled) < 3:
        return None

    # Normalise coordinates to [0, 1]
    pts_norm = sampled.astype(float) / image_size
    pts_norm = np.clip(pts_norm, 0.0, 1.0)

    coords = ' '.join(f'{x:.6f} {y:.6f}' for x, y in pts_norm)
    return f'{CLASS_ROOF} {coords}'


# ─────────────────────────────────────────────────────────────────────────────

def annotate_images(
    images_dir: str,
    output_dir: str,
    sam_checkpoint: str,
    sam_model_type: str = 'vit_h',
    device: str = 'cuda',
    review: bool = False,
    points_per_side: int = 32,
    min_area_ratio: float = 0.005,
    max_area_ratio: float = 0.85,
) -> dict:
    """
    Run SAM on all images in *images_dir* and write YOLO label files.

    Parameters
    ----------
    images_dir     : str   Directory containing .jpg / .png tiles.
    output_dir     : str   Directory to write .txt label files.
    sam_checkpoint : str   Path to SAM model weights (.pth).
    sam_model_type : str   'vit_h', 'vit_l', or 'vit_b'.
    device         : str   'cuda' or 'cpu'.
    review         : bool  If True, also write overlay .png files for QC.
    points_per_side: int   SAM grid density (lower = faster, default 32).
    min_area_ratio : float Minimum mask area fraction (default 0.005).
    max_area_ratio : float Maximum mask area fraction (default 0.85).

    Returns
    -------
    dict  Summary statistics.
    """
    try:
        from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
    except ImportError:
        logger.error(
            "segment-anything is not installed.\n"
            "Install with:\n"
            "  pip install git+https://github.com/facebookresearch/segment-anything.git"
        )
        sys.exit(1)

    try:
        from PIL import Image as PILImage
        HAS_PIL = True
    except ImportError:
        HAS_PIL = False

    try:
        import cv2
        HAS_CV2 = True
    except ImportError:
        HAS_CV2 = False

    images_path = Path(images_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    image_files = (
        list(images_path.glob('*.jpg'))  +
        list(images_path.glob('*.jpeg')) +
        list(images_path.glob('*.png'))
    )
    image_files = sorted(image_files)

    if not image_files:
        logger.warning("No images found in: %s", images_dir)
        return {'annotated': 0, 'skipped': 0, 'total_masks': 0}

    logger.info("Loading SAM (%s) from: %s", sam_model_type.upper(), sam_checkpoint)
    sam = sam_model_registry[sam_model_type](checkpoint=sam_checkpoint)
    sam.to(device=device)

    mask_generator = SamAutomaticMaskGenerator(
        model           = sam,
        points_per_side = points_per_side,
        pred_iou_thresh = 0.86,
        stability_score_thresh = 0.92,
        min_mask_region_area   = 100,
    )

    logger.info(
        "Annotating %d images  |  device=%s  |  points_per_side=%d",
        len(image_files), device, points_per_side,
    )

    annotated   = 0
    skipped     = 0
    total_masks = 0

    for img_path in image_files:
        label_path = output_path / (img_path.stem + '.txt')

        if label_path.exists():
            logger.debug("Skipping (label exists): %s", img_path.name)
            skipped += 1
            continue

        # Load image
        if HAS_PIL:
            img_pil = PILImage.open(str(img_path)).convert('RGB')
            img_np  = np.array(img_pil)
        elif HAS_CV2:
            img_bgr = cv2.imread(str(img_path))
            img_np  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        else:
            logger.error("Need Pillow or OpenCV to read images.  "
                         "pip install Pillow opencv-python")
            sys.exit(1)

        h, w = img_np.shape[:2]

        # Generate masks
        try:
            masks = mask_generator.generate(img_np)
        except Exception as exc:
            logger.warning("SAM failed on %s: %s", img_path.name, exc)
            skipped += 1
            continue

        # Filter to roof-shaped masks
        roof_masks = filter_roof_masks(
            masks,
            image_size     = max(h, w),
            min_area_ratio = min_area_ratio,
            max_area_ratio = max_area_ratio,
        )

        if not roof_masks:
            logger.debug("No roof masks found in: %s", img_path.name)
            # Write empty label file (YOLO expects a file for every image)
            label_path.write_text('')
            skipped += 1
            continue

        # Convert masks to YOLO polygon lines
        lines = []
        for m in roof_masks:
            line = mask_to_yolo_polygon(
                m['segmentation'].astype(np.uint8),
                image_size = max(h, w),
                n_points   = 20,
            )
            if line:
                lines.append(line)

        label_path.write_text('\n'.join(lines) + '\n' if lines else '')
        annotated   += 1
        total_masks += len(lines)

        # Optional review overlay
        if review and HAS_CV2 and lines:
            review_dir = output_path.parent / 'review'
            review_dir.mkdir(exist_ok=True)
            overlay = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR).copy()
            for m in roof_masks[:5]:   # draw up to 5 masks
                colour = (
                    int(np.random.randint(100, 255)),
                    int(np.random.randint(100, 255)),
                    int(np.random.randint(100, 255)),
                )
                seg = m['segmentation'].astype(np.uint8)
                contours, _ = cv2.findContours(
                    seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                cv2.drawContours(overlay, contours, -1, colour, 2)
            cv2.imwrite(
                str(review_dir / (img_path.stem + '_review.png')), overlay
            )

        if (annotated + skipped) % 50 == 0:
            logger.info(
                "  Progress: %d / %d  (annotated=%d, skipped=%d)",
                annotated + skipped, len(image_files), annotated, skipped,
            )

    logger.info(
        "Done. Annotated: %d  |  Skipped: %d  |  Total masks: %d",
        annotated, skipped, total_masks,
    )

    return {
        'annotated':   annotated,
        'skipped':     skipped,
        'total_masks': total_masks,
    }


# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Semi-automatic roof annotation using SAM for YOLOv8 training'
    )
    p.add_argument('--images', '-i', type=str,
                   help='Directory containing image tiles to annotate')
    p.add_argument('--output', '-o', type=str,
                   help='Directory to write YOLO .txt label files')
    p.add_argument('--sam-checkpoint', type=str,
                   default='ai_engine/models/sam_vit_h.pth',
                   help='Path to SAM model weights (.pth)')
    p.add_argument('--sam-model-type', type=str, default='vit_h',
                   choices=['vit_h', 'vit_l', 'vit_b'],
                   help='SAM model variant (default: vit_h)')
    p.add_argument('--device', type=str, default='cuda',
                   choices=['cuda', 'cpu'],
                   help='Inference device (default: cuda)')
    p.add_argument('--points-per-side', type=int, default=32,
                   help='SAM grid density — lower is faster (default: 32)')
    p.add_argument('--review', action='store_true',
                   help='Save overlay PNG files for manual quality review')
    p.add_argument('--download-sam', action='store_true',
                   help='Download SAM checkpoint (set --sam-model-type to choose)')
    p.add_argument('--save-dir', type=str, default='ai_engine/models/',
                   help='Directory to save downloaded SAM checkpoint')
    p.add_argument('--min-area', type=float, default=0.005,
                   help='Minimum mask area as fraction of image (default: 0.005)')
    p.add_argument('--max-area', type=float, default=0.85,
                   help='Maximum mask area as fraction of image (default: 0.85)')
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.download_sam:
        path = download_sam_model(
            model_type = args.sam_model_type,
            save_dir   = args.save_dir,
        )
        print(f"\n  ✅  SAM checkpoint saved to: {path}")
        print(f"\n  Next: python scripts/semi_auto_annotate.py "
              f"--images <tiles_dir> --output <labels_dir> "
              f"--sam-checkpoint {path}")
        return

    if not args.images or not args.output:
        print(
            "\n  Usage:\n"
            "    python scripts/semi_auto_annotate.py \\\n"
            "        --images  datasets/egyptian_roofs/images/train/ \\\n"
            "        --output  datasets/egyptian_roofs/labels/train/ \\\n"
            "        --sam-checkpoint ai_engine/models/sam_vit_h.pth\n"
        )
        sys.exit(1)

    if not Path(args.sam_checkpoint).exists():
        logger.error(
            "SAM checkpoint not found: %s\n"
            "Download it first:\n"
            "    python scripts/semi_auto_annotate.py --download-sam "
            "--sam-model-type %s",
            args.sam_checkpoint, args.sam_model_type,
        )
        sys.exit(1)

    stats = annotate_images(
        images_dir     = args.images,
        output_dir     = args.output,
        sam_checkpoint = args.sam_checkpoint,
        sam_model_type = args.sam_model_type,
        device         = args.device,
        review         = args.review,
        points_per_side= args.points_per_side,
        min_area_ratio = args.min_area,
        max_area_ratio = args.max_area,
    )

    print("\n" + "═" * 60)
    print("  SAM Annotation Complete")
    print("═" * 60)
    print(f"  Annotated images  : {stats['annotated']}")
    print(f"  Skipped           : {stats['skipped']}")
    print(f"  Total roof masks  : {stats['total_masks']}")
    if args.review:
        review_dir = Path(args.output).parent / 'review'
        print(f"  Review overlays   : {review_dir}")
    print("═" * 60)
    print("\n  Next steps:")
    print("  1. Review labels in LabelMe or Roboflow Studio")
    print("  2. Correct any mis-annotated masks")
    print(f"  3. Train:  python scripts/train_yolov8_roof.py "
          f"--device 0 --epochs 100 --copy-best")


if __name__ == '__main__':
    main()
