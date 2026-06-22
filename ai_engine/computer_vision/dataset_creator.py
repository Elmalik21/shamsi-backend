"""
ai_engine/computer_vision/dataset_creator.py
==============================================
YOLO-format dataset creation tools for the Egyptian Roofs Dataset (ERD).

Creates and manages the training dataset for YOLOv8 roof segmentation.

Directory structure produced
----------------------------
    datasets/egyptian_roofs/
    ├── images/
    │   ├── train/   (80% of images)
    │   └── val/     (20% of images)
    ├── labels/
    │   ├── train/   (YOLO-format .txt per image)
    │   └── val/
    ├── data.yaml    (YOLOv8 training config)
    └── raw_images/  (downloaded originals, before train/val split)

YOLO segmentation label format (one line per instance):
    class_id  x1 y1 x2 y2 x3 y3 ... xN yN
    All coordinates normalised to [0, 1] relative to image size.

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CLASSES = [
    'roof_boundary',     # 0
    'chimney',           # 1
    'ac_unit',           # 2
    'water_tank',        # 3
    'satellite_dish',    # 4
    'tree_shadow',       # 5
    'vent',              # 6
    'shade_structure',   # 7
]

# 125 Egyptian locations with diverse architectural styles
EGYPTIAN_LOCATIONS: List[Dict] = [
    # Cairo governorate — dense urban, many flat concrete roofs
    {'name': 'Cairo_Downtown',    'lat': 30.0444, 'lon': 31.2357, 'count': 15},
    {'name': 'Cairo_Nasr_City',   'lat': 30.0626, 'lon': 31.3469, 'count': 12},
    {'name': 'Cairo_Heliopolis',  'lat': 30.0866, 'lon': 31.3218, 'count': 10},
    {'name': 'Cairo_Maadi',       'lat': 29.9597, 'lon': 31.2580, 'count': 10},
    {'name': 'Cairo_Zamalek',     'lat': 30.0626, 'lon': 31.2217, 'count': 8},
    # Giza
    {'name': 'Giza_6_October',    'lat': 29.9285, 'lon': 30.9305, 'count': 10},
    {'name': 'Giza_Haram',        'lat': 30.0131, 'lon': 31.2089, 'count': 8},
    # Alexandria — coastal, different building styles
    {'name': 'Alexandria_Sidi_Bishr', 'lat': 31.2479, 'lon': 29.9935, 'count': 12},
    {'name': 'Alexandria_Montaza',    'lat': 31.2832, 'lon': 30.0151, 'count': 8},
    # Delta region
    {'name': 'Mansoura',          'lat': 31.0409, 'lon': 31.3785, 'count': 8},
    {'name': 'Tanta',             'lat': 30.7865, 'lon': 31.0004, 'count': 8},
    {'name': 'Zagazig',           'lat': 30.5877, 'lon': 31.5021, 'count': 6},
    # Upper Egypt — highest solar potential
    {'name': 'Assiut',            'lat': 27.1810, 'lon': 31.1837, 'count': 8},
    {'name': 'Luxor',             'lat': 25.6872, 'lon': 32.6396, 'count': 8},
    {'name': 'Aswan',             'lat': 24.0889, 'lon': 32.8998, 'count': 8},
    {'name': 'Sohag',             'lat': 26.5569, 'lon': 31.6948, 'count': 6},
    # Red Sea — villas, resort style
    {'name': 'Hurghada',          'lat': 27.2579, 'lon': 33.8116, 'count': 8},
    {'name': 'Sharm_El_Sheikh',   'lat': 27.9158, 'lon': 34.3300, 'count': 6},
    # Suez Canal region
    {'name': 'Port_Said',         'lat': 31.2565, 'lon': 32.2841, 'count': 6},
    {'name': 'Ismailia',          'lat': 30.5965, 'lon': 32.2715, 'count': 6},
]


# ─────────────────────────────────────────────────────────────────────────────

class YOLODatasetCreator:
    """
    Create and manage the YOLO-format Egyptian Roofs Dataset.

    Parameters
    ----------
    dataset_root : str  Root directory for the dataset
    val_split    : float  Fraction of images for validation (default 0.20)
    """

    def __init__(
        self,
        dataset_root: str = 'datasets/egyptian_roofs',
        val_split: float = 0.20,
    ):
        self.root      = Path(dataset_root)
        self.val_split = val_split
        self.classes   = CLASSES

    # ── Directory setup ───────────────────────────────────────────────────────

    def create_dataset_structure(self) -> None:
        """Create all required directories and write data.yaml."""
        for split in ['train', 'val']:
            (self.root / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.root / 'labels' / split).mkdir(parents=True, exist_ok=True)
        (self.root / 'raw_images').mkdir(parents=True, exist_ok=True)

        self._write_data_yaml()
        logger.info("Dataset structure created at %s", self.root)

    def _write_data_yaml(self) -> None:
        """Write the YOLOv8 data.yaml configuration file."""
        try:
            import yaml
        except ImportError:
            # Fallback: write manually
            self._write_data_yaml_manual()
            return

        config = {
            'path':  str(self.root.absolute()),
            'train': 'images/train',
            'val':   'images/val',
            'nc':    len(self.classes),
            'names': self.classes,
            # Egyptian building metadata
            'description': 'Egyptian Roofs Dataset (ERD) — flat concrete roofs',
            'version':     '1.0',
            'author':      'Shamsi Smart AI Team',
        }
        with open(self.root / 'data.yaml', 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        logger.info("data.yaml written.")

    def _write_data_yaml_manual(self) -> None:
        """Write data.yaml without PyYAML dependency."""
        lines = [
            f"path: {self.root.absolute()}",
            "train: images/train",
            "val: images/val",
            f"nc: {len(self.classes)}",
            "names:",
        ]
        for cls in self.classes:
            lines.append(f"  - {cls}")
        with open(self.root / 'data.yaml', 'w') as f:
            f.write('\n'.join(lines) + '\n')

    # ── Image downloading ─────────────────────────────────────────────────────

    def download_sample_roofs(
        self,
        locations: Optional[List[Dict]] = None,
        n_samples: int = 200,
        source: str = 'synthetic',
        zoom: int = 19,
        image_size: int = 640,
    ) -> int:
        """
        Download (or generate) satellite images for Egyptian locations.

        Parameters
        ----------
        locations  : list of location dicts (default: EGYPTIAN_LOCATIONS)
        n_samples  : total images to acquire
        source     : 'google' | 'mapbox' | 'synthetic' (default: synthetic)
        zoom       : map zoom level
        image_size : output image size in pixels

        Returns
        -------
        int  Number of images successfully acquired
        """
        from ai_engine.computer_vision.image_utils import ImageProcessor

        locs      = locations or EGYPTIAN_LOCATIONS
        raw_dir   = self.root / 'raw_images'
        raw_dir.mkdir(parents=True, exist_ok=True)

        rng       = random.Random(42)
        acquired  = 0
        per_loc   = max(1, n_samples // len(locs))

        for loc in locs:
            count = min(loc.get('count', per_loc), n_samples - acquired)
            for i in range(count):
                # Small random offset for geographic variety
                lat = loc['lat'] + (rng.random() - 0.5) * 0.008
                lon = loc['lon'] + (rng.random() - 0.5) * 0.008

                fname = f"{loc['name']}_{i:03d}.jpg"
                fpath = raw_dir / fname

                if fpath.exists():
                    acquired += 1
                    continue

                try:
                    img = ImageProcessor.fetch_satellite_image(
                        latitude=lat, longitude=lon,
                        zoom=zoom, size=image_size,
                        source=source,
                    )
                    ImageProcessor.save_image(img, str(fpath))
                    acquired += 1
                    if acquired % 20 == 0:
                        logger.info("Downloaded %d/%d images…", acquired, n_samples)
                except Exception as exc:
                    logger.warning("Could not fetch %s: %s", fname, exc)

                if acquired >= n_samples:
                    break
            if acquired >= n_samples:
                break

        logger.info("Acquired %d images to %s", acquired, raw_dir)
        return acquired

    # ── Train/val split ───────────────────────────────────────────────────────

    def split_raw_to_train_val(self, seed: int = 42) -> Tuple[int, int]:
        """
        Shuffle raw_images/ and split into train/ and val/ directories.

        Returns
        -------
        (n_train, n_val)  Images moved to each split.
        """
        raw_dir = self.root / 'raw_images'
        images  = sorted(raw_dir.glob('*.jpg')) + sorted(raw_dir.glob('*.png'))

        rng = random.Random(seed)
        rng.shuffle(images)

        n_val   = max(1, int(len(images) * self.val_split))
        val_set = set(str(p) for p in images[:n_val])

        n_train = n_val_count = 0
        for img_path in images:
            split  = 'val' if str(img_path) in val_set else 'train'
            dst    = self.root / 'images' / split / img_path.name
            shutil.copy2(str(img_path), str(dst))
            if split == 'train':
                n_train += 1
            else:
                n_val_count += 1

        logger.info("Split: %d train / %d val", n_train, n_val_count)
        return n_train, n_val_count

    # ── Annotation conversion ─────────────────────────────────────────────────

    def export_labelme_to_yolo(
        self,
        labelme_json_path: str,
        output_dir: Optional[str] = None,
    ) -> bool:
        """
        Convert a LabelMe JSON annotation file to YOLO segmentation format.

        LabelMe polygon format:
            {"shapes": [{"label": "roof_boundary", "points": [[x, y], ...]}]}

        YOLO segmentation format:
            class_id  x1_norm y1_norm x2_norm y2_norm ...

        Parameters
        ----------
        labelme_json_path : str  Path to LabelMe .json file
        output_dir        : str  Where to write the .txt file (default: labels/train/)

        Returns
        -------
        bool  True if conversion succeeded
        """
        try:
            with open(labelme_json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.error("Cannot read LabelMe JSON %s: %s", labelme_json_path, exc)
            return False

        img_w = data.get('imageWidth',  640)
        img_h = data.get('imageHeight', 640)

        lines = []
        for shape in data.get('shapes', []):
            label  = shape.get('label', '')
            points = shape.get('points', [])

            if label not in self.classes:
                logger.warning("Unknown label '%s' — skipping.", label)
                continue
            if len(points) < 3:
                continue

            cls_id = self.classes.index(label)
            # Normalise coordinates to [0, 1]
            norm_pts = []
            for x, y in points:
                norm_pts.extend([
                    round(max(0.0, min(1.0, x / img_w)), 6),
                    round(max(0.0, min(1.0, y / img_h)), 6),
                ])

            lines.append(f"{cls_id} " + " ".join(map(str, norm_pts)))

        if not lines:
            logger.warning("No valid annotations in %s", labelme_json_path)
            return False

        # Output path: same name as JSON, .txt extension
        json_p    = Path(labelme_json_path)
        out_dir_p = Path(output_dir) if output_dir else (self.root / 'labels' / 'train')
        out_dir_p.mkdir(parents=True, exist_ok=True)
        out_path  = out_dir_p / (json_p.stem + '.txt')

        with open(out_path, 'w') as f:
            f.write('\n'.join(lines) + '\n')

        logger.debug("Exported %d annotations → %s", len(lines), out_path)
        return True

    def export_all_labelme(
        self,
        annotation_dir: str,
        output_dir: Optional[str] = None,
    ) -> int:
        """
        Convert all LabelMe JSON files in a directory to YOLO format.

        Returns number of successfully converted files.
        """
        ann_dir = Path(annotation_dir)
        n_ok    = 0
        for json_file in sorted(ann_dir.glob('*.json')):
            if self.export_labelme_to_yolo(str(json_file), output_dir):
                n_ok += 1
        logger.info("Exported %d annotation files.", n_ok)
        return n_ok

    # ── Synthetic annotations ─────────────────────────────────────────────────

    def generate_synthetic_annotations(
        self,
        n_images: int = 50,
        image_size: int = 640,
        split: str = 'train',
    ) -> int:
        """
        Generate synthetic training images WITH ground-truth YOLO labels.

        Useful for initial model testing without any manual annotation.
        Creates plausible Egyptian flat-roof scenes with known obstacle positions.

        Parameters
        ----------
        n_images   : int   Number of image/label pairs to create
        image_size : int   Image resolution
        split      : str   'train' or 'val'

        Returns
        -------
        int  Number of pairs created
        """
        from ai_engine.computer_vision.image_utils import ImageProcessor

        img_dir = self.root / 'images' / split
        lbl_dir = self.root / 'labels' / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        rng = random.Random(99)
        s   = image_size

        for i in range(n_images):
            # ── Generate synthetic image ──────────────────────────────────────
            img = ImageProcessor._synthetic_roof_image(s)

            # ── Roof boundary polygon (with random padding) ───────────────────
            pad = int(s * rng.uniform(0.08, 0.15))
            roof_pts = [
                [pad, pad], [s - pad, pad],
                [s - pad, s - pad], [pad, s - pad],
            ]

            # ── Random obstacles ──────────────────────────────────────────────
            obstacles_yolo = []
            n_obs = rng.randint(1, 4)
            for _ in range(n_obs):
                cls_id = rng.choice([1, 2, 3, 4, 6])   # exclude tree/shade
                ow = int(s * rng.uniform(0.05, 0.12))
                oh = int(s * rng.uniform(0.04, 0.10))
                ox = rng.randint(pad + 10, s - pad - ow - 10)
                oy = rng.randint(pad + 10, s - pad - oh - 10)
                pts = [
                    [ox, oy], [ox + ow, oy],
                    [ox + ow, oy + oh], [ox, oy + oh],
                ]
                obstacles_yolo.append((cls_id, pts))

            # ── Write YOLO label file ─────────────────────────────────────────
            lines = []
            # Roof boundary — class 0
            lines.append(self._pts_to_yolo_line(0, roof_pts, s, s))
            # Obstacles
            for cls_id, pts in obstacles_yolo:
                lines.append(self._pts_to_yolo_line(cls_id, pts, s, s))

            img_path = img_dir / f'synthetic_{i:04d}.jpg'
            lbl_path = lbl_dir / f'synthetic_{i:04d}.txt'

            ImageProcessor.save_image(img, str(img_path))
            with open(lbl_path, 'w') as f:
                f.write('\n'.join(lines) + '\n')

        logger.info("Generated %d synthetic pairs in %s/", n_images, split)
        return n_images

    @staticmethod
    def _pts_to_yolo_line(
        cls_id: int,
        points: List[List[float]],
        img_w: int,
        img_h: int,
    ) -> str:
        """Convert polygon points to a YOLO segmentation label line."""
        norm = []
        for x, y in points:
            norm.extend([
                round(max(0.0, min(1.0, x / img_w)), 6),
                round(max(0.0, min(1.0, y / img_h)), 6),
            ])
        return f"{cls_id} " + " ".join(map(str, norm))

    # ── Synthetic full dataset generator ─────────────────────────────────────

    def generate_synthetic_roof_dataset(
        self,
        n_train: int = 160,
        n_val: int = 40,
        image_size: int = 640,
        seed: int = 42,
    ) -> Dict:
        """
        Generate a complete synthetic Egyptian roof dataset ready for YOLOv8.

        Creates n_train + n_val synthetic satellite-style roof images with
        YOLO segmentation labels covering all 8 roof classes.

        Returns dict with n_train, n_val, dataset_root, classes, image_size.
        """
        try:
            from tqdm import tqdm as _tqdm
            _have_tqdm = True
        except ImportError:
            _have_tqdm = False

        self.create_dataset_structure()

        rng    = random.Random(seed)
        np_rng = np.random.default_rng(seed)
        s      = image_size
        obstacle_classes = [1, 2, 3, 4, 6]

        def _make_image_array(roof_pts, placed_boxes, tree_pts):
            import cv2
            # Background
            base_r = rng.randint(80, 130)
            img = np.full((s, s, 3), [base_r, base_r, base_r], dtype=np.uint8)
            
            # Roof
            roof_pts_np = np.array(roof_pts, dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(img, [roof_pts_np], (rng.randint(150, 180), rng.randint(150, 180), rng.randint(150, 180)))
            
            # Obstacles (Seamless Cloning)
            for box in placed_boxes:
                x1, y1, x2, y2 = box
                w_box, h_box = x2 - x1, y2 - y1
                if w_box < 5 or h_box < 5: 
                    continue
                
                obs_color = (rng.randint(50, 100), rng.randint(50, 100), rng.randint(50, 100))
                src = np.full((h_box, w_box, 3), obs_color, dtype=np.uint8)
                
                # Add texture to obstacle
                noise_src = np_rng.integers(-15, 15, size=(h_box, w_box, 3))
                src = np.clip(src.astype(int) + noise_src, 0, 255).astype(np.uint8)
                
                mask = np.full((h_box, w_box), 255, dtype=np.uint8)
                center = (x1 + w_box // 2, y1 + h_box // 2)
                
                try:
                    # Poisson Blending (NORMAL_CLONE) to adapt to roof lighting
                    img = cv2.seamlessClone(src, img, mask, center, cv2.NORMAL_CLONE)
                except cv2.error:
                    cv2.rectangle(img, (x1, y1), (x2, y2), obs_color, -1)
                
            # Tree Shadows (Alpha Blending for translucent effect)
            if tree_pts:
                tree_pts_np = np.array(tree_pts, dtype=np.int32).reshape((-1, 1, 2))
                tree_layer = img.copy()
                cv2.fillPoly(tree_layer, [tree_pts_np], (rng.randint(0, 50), rng.randint(80, 120), rng.randint(0, 50)))
                cv2.addWeighted(tree_layer, 0.6, img, 0.4, 0, img)

            # Global Optics simulation (Blur)
            img = cv2.GaussianBlur(img, (3, 3), 0)
            noise = np_rng.integers(-8, 8, size=(s, s, 3))
            return np.clip(img.astype(int) + noise, 0, 255).astype(np.uint8)

        def _save_jpeg(img_array, path):
            try:
                from PIL import Image as _PIL
                _PIL.fromarray(img_array).save(str(path), quality=90)
            except ImportError:
                with open(path, 'wb') as f:
                    f.write(f"P6\n{s} {s}\n255\n".encode())
                    f.write(img_array.tobytes())

        def _generate_pair(split, idx):
            img_dir = self.root / 'images' / split
            lbl_dir = self.root / 'labels' / split
            pad = int(s * rng.uniform(0.07, 0.14))
            jitter = int(s * 0.03)

            def _jit():
                return rng.randint(-jitter, jitter)

            roof_pts = [
                [max(0, min(s-1, pad + _jit())),     max(0, min(s-1, pad + _jit()))],
                [max(0, min(s-1, s-pad + _jit())),   max(0, min(s-1, pad + _jit()))],
                [max(0, min(s-1, s-pad + _jit())),   max(0, min(s-1, s-pad + _jit()))],
                [max(0, min(s-1, pad + _jit())),     max(0, min(s-1, s-pad + _jit()))],
            ]

            n_obs = rng.randint(1, 5)
            obstacle_lines = []
            placed_boxes = []

            for _ in range(n_obs * 3):
                if len(obstacle_lines) >= n_obs:
                    break
                cls_id = rng.choice(obstacle_classes)
                ow = int(s * rng.uniform(0.04, 0.13))
                oh = int(s * rng.uniform(0.04, 0.10))
                ox = rng.randint(pad + 5, max(pad + 6, s - pad - ow - 5))
                oy = rng.randint(pad + 5, max(pad + 6, s - pad - oh - 5))
                box = (ox, oy, ox + ow, oy + oh)
                if any(not (box[2] < pb[0] or box[0] > pb[2] or
                            box[3] < pb[1] or box[1] > pb[3])
                       for pb in placed_boxes):
                    continue
                placed_boxes.append(box)
                obs_pts = [[ox, oy], [ox+ow, oy], [ox+ow, oy+oh], [ox, oy+oh]]
                obstacle_lines.append(self._pts_to_yolo_line(cls_id, obs_pts, s, s))

            if rng.random() < 0.3:
                cx = rng.randint(pad + 20, s - pad - 20)
                cy = rng.randint(pad + 20, s - pad - 20)
                r_tree = int(s * rng.uniform(0.05, 0.10))
                n_pts  = rng.randint(5, 9)
                tree_pts = []
                for k in range(n_pts):
                    angle  = 2 * math.pi * k / n_pts
                    r_vary = r_tree * rng.uniform(0.7, 1.3)
                    tree_pts.append([
                        max(0, min(s-1, int(cx + r_vary * math.cos(angle)))),
                        max(0, min(s-1, int(cy + r_vary * math.sin(angle)))),
                    ])
                obstacle_lines.append(self._pts_to_yolo_line(5, tree_pts, s, s))

            lines = [self._pts_to_yolo_line(0, roof_pts, s, s)] + obstacle_lines
            img_fname = f'synthetic_{split}_{idx:04d}.jpg'
            lbl_fname = f'synthetic_{split}_{idx:04d}.txt'
            
            tree_pts_val = tree_pts if 'tree_pts' in locals() else []
            _save_jpeg(_make_image_array(roof_pts, placed_boxes, tree_pts_val), img_dir / img_fname)
            with open(lbl_dir / lbl_fname, 'w') as f:
                f.write('\n'.join(lines) + '\n')

        logger.info("Generating %d synthetic roof images (%d train / %d val)...",
                    n_train + n_val, n_train, n_val)

        train_iter = (_tqdm(range(n_train), desc='Train images', unit='img')
                      if _have_tqdm else range(n_train))
        for i in train_iter:
            _generate_pair('train', i)

        val_iter = (_tqdm(range(n_val), desc='Val images', unit='img')
                    if _have_tqdm else range(n_val))
        for i in val_iter:
            _generate_pair('val', i)

        logger.info("Synthetic YOLO dataset complete: %d train / %d val", n_train, n_val)
        return {
            'n_train':      n_train,
            'n_val':        n_val,
            'dataset_root': str(self.root.absolute()),
            'classes':      self.classes,
            'image_size':   image_size,
        }

    # ── Dataset statistics ────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """Report statistics about the current dataset."""
        stats: Dict = {'train': {}, 'val': {}}
        for split in ['train', 'val']:
            img_dir = self.root / 'images' / split
            lbl_dir = self.root / 'labels' / split
            n_images = (len(list(img_dir.glob('*.jpg'))) +
                        len(list(img_dir.glob('*.png'))))
            n_labels = len(list(lbl_dir.glob('*.txt')))

            class_counts = {cls: 0 for cls in self.classes}
            for txt in lbl_dir.glob('*.txt'):
                with open(txt) as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            try:
                                cls_id = int(parts[0])
                                if 0 <= cls_id < len(self.classes):
                                    class_counts[self.classes[cls_id]] += 1
                            except ValueError:
                                pass

            stats[split] = {
                'n_images':     n_images,
                'n_labels':     n_labels,
                'class_counts': class_counts,
            }
        return stats
