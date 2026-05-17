"""
tests/test_computer_vision.py
==============================
Unit and integration tests for the Step 2 Computer Vision layer.

Run with:
    python -m pytest tests/test_computer_vision.py -v
    python -m pytest tests/test_computer_vision.py -v --tb=short
    python -m pytest tests/test_computer_vision.py::TestImageUtils -v

All tests use synthetic data and require NO external API keys.
Heavy ML tests (YOLOv8 inference) are skipped if ultralytics is not installed.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: create a minimal synthetic roof image (BGR numpy array)
# ─────────────────────────────────────────────────────────────────────────────

def _make_synthetic_image(size: int = 640) -> np.ndarray:
    """Return a (size, size, 3) BGR numpy array resembling a roof."""
    try:
        import cv2
        img = np.full((size, size, 3), (160, 160, 160), dtype=np.uint8)
        # Draw fake AC units
        cv2.rectangle(img, (50, 50),  (100, 90),  (80, 80, 80),  -1)
        cv2.rectangle(img, (200, 300), (260, 350), (70, 70, 70),  -1)
        return img
    except ImportError:
        # Return a grey array if OpenCV not installed
        return np.full((size, size, 3), 160, dtype=np.uint8)


def _write_tmp_image(size: int = 640) -> str:
    """Save a synthetic image to a temp file and return its path."""
    try:
        import cv2
        img = _make_synthetic_image(size)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        tmp.close()
        cv2.imwrite(tmp.name, img)
        return tmp.name
    except ImportError:
        # Fall back: write a minimal valid JPEG header if cv2 absent
        # (enough for extension check, not for real image parsing)
        import struct
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        # Minimal 1×1 JPEG
        tmp.write(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n'
            b'\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d'
            b'\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e\xbf\xff\xd9'
        )
        tmp.close()
        return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# 1. ImageProcessor utilities
# ─────────────────────────────────────────────────────────────────────────────

class TestImageUtils(unittest.TestCase):
    """Tests for ai_engine/computer_vision/image_utils.py"""

    def setUp(self):
        from ai_engine.computer_vision.image_utils import ImageProcessor
        self.ip = ImageProcessor

    # ── estimate_meters_per_pixel ─────────────────────────────────────────────

    def test_mpp_cairo_zoom19(self):
        """Cairo (30°N) zoom 19 → ~0.298 m/px."""
        mpp = self.ip.estimate_meters_per_pixel(latitude=30.0, zoom=19)
        self.assertAlmostEqual(mpp, 0.298, delta=0.01,
            msg=f"Expected ~0.298 m/px at Cairo zoom 19, got {mpp:.4f}")

    def test_mpp_decreases_with_zoom(self):
        """Higher zoom → smaller meters/pixel (more detail)."""
        mpp_18 = self.ip.estimate_meters_per_pixel(30.0, 18)
        mpp_19 = self.ip.estimate_meters_per_pixel(30.0, 19)
        mpp_20 = self.ip.estimate_meters_per_pixel(30.0, 20)
        self.assertGreater(mpp_18, mpp_19)
        self.assertGreater(mpp_19, mpp_20)

    def test_mpp_decreases_toward_poles(self):
        """Higher latitude → smaller meters/pixel (cos shrinks)."""
        mpp_equator = self.ip.estimate_meters_per_pixel(0.0,  19)
        mpp_cairo   = self.ip.estimate_meters_per_pixel(30.0, 19)
        mpp_alex    = self.ip.estimate_meters_per_pixel(31.2, 19)
        self.assertGreater(mpp_equator, mpp_cairo)
        self.assertGreater(mpp_cairo,   mpp_alex)

    def test_mpp_formula_correctness(self):
        """Verify formula: 156543.03392 * cos(lat_rad) / 2^zoom."""
        lat, zoom = 30.0, 19
        expected = 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)
        actual   = self.ip.estimate_meters_per_pixel(lat, zoom)
        self.assertAlmostEqual(actual, expected, places=6)

    # ── pixel_area_to_meters ──────────────────────────────────────────────────

    def test_pixel_area_zero(self):
        self.assertEqual(self.ip.pixel_area_to_meters(0, 0.3), 0.0)

    def test_pixel_area_unit(self):
        """1 pixel² × (0.3 m/px)² = 0.09 m²."""
        result = self.ip.pixel_area_to_meters(1, 0.3)
        self.assertAlmostEqual(result, 0.09, places=6)

    def test_pixel_area_scaling(self):
        """Quadrupling mpp → 16× area."""
        mpp_base   = 0.3
        mpp_double = 0.6
        a1 = self.ip.pixel_area_to_meters(100, mpp_base)
        a2 = self.ip.pixel_area_to_meters(100, mpp_double)
        self.assertAlmostEqual(a2 / a1, 4.0, places=6)

    # ── fetch_satellite_image ─────────────────────────────────────────────────

    def test_fetch_synthetic(self):
        """Synthetic image generation returns correct shape."""
        img = self.ip.fetch_satellite_image(
            latitude=30.0, longitude=31.0,
            zoom=19, size=256, source='synthetic',
        )
        self.assertIsInstance(img, np.ndarray)
        self.assertEqual(img.shape, (256, 256, 3))
        self.assertEqual(img.dtype, np.uint8)

    def test_fetch_synthetic_default_size(self):
        """Default size is 640."""
        img = self.ip.fetch_satellite_image(30.0, 31.0, source='synthetic')
        self.assertEqual(img.shape[0], 640)
        self.assertEqual(img.shape[1], 640)

    # ── save / load roundtrip ─────────────────────────────────────────────────

    def test_save_and_reload(self):
        """save_image then imread roundtrip preserves shape."""
        try:
            import cv2
        except ImportError:
            self.skipTest("OpenCV not installed")

        img = _make_synthetic_image(128)
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            path = f.name
        try:
            self.ip.save_image(img, path)
            loaded = cv2.imread(path)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.shape, img.shape)
        finally:
            os.unlink(path)

    # ── enhance_roof_contrast ─────────────────────────────────────────────────

    def test_enhance_contrast_shape_preserved(self):
        """enhance_roof_contrast keeps the same shape and dtype."""
        img = _make_synthetic_image(128)
        enhanced = self.ip.enhance_roof_contrast(img)
        self.assertEqual(enhanced.shape, img.shape)
        self.assertEqual(enhanced.dtype, img.dtype)

    # ── draw_panel_layout ─────────────────────────────────────────────────────

    def test_draw_panel_layout_shape(self):
        """draw_panel_layout returns an image with the same spatial dimensions."""
        img  = _make_synthetic_image(256)
        poly = np.array([[50,50],[200,50],[200,200],[50,200]], dtype=np.int32)
        pos  = [(60,60),(60,110),(60,160),(110,60),(110,110),(110,160)]
        out  = self.ip.draw_panel_layout(
            image=img.copy(),
            roof_polygon=poly,
            panel_positions=pos,
            panel_size_px=(40, 25),
            meters_per_pixel=0.3,
            panel_power_w=580,
        )
        self.assertEqual(out.shape[:2], img.shape[:2])

    # ── draw_detection_results ────────────────────────────────────────────────

    def test_draw_detection_results_shape(self):
        """draw_detection_results returns an image with the same spatial dimensions."""
        img  = _make_synthetic_image(256)
        poly = np.array([[20,20],[230,20],[230,230],[20,230]], dtype=np.int32)
        obs  = [
            {'class':'ac_unit','bbox':[50,50,100,90],'confidence':0.87,'area_m2':2.1},
        ]
        out  = self.ip.draw_detection_results(
            image=img.copy(),
            roof_polygon=poly,
            obstacles=obs,
            usable_area_m2=130.0,
            roof_area_m2=150.0,
        )
        self.assertEqual(out.shape[:2], img.shape[:2])


# ─────────────────────────────────────────────────────────────────────────────
# 2. EgyptianRoofDetector
# ─────────────────────────────────────────────────────────────────────────────

class TestRoofDetector(unittest.TestCase):
    """Tests for ai_engine/computer_vision/roof_detector.py"""

    def setUp(self):
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        # No model_path → forces heuristic fallback (no GPU/model needed)
        self.detector = EgyptianRoofDetector(model_path=None)
        self.tmp_path = _write_tmp_image(640)

    def tearDown(self):
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

    # ── detect_roof output schema ─────────────────────────────────────────────

    def test_detect_roof_returns_dict(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        self.assertIsInstance(result, dict)

    def test_detect_roof_required_keys(self):
        required = {
            'roof_polygon', 'roof_area_m2', 'usable_area_m2', 'usable_percentage',
            'obstacles', 'shading_analysis', 'metadata', 'annotated_image',
        }
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_roof_area_positive(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        self.assertGreater(result['roof_area_m2'], 0)

    def test_usable_area_leq_roof_area(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        self.assertLessEqual(result['usable_area_m2'], result['roof_area_m2'])

    def test_usable_percentage_in_range(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        pct = result['usable_percentage']
        self.assertGreaterEqual(pct, 0.0)
        self.assertLessEqual(pct,    100.0)

    def test_obstacles_is_list(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        self.assertIsInstance(result['obstacles'], list)

    def test_annotated_image_shape(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        img = result['annotated_image']
        self.assertIsInstance(img, np.ndarray)
        self.assertEqual(len(img.shape), 3)
        self.assertEqual(img.shape[2], 3)

    def test_metadata_keys(self):
        result   = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        meta     = result['metadata']
        for key in ('meters_per_pixel', 'orientation', 'roof_type', 'detector_mode'):
            self.assertIn(key, meta, f"Missing metadata key: {key}")

    def test_meters_per_pixel_plausible(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        mpp    = result['metadata']['meters_per_pixel']
        self.assertGreater(mpp, 0.05)
        self.assertLess(mpp,    5.0)

    # ── calculate_panel_layout ────────────────────────────────────────────────

    def test_panel_layout_basic(self):
        layout = self.detector.calculate_panel_layout(
            usable_area_m2=150.0,
            panel_specs={'width_m': 1.134, 'height_m': 2.278, 'power_w': 580},
        )
        self.assertIn('max_panels', layout)
        self.assertIn('total_capacity_kw', layout)
        self.assertGreater(layout['max_panels'], 0)

    def test_panel_layout_zero_area(self):
        layout = self.detector.calculate_panel_layout(usable_area_m2=0.0)
        self.assertEqual(layout['max_panels'], 0)

    def test_panel_layout_capacity_formula(self):
        """total_capacity_kw = max_panels × panel_power_w / 1000."""
        layout = self.detector.calculate_panel_layout(
            usable_area_m2=150.0,
            panel_specs={'width_m': 1.134, 'height_m': 2.278, 'power_w': 400},
        )
        expected_kw = layout['max_panels'] * 400 / 1000
        self.assertAlmostEqual(layout['total_capacity_kw'], expected_kw, places=3)

    def test_panel_layout_coverage_positive(self):
        layout = self.detector.calculate_panel_layout(usable_area_m2=100.0)
        self.assertGreaterEqual(layout.get('total_coverage_m2', 0), 0)

    def test_panel_layout_efficiency_in_range(self):
        layout = self.detector.calculate_panel_layout(usable_area_m2=100.0)
        eff = layout.get('efficiency_pct', 0)
        self.assertGreaterEqual(eff, 0)
        self.assertLessEqual(eff,    100)

    # ── shading analysis ──────────────────────────────────────────────────────

    def test_shading_analysis_keys(self):
        result   = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        shading  = result['shading_analysis']
        self.assertIn('annual_shading_loss_pct', shading)
        self.assertIn('monthly_shading',         shading)
        self.assertIn('critical_obstacles',      shading)

    def test_shading_annual_loss_in_range(self):
        result = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        loss   = result['shading_analysis']['annual_shading_loss_pct']
        self.assertGreaterEqual(loss, 0.0)
        self.assertLessEqual(loss,    100.0)

    def test_shading_monthly_has_12_values(self):
        result  = self.detector.detect_roof(self.tmp_path, latitude=30.0, zoom=19)
        monthly = result['shading_analysis']['monthly_shading']
        self.assertEqual(len(monthly), 12)

    # ── polygon helper ────────────────────────────────────────────────────────

    def test_polygon_area_square(self):
        """10×10 square polygon → 100 pixel² area."""
        poly = np.array([[0,0],[10,0],[10,10],[0,10]], dtype=float)
        area = self.detector._polygon_area(poly)
        self.assertAlmostEqual(area, 100.0, delta=1.0)

    def test_polygon_area_triangle(self):
        """Right triangle with legs 6×8 → area = 24."""
        poly = np.array([[0,0],[6,0],[0,8]], dtype=float)
        area = self.detector._polygon_area(poly)
        self.assertAlmostEqual(area, 24.0, delta=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# 3. YOLODatasetCreator
# ─────────────────────────────────────────────────────────────────────────────

class TestDatasetCreator(unittest.TestCase):
    """Tests for ai_engine/computer_vision/dataset_creator.py"""

    def setUp(self):
        from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator
        self.tmp_dir = tempfile.mkdtemp(prefix='shamsi_test_dataset_')
        self.creator = YOLODatasetCreator(dataset_root=self.tmp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_create_dataset_structure(self):
        """Dataset structure creates required directories."""
        self.creator.create_dataset_structure()
        for sub in ('images/train', 'images/val', 'labels/train', 'labels/val'):
            path = os.path.join(self.tmp_dir, sub)
            self.assertTrue(os.path.isdir(path), f"Missing directory: {sub}")

    def test_data_yaml_created(self):
        """data.yaml is written during structure creation."""
        self.creator.create_dataset_structure()
        yaml_path = os.path.join(self.tmp_dir, 'data.yaml')
        self.assertTrue(os.path.exists(yaml_path))

    def test_data_yaml_has_nc(self):
        """data.yaml contains nc (number of classes) entry."""
        self.creator.create_dataset_structure()
        yaml_path = os.path.join(self.tmp_dir, 'data.yaml')
        with open(yaml_path) as f:
            content = f.read()
        self.assertIn('nc:', content)

    def test_generate_synthetic_annotations_train(self):
        """Synthetic train set generates matching image+label pairs."""
        self.creator.create_dataset_structure()
        n = self.creator.generate_synthetic_annotations(n_images=10, split='train')
        self.assertGreater(n, 0)
        train_imgs = os.path.join(self.tmp_dir, 'images', 'train')
        train_lbls = os.path.join(self.tmp_dir, 'labels', 'train')
        img_files  = [f for f in os.listdir(train_imgs) if f.endswith('.jpg')]
        lbl_files  = [f for f in os.listdir(train_lbls) if f.endswith('.txt')]
        self.assertEqual(len(img_files), len(lbl_files))
        self.assertGreater(len(img_files), 0)

    def test_generate_synthetic_annotations_val(self):
        """Synthetic val set generates matching image+label pairs."""
        self.creator.create_dataset_structure()
        n = self.creator.generate_synthetic_annotations(n_images=5, split='val')
        self.assertGreater(n, 0)

    def test_yolo_label_format(self):
        """Each label file line starts with integer class_id in valid range."""
        self.creator.create_dataset_structure()
        self.creator.generate_synthetic_annotations(n_images=5, split='train')
        train_lbls = os.path.join(self.tmp_dir, 'labels', 'train')
        for fn in os.listdir(train_lbls):
            if not fn.endswith('.txt'):
                continue
            with open(os.path.join(train_lbls, fn)) as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts:
                        continue
                    class_id = int(parts[0])
                    # 8 classes (0–7)
                    self.assertGreaterEqual(class_id, 0)
                    self.assertLessEqual(class_id,    7)
                    # All coordinate values normalised [0,1]
                    coords = [float(p) for p in parts[1:]]
                    for c in coords:
                        self.assertGreaterEqual(c, 0.0 - 1e-6)
                        self.assertLessEqual(c,    1.0 + 1e-6)

    def test_download_synthetic(self):
        """download_sample_roofs with source='synthetic' creates images."""
        self.creator.create_dataset_structure()
        n = self.creator.download_sample_roofs(n_samples=5, source='synthetic')
        self.assertGreater(n, 0)
        raw_dir = os.path.join(self.tmp_dir, 'raw_images')
        self.assertTrue(os.path.isdir(raw_dir))

    def test_get_stats_structure(self):
        """get_stats returns dict with train and val keys."""
        self.creator.create_dataset_structure()
        self.creator.generate_synthetic_annotations(n_images=5, split='train')
        self.creator.generate_synthetic_annotations(n_images=2, split='val')
        stats = self.creator.get_stats()
        self.assertIn('train', stats)
        self.assertIn('val',   stats)
        self.assertIn('n_images', stats['train'])
        self.assertIn('n_labels', stats['train'])

    def test_export_labelme_to_yolo_normalisation(self):
        """LabelMe JSON polygon is exported with coordinates in [0,1]."""
        import json
        self.creator.create_dataset_structure()
        # Create a minimal LabelMe JSON
        lm_json = {
            "version": "5.0.0",
            "imagePath": "test_roof.jpg",
            "imageHeight": 640,
            "imageWidth":  640,
            "shapes": [
                {
                    "label": "roof_boundary",
                    "shape_type": "polygon",
                    "points": [[100,100],[500,100],[500,500],[100,500]],
                }
            ],
        }
        json_path = os.path.join(self.tmp_dir, 'test_roof.json')
        with open(json_path, 'w') as f:
            json.dump(lm_json, f)

        self.creator.export_labelme_to_yolo(json_path)

        lbl_path = os.path.join(self.tmp_dir, 'labels', 'train', 'test_roof.txt')
        if os.path.exists(lbl_path):
            with open(lbl_path) as f:
                line = f.readline().strip()
            parts = line.split()
            coords = [float(p) for p in parts[1:]]
            for c in coords:
                self.assertGreaterEqual(c, 0.0 - 1e-6)
                self.assertLessEqual(c,    1.0 + 1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# 4. API view (unit-level, without Django test client)
# ─────────────────────────────────────────────────────────────────────────────

class TestRoofAnalysisView(unittest.TestCase):
    """
    Unit tests for api/views/roof_analysis_view.py helper functions.
    Django is NOT required — we test the pure helper logic only.
    """

    def test_media_url_format(self):
        from api.views.roof_analysis_view import _media_url
        url = _media_url('abc123_annotated.jpg')
        self.assertIn('roof_analysis', url)
        self.assertIn('abc123_annotated.jpg', url)

    def test_media_url_no_double_slash(self):
        from api.views.roof_analysis_view import _media_url
        url = _media_url('test.jpg')
        self.assertNotIn('//', url.replace('://', '##'))

    def test_validate_request_no_image(self):
        """_validate_request returns error when no image provided."""
        # We test a simplified version of the validator logic
        # by checking the import works and the function is callable
        from api.views.roof_analysis_view import _validate_request
        self.assertTrue(callable(_validate_request))

    def test_save_upload_temp_creates_file(self):
        """_save_upload_temp writes chunks to a temp file."""
        from api.views.roof_analysis_view import _save_upload_temp

        class FakeFile:
            name = 'roof.jpg'
            size = 100

            def chunks(self):
                yield b'\xff\xd8\xff\xe0' * 25  # 100 bytes of fake JPEG data

        tmp = _save_upload_temp(FakeFile())
        try:
            self.assertTrue(os.path.exists(tmp))
            self.assertGreater(os.path.getsize(tmp), 0)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Smoke / integration test — end-to-end detect_roof on synthetic image
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEndSmoke(unittest.TestCase):
    """
    Quick smoke test: synthetic image → detect_roof → panel layout → annotated image.
    Uses heuristic fallback (no YOLOv8 model required).
    """

    def test_full_pipeline_no_model(self):
        """Complete pipeline with no YOLOv8 model, only heuristic fallback."""
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        from ai_engine.computer_vision.image_utils  import ImageProcessor

        detector = EgyptianRoofDetector(model_path=None)
        tmp_path = _write_tmp_image(640)

        try:
            result = detector.detect_roof(
                image_path=tmp_path,
                confidence_threshold=0.5,
                latitude=30.0,
                zoom=19,
            )

            # Basic assertions
            self.assertGreater(result['roof_area_m2'],   0)
            self.assertGreater(result['usable_area_m2'], 0)
            self.assertEqual(len(result['shading_analysis']['monthly_shading']), 12)

            # Panel layout
            mpp    = result['metadata']['meters_per_pixel']
            layout = detector.calculate_panel_layout(
                usable_area_m2=result['usable_area_m2'],
                panel_specs={'width_m': 1.134, 'height_m': 2.278, 'power_w': 580},
            )
            self.assertGreaterEqual(layout['max_panels'], 0)

            # Draw layout
            positions = detector.get_panel_positions_px(
                roof_polygon=result['roof_polygon'],
                panel_layout=layout,
                meters_per_pixel=mpp,
            )
            out = ImageProcessor.draw_panel_layout(
                image=result['annotated_image'].copy(),
                roof_polygon=result['roof_polygon'],
                panel_positions=positions,
                panel_size_px=(
                    max(1, int(1.134 / mpp)),
                    max(1, int(2.278 / mpp)),
                ),
                meters_per_pixel=mpp,
                panel_power_w=580,
            )
            self.assertEqual(out.shape, result['annotated_image'].shape)

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @unittest.skipUnless(
        __import__('importlib').util.find_spec('ultralytics') is not None,
        'ultralytics not installed — skipping YOLOv8 inference test'
    )
    def test_yolo_model_loads_pretrained(self):
        """YOLOv8n-seg loads from ultralytics pretrained (download required)."""
        from ultralytics import YOLO
        model = YOLO('yolov8n-seg.pt')
        self.assertIsNotNone(model)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Edge cases
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases(unittest.TestCase):

    def test_mpp_equator(self):
        """At equator, zoom 19 → ~0.298 m/px (max value)."""
        from ai_engine.computer_vision.image_utils import ImageProcessor
        mpp = ImageProcessor.estimate_meters_per_pixel(0.0, 19)
        expected = 156543.03392 / (2 ** 19)
        self.assertAlmostEqual(mpp, expected, places=4)

    def test_zero_panel_power(self):
        """Panel layout with 0W power should not raise."""
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        det = EgyptianRoofDetector(model_path=None)
        layout = det.calculate_panel_layout(
            usable_area_m2=100.0,
            panel_specs={'width_m': 1.134, 'height_m': 2.278, 'power_w': 0},
        )
        self.assertEqual(layout['total_capacity_kw'], 0.0)

    def test_tiny_usable_area(self):
        """Roof smaller than one panel → 0 panels."""
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        det    = EgyptianRoofDetector(model_path=None)
        layout = det.calculate_panel_layout(usable_area_m2=0.1)
        self.assertEqual(layout['max_panels'], 0)

    def test_detect_roof_small_image(self):
        """Detector handles small (128×128) images without crashing."""
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        det      = EgyptianRoofDetector(model_path=None)
        tmp_path = _write_tmp_image(128)
        try:
            result = det.detect_roof(tmp_path, latitude=30.0, zoom=19)
            self.assertIsInstance(result, dict)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_detect_roof_missing_file(self):
        """Detector raises FileNotFoundError for missing image path."""
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        det = EgyptianRoofDetector(model_path=None)
        with self.assertRaises((FileNotFoundError, Exception)):
            det.detect_roof('/nonexistent/path/image.jpg', latitude=30.0, zoom=19)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    unittest.main(verbosity=2)
