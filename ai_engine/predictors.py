import numpy as np
import pandas as pd
import joblib
import os
from datetime import datetime, timedelta
from solar_data.models import DailyClimateData

class SolarEnergyPredictor:
    def __init__(self):
        self.models_dir = 'ai_models/'
        os.makedirs(self.models_dir, exist_ok=True)

    def get_model_path(self, location_id):
        return os.path.join(self.models_dir, f'solar_model_{location_id}.pkl')

    def train_and_save(self, location_id):
        """Train model and save to disk"""
        data = self._fetch_data(location_id)  # returns list of dicts
        if len(data) < 30:
            return False

        radiations = [row['allsky_sfc_sw_dwn'] for row in data if row['allsky_sfc_sw_dwn'] is not None]
        model_data = {
            'mean_radiation': float(np.mean(radiations)) if radiations else 5.5,
            'last_updated': datetime.now()
        }

        joblib.dump(model_data, self.get_model_path(location_id))
        return True

    def predict(self, location_id, days=7):
        """Load model and predict"""
        model_path = self.get_model_path(location_id)
        
        # إذا لم يوجد نموذج، قم بالتدريب
        if not os.path.exists(model_path):
            success = self.train_and_save(location_id)
            if not success:
                return self._fallback_prediction(days)
        
        model = joblib.load(model_path)
        base_value = model.get('mean_radiation', 5.0)
        
        # توليد تنبؤات
        predictions = []
        dates = []
        for i in range(days):
            date = datetime.now() + timedelta(days=i+1)
            dates.append(date.strftime('%Y-%m-%d'))
            # تنبؤ بسيط مع عشوائية
            val = base_value + np.random.normal(0, 0.5)
            predictions.append(max(0, round(val, 2)))
            
        return {
            'dates': dates,
            'predictions': predictions,
            'method': 'Pre-trained Simple Model'
        }

    def _fetch_data(self, location_id):
        """Fetch DailyClimateData for a location and return a list of dicts."""
        qs = DailyClimateData.objects.filter(
            location__location_id=location_id
        ).order_by('date').values('date', 'allsky_sfc_sw_dwn', 't2m', 'dust_risk_score')
        return list(qs)  # always a list, never None

    def _fallback_prediction(self, days):
        """Return a naive fallback when no model is available."""
        predictions = []
        dates = []
        for i in range(days):
            date = datetime.now() + timedelta(days=i + 1)
            dates.append(date.strftime('%Y-%m-%d'))
            predictions.append(round(5.5 + np.random.normal(0, 0.3), 2))
        return {
            'dates': dates,
            'predictions': predictions,
            'method': 'Fallback (no data)'
        }