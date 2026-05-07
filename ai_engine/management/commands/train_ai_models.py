"""
ai_engine/management/commands/train_ai_models.py
Django management command to train all Shamsi Smart AI models.

Usage:
    python manage.py train_ai_models
"""
import time
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Train all Shamsi Smart AI models (K-Means dust + Random Forest yield)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-dust', action='store_true',
            help='Skip K-Means dust clusterer training'
        )
        parser.add_argument(
            '--skip-yield', action='store_true',
            help='Skip Random Forest yield predictor training'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            '\n' + '=' * 60 + '\n  Shamsi Smart — AI Model Training\n' + '=' * 60
        ))

        models_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'models'
        )
        os.makedirs(models_dir, exist_ok=True)

        # ── Step 1: K-Means Dust Clusterer ────────────────────────────────────
        if not options['skip_dust']:
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
        if not options['skip_yield']:
            self.stdout.write('\n[2/2] Training Random Forest Yield Predictor (Model 1)...')
            t0 = time.time()
            try:
                from ai_engine.yield_predictor import EgyptianYieldPredictor
                predictor = EgyptianYieldPredictor()
                metrics = predictor.train_and_save()
                elapsed = round(time.time() - t0, 2)

                self.stdout.write(self.style.SUCCESS(
                    f'  Yield predictor trained in {elapsed}s'
                ))
                self.stdout.write(
                    f"  Test  R²:   {metrics['test_r2']:.4f}   "
                    f"(target >= 0.85)"
                )
                self.stdout.write(
                    f"  Test  MAPE: {metrics['test_mape']:.2f}%  "
                    f"(target < 10%)"
                )
                self.stdout.write(
                    f"  Test  MAE:  {metrics['test_mae']:.1f} kWh"
                )
                self.stdout.write(
                    f"  CV    R²:   {metrics['cv_r2_mean']:.4f}"
                )

                # Feature importance
                imp = predictor.get_feature_importance()
                self.stdout.write('  Top 5 features:')
                for feat, val in list(imp.items())[:5]:
                    self.stdout.write(f'    {feat:25s}: {val:.4f}')

                # Verify model loads and predicts
                p2 = EgyptianYieldPredictor()
                test_pred = p2.predict({
                    'avg_ghi': 6.2, 'avg_temperature': 28.0,
                    'max_temperature': 40.0, 'avg_humidity': 35.0,
                    'avg_wind_speed': 3.5, 'dust_risk_score': 0.07,
                    'latitude': 30.0, 'tilt_angle': 30.0,
                    'panel_efficiency': 0.23, 'temp_coefficient': -0.30,
                    'system_kw': 10.0,
                })
                self.stdout.write(
                    f'  Verify: 10 kW system in Cairo → '
                    f'{test_pred["predicted_annual_kwh"]:,.0f} kWh/yr'
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Yield predictor FAILED: {e}'))
        else:
            self.stdout.write('  [skip] Yield predictor skipped.')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(
            '  Training complete. Models saved to ai_engine/models/'
        ))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))
