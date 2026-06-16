"""
ai_engine/dust_clustering.py
Gaussian Mixture Model (GMM) clustering of Egyptian locations into dust/soiling zones.
Model 3 — Dust Zone Classifier
"""
from __future__ import annotations
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')


class EgyptianDustClusterer:
    """
    Gaussian Mixture Model (GMM) clustering of Egyptian locations into dust zones.
    Zones: LOW, MEDIUM, HIGH, EXTREME

    Cluster assignments are based on:
      - avg_dust_risk_score (from DailyClimateData)
      - avg_humidity
      - avg_wind_speed
      - latitude & longitude (geographical proxy for environment)

    Reference centres are calibrated on Egyptian geography:
      - LOW    : Nile Delta / Alexandria winter
      - MEDIUM : Cairo, Giza, Upper Delta
      - HIGH   : Sohag, Minya, Luxor
      - EXTREME: Aswan, New Valley, Sinai
    """

    DUST_ZONES = {
        0: {'name': 'LOW',     'factor': 0.03, 'cleaning_days': 45,
            'description': 'Nile Delta, Alexandria winter'},
        1: {'name': 'MEDIUM',  'factor': 0.07, 'cleaning_days': 21,
            'description': 'Cairo, Giza, Upper Delta'},
        2: {'name': 'HIGH',    'factor': 0.11, 'cleaning_days': 14,
            'description': 'Sohag, Minya, Luxor'},
        3: {'name': 'EXTREME', 'factor': 0.15, 'cleaning_days': 10,
            'description': 'Aswan, New Valley, Sinai'},
    }

    # Rule-based latitude thresholds for fallback / synthetic training
    # (latitude in Egypt: 22°N south → 31.5°N north)
    _LAT_THRESHOLDS = [
        (31.0, 0),   # >= 31° → LOW (Delta)
        (29.5, 1),   # >= 29.5° → MEDIUM (Cairo belt)
        (26.0, 2),   # >= 26° → HIGH (Upper Egypt)
        (0.0,  3),   # < 26° → EXTREME (Deep south)
    ]

    def __init__(self):
        self.model = None
        self.scaler = None
        self._model_path = os.path.join(MODELS_DIR, 'dust_clusterer.pkl')

    # ── Training ──────────────────────────────────────────────────────────────

    def _build_training_data(self):
        """
        Query DailyClimateData and aggregate per location.
        Returns (X, location_ids) where X has columns:
          [avg_dust_risk, avg_humidity, avg_wind, latitude, longitude]
        """
        from solar_data.models import DailyClimateData, Location
        from django.db.models import Avg

        locations = list(Location.objects.all().select_related('governorate'))
        if not locations:
            return None, []

        rows = []
        loc_ids = []
        for loc in locations:
            agg = DailyClimateData.objects.filter(location=loc).aggregate(
                avg_dust=Avg('dust_risk_score'),
                avg_hum=Avg('rh2m'),
                avg_wind=Avg('ws2m'),
            )
            dust  = agg['avg_dust']  or self._latitude_dust_default(loc.latitude)
            hum   = agg['avg_hum']   or 40.0
            wind  = agg['avg_wind']  or 3.0
            rows.append([dust, hum, wind, loc.latitude, loc.longitude])
            loc_ids.append(loc.location_id)

        return np.array(rows, dtype=float), loc_ids

    def _latitude_dust_default(self, lat: float) -> float:
        """Simple latitude-based dust risk estimate when no data available."""
        if lat >= 31.0:
            return 0.03
        elif lat >= 29.5:
            return 0.07
        elif lat >= 26.0:
            return 0.11
        return 0.15

    def train(self):
        """
        Train GMM on DailyClimateData features.
        Assigns cluster centres to named dust zones by dust ordering.
        """
        try:
            from sklearn.mixture import GaussianMixture
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            raise ImportError("scikit-learn required: pip install scikit-learn")

        X, loc_ids = self._build_training_data()

        if X is None or len(X) < 4:
            logger.warning("Not enough location data — using latitude-rule fallback only.")
            return False

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        gmm = GaussianMixture(n_components=4, covariance_type='full', random_state=42, n_init=5, max_iter=300)
        gmm.fit(X_scaled)

        # Re-label clusters by ascending dust risk (means_[:,0] = avg_dust col)
        centres_orig = scaler.inverse_transform(gmm.means_)
        order = np.argsort(centres_orig[:, 0])   # sort by avg_dust ascending
        
        # Re-order GMM internal arrays so predict() maps directly to 0=LOW .. 3=EXTREME
        gmm.means_ = gmm.means_[order]
        gmm.weights_ = gmm.weights_[order]
        gmm.covariances_ = gmm.covariances_[order]
        gmm.precisions_cholesky_ = gmm.precisions_cholesky_[order]
        if hasattr(gmm, 'precisions_'):
            gmm.precisions_ = gmm.precisions_[order]

        self.model = gmm
        self.scaler = scaler

        logger.info("Dust clusterer trained on %d locations.", len(loc_ids))
        return True

    def train_and_save(self):
        """Train model and persist to disk."""
        import joblib
        os.makedirs(MODELS_DIR, exist_ok=True)
        success = self.train()
        if success:
            joblib.dump({'model': self.model, 'scaler': self.scaler}, self._model_path)
            logger.info("Dust clusterer saved to %s", self._model_path)
        return success

    def train_from_synthetic_data(self, verbose: bool = True):
        """
        Generate 119 synthetic Egyptian locations, train GMM (n=4),
        and save to ai_engine/models/dust_clusterer.pkl.

        The synthetic locations cover all four Egyptian dust zones:
          - LOW     : Nile Delta (lat >= 31 deg)
          - MEDIUM  : Cairo belt (29.5-31 deg)
          - HIGH    : Upper Egypt (26-29.5 deg)
          - EXTREME : Deep south / New Valley (< 26 deg)

        Returns
        -------
        (success: bool, metrics: dict)
        """
        try:
            from sklearn.mixture import GaussianMixture
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import silhouette_score
        except ImportError:
            raise ImportError("scikit-learn required: pip install scikit-learn")

        try:
            from tqdm import tqdm as _tqdm
            _have_tqdm = True
        except ImportError:
            _have_tqdm = False

        rng = np.random.default_rng(42)
        n_locations = 119

        # Generate latitude distribution across Egyptian climate zones
        lats = np.concatenate([
            rng.uniform(31.0, 31.5, 15),   # Delta / Alexandria
            rng.uniform(29.5, 31.0, 25),   # Cairo belt
            rng.uniform(26.0, 29.5, 40),   # Upper Egypt
            rng.uniform(22.0, 26.0, 39),   # Deep south
        ])
        np.random.shuffle(lats)  # type: ignore[arg-type]
        lats = lats[:n_locations]
        
        # Approximate longitudes for Egypt (25.0 to 35.0)
        longs = 30.0 + rng.uniform(-4.0, 4.0, n_locations)

        # Derive realistic climate features from latitude
        dust  = 0.15 - (lats - 22.0) * (0.12 / 9.5) + rng.uniform(-0.015, 0.015, n_locations)
        hum   = 25.0 + (lats - 22.0) * (4.5)         + rng.uniform(-5.0,   5.0,   n_locations)
        wind  = 3.0  + rng.uniform(-1.0, 2.5, n_locations)

        dust = np.clip(dust, 0.02, 0.18)
        hum  = np.clip(hum,  15.0, 75.0)
        wind = np.clip(wind,  1.0, 10.0)

        # Feature matrix: [avg_dust, avg_humidity, avg_wind, latitude, longitude]
        X = np.column_stack([dust, hum, wind, lats, longs])

        if verbose:
            print(f"\n  Training Gaussian Mixture Model on {n_locations} synthetic Egyptian locations...")

        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        metrics = {}
        steps = ['Scaling features', 'GMM fit (n=4)', 'Re-labelling zones', 'Saving']
        _iter = (_tqdm(steps, desc='GMM', unit='step')
                 if (_have_tqdm and verbose) else steps)

        gmm = None
        for step in _iter:
            if step == 'GMM fit (n=4)':
                gmm = GaussianMixture(n_components=4, covariance_type='full', random_state=42, n_init=5, max_iter=300)
                gmm.fit(X_scaled)
            elif step == 'Re-labelling zones':
                # Re-label clusters by ascending dust risk (column 0 = dust)
                centres_orig = scaler.inverse_transform(gmm.means_)
                order = np.argsort(centres_orig[:, 0])
                
                gmm.means_ = gmm.means_[order]
                gmm.weights_ = gmm.weights_[order]
                gmm.covariances_ = gmm.covariances_[order]
                gmm.precisions_cholesky_ = gmm.precisions_cholesky_[order]
                if hasattr(gmm, 'precisions_'):
                    gmm.precisions_ = gmm.precisions_[order]
                
                labels = gmm.predict(X_scaled)

                # Metrics
                sil = float(silhouette_score(X_scaled, labels))
                metrics = {
                    'silhouette_score': round(sil, 4),
                    'n_locations':      n_locations,
                    'cluster_counts': {
                        self.DUST_ZONES[i]['name']: int(np.sum(labels == i))
                        for i in range(4)
                    },
                }

                if verbose:
                    print(f"\n  GMM Results:")
                    print(f"    Silhouette   : {sil:.4f}")
                    for zone_name, count in metrics['cluster_counts'].items():
                        print(f"    {zone_name:<10}: {count} locations")

            elif step == 'Saving':
                import joblib
                self.model  = gmm
                self.scaler = scaler
                os.makedirs(MODELS_DIR, exist_ok=True)
                joblib.dump({'model': self.model, 'scaler': self.scaler}, self._model_path)
                joblib.dump({'model': self.model, 'scaler': self.scaler}, self._model_path)
                logger.info("Dust clusterer saved -> %s", self._model_path)

        return True, metrics

    def _load(self):
        """Load model from disk if available."""
        if self.model is not None:
            return True
        if not os.path.exists(self._model_path):
            logger.warning(
                "Dust clusterer model not found at %s — using latitude-rule fallback. "
                "Run scripts/step1_full_pipeline.py to train.",
                self._model_path,
            )
            return False
        try:
            import joblib
            data = joblib.load(self._model_path)
            self.model = data['model']
            self.scaler = data['scaler']
            logger.info("✅ Loaded dust clusterer from %s", self._model_path)
            return True
        except Exception as exc:
            logger.error("Failed to load dust clusterer: %s", exc)
            return False

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_zone_by_features(self, lat: float, lon: float, dust: float = None, hum: float = 40.0, wind: float = 3.0) -> dict:
        if dust is None:
            dust = self._latitude_dust_default(lat)

        if self._load():
            x   = np.array([[dust, hum, wind, lat, lon]])
            x_s = self.scaler.transform(x)

            cluster = int(self.model.predict(x_s)[0])
            memberships  = self.model.predict_proba(x_s)[0]
            zone_factors = [self.DUST_ZONES[i]['factor'] for i in range(4)]
            weighted_factor = float(np.dot(memberships, zone_factors))
        else:
            cluster         = self._latitude_to_cluster(lat)
            weighted_factor = self.DUST_ZONES[cluster]['factor']
            memberships     = None

        zone = dict(self.DUST_ZONES[cluster])
        zone['location_id']     = None
        zone['governorate']     = 'Dynamic'
        zone['factor']          = round(weighted_factor, 4)
        if memberships is not None:
            zone['memberships'] = [round(float(m), 3) for m in memberships]
        return zone

    def predict_zone(self, location_id: int) -> dict:
        """
        Return dust zone info for a location.
        Falls back to latitude rule if model not trained.

        Uses soft membership (weighted distances) for a more accurate dust factor
        than a hard cluster assignment — especially for border-zone locations.
        """
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg

        try:
            loc = Location.objects.get(location_id=location_id)
        except Location.DoesNotExist:
            return dict(self.DUST_ZONES[1])  # MEDIUM default

        agg = DailyClimateData.objects.filter(location=loc).aggregate(
            avg_dust=Avg('dust_risk_score'),
            avg_hum=Avg('rh2m'),
            avg_wind=Avg('ws2m'),
        )
        dust = agg['avg_dust']
        hum  = agg['avg_hum']  if agg['avg_hum'] is not None else 40.0
        wind = agg['avg_wind'] if agg['avg_wind'] is not None else 3.0

        zone = self.predict_zone_by_features(loc.latitude, loc.longitude, dust, hum, wind)
        zone['location_id'] = location_id
        zone['governorate'] = loc.governorate.name if loc.governorate else ''
        return zone

    def _latitude_to_cluster(self, lat: float) -> int:
        for threshold, cluster in self._LAT_THRESHOLDS:
            if lat >= threshold:
                return cluster
        return 3

    def get_all_zones(self) -> list:
        """Return dust zone dict for every Location in the database."""
        from solar_data.models import Location
        results = []
        for loc in Location.objects.all().select_related('governorate'):
            zone = self.predict_zone(loc.location_id)
            results.append(zone)
        return results

    def print_metrics(self):
        """Print cluster distribution after training."""
        if self.model is None:
            print("Model not trained yet.")
            return
        # Create dummy locations or use a cached labels array if needed.
        # GMM doesn't store labels_ like KMeans.
        print("Model is GMM. Use synthetic generator to view distribution metrics.")
