"""
scripts/annotate_roofs_labelme.py
===================================
Helper for building the Egyptian Roofs Dataset (ERD).

Workflow
--------
  Step 1 — Download satellite images:
      python scripts/annotate_roofs_labelme.py --download
      python scripts/annotate_roofs_labelme.py --download --source synthetic --n 50

  Step 2 — Annotate with LabelMe GUI:
      python scripts/annotate_roofs_labelme.py --annotate

  Step 3 — Export LabelMe JSON → YOLO format:
      python scripts/annotate_roofs_labelme.py --export

  All steps at once (synthetic data, no API key needed):
      python scripts/annotate_roofs_labelme.py --full --source synthetic

LabelMe tips
------------
  - Press 'a' to create a polygon for roof_boundary
  - Label the main roof area as 'roof_boundary' first
  - Label each obstacle separately (ac_unit, water_tank, chimney, etc.)
  - Save (Ctrl+S) before moving to next image
  - You can edit existing polygons by clicking the label
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

DATASET_ROOT  = os.path.join(PROJECT_ROOT, 'datasets', 'egyptian_roofs')
ANNOTATIONS   = os.path.join(DATASET_ROOT, 'annotations')
RAW_IMAGES    = os.path.join(DATASET_ROOT, 'raw_images')

LABELME_LABELS = ','.join([
    'roof_boundary', 'chimney', 'ac_unit', 'water_tank',
    'satellite_dish', 'tree_shadow', 'vent', 'shade_structure',
])


# ─────────────────────────────────────────────────────────────────────────────

def cmd_download(args) -> None:
    """Download satellite images for annotation."""
    from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator

    creator = YOLODatasetCreator(dataset_root=DATASET_ROOT)
    creator.create_dataset_structure()

    logger.info("Downloading %d images using source='%s'…", args.n, args.source)
    n = creator.download_sample_roofs(
        n_samples=args.n,
        source=args.source,
        zoom=args.zoom,
        image_size=args.size,
    )
    logger.info("✅ Downloaded %d images to %s", n, RAW_IMAGES)

    if args.source == 'synthetic':
        # Also generate labelled synthetic pairs for immediate training
        logger.info("Generating %d synthetic labelled pairs…", n)
        n_train = int(n * 0.8)
        n_val   = n - n_train
        creator.generate_synthetic_annotations(n_train, split='train')
        creator.generate_synthetic_annotations(n_val,   split='val')
        logger.info("✅ Synthetic dataset ready — skip annotation step and go straight to training!")


def cmd_annotate(args) -> None:
    """Launch LabelMe GUI for manual annotation."""
    os.makedirs(ANNOTATIONS, exist_ok=True)

    # Check LabelMe is installed
    try:
        subprocess.run(['labelme', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n❌ LabelMe not installed.")
        print("   Install with:  pip install labelme")
        print("   Then re-run:   python scripts/annotate_roofs_labelme.py --annotate")
        sys.exit(1)

    logger.info("Opening LabelMe… annotate at least 50 images for good results.")
    logger.info("Save each image before moving to the next (Ctrl+S).")

    cmd = [
        'labelme',
        RAW_IMAGES,
        '--output', ANNOTATIONS,
        '--labels', LABELME_LABELS,
        '--autosave',
        '--nodata',   # don't embed image in JSON (keeps files small)
    ]
    logger.info("Command: %s", ' '.join(cmd))
    subprocess.run(cmd)


def cmd_export(args) -> None:
    """Convert LabelMe JSON annotations → YOLO format and split train/val."""
    from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator

    creator = YOLODatasetCreator(dataset_root=DATASET_ROOT)
    creator.create_dataset_structure()

    if not os.path.isdir(ANNOTATIONS) or not list(Path(ANNOTATIONS).glob('*.json')):
        print("⚠️  No annotation files found in:", ANNOTATIONS)
        print("   Run --annotate first.")
        return

    # Export all JSON → YOLO .txt (put everything in train first, then split)
    n = creator.export_all_labelme(ANNOTATIONS)
    logger.info("Exported %d label files.", n)

    # Copy corresponding images and split train/val
    ann_dir = Path(ANNOTATIONS)
    img_src = Path(RAW_IMAGES)

    json_files = sorted(ann_dir.glob('*.json'))
    random.Random(42).shuffle(json_files)
    n_val = max(1, int(len(json_files) * 0.20))

    for i, jf in enumerate(json_files):
        split    = 'val' if i < n_val else 'train'
        img_name = jf.stem + '.jpg'
        src_img  = img_src / img_name

        if src_img.exists():
            dst = Path(DATASET_ROOT) / 'images' / split / img_name
            import shutil
            shutil.copy2(str(src_img), str(dst))

        # Move label to correct split
        lbl_src = Path(DATASET_ROOT) / 'labels' / 'train' / (jf.stem + '.txt')
        if lbl_src.exists() and split == 'val':
            lbl_dst = Path(DATASET_ROOT) / 'labels' / 'val' / lbl_src.name
            lbl_src.rename(lbl_dst)

    # Print stats
    stats = creator.get_stats()
    print("\n✅ Dataset export complete!")
    print(f"   Train: {stats['train']['n_images']} images, {stats['train']['n_labels']} labels")
    print(f"   Val  : {stats['val']['n_images']} images, {stats['val']['n_labels']} labels")
    print(f"\n   Class distribution (train):")
    for cls, cnt in stats['train']['class_counts'].items():
        print(f"     {cls:<20} {cnt}")
    print(f"\n   Next step: python scripts/train_yolov8_roof.py")


def cmd_stats(args) -> None:
    """Print dataset statistics."""
    from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator
    creator = YOLODatasetCreator(dataset_root=DATASET_ROOT)
    stats   = creator.get_stats()
    for split, s in stats.items():
        print(f"\n  {split.upper()}: {s['n_images']} images, {s['n_labels']} labels")
        for cls, cnt in s['class_counts'].items():
            bar = '█' * cnt
            print(f"    {cls:<22} {cnt:4d}  {bar}")


def cmd_full(args) -> None:
    """Full pipeline: download synthetic + generate labels (no API key needed)."""
    args.source = 'synthetic'
    args.n      = getattr(args, 'n', 200)
    cmd_download(args)
    logger.info("✅ Full synthetic dataset ready.")
    logger.info("   Next: python scripts/train_yolov8_roof.py --epochs 50 --device cpu")


# ─────────────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description='Egyptian Roofs Dataset — download, annotate, and export.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--download',  action='store_true', help='Download satellite images')
    p.add_argument('--annotate',  action='store_true', help='Launch LabelMe GUI')
    p.add_argument('--export',    action='store_true', help='Export annotations to YOLO format')
    p.add_argument('--stats',     action='store_true', help='Print dataset statistics')
    p.add_argument('--full',      action='store_true', help='Full synthetic pipeline (no API key)')

    p.add_argument('--n',      type=int,   default=200, help='Number of images to download')
    p.add_argument('--source', type=str,   default='synthetic',
                   choices=['google', 'mapbox', 'osm', 'synthetic'],
                   help='Image source (default: synthetic)')
    p.add_argument('--zoom',   type=int,   default=19,  help='Map zoom level')
    p.add_argument('--size',   type=int,   default=640, help='Image size in pixels')

    args = p.parse_args()

    if args.full:
        cmd_full(args)
    elif args.download:
        cmd_download(args)
    elif args.annotate:
        cmd_annotate(args)
    elif args.export:
        cmd_export(args)
    elif args.stats:
        cmd_stats(args)
    else:
        p.print_help()
        print("\n  Quick start (no API key needed):")
        print("    python scripts/annotate_roofs_labelme.py --full")


if __name__ == '__main__':
    main()
