# api/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    
    def ready(self):
        """
        App is ready - handle signals gracefully
        """
        # لا تحاول استيراد إشارات إذا لم تكن موجودة
        try:
            import api.signals
            logger.info("API signals imported successfully")
        except ImportError:
            # هذا طبيعي - ليس كل التطبيقات تحتاج إشارات
            pass
        except Exception as e:
            logger.debug(f"Could not import API signals: {e}")
    
    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        يجب أن تقبل جميع المعلمات المطلوبة
        """
        return super().get_models(
            include_auto_created=include_auto_created,
            include_swapped=include_swapped
        )