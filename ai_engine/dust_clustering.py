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

    def _load(self):
        """Load model from disk if available."""
        if self.model is not None:
            return True
        if not os.path.exists(self._model_path):
            return False
        import joblib
        data = joblib.load(self._model_path)
        self.model = data['model']
        self.scaler = data['scaler']
        return True

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict_zone(self, location_id: int) -> dict:
        """
        Return dust zone info for a location.
        Falls back to latitude rule if model not trained.
        """
        from solar_data.models import Location, DailyClimateData
        from django.db.models import Avg

        try:
            loc = Location.objects.get(location_id=location_id)
        except Location.DoesNotExist:
            return self.DUST_ZONES[1]  # MEDIUM default

        if self._load():
            agg = DailyClimateData.objects.filter(location=loc).aggregate(
                avg_dust=Avg('dust_risk_score'),
                avg_hum=Avg('rh2m'),
                avg_wind=Avg('ws2m'),
            )
            dust  = agg['avg_dust']  or self._latitude_dust_default(loc.latitude)
            hum   = agg['avg_hum']   or 40.0
            wind  = agg['avg_wind']  or 3.0
            x = np.array([[dust, hum, wind, loc.latitude]])
            x_s = self.scaler.transform(x)
            cluster = int(self.model.predict(x_s)[0])
        else:
            cluster = self._latitude_to_cluster(loc.latitude)

        zone = dict(self.DUST_ZONES[cluster])
        zone['location_id'] = location_id
        zone['governorate'] = loc.governorate.name
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
