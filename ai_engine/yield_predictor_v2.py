"""
ai_engine/yield_predictor_v2.py
================================
Random Forest V2 — Shamsi Smart Solar Yield Predictor (FIXED)

Key fixes over V1:
  1. TARGET: specific yield (kWh/kWp) instead of absolute kWh
     → removes system_kw from the target formula
  2. FEATURES: system_kw EXCLUDED from feature vector
     → eliminates the dominant linear leakage factor
  3. SPLIT: location-based (GroupKFold) instead of random row split
     → truly tests generalisation to unseen geographic locations
  4. CV: GroupKFold(n_splits=5) grouped by location_id
     → prevents same-location data leaking across folds

Expected performance (realistic):
  MAPE  3 – 7 %        (vs. V1's fraudulent 0.12 %)
  R²    0.85 – 0.93    (vs. V1's fraudulent 0.9999)
  MAE   80 – 180 kWh/kWp

Academic context:
  Comparable to NREL PVWatts MAPE of 5–15 %.
  This is the Random Forest baseline for comparison with CNN-LSTM.

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import os
import logging
import warnings
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true > 1e-6
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────

class EgyptianYieldPredictorV2:
    """
    Random Forest trained on NASA POWER annual aggregates.

    TARGET  : specific_yield  [kWh / kWp / year]
              = annual_kWh_generated / system_kW_installed
              (scale-independent, comparable across system sizes)

    FEATURES (10, no system_kw):
        avg_ghi           – Annual average GHI  [kWh/m²/day]
        avg_temperature   – Annual avg temperature  [°C]
        max_temperature   – Peak summer temperature [°C]
        avg_humidity      – Annual avg humidity  [%]
        avg_wind_speed    – Annual avg wind speed [m/s]
        dust_risk_score   – Dust/soiling loss factor  [0.03–0.15]
        latitude          – Site latitude  [degrees]
        tilt_angle        – Panel tilt  [degrees]
        panel_efficiency  – Panel STC efficiency  [decimal, e.g. 0.23]
        temp_coefficient  – Panel temperature coefficient [%/°C, negative]

    SPLIT: 80 % of locations train / 20 % test (GroupKFold)
    CV   : 5-fold GroupKFold grouped by location_id
    """

    FEATURES = [
        'avg_ghi', 'avg_temperature', 'max_temperature',
        'avg_humidity', 'avg_wind_speed', 'dust_risk_score',
        'latitude', 'tilt_angle', 'panel_efficiency', 'temp_coefficient',
    ]
    TARGET = 'specific_yield_kwh_per_kwp'

    # Monthly distribution for Egypt (Jan–Dec); sum = 1.0
    _MONTHLY_WEIGHTS = [
        0.062, 0.068, 0.088, 0.095, 0.102, 0.105,
        0.107, 0.103, 0.090, 0.079, 0.063, 0.058,
    ]

    def __init__(self):
        self.model = None
        self.scaler = None
        self._metrics: dict = {}
        self._model_path = os.path.join(MODELS_DIR, 'yield_predictor_v2.pkl')

    # ── Training data ─────────────────────────────────────────────────────────

    def prepare_training_data(self):
        """
        Build training dataset from DailyClimateData.

        Returns
        -------
        X         : np.ndarray  shape (n_samples, 10)
        y         : np.ndarray  shape (n_samples,)  — specific yield kWh/kWp
        groups    : np.ndarray  shape (n_samples,)  — location_id for GroupKFold
        loc_names : list[str]   — human-readable location names (same order as groups)
        """
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg, Max
        from ai_engine.dust_clustering import EgyptianDustClusterer

        clusterer = EgyptianDustClusterer()
        locations = list(Location.objects.all().select_related('governorate'))

        if not locations:
            logger.warning("No locations found — using synthetic data.")
            return self._synthetic_data()

        X_rows, y_rows, groups, loc_names = [], [], [], []

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

            # Vary panel parameters → richer feature space
            # NOTE: system_kw is deliberately excluded from features.
            #       We vary it only to compute a realistic specific_yield range.
            for eff in [0.20, 0.21, 0.22, 0.23]:
                for tilt in [loc.latitude - 5, loc.latitude, loc.latitude + 5]:
                    temp_coeff = -0.32

                    # ── TARGET: specific yield (kWh / kWp) — scale-free ──────
                    temp_loss = max(0.0, (avg_temp - 25) * abs(temp_coeff) * 0.01)
                    # specific_yield = GHI * 365 * PR * loss_factors
                    # system_kw cancels out when we normalise by system_kw:
                    #   annual_kWh / system_kw = GHI*365*0.86*(1-temp_loss)*(1-dust)
                    specific_yield = (
                        avg_ghi * 365 * 0.86
                        * (1 - temp_loss)
                        * (1 - dust_risk)
                    )

                    X_rows.append([
                        avg_ghi, avg_temp, max_temp, avg_hum, avg_wind,
                        dust_risk, loc.latitude, tilt, eff, temp_coeff,
                    ])
                    y_rows.append(specific_yield)
                    groups.append(loc.location_id)
                    loc_names.append(str(loc))

        if not X_rows:
            logger.warning("No training rows built — using synthetic data.")
            return self._synthetic_data()

        return (
            np.array(X_rows, dtype=float),
            np.array(y_rows, dtype=float),
            np.array(groups, dtype=int),
            loc_names,
        )

    # ── Training ──────────────────────────────────────────────────────────────

    def train(self, verbose: bool = True) -> dict:
        """
        Train Random Forest V2 with location-based train/test split and CV.

        Returns
        -------
        dict with keys: train_mae, test_mae, test_rmse, test_mape, test_r2,
                        cv_r2_mean, cv_r2_std, n_train_locations, n_test_locations
        """
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
            from sklearn.model_selection import GroupKFold, cross_val_score
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        except ImportError:
            raise ImportError("pip install scikit-learn")

        result = self.prepare_training_data()
        if len(result) == 4:
            X, y, groups, loc_names = result
        else:
            # synthetic fallback returns (X, y, groups, loc_names) too
            X, y, groups, loc_names = result

        # ── Location-based train/test split ───────────────────────────────────
        # 80 % of unique locations → train, 20 % → test
        unique_locs = np.unique(groups)
        rng = np.random.default_rng(42)
        rng.shuffle(unique_locs)
        n_test = max(1, int(len(unique_locs) * 0.20))
        test_locs  = set(unique_locs[:n_test])
        train_locs = set(unique_locs[n_test:])

        train_mask = np.array([g in train_locs for g in groups])
        test_mask  = np.array([g in test_locs  for g in groups])

        X_tr, X_te = X[train_mask], X[test_mask]
        y_tr, y_te = y[train_mask], y[test_mask]
        g_tr       = groups[train_mask]

        if verbose:
            print(f"  Train: {train_mask.sum()} samples from {len(train_locs)} locations")
            print(f"  Test : {test_mask.sum()}  samples from {len(test_locs)}  locations")

        # ── Scaling ───────────────────────────────────────────────────────────
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)

        # ── Model ─────────────────────────────────────────────────────────────
        rf = RandomForestRegressor(
            n_estimators=300,
            max_depth=12,
            min_samples_split=8,
            min_samples_leaf=4,
            max_features='sqrt',
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_tr_s, y_tr)

        # ── Metrics ───────────────────────────────────────────────────────────
        y_pred_tr = rf.predict(X_tr_s)
        y_pred_te = rf.predict(X_te_s)

        mae_tr   = mean_absolute_error(y_tr, y_pred_tr)
        mae_te   = mean_absolute_error(y_te, y_pred_te)
        rmse_te  = float(np.sqrt(mean_squared_error(y_te, y_pred_te)))
        mape_te  = _mape(y_te, y_pred_te)
        r2_tr    = r2_score(y_tr, y_pred_tr)
        r2_te    = r2_score(y_te, y_pred_te)

        # ── GroupKFold CV on training set ─────────────────────────────────────
        gkf = GroupKFold(n_splits=5)
        X_all_s = scaler.transform(X)
        cv_r2 = cross_val_score(
            rf, X_tr_s, y_tr,
            cv=gkf.split(X_tr_s, y_tr, g_tr),
            scoring='r2',
        )

        if verbose:
            print(f"\n  ═══════════════════════════════════════════════")
            print(f"  Random Forest V2 Results (specific yield kWh/kWp)")
            print(f"  ═══════════════════════════════════════════════")
            print(f"  Train  — MAE: {mae_tr:.1f}   R²: {r2_tr:.4f}")
            print(f"  Test   — MAE: {mae_te:.1f}   RMSE: {rmse_te:.1f}   MAPE: {mape_te:.2f}%   R²: {r2_te:.4f}")
            print(f"  5-fold GroupKFold CV R²: {cv_r2.mean():.4f} ± {cv_r2.std():.4f}")
            print(f"  ═══════════════════════════════════════════════")

            # Feature importances
            print(f"\n  Feature Importances:")
            fi = sorted(zip(self.FEATURES, rf.feature_importances_),
                        key=lambda x: x[1], reverse=True)
            for feat, imp in fi:
                bar = '█' * int(imp * 40)
                print(f"    {feat:<22} {imp:.4f}  {bar}")

        self.model  = rf
        self.scaler = scaler
        self._metrics = {
            'train_mae':          float(mae_tr),
            'test_mae':           float(mae_te),
            'test_rmse':          float(rmse_te),
            'test_mape':          float(mape_te),
            'train_r2':           float(r2_tr),
            'test_r2':            float(r2_te),
            'cv_r2_mean':         float(cv_r2.mean()),
            'cv_r2_std':          float(cv_r2.std()),
            'n_train_locations':  len(train_locs),
            'n_test_locations':   len(test_locs),
        }
        return self._metrics

    def train_and_save(self) -> dict:
        """Full pipeline: prepare → train → evaluate → save."""
        import joblib
        os.makedirs(MODELS_DIR, exist_ok=True)
        metrics = self.train()
        joblib.dump({
            'model':   self.model,
            'scaler':  self.scaler,
            'metrics': self._metrics,
            'features': self.FEATURES,
            'target':  self.TARGET,
        }, self._model_path)
        logger.info("RF V2 saved → %s", self._model_path)
        return metrics

    def train_from_synthetic_data(self, verbose: bool = True) -> dict:
        """
        Generate synthetic Egyptian solar data, train, validate, and save.

        Creates 119 synthetic Egyptian locations × 12 parameter combinations
        (4 efficiencies × 3 tilts) = 1428 training samples, covering all
        Egyptian climate zones from the Nile Delta to deep Upper Egypt.

        Returns
        -------
        dict  Training metrics (same schema as train())
        """
        import joblib

        try:
            from tqdm import tqdm as _tqdm
            _have_tqdm = True
        except ImportError:
            _have_tqdm = False

        if verbose:
            print("\n  Generating synthetic training data for Random Forest…")

        rng = np.random.default_rng(42)
        n_locations = 119

        # Egyptian cities/regions — realistic climate profiles
        # Latitude band drives GHI, dust and temperature
        lats = np.concatenate([
            rng.uniform(30.5, 31.5, 25),   # Nile Delta (low dust, humid)
            rng.uniform(29.5, 30.5, 20),   # Cairo belt (medium)
            rng.uniform(27.5, 29.5, 30),   # Middle Egypt (high)
            rng.uniform(24.0, 27.5, 25),   # Upper Egypt (high)
            rng.uniform(22.0, 24.0, 19),   # Deep south / New Valley (extreme)
        ])
        np.random.shuffle(lats)  # type: ignore[arg-type]
        lats = lats[:n_locations]

        rows_per_loc = 12   # 4 eff × 3 tilt
        n = n_locations * rows_per_loc

        # Climate values correlated with latitude
        # Farther south → higher GHI, lower humidity, higher dust
        ghi_base  = 7.5 - (lats - 22.0) * (3.0 / 9.5)          # ~7.5 south, ~5 north
        ghi_base  = np.clip(ghi_base, 4.5, 7.5)
        temp_base = 35.0 - (lats - 22.0) * (0.7)                # hotter south
        temp_base = np.clip(temp_base, 18.0, 38.0)
        dust_base = 0.15 - (lats - 22.0) * (0.12 / 9.5)         # dustier south
        dust_base = np.clip(dust_base, 0.03, 0.15)
        hum_base  = 25.0 + (lats - 22.0) * (4.5)                # more humid north
        hum_base  = np.clip(hum_base, 20.0, 70.0)

        # Add realistic noise
        ghi_loc   = ghi_base  + rng.uniform(-0.3, 0.3, n_locations)
        temp_loc  = temp_base + rng.uniform(-2.0, 2.0, n_locations)
        dust_loc  = dust_base + rng.uniform(-0.01, 0.01, n_locations)
        hum_loc   = hum_base  + rng.uniform(-5.0, 5.0, n_locations)
        wind_loc  = rng.uniform(2.0, 6.5, n_locations)
        max_t_loc = temp_loc  + rng.uniform(5.0, 12.0, n_locations)

        # Tile per location
        ghi_r   = np.repeat(ghi_loc,  rows_per_loc)
        temp_r  = np.repeat(temp_loc, rows_per_loc)
        dust_r  = np.repeat(dust_loc, rows_per_loc)
        hum_r   = np.repeat(hum_loc,  rows_per_loc)
        wind_r  = np.repeat(wind_loc, rows_per_loc)
        max_t_r = np.repeat(max_t_loc, rows_per_loc)
        lat_r   = np.repeat(lats,     rows_per_loc)
        loc_ids = np.repeat(np.arange(n_locations), rows_per_loc)

        # Vary panel parameters across the 12 combinations per location
        effs  = [0.20, 0.20, 0.20, 0.21, 0.21, 0.21, 0.22, 0.22, 0.22, 0.23, 0.23, 0.23]
        tilts_offset = [-5, 0, 5] * 4
        eff_r   = np.tile(effs, n_locations).astype(float)
        tilt_r  = lat_r + np.tile(tilts_offset, n_locations)
        temp_c_r = np.full(n, -0.32)

        # Target: specific yield = GHI×365×PR×(1-temp_loss)×(1-dust) + noise
        temp_loss_r = np.maximum(0.0, (temp_r - 25) * np.abs(temp_c_r) * 0.01)
        y = (ghi_r * 365 * 0.86 * (1 - temp_loss_r) * (1 - dust_r)
             * rng.uniform(0.97, 1.03, n))

        X = np.column_stack([ghi_r, temp_r, max_t_r, hum_r, wind_r,
                              dust_r, lat_r, tilt_r, eff_r, temp_c_r])

        # Train using the standard train() method with this data
        # (monkey-patch prepare_training_data to use synthetic data)
        _orig = self.prepare_training_data

        def _synthetic_prep():
            loc_names = [f'EgyptLoc_{i}' for i in loc_ids]
            return X, y, loc_ids, loc_names

        self.prepare_training_data = _synthetic_prep

        try:
            if verbose:
                print(f"  Training on {n} synthetic samples from {n_locations} locations…")

            # Use tqdm progress bar if available
            if _have_tqdm and verbose:
                steps = ['Preparing data', 'Training RF (300 trees)', 'Evaluating', 'Saving']
                with _tqdm(total=len(steps), desc='Random Forest', unit='step') as pbar:
                    for step in steps:
                        pbar.set_description(f'RF: {step}')
                        if step == 'Training RF (300 trees)':
                            metrics = self.train(verbose=verbose)
                        elif step == 'Saving':
                            import joblib as jl
                            os.makedirs(MODELS_DIR, exist_ok=True)
                            # Save under canonical name yield_predictor.pkl
                            canonical = os.path.join(MODELS_DIR, 'yield_predictor.pkl')
                            jl.dump({
                                'model':    self.model,
                                'scaler':   self.scaler,
                                'metrics':  self._metrics,
                                'features': self.FEATURES,
                                'target':   self.TARGET,
                            }, canonical)
                            jl.dump({
                                'model':    self.model,
                                'scaler':   self.scaler,
                                'metrics':  self._metrics,
                                'features': self.FEATURES,
                                'target':   self.TARGET,
                            }, self._model_path)
                            logger.info("RF saved → %s (and yield_predictor.pkl)", self._model_path)
                        pbar.update(1)
            else:
                metrics = self.train(verbose=verbose)
                import joblib as jl
                os.makedirs(MODELS_DIR, exist_ok=True)
                canonical = os.path.join(MODELS_DIR, 'yield_predictor.pkl')
                jl.dump({
                    'model':    self.model,
                    'scaler':   self.scaler,
                    'metrics':  self._metrics,
                    'features': self.FEATURES,
                    'target':   self.TARGET,
                }, canonical)
                jl.dump({
                    'model':    self.model,
                    'scaler':   self.scaler,
                    'metrics':  self._metrics,
                    'features': self.FEATURES,
                    'target':   self.TARGET,
                }, self._model_path)
                logger.info("RF saved → %s (and yield_predictor.pkl)", self._model_path)
        finally:
            self.prepare_training_data = _orig

        return metrics

    # ── Inference ─────────────────────────────────────────────────────────────

    def _load(self) -> bool:
        if self.model is not None:
            return True
        if not os.path.exists(self._model_path):
            return False
        import joblib
        try:
            data = joblib.load(self._model_path)
            self.model   = data['model']
            self.scaler  = data['scaler']
            self._metrics = data.get('metrics', {})
            return True
        except Exception as e:
            logger.error("Failed to load yield predictor V2 model: %s", e)
            return False

    def predict(self, features: dict, system_kw: float = 10.0) -> dict:
        """
        Predict annual yield for a given system.

        Parameters
        ----------
        features  : dict with keys matching self.FEATURES (no system_kw)
        system_kw : installed capacity [kW] — used ONLY to scale the output

        Returns
        -------
        dict:
            specific_yield_kwh_per_kwp  – kWh/kWp/year (model output)
            predicted_annual_kwh        – total kWh = specific_yield × system_kw
            predicted_monthly           – list[12] monthly kWh values
            confidence_interval         – {low, high} at 90 % CI
            model_metrics               – {r2, mape, rmse}
        """
        if not self._load():
            return self._physics_fallback(features, system_kw)

        x = np.array([[features.get(f, 0.0) for f in self.FEATURES]], dtype=float)
        x_s = self.scaler.transform(x)

        tree_preds = np.array([t.predict(x_s)[0] for t in self.model.estimators_])
        specific_yield = float(tree_preds.mean())
        pred_std       = float(tree_preds.std())

        annual_kwh = specific_yield * system_kw
        monthly    = [round(annual_kwh * w, 1) for w in self._MONTHLY_WEIGHTS]

        return {
            'specific_yield_kwh_per_kwp': round(specific_yield, 1),
            'predicted_annual_kwh':       round(annual_kwh, 1),
            'predicted_monthly':          monthly,
            'confidence_interval': {
                'low':  round(max(0, annual_kwh - 1.645 * pred_std * system_kw), 1),
                'high': round(annual_kwh + 1.645 * pred_std * system_kw, 1),
            },
            'model_metrics': {
                'r2':   round(self._metrics.get('test_r2', 0.0), 4),
                'mape': round(self._metrics.get('test_mape', 0.0), 2),
                'rmse': round(self._metrics.get('test_rmse', 0.0), 1),
            },
        }

    def _physics_fallback(self, features: dict, system_kw: float) -> dict:
        ghi       = features.get('avg_ghi', 5.5)
        temp      = features.get('avg_temperature', 25.0)
        dust      = features.get('dust_risk_score', 0.07)
        temp_c    = features.get('temp_coefficient', -0.32)
        temp_loss = max(0.0, (temp - 25) * abs(temp_c) * 0.01)
        # Specific yield (kWh/kWp) does not depend on panel efficiency.
        specific  = ghi * 365 * (1 - temp_loss) * (1 - dust) * 0.86
        annual    = specific * system_kw
        monthly   = [round(annual * w, 1) for w in self._MONTHLY_WEIGHTS]
        return {
            'specific_yield_kwh_per_kwp': round(specific, 1),
            'predicted_annual_kwh': round(annual, 1),
            'predicted_monthly': monthly,
            'confidence_interval': {'low': round(annual * 0.90, 1), 'high': round(annual * 1.10, 1)},
            'model_metrics': {'r2': 0.0, 'mape': 0.0, 'rmse': 0.0},
        }

    def get_feature_importance(self) -> dict:
        if not self._load():
            return {}
        return {
            f: round(float(imp), 4)
            for f, imp in sorted(
                zip(self.FEATURES, self.model.feature_importances_),
                key=lambda x: x[1], reverse=True,
            )
        }

    def generate_diagnostic_plots(self, save_dir: str = 'results/step1/plots') -> None:
        """
        Generate publication-quality diagnostic plots:
          - Predictions vs. actual scatter
          - Residual distribution
          - Feature importance bar chart
          - Cross-validation R² box plot
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not installed — skipping plots")
            return

        os.makedirs(save_dir, exist_ok=True)

        result = self.prepare_training_data()
        X, y, groups, _ = result

        unique_locs = np.unique(groups)
        rng = np.random.default_rng(42)
        rng.shuffle(unique_locs)
        n_test = max(1, int(len(unique_locs) * 0.20))
        test_locs  = set(unique_locs[:n_test])
        train_locs = set(unique_locs[n_test:])
        test_mask  = np.array([g in test_locs for g in groups])

        X_te_s = self.scaler.transform(X[test_mask])
        y_te   = y[test_mask]
        y_pred = self.model.predict(X_te_s)
        residuals = y_te - y_pred

        # 1 — Predictions vs Actual
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.scatter(y_te, y_pred, alpha=0.6, edgecolors='steelblue',
                   facecolors='lightblue', s=60, linewidths=0.8)
        lim = [min(y_te.min(), y_pred.min()) * 0.95,
               max(y_te.max(), y_pred.max()) * 1.05]
        ax.plot(lim, lim, 'r--', lw=1.5, label='Perfect prediction')
        ax.set_xlabel('Actual Specific Yield (kWh/kWp)', fontsize=13)
        ax.set_ylabel('Predicted Specific Yield (kWh/kWp)', fontsize=13)
        ax.set_title('RF V2 — Predictions vs. Actual\n(test locations only)', fontsize=14)
        r2 = self._metrics.get('test_r2', 0)
        mape = self._metrics.get('test_mape', 0)
        ax.text(0.05, 0.93, f'R² = {r2:.3f}\nMAPE = {mape:.2f}%',
                transform=ax.transAxes, fontsize=12,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.legend(fontsize=11)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'rf_v2_predictions_vs_actual.png'), dpi=150)
        plt.close()

        # 2 — Residual distribution
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(residuals, bins=30, color='steelblue', alpha=0.8, edgecolor='white')
        ax.axvline(0, color='red', linestyle='--', lw=2, label='Zero error')
        ax.set_xlabel('Residual (kWh/kWp)', fontsize=13)
        ax.set_ylabel('Count', fontsize=13)
        ax.set_title('RF V2 — Residual Distribution', fontsize=14)
        ax.text(0.72, 0.90,
                f'μ = {residuals.mean():.1f}\nσ = {residuals.std():.1f}',
                transform=ax.transAxes, fontsize=12,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax.legend(fontsize=11)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'rf_v2_residuals.png'), dpi=150)
        plt.close()

        # 3 — Feature importance
        fi = sorted(zip(self.FEATURES, self.model.feature_importances_),
                    key=lambda x: x[1])
        feats, imps = zip(*fi)
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.barh(feats, imps, color='steelblue', alpha=0.85)
        ax.set_xlabel('Importance', fontsize=13)
        ax.set_title('RF V2 — Feature Importance', fontsize=14)
        for bar, imp in zip(bars, imps):
            ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
                    f'{imp:.3f}', va='center', fontsize=10)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'rf_v2_feature_importance.png'), dpi=150)
        plt.close()

        logger.info("RF V2 diagnostic plots saved to %s", save_dir)

    # ── Synthetic fallback ────────────────────────────────────────────────────

    def _synthetic_data(self):
        """
        Generate realistic synthetic Egyptian data for offline testing.
        Returns (X, y, groups, loc_names) matching real data format.
        """
        rng = np.random.default_rng(42)
        n_locations = 100
        rows_per_loc = 12  # 4 efficiencies × 3 tilts
        n = n_locations * rows_per_loc

        loc_ids  = np.repeat(np.arange(n_locations), rows_per_loc)
        ghi      = np.repeat(rng.uniform(4.5, 7.5,  n_locations), rows_per_loc)
        temp     = np.repeat(rng.uniform(18.0, 35.0, n_locations), rows_per_loc)
        lat      = np.repeat(rng.uniform(22.0, 31.5, n_locations), rows_per_loc)
        hum      = np.repeat(rng.uniform(25.0, 70.0, n_locations), rows_per_loc)
        wind     = np.repeat(rng.uniform(2.0, 6.0,   n_locations), rows_per_loc)
        dust     = np.repeat(rng.uniform(0.03, 0.15, n_locations), rows_per_loc)
        max_t    = temp + rng.uniform(5, 12, n)

        eff       = rng.choice([0.20, 0.21, 0.22, 0.23], n)
        tilt      = lat + rng.uniform(-5, 5, n)
        temp_c    = np.full(n, -0.32)

        temp_loss = np.maximum(0.0, (temp - 25) * np.abs(temp_c) * 0.01)
        # Target = specific yield (no system_kw)
        y = ghi * 365 * eff * (1 - temp_loss) * (1 - dust)
        # Add realistic noise (±3%)
        y *= rng.uniform(0.97, 1.03, n)

        X = np.column_stack([ghi, temp, max_t, hum, wind, dust, lat, tilt, eff, temp_c])
        loc_names = [f'SyntheticLoc_{i}' for i in loc_ids]

        return X, y, loc_ids, loc_names
