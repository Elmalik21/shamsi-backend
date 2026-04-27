# [file name]: solar_data/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
import logging
from .models import Location, DailyClimateData, MonthlySummary

logger = logging.getLogger(__name__)

@receiver(post_save, sender=DailyClimateData)
def update_stats_async(sender, instance, created, **kwargs):
    """
    Update location stats only after transaction commits to avoid locking
    """
    if instance.location_id:
        # استخدام on_commit يضمن أن البيانات حُفظت بالفعل قبل إعادة الحساب
        transaction.on_commit(lambda: _recalc_location(instance.location_id))

def _recalc_location(location_id):
    try:
        loc = Location.objects.get(id=location_id)
        loc.calculate_statistics()
        # مسح الكاش
        cache.delete(f'location_stats_{location_id}')
    except Location.DoesNotExist:
        pass