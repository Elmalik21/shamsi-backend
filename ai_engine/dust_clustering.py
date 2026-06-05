"""
ai_engine/dust_clustering.py
K-Means clustering of Egyptian locations into dust/soiling zones.
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
    K-Means clustering of Egyptian locations into dust zones.
    Zones: LOW, MEDIUM, HIGH, EXTREME

    Cluster assignments are based on:
      - avg_dust_risk_score (from DailyClimateData)
      - avg_humidity
      - avg_wind_speed
      - latitude (proxy for desert proximity)

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
          [avg_dust_risk, avg_humidity, avg_wind, latitude]
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
            rows.append([dust, hum, wind, loc.latitude])
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
        Train K-Means on DailyClimateData features.
        Assigns cluster centres to named dust zones by latitude ordering.
        """
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            raise ImportError("scikit-learn required: pip install scikit-learn")

        X, loc_ids = self._build_training_data()

        if X is None or len(X) < 4:
            logger.warning("Not enough location data — using latitude-rule fallback only.")
            return False

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        km = KMeans(n_clusters=4, random_state=42, n_init=10, max_iter=300)
        km.fit(X_scaled)

        # Re-label clusters by ascending dust risk (centre[:,0] = avg_dust col)
        centres_orig = scaler.inverse_transform(km.cluster_centers_)
        order = np.argsort(centres_orig[:, 0])   # sort by avg_dust ascending
        remap = {old: new for new, old in enumerate(order)}
        km.labels_ = np.array([remap[l] for l in km.labels_])
        # Re-order cluster centres to match LOW=0..EXTREME=3
        km.cluster_centers_ = km.cluster_centers_[order]

        self.model = km
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
        Generate 119 synthetic Egyptian locations, train K-Means (k=4),
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
            from sklearn.cluster import KMeans
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

        # Derive realistic climate features from latitude
        dust  = 0.15 - (lats - 22.0) * (0.12 / 9.5) + rng.uniform(-0.015, 0.015, n_locations)
        hum   = 25.0 + (lats - 22.0) * (4.5)         + rng.uniform(-5.0,   5.0,   n_locations)
        wind  = 3.0  + rng.uniform(-1.0, 2.5, n_locations)

        dust = np.clip(dust, 0.02, 0.18)
        hum  = np.clip(hum,  15.0, 75.0)
        wind = np.clip(wind,  1.0, 10.0)

        # Feature matrix: [avg_dust, avg_humidity, avg_wind, latitude]
        X = np.column_stack([dust, hum, wind, lats])

        if verbose:
            print(f"\n  Training K-Means on {n_locations} synthetic Egyptian locations...")

        scaler   = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        metrics = {}
        steps = ['Scaling features', 'K-Means fit (k=4)', 'Re-labelling zones', 'Saving']
        _iter = (_tqdm(steps, desc='K-Means', unit='step')
                 if (_have_tqdm and verbose) else steps)

        km = None
        for step in _iter:
            if step == 'K-Means fit (k=4)':
                km = KMeans(n_clusters=4, random_state=42, n_init=10, max_iter=300)
                km.fit(X_scaled)
            elif step == 'Re-labelling zones':
                # Re-label clusters by ascending dust risk (column 0 = dust)
                centres_orig = scaler.inverse_transform(km.cluster_centers_)
                order = np.argsort(centres_orig[:, 0])
                remap = {int(old): new for new, old in enumerate(order)}
                km.labels_ = np.array([remap[int(l)] for l in km.labels_])
                km.cluster_centers_ = km.cluster_centers_[order]

                # Metrics
                sil = float(silhouette_score(X_scaled, km.labels_))
                metrics = {
                    'inertia':          round(float(km.inertia_), 2),
                    'silhouette_score': round(sil, 4),
                    'n_locations':      n_locations,
                    'cluster_counts': {
                        self.DUST_ZONES[i]['name']: int(np.sum(km.labels_ == i))
                        for i in range(4)
                    },
                }

                if verbose:
                    print(f"\n  K-Means Results:")
                    print(f"    Inertia      : {metrics['inertia']:.2f}")
                    print(f"    Silhouette   : {sil:.4f}")
                    for zone_name, count in metrics['cluster_counts'].items():
                        print(f"    {zone_name:<10}: {count} locations")

            elif step == 'Saving':
                import joblib
                self.model  = km
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

        if self._load():
            agg = DailyClimateData.objects.filter(location=loc).aggregate(
                avg_dust=Avg('dust_risk_score'),
                avg_hum=Avg('rh2m'),
                avg_wind=Avg('ws2m'),
            )
            dust = agg['avg_dust']  or self._latitude_dust_default(loc.latitude)
            hum  = agg['avg_hum']   or 40.0
            wind = agg['avg_wind']  or 3.0

            x   = np.array([[dust, hum, wind, loc.latitude]])
            x_s = self.scaler.transform(x)

            # Hard cluster for zone name / cleaning schedule
            cluster = int(self.model.predict(x_s)[0])

            # Soft membership: distances to all cluster centres → weighted factor
            # This gives a smoother, more accurate dust factor than a discrete jump.
            # e.g. a location 80% MEDIUM / 20% HIGH → factor = 0.80×0.07 + 0.20×0.11 = 0.078
            distances    = self.model.transform(x_s)[0]          # (4,) distance to each centre
            inv_dist     = 1.0 / (distances + 1e-8)              # inverse distance weights
            memberships  = inv_dist / inv_dist.sum()              # normalise to sum=1
            zone_factors = [self.DUST_ZONES[i]['factor'] for i in range(4)]
            weighted_factor = float(np.dot(memberships, zone_factors))

        else:
            cluster         = self._latitude_to_cluster(loc.latitude)
            weighted_factor = self.DUST_ZONES[cluster]['factor']
            memberships     = None

        zone = dict(self.DUST_ZONES[cluster])
        zone['location_id']     = location_id
        zone['governorate']     = loc.governorate.name if loc.governorate else ''
        # Soft-weighted factor is more accurate than the hard cluster value
        zone['factor']          = round(weighted_factor, 4)
        if memberships is not None:
            zone['memberships'] = [round(float(m), 3) for m in memberships]
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
        labels = self.model.labels_
        for idx, info in self.DUST_ZONES.items():
            count = int(np.sum(labels == idx))
            print(f"  Cluster {idx} [{info['name']:8s}]: {count} locations")
