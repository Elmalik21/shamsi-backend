import sys
import os
import django

sys.path.append(r"e:\New folder (2)\shamsi-backend-main")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shamsi_smart.settings.production')
# Make sure to set the production DB URL so it can load the models if needed
os.environ['DATABASE_URL'] = 'postgresql://postgres:oKmkfaeaRLjmPmUCstYfDXgbPejUZEeE@switchback.proxy.rlwy.net:36668/railway'

django.setup()

from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2

def main():
    predictor = EgyptianYieldPredictorV2()
    print("Training Yield Predictor V2 with corrected physical formula...")
    metrics = predictor.train_from_synthetic_data(verbose=True)
    print("Metrics:", metrics)
    print("Done!")

if __name__ == '__main__':
    main()
