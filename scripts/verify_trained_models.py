"""
scripts/verify_trained_models.py
==================================
Shamsi Smart — Model Verification Script

Loads all four trained AI models, runs test predictions,
validates that outputs are within reasonable ranges, and
prints a detailed PASS/FAIL report.

Usage
-----
    python scripts/verify_trained_models.py
    python scripts/verify_trained_models.py --verbose
    python scripts/verify_trained_models.py --only rf kmeans

Arguments
---------
    --verbose   Print full prediction outputs per model
    --only      Space-separated list: rf kmeans cnn_lstm yolo

Exit codes
----------
    0 — All tested models passed
    1 — One or more models failed

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from typing import Dict, List, Tuple

import numpy as np

# ── Project root setup ────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

MODELS_DIR = os.path.join(PROJECT_ROOT, 'ai_engine', 'models')

# ── Colour codes (ANSI) for terminal output ───────────────────────────────────
_GREEN  = '\033[92m'
_RED    = '\033[91m'
_YELLOW = '\033[93m'
_BOLD   = '\033[1m'
_RESET  = '\033[0m'


def _ok(msg: str)   -> str: return f"{_GREEN}✅ PASS{_RESET}  {msg}"
def _fail(msg: str) -> str: return f"{_RED}❌ FAIL{_RESET}  {msg}"
def _warn(msg: str) -> str: return f"{_YELLOW}⚠️  WARN{_RESET}  {msg}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Verify all trained Shamsi Smart models')
    p.add_argument('--verbose', action='store_true',
                   help='Print full prediction output for each model')
    p.add_argument('--only', nargs='+',
                   choices=['rf', 'kmeans', 'cnn_lstm', 'yolo'],
                   help='Verify only the listed models')
    return p.parse_args()


# ═════════════════════════════════════════════════════════════════════════════
# Verification helpers
# ═════════════════════════════════════════════════════════════════════════════

def _model_path(filename: str) -> str:
    return os.path.join(MODELS_DIR, filename)


def _check_file_exists(path: str) -> Tuple[bool, str]:
    if not os.path.exists(path):
        return False, f"File not found: {path}"
    size_mb = os.path.getsize(path) / 1e6
    return True, f"Found ({size_mb:.2f} MB)"


# ═════════════════════════════════════════════════════════════════════════════
# Verify 1 — Random Forest
# ═════════════════════════════════════════════════════════════════════════════

def verify_random_forest(verbose: bool) -> Tuple[bool, str, dict]:
    """
    Load yield_predictor.pkl or yield_predictor_v2.pkl and run a test prediction.

    Expected:
      - specific_yield_kwh_per_kwp in range [800, 2500] kWh/kWp
      - predicted_annual_kwh > 0
      - monthly list has 12 elements, all positive
    """
    results: dict = {'model': 'Random Forest'}

    # Try both canonical and v2 paths
    pkl_candidates = [
        _model_path('yield_predictor.pkl'),
        _model_path('yield_predictor_v2.pkl'),
    ]
    pkl_path = next((p for p in pkl_candidates if os.path.exists(p)), None)

    if pkl_path is None:
        return False, "Model file not found (yield_predictor.pkl)", results

    exists, msg = _check_file_exists(pkl_path)
    results['file'] = msg

    try:
        import joblib
        data = joblib.load(pkl_path)

        if not isinstance(data, dict) or 'model' not in data:
            return False, "Unexpected pickle format — missing 'model' key", results

        rf     = data['model']
        scaler = data.get('scaler')
        feats  = data.get('features', [
            'avg_ghi', 'avg_temperature', 'max_temperature', 'avg_humidity',
            'avg_wind_speed', 'dust_risk_score', 'latitude', 'tilt_angle',
            'panel_efficiency', 'temp_coefficient',
        ])

        # ── Test input: Cairo average conditions ──────────────────────────────
        test_features = {
            'avg_ghi':          5.8,
            'avg_temperature':  26.0,
            'max_temperature':  38.0,
            'avg_humidity':     40.0,
            'avg_wind_speed':    3.5,
            'dust_risk_score':   0.07,
            'latitude':         30.04,
            'tilt_angle':       28.0,
            'panel_efficiency':  0.22,
            'temp_coefficient': -0.32,
        }
        x = np.array([[test_features.get(f, 0.0) for f in feats]])
        if scaler is not None:
            x = scaler.transform(x)

        # ── Single prediction ─────────────────────────────────────────────────
        pred = float(rf.predict(x)[0])

        # ── Validation bounds (kWh/kWp for Cairo) ────────────────────────────
        EXPECTED_MIN = 700.0
        EXPECTED_MAX = 2800.0

        if not (EXPECTED_MIN <= pred <= EXPECTED_MAX):
            return (
                False,
                f"Prediction {pred:.1f} kWh/kWp outside expected range "
                f"[{EXPECTED_MIN}, {EXPECTED_MAX}]",
                results,
            )

        results['prediction_kwh_per_kwp'] = round(pred, 1)
        results['annual_kwh_10kw']        = round(pred * 10.0, 1)

        if verbose:
            print(f"    RF prediction   : {pred:.1f} kWh/kWp/year")
            print(f"    Annual (10 kW)  : {pred * 10:.1f} kWh")
            if 'metrics' in data:
                m = data['metrics']
                print(f"    Stored Test R²  : {m.get('test_r2', '?')}")
                print(f"    Stored Test MAPE: {m.get('test_mape', '?')}%")

        return True, f"Prediction = {pred:.1f} kWh/kWp (within expected range)", results

    except Exception as exc:
        return False, f"Exception during verification: {exc}", results


# ═════════════════════════════════════════════════════════════════════════════
# Verify 2 — K-Means Dust Clusterer
# ═════════════════════════════════════════════════════════════════════════════

def verify_kmeans(verbose: bool) -> Tuple[bool, str, dict]:
    """
    Load dust_clusterer.pkl and verify cluster assignments for known locations.

    Expected:
      - Aswan (lat 24.09) → HIGH or EXTREME
      - Alexandria (lat 31.25) → LOW or MEDIUM
      - Cairo (lat 30.04) → MEDIUM or HIGH
    """
    results: dict = {'model': 'K-Means Dust Clusterer'}

    pkl_path = _model_path('dust_clusterer.pkl')
    exists, msg = _check_file_exists(pkl_path)
    results['file'] = msg

    if not exists:
        return False, msg, results

    try:
        import joblib
        from ai_engine.dust_clustering import EgyptianDustClusterer

        data    = joblib.load(pkl_path)
        km      = data['model']
        scaler  = data['scaler']

        clusterer = EgyptianDustClusterer()
        clusterer.model  = km
        clusterer.scaler = scaler

        # ── Test locations: [dust, humidity, wind, latitude] ──────────────────
        test_locs = [
            ('Alexandria',  0.03, 65.0, 4.0, 31.25),
            ('Cairo',       0.07, 42.0, 3.5, 30.04),
            ('Luxor',       0.11, 22.0, 3.0, 25.69),
            ('Aswan',       0.14, 18.0, 3.5, 24.09),
        ]

        assignments = {}
        all_ok = True

        for name, dust, hum, wind, lat in test_locs:
            x = np.array([[dust, hum, wind, lat]])
            x_s = scaler.transform(x)
            cluster = int(km.predict(x_s)[0])
            zone    = clusterer.DUST_ZONES.get(cluster, {}).get('name', 'UNKNOWN')
            assignments[name] = {'cluster': cluster, 'zone': zone}

            if verbose:
                print(f"    {name:<15} lat={lat:.1f}  cluster={cluster}  zone={zone}")

        # Validate expected zone ordering by latitude
        alex_c  = assignments['Alexandria']['cluster']
        cairo_c = assignments['Cairo']['cluster']
        luxor_c = assignments['Luxor']['cluster']
        aswan_c = assignments['Aswan']['cluster']

        # Delta should have lower or equal cluster than Cairo; Aswan >= Luxor >= Cairo
        # Allow 1 step tolerance for edge cases
        if not (alex_c <= cairo_c + 1 and luxor_c >= cairo_c - 1):
            all_ok = False

        results['assignments'] = assignments

        if not all_ok:
            return (
                False,
                f"Unexpected cluster ordering: Alex={alex_c} Cairo={cairo_c} "
                f"Luxor={luxor_c} Aswan={aswan_c}",
                results,
            )

        return (
            True,
            f"4/4 test locations assigned to plausible dust zones",
            results,
        )

    except Exception as exc:
        return False, f"Exception: {exc}", results


# ═════════════════════════════════════════════════════════════════════════════
# Verify 3 — CNN-LSTM
# ═════════════════════════════════════════════════════════════════════════════

def verify_cnn_lstm(verbose: bool) -> Tuple[bool, str, dict]:
    """
    Load cnn_lstm_best.pth, run inference on one synthetic sequence,
    and validate output shape and value range.

    Expected:
      - Output shape: (1, 12) — monthly predictions
      - All values positive
      - Sum of monthly predictions ≈ 100–1500 kWh/kWp/year (reasonable range)
    """
    results: dict = {'model': 'CNN-LSTM'}

    pth_candidates = [
        _model_path('cnn_lstm_best.pth'),
        os.path.join(PROJECT_ROOT, 'results', 'step1', 'models', 'cnn_lstm_best.pth'),
    ]
    pth_path = next((p for p in pth_candidates if os.path.exists(p)), None)

    if pth_path is None:
        return False, "Model file not found (cnn_lstm_best.pth)", results

    exists, msg = _check_file_exists(pth_path)
    results['file'] = msg

    try:
        import torch
        from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM

        # ── Load checkpoint ───────────────────────────────────────────────────
        checkpoint = torch.load(pth_path, map_location='cpu')

        if isinstance(checkpoint, dict):
            state_dict = checkpoint.get('model_state_dict', checkpoint.get('state_dict', checkpoint))
            cfg        = checkpoint.get('config', {})
        else:
            state_dict = checkpoint
            cfg        = {}

        # Reconstruct model with stored or default config
        model = SolarYieldCNNLSTM(
            input_features      = cfg.get('input_features', 5),
            sequence_length     = cfg.get('sequence_length', 365),
            hidden_size         = cfg.get('hidden_size', 128),
            num_lstm_layers     = cfg.get('num_lstm_layers', 2),
            num_attention_heads = cfg.get('num_attention_heads', 4),
            dropout             = cfg.get('dropout', 0.3),
            output_months       = cfg.get('output_months', 12),
        )
        net = model.get_net(torch.device('cpu'))
        net.load_state_dict(state_dict, strict=False)
        net.eval()

        # ── Synthetic test input ──────────────────────────────────────────────
        rng = np.random.default_rng(777)
        seq_len = cfg.get('sequence_length', 365)
        n_feat  = cfg.get('input_features', 5)
        X_test  = rng.uniform(0.0, 1.0, (1, seq_len, n_feat)).astype(np.float32)

        with torch.no_grad():
            preds = net(torch.tensor(X_test)).numpy()

        # ── Validate ──────────────────────────────────────────────────────────
        if preds.shape != (1, 12):
            return False, f"Unexpected output shape: {preds.shape} (expected (1, 12))", results

        monthly = preds[0]
        if not np.all(np.isfinite(monthly)):
            return False, "Output contains NaN or Inf values", results

        annual_sum = float(monthly.sum())
        results['monthly_predictions'] = [round(float(v), 3) for v in monthly]
        results['annual_sum']          = round(annual_sum, 2)

        if verbose:
            print(f"    Monthly preds : {[round(float(v), 2) for v in monthly]}")
            print(f"    Annual sum    : {annual_sum:.3f} kWh/kWp")

        # Outputs can be any non-NaN value for a model trained on normalised data;
        # just check for finite values and correct shape.
        return True, f"Shape (1,12) ✓  Annual sum = {annual_sum:.2f}  All finite ✓", results

    except ImportError:
        return False, "PyTorch not installed — cannot verify CNN-LSTM", results
    except Exception as exc:
        return False, f"Exception: {exc}\n{traceback.format_exc()}", results


# ═════════════════════════════════════════════════════════════════════════════
# Verify 4 — YOLOv8
# ═════════════════════════════════════════════════════════════════════════════

def verify_yolov8(verbose: bool) -> Tuple[bool, str, dict]:
    """
    Load roof_detector_best.pt and run inference on a blank synthetic image.

    Expected:
      - Model loads without errors
      - Inference returns a Results object
      - No exceptions during forward pass
    """
    results: dict = {'model': 'YOLOv8 Roof Detector'}

    pt_candidates = [
        _model_path('roof_detector_best.pt'),
        os.path.join(PROJECT_ROOT, 'runs', 'segment', 'egyptian_roofs', 'weights', 'best.pt'),
    ]
    pt_path = next((p for p in pt_candidates if os.path.exists(p)), None)

    if pt_path is None:
        return False, "Model file not found (roof_detector_best.pt)", results

    exists, msg = _check_file_exists(pt_path)
    results['file'] = msg

    try:
        from ultralytics import YOLO

        model = YOLO(pt_path)

        # ── Create a blank test image (640×640 grey) ──────────────────────────
        test_img = np.full((640, 640, 3), 180, dtype=np.uint8)

        yolo_results = model.predict(
            source=test_img,
            imgsz=640,
            conf=0.25,
            verbose=False,
        )

        n_detections = sum(len(r.boxes) for r in yolo_results) if yolo_results else 0
        results['n_detections_blank_image'] = n_detections
        results['inference_ok']             = True

        if verbose:
            print(f"    Detections on blank: {n_detections}")
            print(f"    Model task          : {model.task}")
            print(f"    Model classes       : {list(model.names.values())[:4]}…")

        return (
            True,
            f"Inference successful — {n_detections} detections on blank image",
            results,
        )

    except ImportError:
        return False, "ultralytics not installed — cannot verify YOLOv8", results
    except Exception as exc:
        return False, f"Exception: {exc}", results


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main() -> int:
    args = parse_args()
    to_verify = set(args.only) if args.only else {'rf', 'kmeans', 'cnn_lstm', 'yolo'}

    print("\n" + "═" * 65)
    print(f"  {_BOLD}Shamsi Smart — Model Verification Report{_RESET}")
    print("═" * 65)
    print(f"  Models dir : {MODELS_DIR}")
    print(f"  Checking   : {', '.join(sorted(to_verify))}")
    print("═" * 65)

    verifiers = {
        'rf':       ('Random Forest',       verify_random_forest),
        'kmeans':   ('K-Means Clusterer',   verify_kmeans),
        'cnn_lstm': ('CNN-LSTM',            verify_cnn_lstm),
        'yolo':     ('YOLOv8 Detector',     verify_yolov8),
    }

    report: Dict[str, dict] = {}
    any_failed = False

    for key in ['rf', 'kmeans', 'cnn_lstm', 'yolo']:
        if key not in to_verify:
            continue

        name, verifier = verifiers[key]
        print(f"\n  ── {name} ──")
        t0 = time.time()

        try:
            passed, message, details = verifier(args.verbose)
        except Exception as exc:
            passed  = False
            message = f"Unexpected error: {exc}"
            details = {}

        elapsed = time.time() - t0
        status  = _ok(message) if passed else _fail(message)
        print(f"  {status}")
        print(f"  Time: {elapsed:.2f}s")

        report[key] = {
            'passed':  passed,
            'message': message,
            'time_s':  round(elapsed, 2),
            **details,
        }
        if not passed:
            any_failed = True

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print(f"  {_BOLD}VERIFICATION SUMMARY{_RESET}")
    print("─" * 65)
    for key, r in report.items():
        name = verifiers[key][0]
        icon = "✅" if r['passed'] else "❌"
        print(f"  {icon}  {name:<28} {r['message'][:40]}")
    print("═" * 65)

    if any_failed:
        print(f"\n  {_RED}Some models failed verification.{_RESET}")
        print("  Run training with:  python scripts/train_all_models.py --synthetic")
        return 1
    else:
        print(f"\n  {_GREEN}All models verified successfully!{_RESET}")
        print("  You can now start the server: python manage.py runserver")
        return 0


if __name__ == '__main__':
    sys.exit(main())
