"""
ai_engine/model_registry.py
============================
Global singleton that holds loaded AI models.

Problem it solves
-----------------
Without this, every Django request that needs a model creates a new
EgyptianYieldPredictor() / EgyptianDustClusterer() instance and loads
the .pkl file from disk.  On Railway Free Tier that means:
  - 13 MB joblib.load() per request for RF
  - Duplicate objects in memory if two requests overlap

With this registry:
  - Models loaded ONCE at Django startup (AppConfig.ready())
  - All views & optimizer share the same in-memory objects
  - Zero disk I/O after startup
  - Thread-safe reads (scikit-learn predict() is GIL-safe for read-only)

Usage
-----
    from ai_engine.model_registry import registry

    predictor = registry.yield_predictor   # pre-loaded EgyptianYieldPredictor
    clusterer = registry.dust_clusterer    # pre-loaded EgyptianDustClusterer

    # Check if a model is available
    if registry.is_ready('yield_predictor'):
        result = predictor.predict(features)

Author: Shamsi Smart AI Team
"""
from __future__ import annotations
import logging
import threading

logger = logging.getLogger(__name__)


class _ModelRegistry:
    """
    Thread-safe singleton holding all loaded AI model instances.

    Attributes
    ----------
    yield_predictor  : EgyptianYieldPredictor | None
    dust_clusterer   : EgyptianDustClusterer  | None
    _status          : dict  — per-model load status & metadata
    """

    def __init__(self):
        self._lock            = threading.Lock()
        self.yield_predictor  = None
        self.dust_clusterer   = None
        self._status: dict    = {}

    # ── Loading ───────────────────────────────────────────────────────────────

    def load_all(self, force: bool = False) -> dict:
        """
        Load all models into memory.  Called once from AppConfig.ready().

        Parameters
        ----------
        force : bool  Re-load even if already loaded (use for hot-reload).

        Returns
        -------
        dict  Summary of load results.
        """
        with self._lock:
            results = {}
            results['yield_predictor'] = self._load_yield_predictor(force)
            results['dust_clusterer']  = self._load_dust_clusterer(force)
            return results

    def _load_yield_predictor(self, force: bool = False) -> str:
        if self.yield_predictor is not None and not force:
            return 'already_loaded'
        try:
            from ai_engine.yield_predictor import EgyptianYieldPredictor
            pred = EgyptianYieldPredictor()
            loaded = pred._load()   # triggers joblib.load() from disk
            self.yield_predictor = pred
            self._status['yield_predictor'] = {
                'loaded': loaded,
                'r2':     pred._model_r2,
                'mape':   pred._model_mape,
                'path':   pred._model_path,
            }
            if loaded:
                logger.info("✅ Registry: yield_predictor loaded (R²=%.4f)", pred._model_r2 or 0)
            else:
                logger.warning("⚠️  Registry: yield_predictor → physics fallback (no .pkl)")
            return 'ok' if loaded else 'fallback'
        except Exception as exc:
            logger.error("Registry: yield_predictor load failed: %s", exc)
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
