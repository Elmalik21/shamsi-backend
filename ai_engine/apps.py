"""
ai_engine/apps.py
==================
Django AppConfig for ai_engine.

Loads all AI models into the ModelRegistry singleton when Django starts.
This ensures every request shares the same in-memory model objects
instead of loading 13 MB .pkl files from disk on each request.
"""
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AiEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_engine'
    verbose_name = 'Shamsi Smart AI Engine'

    def ready(self):
        """
        Called once when Django finishes loading.
        Loads RF + K-Means into the global ModelRegistry.

        We guard with try/except so a missing .pkl never prevents Django
        from starting — the registry falls back to physics models gracefully.
        """
        # Skip during management command introspection (migrate, collectstatic, etc.)
        import sys
        skip_commands = {'migrate', 'makemigrations', 'collectstatic', 'shell',
                         'dbshell', 'check', 'inspectdb', 'showmigrations'}
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        try:
            from ai_engine.model_registry import registry
            results = registry.load_all()
            logger.info(
                "[AiEngineConfig.ready()] Model registry loaded: %s",
                {k: v for k, v in results.items()},
            )
        except Exception as exc:
            # Non-fatal: views will fall back to per-request loading
            logger.warning(
                "[AiEngineConfig.ready()] Registry pre-load failed (non-fatal): %s", exc
            )
