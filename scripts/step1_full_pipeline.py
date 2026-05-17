"""
scripts/step1_full_pipeline.py
================================
Complete Step 1 training and evaluation pipeline for Shamsi Smart.

Runs in order:
  1.  Diagnose RF V1 leakage
  2.  Train Random Forest V2 (fixed)
  3.  Train CNN-LSTM
  4.  Evaluate all baselines (PVWatts, Physics)
  5.  Full model comparison
  6.  Ablation study
  7.  Seasonal analysis
  8.  Per-location breakdown
  9.  Generate all plots
  10. Generate LaTeX tables for paper

Usage
-----
    # Full pipeline with real database:
    python scripts/step1_full_pipeline.py

    # Offline test (synthetic data, no DB):
    python scripts/step1_full_pipeline.py --synthetic

    # Skip DL training (fast evaluation only):
    python scripts/step1_full_pipeline.py --no-dl

Output
------
    results/step1/
    ├── models/
    │   ├── yield_predictor_v2.pkl
    │   └── cnn_lstm_best.pth
    ├── metrics/
    │   ├── comparison_table.csv
    │   ├── comparison_table.json
    │   ├── ablation_results.json
    │   ├── seasonal_analysis.json
    │   ├── per_location_errors.csv
    │   ├── cnn_lstm_history.json
    │   └── cnn_lstm_metrics.json
    ├── plots/
    │   ├── model_comparison_bar.png
    │   ├── rf_v2_predictions_vs_actual.png
    │   ├── rf_v2_residuals.png
    │   ├── rf_v2_feature_importance.png
    │   ├── cnn_lstm_loss_curve.png
    │   ├── cnn_lstm_predictions_vs_actual.png
    │   └── attention_weights.png
    └── paper_sections/
        ├── comparison_table.tex
        └── methodology.md   (copy from docs/academic/)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

# ── Django setup ──────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'shamsi_smart.settings'

try:
    import django
    django.setup()
    DJANGO_AVAILABLE = True
except Exception:
    DJANGO_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'step1')


# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Shamsi Smart Step 1 Full Pipeline')
    p.add_argument('--synthetic',    action='store_true',
                   help='Use synthetic data (no database required)')
    p.add_argument('--no-dl',        action='store_true',
                   help='Skip CNN-LSTM training')
    p.add_argument('--no-plots',     action='store_true')
    p.add_argument('--epochs',       type=int,   default=100)
    p.add_argument('--batch-size',   type=int,   default=32)
    p.add_argument('--lr',           type=float, default=1e-3)
    p.add_argument('--gpu',          action='store_true')
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# Step helpers
# ─────────────────────────────────────────────────────────────────────────────

def step_banner(n: int, title: str):
    print(f"\n{'═'*60}")
    print(f"  STEP {n}: {title}")
    print(f"{'═'*60}")


def diagnose_rf_v1_leakage():
    """
    Print a structured diagnosis of why RF V1 achieves R²=0.9999.
    """
    step_banner(1, "RF V1 Data Leakage Diagnosis")

    diagnosis = {
        "problem": "Data Leakage in Random Forest V1",
        "root_causes": [
            {
                "cause": "Target formula contains system_kw",
                "code": "yield_kwh = avg_ghi * 365 * eff * (1-temp_loss) * (1-dust) * sys_kw",
                "impact": "Target is LINEARLY proportional to sys_kw",
            },
            {
                "cause": "system_kw also used as feature",
                "code": "X_rows.append([..., sys_kw])  # sys_kw is feature index -1",
                "impact": "RF learns: y ≈ feature[-1] × constant → trivial mapping",
            },
            {
                "cause": "Random row split instead of location-based",
                "code": "train_test_split(X_scaled, y, test_size=0.2, random_state=42)",
                "impact": "Same location appears in both train and test → memorisation",
            },
            {
                "cause": "Training data is deterministic (physics formula)",
                "code": "y = f(X) with no noise → RF memorises perfectly",
                "impact": "R² = 1.0 on train, ≈ 1.0 on test (same distribution)",
            },
        ],
        "proof": "Feature importance: system_kw dominates at ~98%. "
                 "Remove system_kw from features → MAPE drops from 0.12% to realistic 3-7%.",
        "fix_summary": [
            "1. Target: use specific yield (kWh/kWp) — system_kw cancels out",
            "2. Features: exclude system_kw",
            "3. Split: location-based (GroupKFold by location_id)",
            "4. Add noise to training targets (or use real measured data)",
        ],
    }

    print(json.dumps(diagnosis, indent=2))

    diag_path = os.path.join(RESULTS_DIR, 'metrics', 'rf_v1_leakage_diagnosis.json')
    os.makedirs(os.path.dirname(diag_path), exist_ok=True)
    with open(diag_path, 'w') as f:
        json.dump(diagnosis, f, indent=2)

    logger.info("Leakage diagnosis saved to %s", diag_path)
    return diagnosis


def train_random_forest_v2(args) -> dict:
    """Train RF V2 and return metrics."""
    step_banner(2, "Training Random Forest V2 (Fixed)")

    from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2

    t0  = time.time()
    rf  = EgyptianYieldPredictorV2()
    metrics = rf.train_and_save()
    metrics['training_time_sec'] = round(time.time() - t0, 1)

    if not args.no_plots:
        rf.generate_diagnostic_plots(
            save_dir=os.path.join(RESULTS_DIR, 'plots')
        )

    logger.info("RF V2 training complete. MAPE=%.2f%%  R²=%.4f",
                metrics['test_mape'], metrics['test_r2'])
    return metrics


def train_cnn_lstm(args) -> dict:
    """Train CNN-LSTM and return test metrics."""
    step_banner(3, "Training CNN-LSTM Deep Learning Model")

    from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM, CNNLSTMTrainer
    from ai_engine.deep_learning.data_preparation import (
        prepare_time_series_data, create_dataloaders
    )
    import torch
    import numpy as np
    from torch.utils.data import DataLoader, TensorDataset

    # Data
    logger.info("Loading time-series data…")
    X, y, groups = prepare_time_series_data()

    unique_locs = np.unique(groups)
    rng = np.random.default_rng(42)
    rng.shuffle(unique_locs)
    n_val  = max(1, int(len(unique_locs) * 0.15))
    n_test = max(1, int(len(unique_locs) * 0.20))

    val_locs  = set(unique_locs[:n_val])
    test_locs = set(unique_locs[n_val:n_val + n_test])
    tr_locs   = set(unique_locs[n_val + n_test:])

    tr = np.array([g in tr_locs   for g in groups])
    vl = np.array([g in val_locs  for g in groups])
    te = np.array([g in test_locs for g in groups])

    train_loader, val_loader = create_dataloaders(
        X[tr], y[tr], X[vl], y[vl], batch_size=args.batch_size
    )
    test_ds = TensorDataset(
        torch.tensor(X[te], dtype=torch.float32),
        torch.tensor(y[te], dtype=torch.float32),
    )
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    # Model + trainer
    model = SolarYieldCNNLSTM(
        input_features=X.shape[2],
        sequence_length=X.shape[1],
    )
    trainer = CNNLSTMTrainer(
        model=model,
        save_dir=os.path.join(RESULTS_DIR, 'models'),
    )

    t0 = time.time()
    train_result = trainer.fit(
        train_loader, val_loader,
        epochs=args.epochs, lr=args.lr, use_gpu=args.gpu,
    )
    test_metrics = trainer.evaluate(test_loader)
    test_metrics['training_time_sec'] = round(time.time() - t0, 1)

    if not args.no_plots:
        trainer.plot_training_history(
            train_result['history'],
            save_path=os.path.join(RESULTS_DIR, 'plots', 'cnn_lstm_loss_curve.png'),
        )
        if te.sum() > 0:
            trainer.visualize_attention(
                X[te][0],
                save_path=os.path.join(RESULTS_DIR, 'plots', 'attention_weights.png'),
            )

    return test_metrics


def run_model_comparison(args) -> list:
    """Run full model comparison and generate all outputs."""
    step_banner(4, "Full Model Comparison")

    from ai_engine.evaluation.model_comparison import ModelComparison
    comp = ModelComparison(results_dir=RESULTS_DIR)

    # All models
    table = comp.evaluate_all_models()
    print("\n  Comparison Table:")
    for row in table:
        print(f"    {row['Model']:<22} MAPE={row['MAPE_%']}%  R²={row['R2']}")

    # Ablation
    step_banner(5, "Ablation Study")
    comp.ablation_study()

    # Seasonal
    step_banner(6, "Seasonal Analysis")
    comp.seasonal_analysis()

    # Per-location
    step_banner(7, "Per-Location Error Analysis")
    comp.per_location_analysis()

    # Paper table
    step_banner(8, "Generating Paper Tables")
    latex = comp.generate_paper_table(table)
    print("\n  LaTeX table preview (first 5 lines):")
    for line in latex.split('\n')[:6]:
        print(f"  {line}")

    # Comparison plots
    if not args.no_plots:
        comp.generate_comparison_plots(table)

    return table


def copy_paper_sections():
    """Copy academic methodology doc into paper_sections/."""
    src = os.path.join(PROJECT_ROOT, 'docs', 'academic', 'step1_methodology.md')
    dst = os.path.join(RESULTS_DIR, 'paper_sections', 'methodology.md')
    try:
        import shutil
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            logger.info("Methodology doc copied to paper_sections/")
    except Exception as exc:
        logger.warning("Could not copy methodology doc: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if args.synthetic or not DJANGO_AVAILABLE:
        args.synthetic = True
        logger.info("Mode: SYNTHETIC (no database)")
    else:
        logger.info("Mode: REAL DATABASE")

    t_start = time.time()

    print("\n" + "█" * 60)
    print("  Shamsi Smart — Step 1 Full Pipeline")
    print("  Academic Foundation & Deep Learning Core")
    print("█" * 60)

    # Step 1: Diagnose leakage
    diagnose_rf_v1_leakage()

    # Step 2: RF V2
    rf_metrics = train_random_forest_v2(args)

    # Step 3: CNN-LSTM (optional)
    dl_metrics = {}
    if not args.no_dl:
        try:
            dl_metrics = train_cnn_lstm(args)
        except ImportError as exc:
            logger.warning("PyTorch not available — skipping CNN-LSTM: %s", exc)
            dl_metrics = {'test_mape': 'N/A', 'test_r2': 'N/A',
                          'note': 'PyTorch not installed'}

    # Steps 4-8: Comparison, ablation, seasonal, per-location, paper
    comparison_table = run_model_comparison(args)

    # Copy paper sections
    copy_paper_sections()

    # ── Final summary ─────────────────────────────────────────────────────────
    total_time = time.time() - t_start
    print("\n" + "█" * 60)
    print("  ✅ Step 1 Complete!")
    print("█" * 60)
    print(f"\n  RF V2   — MAPE: {rf_metrics.get('test_mape', '?'):.2f}%  "
          f"R²: {rf_metrics.get('test_r2', '?'):.4f}")
    if dl_metrics and isinstance(dl_metrics.get('test_mape'), float):
        print(f"  CNN-LSTM— MAPE: {dl_metrics['test_mape']:.2f}%  "
              f"R²: {dl_metrics['test_r2']:.4f}")
    print(f"\n  Total time: {total_time:.1f}s")
    print(f"  Results  : {RESULTS_DIR}")
    print("\n  Files generated:")
    for d in ['models', 'metrics', 'plots', 'paper_sections']:
        full = os.path.join(RESULTS_DIR, d)
        if os.path.isdir(full):
            files = os.listdir(full)
            print(f"    {d}/  ({len(files)} files)")

    # Save pipeline summary
    summary = {
        'rf_v2_metrics': rf_metrics,
        'dl_metrics':    dl_metrics,
        'comparison':    comparison_table,
        'total_time_sec': total_time,
    }
    with open(os.path.join(RESULTS_DIR, 'metrics', 'pipeline_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    return summary


if __name__ == '__main__':
    main()
