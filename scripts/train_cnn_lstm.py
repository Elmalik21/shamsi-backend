"""
scripts/train_cnn_lstm.py
==========================
Standalone CNN-LSTM training script for Shamsi Smart Step 1.

Usage
-----
    # From the project root (Django settings must be configured):
    python scripts/train_cnn_lstm.py
    python scripts/train_cnn_lstm.py --epochs 100 --batch-size 32 --gpu
    python scripts/train_cnn_lstm.py --synthetic   # offline test without DB

Arguments
---------
    --epochs      int   Max training epochs (default: 100)
    --batch-size  int   Mini-batch size (default: 32)
    --lr          float Initial learning rate (default: 1e-3)
    --gpu               Use CUDA if available
    --synthetic         Use synthetic data (no Django ORM needed)
    --no-plots          Skip plot generation

Output (results/step1/)
-----------------------
    models/cnn_lstm_best.pth
    metrics/cnn_lstm_history.json
    metrics/cnn_lstm_metrics.json
    plots/cnn_lstm_loss_curve.png
    plots/cnn_lstm_predictions_vs_actual.png
    plots/attention_weights.png
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

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

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'step1')


def parse_args():
    p = argparse.ArgumentParser(description='Train CNN-LSTM solar yield predictor')
    p.add_argument('--epochs',      type=int,   default=100)
    p.add_argument('--batch-size',  type=int,   default=32)
    p.add_argument('--lr',          type=float, default=1e-3)
    p.add_argument('--gpu',         action='store_true')
    p.add_argument('--synthetic',   action='store_true',
                   help='Use synthetic data (no database required)')
    p.add_argument('--no-plots',    action='store_true')
    p.add_argument('--patience',    type=int, default=15)
    return p.parse_args()


def train(args):
    import torch
    from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM, CNNLSTMTrainer
    from ai_engine.deep_learning.data_preparation import (
        prepare_time_series_data,
        generate_synthetic_time_series_data,
        create_dataloaders,
    )

    # Support both attribute names: args.batch_size and args.batch_size (from argparse)
    batch_size = getattr(args, 'batch_size', getattr(args, 'batch_size', 32))

    print("\n" + "═" * 60)
    print("  Shamsi Smart — CNN-LSTM Training")
    print("═" * 60)
    print(f"  PyTorch: {torch.__version__}")
    print(f"  CUDA   : {torch.cuda.is_available()}")
    print(f"  Epochs : {args.epochs}  |  Batch: {batch_size}  |  LR: {args.lr}")
    print(f"  Data   : {'Synthetic' if args.synthetic else 'Database'}")
    print("═" * 60)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    if args.synthetic:
        logger.info("Generating synthetic time-series data (119 locations × 3 years)…")
        X, y, groups = generate_synthetic_time_series_data(
            n_locations=119,
            n_years=3,
            sequence_length=365,
        )
    else:
        logger.info("Loading data from database…")
        X, y, groups = prepare_time_series_data(
            location_ids=None,
            sequence_length=365,
        )
    logger.info("Dataset shape: X=%s  y=%s  unique_locations=%d",
                X.shape, y.shape, len(np.unique(groups)))

    # ── 2. Location-based train/val split ─────────────────────────────────────
    unique_locs = np.unique(groups)
    rng = np.random.default_rng(42)
    rng.shuffle(unique_locs)
    n_val    = max(1, int(len(unique_locs) * 0.15))
    n_test   = max(1, int(len(unique_locs) * 0.20))
    val_locs  = set(unique_locs[:n_val])
    test_locs = set(unique_locs[n_val:n_val+n_test])
    train_locs = set(unique_locs[n_val+n_test:])

    tr_mask = np.array([g in train_locs for g in groups])
    vl_mask = np.array([g in val_locs   for g in groups])
    te_mask = np.array([g in test_locs  for g in groups])

    X_tr, y_tr = X[tr_mask], y[tr_mask]
    X_vl, y_vl = X[vl_mask], y[vl_mask]
    X_te, y_te = X[te_mask], y[te_mask]

    print(f"\n  Train: {tr_mask.sum()} samples  ({len(train_locs)} locations)")
    print(f"  Val  : {vl_mask.sum()} samples  ({len(val_locs)} locations)")
    print(f"  Test : {te_mask.sum()} samples  ({len(test_locs)} locations)")

    # ── 3. DataLoaders ────────────────────────────────────────────────────────
    train_loader, val_loader = create_dataloaders(
        X_tr, y_tr, X_vl, y_vl, batch_size=batch_size
    )

    # Make a test DataLoader for evaluation
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    test_ds = TensorDataset(
        torch.tensor(X_te, dtype=torch.float32),
        torch.tensor(y_te, dtype=torch.float32),
    )
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

    # ── 4. Model ──────────────────────────────────────────────────────────────
    model   = SolarYieldCNNLSTM(
        input_features      = X.shape[2],
        sequence_length     = X.shape[1],
        hidden_size         = 128,
        num_lstm_layers     = 2,
        num_attention_heads = 4,
        dropout             = 0.3,
        output_months       = 12,
    )
    trainer = CNNLSTMTrainer(
        model    = model,
        save_dir = os.path.join(RESULTS_DIR, 'models'),
        patience = args.patience,
    )

    # ── 5. Train ──────────────────────────────────────────────────────────────
    logger.info("Starting training…")
    train_result = trainer.fit(
        train_loader, val_loader,
        epochs  = args.epochs,
        lr      = args.lr,
        use_gpu = args.gpu,
    )

    # ── 6. Evaluate ───────────────────────────────────────────────────────────
    logger.info("Evaluating on test set…")
    test_metrics = trainer.evaluate(test_loader)

    # ── 7. Plots ──────────────────────────────────────────────────────────────
    if not args.no_plots:
        logger.info("Generating plots…")

        # Loss curve
        trainer.plot_training_history(
            train_result['history'],
            save_path=os.path.join(RESULTS_DIR, 'plots', 'cnn_lstm_loss_curve.png'),
        )

        # Attention visualisation (first test sample)
        if len(X_te) > 0:
            trainer.visualize_attention(
                sample_X=X_te[0],
                save_path=os.path.join(RESULTS_DIR, 'plots', 'attention_weights.png'),
            )

        # Predictions vs actual scatter
        _plot_predictions_scatter(trainer, test_loader,
                                  os.path.join(RESULTS_DIR, 'plots',
                                               'cnn_lstm_predictions_vs_actual.png'))

    # ── 8. Summary ────────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  CNN-LSTM Training Complete")
    print("═" * 60)
    print(f"  Best epoch   : {train_result['best_epoch']}")
    print(f"  Training time: {train_result['training_time_sec']:.1f}s")
    print(f"  Test MAPE    : {test_metrics['test_mape']:.2f}%")
    print(f"  Test R²      : {test_metrics['test_r2']:.4f}")
    print(f"  Test MAE     : {test_metrics['test_mae']:.2f} kWh/kWp")
    print("═" * 60)
    print(f"\n  Results saved to: {RESULTS_DIR}")

    return test_metrics


def _plot_predictions_scatter(trainer, test_loader, save_path: str):
    try:
        import torch
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        net    = trainer.model.get_net(device)
        net.eval()

        preds, targets = [], []
        with torch.no_grad():
            for Xb, yb in test_loader:
                p = net(Xb.to(device)).cpu().numpy()
                preds.extend(p.flatten())
                targets.extend(yb.numpy().flatten())

        preds   = np.array(preds)
        targets = np.array(targets)

        fig, ax = plt.subplots(figsize=(7, 7))
        ax.scatter(targets, preds, alpha=0.4, s=30, color='steelblue', edgecolors='none')
        lim = [min(targets.min(), preds.min()) * 0.95,
               max(targets.max(), preds.max()) * 1.05]
        ax.plot(lim, lim, 'r--', lw=1.5, label='Perfect prediction')
        ax.set_xlabel('Actual Monthly Yield (kWh/kWp)', fontsize=12)
        ax.set_ylabel('Predicted Monthly Yield (kWh/kWp)', fontsize=12)
        ax.set_title('CNN-LSTM — Predictions vs. Actual', fontsize=13)
        mape = float(np.mean(np.abs((targets - preds) / (targets + 1e-6))) * 100)
        ss_r = np.sum((targets - preds)**2)
        ss_t = np.sum((targets - targets.mean())**2)
        r2   = 1 - ss_r/ss_t if ss_t > 0 else 0
        ax.text(0.05, 0.93, f'MAPE = {mape:.2f}%\nR² = {r2:.3f}',
                transform=ax.transAxes, fontsize=11,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.legend()
        plt.tight_layout()
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path, dpi=150)
        plt.close()
        logger.info("Predictions scatter plot saved to %s", save_path)
    except Exception as exc:
        logger.warning("Scatter plot failed: %s", exc)


if __name__ == '__main__':
    args = parse_args()
    if args.synthetic or not DJANGO_AVAILABLE:
        args.synthetic = True
        logger.info("Using synthetic data (no Django ORM)")
    train(args)
