# solar_data/apps.py

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


class SolarDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'solar_data'
    verbose_name = _("Solar Data Management")
    
    def ready(self):
        """
        App is ready - import signals and other startup code
        """
        # لا تقم بتنفيذ أي استعلامات قاعدة بيانات هنا
        # فقط استورد الإشارات إذا كانت موجودة
        try:
            # Import signal handlers
            import solar_data.signals
            logger.info("Solar Data signals imported successfully")
        except ImportError as e:
            # لا بأس إذا لم تكن هناك إشارات
            pass
        except Exception as e:
            logger.debug(f"Could not import solar_data signals: {e}")
    
    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        Override get_models to handle cacheops compatibility
        يجب أن تقبل جميع المعلمات المطلوبة
        """
        # Call parent method with all required parameters
        return super().get_models(
            include_auto_created=include_auto_created,
            include_swapped=include_swapped
        )