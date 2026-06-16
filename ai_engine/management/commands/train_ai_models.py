"""
ai_engine/management/commands/train_ai_models.py
Django management command to train all Shamsi Smart AI models.

Usage:
    python manage.py train_ai_models           # skip if models already exist
    python manage.py train_ai_models --force   # always retrain
"""
import time
import os
from django.core.management.base import BaseCommand

# Minimum file size to consider a model "already trained"
_DUST_MIN_BYTES  =    50_000   # 50 KB
_YIELD_MIN_BYTES = 1_000_000   # 1 MB


class Command(BaseCommand):
    help = 'Train all Shamsi Smart AI models (K-Means dust + Random Forest yield)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-dust', action='store_true',
            help='Skip K-Means dust clusterer training',
        )
        parser.add_argument(
            '--skip-yield', action='store_true',
            help='Skip Random Forest yield predictor training',
        )
        parser.add_argument(
            '--train-cnn', action='store_true',
            help='Train the CNN-LSTM deep learning predictor',
        )
        parser.add_argument(
            '--skip-yield', action='store_true',
            help='Skip Random Forest yield predictor training',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Retrain even if model files already exist (default: skip when file is large enough)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            '\n' + '=' * 60 + '\n  Shamsi Smart — AI Model Training\n' + '=' * 60
        ))

        models_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'models',
        )
        os.makedirs(models_dir, exist_ok=True)

        force = options.get('force', False)

        # ── Step 1: K-Means Dust Clusterer ────────────────────────────────────
        dust_model_path = os.path.join(models_dir, 'dust_clusterer.pkl')
        dust_exists = (
            os.path.exists(dust_model_path)
            and os.path.getsize(dust_model_path) > _DUST_MIN_BYTES
        )

        if not options['skip_dust']:
            if dust_exists and not force:
                self.stdout.write(self.style.SUCCESS(
                    f'\n[1/2] ✅ Dust clusterer already trained '
                    f'({os.path.getsize(dust_model_path) // 1024} KB) — skipping. '
                    f'Pass --force to retrain.'
                ))
            else:
                self.stdout.write('\n[1/2] Training K-Means Dust Clusterer (Model 3)...')
                t0 = time.time()
                try:
                    from ai_engine.dust_clustering import EgyptianDustClusterer
                    clusterer = EgyptianDustClusterer()
                    success = clusterer.train_and_save()
                    elapsed = round(time.time() - t0, 2)

                    if success:
                        self.stdout.write(self.style.SUCCESS(
                            f'  Dust clusterer trained in {elapsed}s'
                        ))
                        clusterer.print_metrics()
                    else:
                        self.stdout.write(self.style.WARNING(
                            f'  No location data found — using latitude-rule fallback. ({elapsed}s)'
                        ))

                    # Verify model loads
                    c2 = EgyptianDustClusterer()
                    zone = c2.predict_zone(1) if success else {'name': 'MEDIUM (fallback)'}
                    self.stdout.write(f'  Verify: location 1 → zone {zone.get("name", "?")}')

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Dust clusterer FAILED: {e}'))
        else:
            self.stdout.write('  [skip] Dust clusterer skipped.')

        # ── Step 2: Random Forest Yield Predictor ─────────────────────────────
        rf_v2_path = os.path.join(models_dir, 'yield_predictor_v2.pkl')
        rf_v1_path = os.path.join(models_dir, 'yield_predictor.pkl')
        rf_exists = (
            (os.path.exists(rf_v2_path) and os.path.getsize(rf_v2_path) > _YIELD_MIN_BYTES)
            or (os.path.exists(rf_v1_path) and os.path.getsize(rf_v1_path) > _YIELD_MIN_BYTES)
        )
        rf_path_found = rf_v2_path if os.path.exists(rf_v2_path) else rf_v1_path

        if not options['skip_yield']:
            if rf_exists and not force:
                self.stdout.write(self.style.SUCCESS(
                    f'\n[2/2] ✅ Yield predictor already trained '
                    f'({os.path.getsize(rf_path_found) // 1024} KB) — skipping. '
                    f'Pass --force to retrain.'
                ))
            else:
                self.stdout.write('\n[2/2] Training Random Forest Yield Predictor (Model 1)...')
                t0 = time.time()
                try:
                    from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
                    predictor = EgyptianYieldPredictorV2()
                    metrics = predictor.train_and_save()
                    elapsed = round(time.time() - t0, 2)

                    self.stdout.write(self.style.SUCCESS(
                        f'  Yield predictor trained in {elapsed}s'
                    ))
                    self.stdout.write(
                        f"  Test  R²:   {metrics['test_r2']:.4f}   (target >= 0.85)"
                    )
                    self.stdout.write(
                        f"  Test  MAPE: {metrics['test_mape']:.2f}%  (target < 10%)"
                    )
                    self.stdout.write(
                        f"  Test  MAE:  {metrics['test_mae']:.1f} kWh/kWp"
                    )
                    self.stdout.write(
                        f"  CV    R²:   {metrics['cv_r2_mean']:.4f}"
                    )

                    # Feature importance
                    imp = predictor.get_feature_importance()
                    self.stdout.write('  Top 5 features (system_kw is NOT a feature — it is a post-prediction multiplier):')
                    for feat, val in list(imp.items())[:5]:
                        self.stdout.write(f'    {feat:25s}: {val:.4f}')

                    # Verify model loads and predicts correctly
                    p2 = EgyptianYieldPredictorV2()
                    test_pred = p2.predict({
                        'avg_ghi': 6.2, 'avg_temperature': 28.0,
                        'max_temperature': 40.0, 'avg_humidity': 35.0,
                        'avg_wind_speed': 3.5, 'dust_risk_score': 0.07,
                        'latitude': 30.0, 'tilt_angle': 30.0,
                        'temp_coefficient': -0.30,
                    }, system_kw=10.0)
                    kwh = test_pred['predicted_annual_kwh']
                    self.stdout.write(
                        f'  Verify: 10 kW system in Cairo → {kwh:,.0f} kWh/yr '
                        f'(expect 1400–1800)'
                    )
                    if not (1_000 <= kwh <= 3_000):
                        self.stdout.write(self.style.WARNING(
                            f'  ⚠️  Predicted value {kwh:.0f} looks suspicious — check training data.'
                        ))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  Yield predictor FAILED: {e}'))
        else:
            self.stdout.write('  [skip] Yield predictor skipped.')

        # ── Step 3: CNN-LSTM Deep Learning Predictor ──────────────────────────
        cnn_path = os.path.join(models_dir, 'cnn_lstm_best.pth')
        cnn_exists = os.path.exists(cnn_path)
        
        if options.get('train_cnn'):
            self.stdout.write('\n[3/3] Training CNN-LSTM Predictor (Deep Learning)...')
            try:
                import torch
                from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM, CNNLSTMTrainer
                from ai_engine.deep_learning.dataset import get_dataloaders
                
                self.stdout.write('  Preparing dataloaders (this might take a moment)...')
                train_loader, val_loader, test_loader = get_dataloaders(batch_size=32)
                
                model = SolarYieldCNNLSTM()
                trainer = CNNLSTMTrainer(model=model, save_dir=models_dir, patience=10)
                
                self.stdout.write('  Starting PyTorch training loop...')
                t0 = time.time()
                history = trainer.fit(train_loader, val_loader, epochs=50, use_gpu=True)
                elapsed = round(time.time() - t0, 2)
                
                self.stdout.write(self.style.SUCCESS(f'  CNN-LSTM trained in {elapsed}s'))
                self.stdout.write(f"  Best Val Loss: {history['best_val_loss']:.4f}")
                
                self.stdout.write('  Evaluating on Test Set...')
                metrics = trainer.evaluate(test_loader)
                
            except ImportError as e:
                self.stdout.write(self.style.ERROR(f'  CNN-LSTM skipped: {e} (PyTorch missing?)'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  CNN-LSTM FAILED: {e}'))
        else:
            if cnn_exists:
                self.stdout.write(self.style.SUCCESS(
                    f'\n[3/3] ✅ CNN-LSTM already exists '
                    f'({os.path.getsize(cnn_path) // 1024} KB). '
                    f'Pass --train-cnn to retrain.'
                ))
            else:
                self.stdout.write('\n[3/3] ⚠️ CNN-LSTM not trained. Pass --train-cnn to train it.')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(
            '  Training complete. Models saved to ai_engine/models/'
        ))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))
