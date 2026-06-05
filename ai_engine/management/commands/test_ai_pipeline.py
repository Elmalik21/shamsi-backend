import os
import time
import tempfile
import cv2
import numpy as np
import traceback
from django.core.management.base import BaseCommand
from ai_engine.model_registry import registry
from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM

class Command(BaseCommand):
    help = 'Runs smoke tests on all AI models to verify pipeline health.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting AI Pipeline Diagnostics...\n'))
        
        # 1. Random Forest (Yield Predictor)
        self.stdout.write(self.style.WARNING('1. Testing Random Forest Yield Predictor'))
        try:
            start = time.time()
            registry.load_all() # Ensure models are loaded
            
            features = {
                'avg_ghi': 6.0,
                'avg_temperature': 25.0,
                'max_temperature': 35.0,
                'avg_humidity': 40.0,
                'avg_wind_speed': 3.5,
                'dust_risk_score': 0.05,
                'latitude': 30.0,
                'tilt_angle': 25.0,
                'panel_efficiency': 0.22,
                'temp_coefficient': -0.32,
                'system_kw': 10.0
            }
            res = registry.yield_predictor.predict(features)
            latency = (time.time() - start) * 1000
            if 'predicted_annual_kwh' in res:
                self.stdout.write(self.style.SUCCESS(f'  [PASS] Output: {res["predicted_annual_kwh"]} kWh | Latency: {latency:.1f} ms\n'))
            else:
                self.stdout.write(self.style.ERROR('  [FAIL] Malformed output\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [FAIL] {e}\n{traceback.format_exc()}'))

        # 2. K-Means (Dust Clusterer)
        self.stdout.write(self.style.WARNING('2. Testing Dust Clusterer'))
        try:
            start = time.time()
            res = registry.dust_clusterer.predict_zone(1)
            latency = (time.time() - start) * 1000
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Output: {res["cluster_name"]} ({res["risk_level"]} Risk) | Latency: {latency:.1f} ms\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [FAIL] {e}\n{traceback.format_exc()}'))

        # 3. YOLOv8 (Roof Detector)
        self.stdout.write(self.style.WARNING('3. Testing YOLOv8 Roof Detector'))
        tmp_path = None
        try:
            start = time.time()
            # Create a dummy image
            fd, tmp_path = tempfile.mkstemp(suffix='.jpg')
            os.close(fd)
            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            # draw a white square to simulate a roof
            cv2.rectangle(dummy_img, (200, 200), (440, 440), (255, 255, 255), -1)
            cv2.imwrite(tmp_path, dummy_img)
            
            detector = EgyptianRoofDetector()
            res = detector.detect_roof(tmp_path)
            latency = (time.time() - start) * 1000
            
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Usable Area: {res["usable_area_m2"]} m² | Panels: {res["panel_layout"]["max_panels"]} | Latency: {latency:.1f} ms\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [FAIL] {e}\n{traceback.format_exc()}'))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 4. CNN-LSTM
        self.stdout.write(self.style.WARNING('4. Testing CNN-LSTM Predictor'))
        try:
            start = time.time()
            import torch
            model = SolarYieldCNNLSTM()
            net = model.get_net(torch.device('cpu'))
            net.eval()
            dummy_sequence = torch.ones((1, 365, 5), dtype=torch.float32)
            with torch.no_grad():
                res_monthly = net(dummy_sequence)[0].numpy()
            predicted_annual_kwh = float(sum(res_monthly)) * 10.0
            latency = (time.time() - start) * 1000
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Output: {predicted_annual_kwh:.1f} kWh | Latency: {latency:.1f} ms\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [FAIL] {e}\n{traceback.format_exc()}'))

        self.stdout.write(self.style.NOTICE('Diagnostic Pipeline Finished!'))
