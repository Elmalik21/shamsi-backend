"""
ai_engine/yield_predictor.py
Random Forest Regressor trained on NASA POWER data.
Predicts annual energy yield (kWh/kW installed) for any Egyptian location.
Model 1 — Yield Predictor
"""
from __future__ import annotations
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')


class EgyptianYieldPredictor:
    """
    Random Forest trained on 8-year NASA POWER aggregated data.

    Target MAPE: < 10%   |   Target R²: > 0.85

    Features (must be passed as a dict with these exact keys):
        avg_ghi           – Annual average GHI kWh/m²/day
        avg_temperature   – Annual average temperature °C
        max_temperature   – Peak summer temperature °C
        avg_humidity      – Annual average humidity %
        avg_wind_speed    – Annual average wind m/s
        dust_risk_score   – Dust loss factor (0.03–0.15)
        latitude          – Site latitude degrees
        tilt_angle        – Panel tilt degrees
        panel_efficiency  – Panel efficiency as decimal (e.g. 0.231)
        temp_coefficient  – Panel temp coefficient %/°C (negative)
        system_kw         – System size kW
    """

    FEATURES = [
        'avg_ghi', 'avg_temperature', 'max_temperature',
        'avg_humidity', 'avg_wind_speed', 'dust_risk_score',
        'latitude', 'tilt_angle', 'panel_efficiency',
        'temp_coefficient', 'system_kw',
    ]

    # Monthly solar fraction for Egypt (north→south varies slightly)
    # Relative weights of each month's irradiance (sum = 1.0)
    _MONTHLY_WEIGHTS = [
        0.062, 0.068, 0.088, 0.095, 0.102, 0.105,
        0.107, 0.103, 0.090, 0.079, 0.063, 0.058,
    ]

    def __init__(self):
        self.model = None
        self.scaler = None
        self._model_r2 = None
        self._model_mape = None
        # yield_predictor_v2.pkl is the canonical file produced by yield_predictor_v2.py
        # (also saved as yield_predictor.pkl by the v2 trainer for backward compat)
        _v2_path = os.path.join(MODELS_DIR, 'yield_predictor_v2.pkl')
        _v1_path = os.path.join(MODELS_DIR, 'yield_predictor.pkl')
        self._model_path = _v2_path if os.path.exists(_v2_path) else _v1_path

    # ── Training data ─────────────────────────────────────────────────────────

    def prepare_training_data(self):
        """
        Build training dataset from DailyClimateData.
        Aggregates daily → annual per location.
        Target = physics-based annual yield per kW installed.
        """
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg, Max
        from ai_engine.dust_clustering import EgyptianDustClusterer

        clusterer = EgyptianDustClusterer()
        locations = list(Location.objects.all().select_related('governorate'))

        if not locations:
            return None, None

        X_rows, y_rows = [], []
        for loc in locations:
            qs = DailyClimateData.objects.filter(location=loc)
            if qs.count() < 30:
                continue

            agg = qs.aggregate(
                avg_ghi=Avg('allsky_sfc_sw_dwn'),
                avg_temp=Avg('t2m'),
                max_temp=Max('t2m_max'),
                avg_hum=Avg('rh2m'),
                avg_wind=Avg('ws2m'),
                avg_dust=Avg('dust_risk_score'),
            )

            avg_ghi   = agg['avg_ghi']  or 5.5
            avg_temp  = agg['avg_temp'] or 25.0
            max_temp  = agg['max_temp'] or 38.0
            avg_hum   = agg['avg_hum']  or 40.0
            avg_wind  = agg['avg_wind'] or 3.0
            dust_risk = agg['avg_dust'] or clusterer._latitude_dust_default(loc.latitude)

            # Vary panel & system parameters for richer training set
            for eff in [0.21, 0.22, 0.23]:
                for tilt in [loc.latitude - 5, loc.latitude, loc.latitude + 5]:
                    for sys_kw in [5.0, 10.0, 15.0]:
                        temp_coeff = -0.32

                        # Physics target: annual kWh per kW installed
                        temp_loss  = max(0.0, (avg_temp - 25) * abs(temp_coeff) * 0.01)
                        dust_loss  = dust_risk
                        yield_kwh  = (avg_ghi * 365 * eff
                                      * (1 - temp_loss)
                                      * (1 - dust_loss)
                                      * sys_kw)

                        X_rows.append([
                            avg_ghi, avg_temp, max_temp, avg_hum, avg_wind,
                            dust_risk, loc.latitude, tilt, eff, temp_coeff, sys_kw,
                        ])
                        y_rows.append(yield_kwh)

        if not X_rows:
            return None, None

        return np.array(X_rows, dtype=float), np.array(y_rows, dtype=float)

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self):
        """
        Train Random Forest with 5-fold CV.
        Prints MAE, MAPE, R² for train and test sets.
        """
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import cross_val_score, train_test_split
            from sklearn.metrics import mean_absolute_error, r2_score
        except ImportError:
            raise ImportError("scikit-learn required")

        X, y = self.prepare_training_data()
        if X is None:
            logger.warning("No training data available. Using synthetic fallback.")
            X, y = self._synthetic_data()

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        X_tr, X_te, y_tr, y_te = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )

        rf = RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_tr, y_tr)

        y_pred_tr = rf.predict(X_tr)
        y_pred_te = rf.predict(X_te)

        mae_tr  = mean_absolute_error(y_tr, y_pred_tr)
        mae_te  = mean_absolute_error(y_te, y_pred_te)
        r2_tr   = r2_score(y_tr, y_pred_tr)
        r2_te   = r2_score(y_te, y_pred_te)
        mape_te = float(np.mean(np.abs((y_te - y_pred_te) / (y_te + 1e-9))) * 100)

        # 5-fold CV R²
        cv_r2 = cross_val_score(rf, X_scaled, y, cv=5, scoring='r2')

        print(f"  Train  — MAE: {mae_tr:.1f} kWh   R²: {r2_tr:.4f}")
        print(f"  Test   — MAE: {mae_te:.1f} kWh   MAPE: {mape_te:.2f}%   R²: {r2_te:.4f}")
        print(f"  5-fold CV R²: {cv_r2.mean():.4f} ± {cv_r2.std():.4f}")

        self.model  = rf
        self.scaler = scaler
        self._model_r2   = float(r2_te)
        self._model_mape = float(mape_te)

        return {
            'train_mae': mae_tr, 'test_mae': mae_te,
            'train_r2': r2_tr,  'test_r2': r2_te,
            'test_mape': mape_te,
            'cv_r2_mean': float(cv_r2.mean()),
        }

    def _synthetic_data(self):
        """Generate synthetic Egyptian data for fallback training."""
        rng = np.random.default_rng(42)
        n = 500
        ghi  = rng.uniform(4.5, 7.5, n)
        temp = rng.uniform(18.0, 35.0, n)
        lat  = rng.uniform(22.0, 31.5, n)
        eff  = rng.uniform(0.20, 0.24, n)
        dust = rng.uniform(0.03, 0.15, n)
        tilt = lat + rng.uniform(-5, 5, n)
        sys_kw = rng.uniform(3.0, 20.0, n)
        temp_coeff = rng.uniform(-0.35, -0.28, n)
        hum  = rng.uniform(25.0, 70.0, n)
        wind = rng.uniform(2.0, 6.0, n)
        max_t = temp + rng.uniform(5, 12, n)

        temp_loss = np.maximum(0.0, (temp - 25) * np.abs(temp_coeff) * 0.01)
        y = ghi * 365 * eff * (1 - temp_loss) * (1 - dust) * sys_kw

        X = np.column_stack([ghi, temp, max_t, hum, wind, dust, lat, tilt, eff, temp_coeff, sys_kw])
        return X, y

    def train_and_save(self):
        """Full pipeline: prepare → train → evaluate → save."""
        import joblib
        os.makedirs(MODELS_DIR, exist_ok=True)
        metrics = self.train()
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'r2': self._model_r2,
            'mape': self._model_mape,
        }, self._model_path)
        logger.info("Yield predictor saved to %s", self._model_path)
        return metrics

    def _load(self):
        if self.model is not None:
            return True
        if not os.path.exists(self._model_path):
            logger.warning(
                "Yield predictor model not found at %s — using physics fallback. "
                "Run scripts/step1_full_pipeline.py to train.",
                self._model_path,
            )
            return False
        try:
            import joblib
            data = joblib.load(self._model_path)
            self.model  = data['model']
            self.scaler = data['scaler']
            self._model_r2   = data.get('r2')
            self._model_mape = data.get('mape')
            logger.info("✅ Loaded yield predictor from %s", self._model_path)
            return True
        except Exception as exc:
            logger.error("Failed to load yield predictor: %s", exc)
            return False

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict(self, features: dict) -> dict:
        """
        Predict annual yield for a given feature set.

        Returns
        -------
        dict with keys:
            predicted_annual_kwh  – total annual energy (kWh)
            predicted_monthly     – list of 12 monthly values
            confidence_interval   – {'low': float, 'high': float}
            model_r2              – model R²
            model_mape            – model MAPE %
        """
        if not self._load():
            # Fallback: pure physics estimate
            return self._physics_estimate(features)

        x = np.array([[features[f] for f in self.FEATURES]], dtype=float)
        x_s = self.scaler.transform(x)

        # Tree-level predictions for uncertainty
        tree_preds = np.array([t.predict(x_s)[0] for t in self.model.estimators_])
        pred_mean  = float(tree_preds.mean())
        pred_std   = float(tree_preds.std())

        monthly = [round(pred_mean * w, 1) for w in self._MONTHLY_WEIGHTS]

        return {
            'predicted_annual_kwh':  round(pred_mean, 1),
            'predicted_monthly':     monthly,
            'confidence_interval': {
                'low':  round(max(0, pred_mean - 1.645 * pred_std), 1),
                'high': round(pred_mean + 1.645 * pred_std, 1),
            },
            'model_r2':   round(self._model_r2 or 0.0, 4),
            'model_mape': round(self._model_mape or 0.0, 2),
        }

    def _physics_estimate(self, features: dict) -> dict:
        """Pure physics fallback when model not trained."""
        ghi       = features.get('avg_ghi', 5.5)
        temp      = features.get('avg_temperature', 25.0)
        dust      = features.get('dust_risk_score', 0.07)
        eff       = features.get('panel_efficiency', 0.22)
        temp_c    = features.get('temp_coefficient', -0.32)
        sys_kw    = features.get('system_kw', 10.0)

        temp_loss = max(0.0, (temp - 25) * abs(temp_c) * 0.01)
        annual    = ghi * 365 * eff * (1 - temp_loss) * (1 - dust) * sys_kw
        monthly   = [round(annual * w, 1) for w in self._MONTHLY_WEIGHTS]

        return {
            'predicted_annual_kwh': round(annual, 1),
            'predicted_monthly': monthly,
            'confidence_interval': {
                'low':  round(annual * 0.90, 1),
                'high': round(annual * 1.10, 1),
            },
            'model_r2': 0.0,
            'model_mape': 0.0,
        }

    def get_feature_importance(self) -> dict:
        """Return feature importance rankings."""
        if not self._load():
            return {}
        importances = self.model.feature_importances_
        ranked = sorted(
            zip(self.FEATURES, importances),
            key=lambda x: x[1], reverse=True
        )
        return {feat: round(float(imp), 4) for feat, imp in ranked}
