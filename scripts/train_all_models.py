"""
scripts/train_all_models.py
============================
Shamsi Smart — Master AI Training Orchestrator

Trains all four AI models in sequence:
  1. Random Forest   → ai_engine/models/yield_predictor.pkl
  2. K-Means         → ai_engine/models/dust_clusterer.pkl
  3. CNN-LSTM        → ai_engine/models/cnn_lstm_best.pth
  4. YOLOv8          → ai_engine/models/roof_detector_best.pt

Usage
-----
    # Full training with --synthetic (no database needed):
    python scripts/train_all_models.py --synthetic

    # Full training from real database:
    python scripts/train_all_models.py

    # Train only specific models:
    python scripts/train_all_models.py --synthetic --only rf kmeans

    # Full training with GPU for deep learning models:
    python scripts/train_all_models.py --synthetic --gpu

    # Quick smoke-test (reduced epochs):
    python scripts/train_all_models.py --synthetic --quick

Arguments
---------
    --synthetic     Use synthetic data (no database required)
    --gpu           Enable CUDA for CNN-LSTM and YOLOv8
    --quick         Reduced epochs for testing (CNN-LSTM: 5, YOLO: 3)
    --only          Space-separated list of models to train: rf kmeans cnn_lstm yolo
    --epochs-lstm   Epochs for CNN-LSTM (default: 100)
    --epochs-yolo   Epochs for YOLOv8 (default: 50)
    --batch-size    Batch size for CNN-LSTM (default: 32)
    --skip-plots    Skip generating training plots
    --output-dir    Directory for results (default: results/)

Output
------
    ai_engine/models/
        yield_predictor.pkl
        dust_clusterer.pkl
        cnn_lstm_best.pth
        roof_detector_best.pt

    results/
        training_report.json
        cnn_lstm_loss_curve.png
        yolo_metrics/

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Load .env from project root (must happen before any DB access) ────────────
try:
    from dotenv import load_dotenv as _load_dotenv
    _env_path = Path(__file__).parent.parent / '.env'
    _load_dotenv(dotenv_path=_env_path if _env_path.exists() else None)
except ImportError:
    pass  # python-dotenv not installed; rely on env vars already set

from typing import Dict, List, Optional

# ── Progress bars ─────────────────────────────────────────────────────────────
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Minimal fallback
    class tqdm:  # noqa: N801
        def __init__(self, iterable=None, total=None, desc='', **kwargs):
            self._iter = iterable
            self._total = total
            self._desc = desc
            self._n = 0
        def __iter__(self):
            for item in (self._iter or []):
                self._n += 1
                yield item
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def update(self, n=1):
            self._n += n
        def set_postfix(self, **kwargs):
            pass
        def set_description(self, desc):
            self._desc = desc
        def close(self):
            pass

# ── Project root setup ────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

MODELS_DIR  = os.path.join(PROJECT_ROOT, 'ai_engine', 'models')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Railway internal hostname detection
# postgresql://...@postgres.railway.internal:5432/railway
# is ONLY reachable from within Railway's private network (i.e. a running
# Railway service or GitHub Actions with Railway's RAILWAY_ENVIRONMENT set).
# Running this script on a local Windows machine or Colab will time-out when
# trying to connect with the internal hostname.
# ─────────────────────────────────────────────────────────────────────────────

_RAILWAY_INTERNAL_HOST = 'postgres.railway.internal'
_DB_URL = os.environ.get('DATABASE_URL', '')

def _check_railway_connectivity() -> None:
    """
    Warn the user if DATABASE_URL points to Railway's private network
    but the script is not running inside Railway.

    Detection logic:
      - If RAILWAY_ENVIRONMENT is set → we are inside Railway → OK.
      - If DATABASE_URL contains 'railway.internal' and
        RAILWAY_ENVIRONMENT is not set → warn and offer the public proxy URL.
    """
    in_railway = bool(os.environ.get('RAILWAY_ENVIRONMENT'))
    uses_internal = _RAILWAY_INTERNAL_HOST in _DB_URL

    if uses_internal and not in_railway:
        print(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║  ⚠️  Railway Internal Hostname Detected — External Warning   ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  DATABASE_URL uses:  postgres.railway.internal               ║\n"
            "║  This hostname is ONLY reachable from inside Railway's       ║\n"
            "║  private network. Connecting from a local machine will       ║\n"
            "║  time out (typically after 30 seconds).                      ║\n"
            "║                                                              ║\n"
            "║  Solutions:                                                  ║\n"
            "║  1. Use the PUBLIC proxy URL from your Railway dashboard:    ║\n"
            "║     Dashboard → your PostgreSQL service → Connect tab        ║\n"
            "║     Copy 'Public URL' (contains .railway.app:NNNNN)         ║\n"
            "║     Set:  DATABASE_URL=postgresql://postgres:<pass>@...      ║\n"
            "║                                                              ║\n"
            "║  2. Train with --synthetic (no database needed):             ║\n"
            "║     python scripts/train_all_models.py --synthetic           ║\n"
            "║                                                              ║\n"
            "║  3. Deploy this script as a Railway service and run it       ║\n"
            "║     inside Railway's private network.                        ║\n"
            "╚══════════════════════════════════════════════════════════════╝\n"
        )
        logger.warning(
            "DATABASE_URL uses Railway internal hostname — "
            "connection will fail outside Railway. "
            "Use --synthetic or switch to the public proxy URL."
        )


# ═════════════════════════════════════════════════════════════════════════════
# Argument parsing
# ═════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description='Shamsi Smart — Train all AI models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument('--synthetic',    action='store_true',
                   help='Use synthetic data (no database required)')
    p.add_argument('--gpu',          action='store_true',
                   help='Use CUDA GPU for deep learning models')
    p.add_argument('--quick',        action='store_true',
                   help='Quick test: few epochs only')
    p.add_argument('--only',         nargs='+',
                   choices=['rf', 'kmeans', 'cnn_lstm', 'yolo'],
                   help='Train only the listed models')
    p.add_argument('--epochs-lstm',  type=int, default=100,
                   help='Max epochs for CNN-LSTM (default: 100)')
    p.add_argument('--epochs-yolo',  type=int, default=50,
                   help='Max epochs for YOLOv8 (default: 50)')
    p.add_argument('--batch-size',   type=int, default=32,
                   help='Batch size for CNN-LSTM (default: 32)')
    p.add_argument('--skip-plots',   action='store_true',
                   help='Skip generating training plots')
    p.add_argument('--output-dir',   type=str, default=RESULTS_DIR,
                   help='Root directory for results (default: results/)')
    return p.parse_args()


# ═════════════════════════════════════════════════════════════════════════════
# Django setup (optional — only needed for real-data mode)
# ═════════════════════════════════════════════════════════════════════════════

def setup_django() -> bool:
    """Attempt to initialise Django. Returns True if successful."""
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'shamsi_smart.settings'
    try:
        import django
        django.setup()
        return True
    except Exception as exc:
        logger.warning("Django not available (%s) — switching to --synthetic mode.", exc)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Model 1 — Random Forest
# ═════════════════════════════════════════════════════════════════════════════

def train_random_forest(args, report: Dict) -> bool:
    """Train Random Forest yield predictor and save to models/yield_predictor.pkl."""
    print("\n" + "─" * 60)
    print("  [1/4] Random Forest — Solar Yield Predictor")
    print("─" * 60)
    t0 = time.time()

    try:
        from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2

        predictor = EgyptianYieldPredictorV2()

        if args.synthetic:
            metrics = predictor.train_from_synthetic_data(verbose=True)
        else:
            metrics = predictor.train_and_save()

        elapsed = time.time() - t0
        report['random_forest'] = {
            'status':          'success',
            'training_time_s': round(elapsed, 1),
            'metrics':         metrics,
            'model_path':      os.path.join(MODELS_DIR, 'yield_predictor.pkl'),
        }
        print(f"\n  ✅ Random Forest trained in {elapsed:.1f}s")
        print(f"     Test R²  : {metrics.get('test_r2', 0):.4f}")
        print(f"     Test MAPE: {metrics.get('test_mape', 0):.2f}%")
        return True

    except Exception as exc:
        logger.error("Random Forest training failed: %s", exc, exc_info=True)
        report['random_forest'] = {'status': 'failed', 'error': str(exc)}
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Model 2 — K-Means Dust Clusterer
# ═════════════════════════════════════════════════════════════════════════════

def train_kmeans(args, report: Dict) -> bool:
    """Train K-Means dust zone clusterer and save to models/dust_clusterer.pkl."""
    print("\n" + "─" * 60)
    print("  [2/4] K-Means — Dust Zone Clusterer")
    print("─" * 60)
    t0 = time.time()

    try:
        from ai_engine.dust_clustering import EgyptianDustClusterer

        clusterer = EgyptianDustClusterer()

        if args.synthetic:
            success, metrics = clusterer.train_from_synthetic_data(verbose=True)
        else:
            success = clusterer.train_and_save()
            metrics = {}

        elapsed = time.time() - t0

        if success:
            report['kmeans'] = {
                'status':          'success',
                'training_time_s': round(elapsed, 1),
                'metrics':         metrics,
                'model_path':      os.path.join(MODELS_DIR, 'dust_clusterer.pkl'),
            }
            print(f"\n  ✅ K-Means trained in {elapsed:.1f}s")
            if metrics:
                print(f"     Inertia    : {metrics.get('inertia', 0):.2f}")
                print(f"     Silhouette : {metrics.get('silhouette_score', 0):.4f}")
        else:
            report['kmeans'] = {'status': 'failed', 'error': 'train() returned False'}
        return success

    except Exception as exc:
        logger.error("K-Means training failed: %s", exc, exc_info=True)
        report['kmeans'] = {'status': 'failed', 'error': str(exc)}
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Model 3 — CNN-LSTM
# ═════════════════════════════════════════════════════════════════════════════

def train_cnn_lstm(args, report: Dict) -> bool:
    """Train CNN-LSTM time-series predictor."""
    print("\n" + "─" * 60)
    print("  [3/4] CNN-LSTM — Deep Learning Yield Predictor")
    print("─" * 60)
    t0 = time.time()

    try:
        # Build argument namespace for the subprocess-style train() function
        class _Args:
            synthetic   = args.synthetic
            gpu         = args.gpu
            epochs      = 5 if args.quick else args.epochs_lstm
            batch_size  = args.batch_size
            lr          = 1e-3
            no_plots    = args.skip_plots
            patience    = 10

        # Import and run the training function directly
        import importlib.util, types

        script_path = os.path.join(PROJECT_ROOT, 'scripts', 'train_cnn_lstm.py')
        spec = importlib.util.spec_from_file_location('train_cnn_lstm', script_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        cnn_args = _Args()
        # Replicate the argparse Namespace structure expected by train()
        import argparse as _ap
        ns = _ap.Namespace(
            epochs     = cnn_args.epochs,
            batch_size = cnn_args.batch_size,
            lr         = cnn_args.lr,
            gpu        = cnn_args.gpu,
            synthetic  = cnn_args.synthetic,
            no_plots   = cnn_args.no_plots,
            patience   = cnn_args.patience,
        )

        # Fix attribute name: train() uses args.batch_size
        ns.batch_size = cnn_args.batch_size

        metrics = mod.train(ns)
        elapsed = time.time() - t0

        # Copy best model to ai_engine/models/
        src = os.path.join(PROJECT_ROOT, 'results', 'step1', 'models', 'cnn_lstm_best.pth')
        dst = os.path.join(MODELS_DIR, 'cnn_lstm_best.pth')
        if os.path.exists(src):
            import shutil
            os.makedirs(MODELS_DIR, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info("Copied cnn_lstm_best.pth → %s", dst)

        report['cnn_lstm'] = {
            'status':          'success',
            'training_time_s': round(elapsed, 1),
            'metrics':         metrics,
            'model_path':      dst,
        }
        print(f"\n  ✅ CNN-LSTM trained in {elapsed:.1f}s")
        print(f"     Test MAPE: {metrics.get('test_mape', 0):.2f}%")
        print(f"     Test R²  : {metrics.get('test_r2', 0):.4f}")
        return True

    except Exception as exc:
        logger.error("CNN-LSTM training failed: %s", exc, exc_info=True)
        report['cnn_lstm'] = {'status': 'failed', 'error': str(exc)}
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Model 4 — YOLOv8
# ═════════════════════════════════════════════════════════════════════════════

def train_yolov8(args, report: Dict) -> bool:
    """Train YOLOv8 roof detector."""
    print("\n" + "─" * 60)
    print("  [4/4] YOLOv8 — Egyptian Roof Detector")
    print("─" * 60)
    t0 = time.time()

    try:
        import importlib.util

        script_path = os.path.join(PROJECT_ROOT, 'scripts', 'train_yolov8_roof.py')
        spec = importlib.util.spec_from_file_location('train_yolov8_roof', script_path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        import argparse as _ap
        ns = _ap.Namespace(
            data      = os.path.join(PROJECT_ROOT, 'datasets', 'egyptian_roofs', 'data.yaml'),
            weights   = 'yolov8n-seg.pt',
            epochs    = 3 if args.quick else args.epochs_yolo,
            batch     = 16,
            imgsz     = 640,
            device    = '0' if args.gpu else 'cpu',
            resume    = None,
            name      = 'egyptian_roofs',
            patience  = 20,
            workers   = 0,
            copy_best = True,
            synthetic = args.synthetic,
        )

        # Generate synthetic dataset if needed
        if args.synthetic:
            _ensure_synthetic_yolo_dataset()

        metrics = mod.train_roof_detector(ns)
        elapsed = time.time() - t0

        report['yolov8'] = {
            'status':          'success',
            'training_time_s': round(elapsed, 1),
            'metrics':         metrics,
            'model_path':      os.path.join(MODELS_DIR, 'roof_detector_best.pt'),
        }
        print(f"\n  ✅ YOLOv8 trained in {elapsed:.1f}s")
        return True

    except Exception as exc:
        logger.error("YOLOv8 training failed: %s", exc, exc_info=True)
        report['yolov8'] = {'status': 'failed', 'error': str(exc)}
        return False


def _ensure_synthetic_yolo_dataset():
    """Create synthetic YOLO dataset if it doesn't already exist."""
    from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator

    dataset_root = os.path.join(PROJECT_ROOT, 'datasets', 'egyptian_roofs')
    train_dir    = os.path.join(dataset_root, 'images', 'train')

    # Check if dataset already present
    if (os.path.isdir(train_dir) and
            len(list(Path(train_dir).glob('*.jpg'))) >= 100):
        logger.info("YOLO dataset already exists — skipping generation.")
        return

    logger.info("Generating synthetic YOLO dataset…")
    creator = YOLODatasetCreator(dataset_root=dataset_root)
    creator.create_dataset_structure()
    creator.generate_synthetic_roof_dataset(
        n_train=160,
        n_val=40,
        image_size=640,
    )
    logger.info("Synthetic YOLO dataset ready at %s", dataset_root)


# ═════════════════════════════════════════════════════════════════════════════
# Report generation
# ═════════════════════════════════════════════════════════════════════════════

def save_report(report: Dict, output_dir: str) -> str:
    """Save training report as JSON and print summary table."""
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, 'training_report.json')

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  SHAMSI SMART — TRAINING SUMMARY")
    print("═" * 65)
    print(f"  {'Model':<22} {'Status':<10} {'Time (s)':<12} {'Key Metric'}")
    print("  " + "─" * 61)

    model_info = {
        'random_forest': ('Random Forest',  'test_r2',    'R²'),
        'kmeans':        ('K-Means',         'silhouette_score', 'Silhouette'),
        'cnn_lstm':      ('CNN-LSTM',         'test_mape',  'MAPE%'),
        'yolov8':        ('YOLOv8',           'box_map50',  'mAP50'),
    }

    all_ok = True
    for key, (name, metric_key, metric_label) in model_info.items():
        entry = report.get(key, {})
        status = entry.get('status', 'skipped')
        t_str  = f"{entry.get('training_time_s', 0):.1f}s" if status == 'success' else '—'
        m_val  = entry.get('metrics', {}).get(metric_key)
        m_str  = f"{metric_label}={m_val:.4f}" if m_val is not None else '—'
        icon   = '✅' if status == 'success' else ('⏭' if status == 'skipped' else '❌')
        print(f"  {name:<22} {icon} {status:<8} {t_str:<12} {m_str}")
        if status == 'failed':
            all_ok = False

    print("═" * 65)
    total = report.get('total_time_s', 0)
    print(f"  Total training time: {total:.1f}s  ({total/60:.1f} min)")
    print(f"  Report saved: {report_path}")
    print("═" * 65)

    return report_path


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()

    # Check Railway internal hostname connectivity before attempting DB access
    if not args.synthetic:
        _check_railway_connectivity()

    # Override epochs in quick mode
    if args.quick:
        args.epochs_lstm = 5
        args.epochs_yolo = 3
        logger.info("Quick mode: CNN-LSTM epochs=%d  YOLO epochs=%d",
                    args.epochs_lstm, args.epochs_yolo)

    # Determine which models to train
    all_models = ['rf', 'kmeans', 'cnn_lstm', 'yolo']
    to_train   = set(args.only) if args.only else set(all_models)

    # Setup Django if needed
    django_ok = False
    if not args.synthetic:
        django_ok = setup_django()
        if not django_ok:
            logger.warning("Falling back to --synthetic mode.")
            args.synthetic = True

    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    # ── Print header ──────────────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  SHAMSI SMART — AI Training Pipeline")
    print("═" * 65)
    print(f"  Date       : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Data mode  : {'Synthetic' if args.synthetic else 'Database'}")
    print(f"  GPU        : {args.gpu}")
    print(f"  Models     : {', '.join(sorted(to_train))}")
    print(f"  Quick mode : {args.quick}")
    print("═" * 65)

    report: Dict = {
        'timestamp':  datetime.now().isoformat(),
        'synthetic':  args.synthetic,
        'gpu':        args.gpu,
        'quick_mode': args.quick,
    }

    # ── Progress bar over pipeline stages ────────────────────────────────────
    pipeline_steps = []
    if 'rf'       in to_train: pipeline_steps.append(('rf',       'Random Forest'))
    if 'kmeans'   in to_train: pipeline_steps.append(('kmeans',   'K-Means'))
    if 'cnn_lstm' in to_train: pipeline_steps.append(('cnn_lstm', 'CNN-LSTM'))
    if 'yolo'     in to_train: pipeline_steps.append(('yolo',     'YOLOv8'))

    t_global_start = time.time()

    with tqdm(total=len(pipeline_steps), desc='Overall progress',
              unit='model', position=0) as pbar:

        for model_key, model_name in pipeline_steps:
            pbar.set_description(f'Training {model_name}')

            if model_key == 'rf':
                train_random_forest(args, report)
            elif model_key == 'kmeans':
                train_kmeans(args, report)
            elif model_key == 'cnn_lstm':
                train_cnn_lstm(args, report)
            elif model_key == 'yolo':
                train_yolov8(args, report)

            pbar.update(1)

    report['total_time_s'] = round(time.time() - t_global_start, 1)

    # ── Save report ───────────────────────────────────────────────────────────
    report_path = save_report(report, args.output_dir)

    # Mark models not trained as skipped
    for m in all_models:
        key = {'rf': 'random_forest', 'kmeans': 'kmeans',
               'cnn_lstm': 'cnn_lstm', 'yolo': 'yolo'}[m]
        if key not in report:
            report[key] = {'status': 'skipped'}

    # ── Print final summary ───────────────────────────────────────────────────
    print("\n" + "═" * 65)
    print("  Shamsi Smart — Training Complete")
    print("═" * 65)
    for m in all_models:
        key = {'rf': 'random_forest', 'kmeans': 'kmeans',
               'cnn_lstm': 'cnn_lstm', 'yolo': 'yolo'}[m]
        r   = report.get(key, {})
        status = r.get('status', 'skipped')
        icon   = '✅' if status == 'success' else ('❌' if status == 'failed' else '⏭️ ')
        print(f"  {icon}  {key:<16}  {status}")
    print(f"\n  Total time : {report['total_time_s']:.1f}s")
    print(f"  Report     : {report_path}")
    print("\n  Next: python scripts/verify_trained_models.py --verbose")


if __name__ == '__main__':
    main()
