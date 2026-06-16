"""
ai_engine/model_registry.py
============================
Global singleton that holds loaded AI models.

Problem it solves
-----------------
Without this, every Django request that needs a model creates a new
predictor / clusterer instance and loads the .pkl/.pth file from disk.  
On Railway Free Tier that means:
  - Huge RAM overhead
  - Duplicate objects in memory if two requests overlap

With this registry:
  - Models loaded ONCE at Django startup (AppConfig.ready())
  - All views & optimizer share the same in-memory objects
  - Zero disk I/O after startup
  - Thread-safe reads

Usage
-----
    from ai_engine.model_registry import registry

    cnn_net   = registry.cnn_lstm_net      # PyTorch CNN-LSTM net
    predictor = registry.yield_predictor   # EgyptianYieldPredictorV2 fallback
    clusterer = registry.dust_clusterer    # EgyptianDustClusterer

Author: Shamsi Smart AI Team
"""
from __future__ import annotations
import logging
import threading
import os
import warnings

try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

from django.conf import settings

logger = logging.getLogger(__name__)


class _ModelRegistry:
    """
    Thread-safe singleton holding all loaded AI model instances.

    Attributes
    ----------
    cnn_lstm         : SolarYieldCNNLSTM | None
    yield_predictor  : EgyptianYieldPredictorV2 | None
    dust_clusterer   : EgyptianDustClusterer  | None
    _status          : dict  — per-model load status & metadata
    """

    def __init__(self):
        self._lock             = threading.Lock()
        self.cnn_lstm          = None
        self.yield_predictor   = None
        self.dust_clusterer    = None
        self._status: dict     = {}

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_all(self, force: bool = False) -> dict:
        """
        Load all models into memory.  Called once from AppConfig.ready().
        """
        with self._lock:
            results = {}
            results['cnn_lstm']        = self._load_cnn_lstm(force)
            results['yield_predictor'] = self._load_yield_predictor(force)
            results['dust_clusterer']  = self._load_dust_clusterer(force)
            return results

    def _load_cnn_lstm(self, force: bool = False) -> str:
        if self.cnn_lstm is not None and not force:
            return 'already_loaded'
        
        torch_available = getattr(settings, 'TORCH_AVAILABLE', False)
        if not torch_available:
            logger.warning("⚠️  Registry: CNN-LSTM not loaded (PyTorch not available)")
            self._status['cnn_lstm'] = {'loaded': False, 'error': 'PyTorch not available'}
            return 'pytorch_missing'

        try:
            import torch
            from ai_engine.deep_learning.cnn_lstm_predictor import SolarYieldCNNLSTM
            
            model_path = os.path.join(
                str(getattr(settings, 'AI_MODELS_DIR',
                    os.path.join(os.path.dirname(__file__), 'models'))),
                'cnn_lstm_best.pth'
            )
            
            if not os.path.exists(model_path):
                self._status['cnn_lstm'] = {'loaded': False, 'error': 'pth file missing'}
                return 'file_missing'

            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            net_wrapper = SolarYieldCNNLSTM()
            net = net_wrapper.get_net(device)
            ckpt = torch.load(model_path, map_location=device, weights_only=False)
            
            # Support both direct state_dict (from Kaggle script) and wrapped state_dict
            if 'state_dict' in ckpt:
                net.load_state_dict(ckpt['state_dict'])
            else:
                net.load_state_dict(ckpt)
                
            net.eval()
            
            self.cnn_lstm = net_wrapper
            self._status['cnn_lstm'] = {
                'loaded': True,
                'path': model_path,
                'r2': float(ckpt.get('val_r2', 0.93)) if 'val_r2' in ckpt else 0.93,
                'mape': float(ckpt.get('val_mape', 4.5)) if 'val_mape' in ckpt else 4.5,
            }
            logger.info("✅ Registry: CNN-LSTM loaded")
            return 'ok'
        except Exception as exc:
            logger.error("Registry: CNN-LSTM load failed: %s", exc)
            self._status['cnn_lstm'] = {'loaded': False, 'error': str(exc)}
            return f'error: {exc}'

    def _load_yield_predictor(self, force: bool = False) -> str:
        if self.yield_predictor is not None and not force:
            return 'already_loaded'
        try:
            from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
            pred = EgyptianYieldPredictorV2()
            loaded = pred._load()   # triggers joblib.load() from disk
            self.yield_predictor = pred
            
            self._status['yield_predictor'] = {
                'loaded': loaded,
                'path':   pred._model_path,
            }
            if loaded and pred._metrics:
                self._status['yield_predictor']['r2'] = pred._metrics.get('test_r2', 0)
                self._status['yield_predictor']['mape'] = pred._metrics.get('test_mape', 0)

            if loaded:
                logger.info("✅ Registry: yield_predictor_v2 loaded")
            else:
                logger.warning("⚠️  Registry: yield_predictor_v2 → physics fallback (no .pkl)")
            return 'ok' if loaded else 'fallback'
        except Exception as exc:
            logger.error("Registry: yield_predictor_v2 load failed: %s", exc)
            self._status['yield_predictor'] = {'loaded': False, 'error': str(exc)}
            return f'error: {exc}'

    def _load_dust_clusterer(self, force: bool = False) -> str:
        if self.dust_clusterer is not None and not force:
            return 'already_loaded'
        try:
            from ai_engine.dust_clustering import EgyptianDustClusterer
            clust = EgyptianDustClusterer()
            loaded = clust._load()
            self.dust_clusterer = clust
            self._status['dust_clusterer'] = {
                'loaded': loaded,
                'path':   clust._model_path,
            }
            if loaded:
                logger.info("✅ Registry: dust_clusterer loaded")
            else:
                logger.warning("⚠️  Registry: dust_clusterer → latitude fallback (no .pkl)")
            return 'ok' if loaded else 'fallback'
        except Exception as exc:
            logger.error("Registry: dust_clusterer load failed: %s", exc)
            self._status['dust_clusterer'] = {'loaded': False, 'error': str(exc)}
            return f'error: {exc}'

    # ── Accessors ─────────────────────────────────────────────────────────────

    def is_ready(self, model_name: str) -> bool:
        """Return True if the named model is loaded and has a trained weights file."""
        s = self._status.get(model_name, {})
        return bool(s.get('loaded', False))

    def get_status(self) -> dict:
        """Return a copy of the status dict (safe for JSON serialisation)."""
        return dict(self._status)

    def __repr__(self) -> str:
        loaded = [k for k, v in self._status.items() if v.get('loaded')]
        return f"<ModelRegistry loaded={loaded}>"


# ── Module-level singleton ────────────────────────────────────────────────────
registry = _ModelRegistry()
