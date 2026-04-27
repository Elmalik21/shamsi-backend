import datetime
from django.core.management.base import BaseCommand
from django.db.models import Avg, Sum
from solar_data.models import Location, DailyClimateData, MonthlySummary

class Command(BaseCommand):
    help = 'Generate monthly summaries for solar data with fixed model fields'

    def handle(self, *args, **options):
        locations = Location.objects.all()
        self.stdout.write(f"🚀 Starting summary generation for {locations.count()} locations...")

        for loc in locations:
            # الحصول على التواريخ الفريدة (سنة وشهر)
            distinct_months = DailyClimateData.objects.filter(location=loc).values_list('date__year', 'date__month').distinct()
            
            if not distinct_months:
                continue

            for year, month in distinct_months:
                # تجميع البيانات باستخدام الحقول المتوفرة في DailyClimateData
                data = DailyClimateData.objects.filter(
                    location=loc, 
                    date__year=year, 
                    date__month=month
                ).aggregate(
                    avg_rad=Avg('allsky_sfc_sw_dwn'),
                    avg_temp=Avg('t2m'),
                    sum_precip=Sum('prectotcorr')
                )

                # حساب التقييم (Grade) بناءً على الإشعاع
                avg_rad = data['avg_rad'] or 0
                if avg_rad > 6.0: grade = 'A'
                elif avg_rad > 5.0: grade = 'B'
                elif avg_rad > 4.0: grade = 'C'
                else: grade = 'D'

                # التحديث أو الإنشاء باستخدام الحقول الموجودة في MonthlySummary حصراً
                MonthlySummary.objects.update_or_create(
                    location=loc,
                    year=year,
                    month=month,
                    defaults={
                        'avg_radiation': avg_rad,
                        'avg_temperature': data['avg_temp'] or 0,
                        'total_precipitation': data['sum_precip'] or 0,
                        'solar_grade': grade,
                    }
                )
            
            self.stdout.write(f"✅ Processed: {loc.name}")
            
            # تحديث إحصائيات الموقع الكلية بعد إنهاء الأشهر
            loc.calculate_statistics()

        self.stdout.write(self.style.SUCCESS("✨ Monthly summaries generated successfully!"))