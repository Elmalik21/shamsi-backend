import os
import django
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shamsi_smart.settings')
django.setup()

from ai_engine.nasa_client import fetch_nasa_climate_for_coords
from api.views import PredictYieldView
from rest_framework.test import APIRequestFactory

def run_test():
    factory = APIRequestFactory()

    # Example remote location: Deep in the Western Desert (near East Oweinat)
    lat, lon = 22.5, 28.5

    print("==================================================")
    print(f"1. Testing Direct NASA API Fetch (Lat: {lat}, Lon: {lon})")
    print("==================================================")

    t0 = time.time()
    data = fetch_nasa_climate_for_coords(lat, lon)
    t1 = time.time()

    if data:
        print(f"✅ Success! Data fetched directly from NASA in {t1-t0:.2f} seconds.")
        print(f"   📊 Aggregates calculated: {data['agg']}")
        print(f"   📅 Daily records retrieved: {len(data['daily_records'])} days")
    else:
        print("❌ Direct Fetch failed!")

    print("\n==================================================")
    print("2. Testing Full API Pipeline (PredictYieldView)")
    print("==================================================")

    request = factory.post('/api/v1/ai/predict-yield/', {
        'latitude': lat,
        'longitude': lon,
        'system_kw': 10.0,
        'panel_efficiency': 0.22,
        'tilt_angle': 25.0
    }, format='json')

    view = PredictYieldView.as_view()
    t0 = time.time()
    response = view(request)
    t1 = time.time()

    print(f"📡 API Status Code: {response.status_code}")
    print(f"⏱️ Total API Execution Time: {t1-t0:.2f} seconds")

    if response.status_code == 200:
        res_data = response.data
        print(f"✅ Predicted Annual Yield: {res_data.get('predicted_annual_kwh')} kWh")
        print(f"✅ Predicted Monthly (first 3): {res_data.get('predicted_monthly')[:3]}...")
        print(f"✅ Location Handled As: {res_data.get('location')}")
        print(f"✅ Dust Zone Assigned: {res_data.get('dust_zone')}")
    else:
        print(f"❌ API Error: {response.data}")

if __name__ == '__main__':
    run_test()

