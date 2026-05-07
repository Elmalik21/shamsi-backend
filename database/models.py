# database/models.py
# NOTE: This app is NOT in INSTALLED_APPS and is not used in production.
# GIS import replaced with stub — PostGIS not available on Railway free tier.
from django.db import models
gis_models = models  # Stub: replaces django.contrib.gis.db import

class EgyptianCity(models.Model):
    """المدن المصرية بتصنيف ذكي"""
    
    CITY_SIZES = [
        ('XXL', 'كبير جداً'),
        ('XL', 'كبير'),
        ('M', 'متوسط'),
        ('S', 'صغير'),
    ]
    
    city_id = models.AutoField(primary_key=True)
    name_ar = models.CharField(max_length=100, verbose_name="اسم المدينة")
    name_en = models.CharField(max_length=100, verbose_name="City Name")
    
    # التصنيف الذكي
    size_category = models.CharField(max_length=3, choices=CITY_SIZES, verbose_name="حجم المدينة")
    smart_points = models.IntegerField(verbose_name="عدد النقاط الذكية")
    
    # الجغرافيا
    center_lat = models.FloatField(verbose_name="خط العرض المركزي")
    center_lon = models.FloatField(verbose_name="خط الطول المركزي")
    governorate = models.CharField(max_length=100, verbose_name="المحافظة")
    region = models.CharField(max_length=50, verbose_name="المنطقة")  # دلتا، صعيد، ساحل
    
    # الإحصائيات
    population = models.IntegerField(null=True, blank=True, verbose_name="عدد السكان")
    area_km2 = models.FloatField(null=True, blank=True, verbose_name="المساحة (كم²)")
    coverage_score = models.FloatField(default=0, verbose_name="درجة التغطية")
    
    # التواريخ
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "مدينة مصرية"
        verbose_name_plural = "المدن المصرية"
        ordering = ['-smart_points', 'name_ar']
        indexes = [
            models.Index(fields=['size_category']),
            models.Index(fields=['region']),
            models.Index(fields=['governorate']),
        ]
    
    def __str__(self):
        return f"{self.name_ar} ({self.get_size_category_display()}) - {self.smart_points} نقطة"

class SmartSamplingPoint(models.Model):
    """نقاط العينات الذكية"""
    
    point_id = models.AutoField(primary_key=True)
    city = models.ForeignKey(EgyptianCity, on_delete=models.CASCADE, related_name='sampling_points')
    
    # موقع النقطة
    point_name = models.CharField(max_length=100, verbose_name="اسم النقطة")
    point_order = models.IntegerField(verbose_name="ترتيب النقطة")
    latitude = models.FloatField(verbose_name="خط العرض")
    longitude = models.FloatField(verbose_name="خط الطول")
    
    # الجيومكانية (للاستخدام المستقبلي مع PostGIS)
    # PointField replaced with TextField — PostGIS not available; lat/lon stored above
    location = models.TextField(null=True, blank=True, verbose_name="الموقع الجغرافي (WKT)")
    
    # الوصف
    description = models.TextField(blank=True, verbose_name="وصف النقطة")
    urban_type = models.CharField(max_length=50, choices=[
        ('URBAN_CENTER', 'مركز حضري'),
        ('RESIDENTIAL', 'سكني'),
        ('INDUSTRIAL', 'صناعي'),
        ('COASTAL', 'ساحلي'),
        ('RURAL', 'ريفي'),
        ('TOURISTIC', 'سياحي'),
    ], verbose_name="نوع المنطقة")
    
    # حالة التحميل
    download_status = models.CharField(max_length=20, choices=[
        ('PENDING', 'قيد الانتظار'),
        ('SUCCESS', 'نجح'),
        ('FAILED', 'فشل'),
        ('PARTIAL', 'جزئي'),
    ], default='PENDING', verbose_name="حالة التحميل")
    
    download_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ التحميل")
    
    class Meta:
        verbose_name = "نقطة عينة ذكية"
        verbose_name_plural = "نقاط العينات الذكية"
        ordering = ['city', 'point_order']
        unique_together = ['city', 'point_name']
        indexes = [
            models.Index(fields=['download_status']),
            models.Index(fields=['urban_type']),
        ]
    
    def __str__(self):
        return f"{self.city.name_ar} - {self.point_name}"

class ClimateData(models.Model):
    """البيانات المناخية اليومية"""
    
    data_id = models.AutoField(primary_key=True)
    sampling_point = models.ForeignKey(SmartSamplingPoint, on_delete=models.CASCADE, related_name='climate_data')
    
    # التاريخ
    date = models.DateField(verbose_name="التاريخ")
    year = models.IntegerField(verbose_name="السنة")
    month = models.IntegerField(verbose_name="الشهر")
    day = models.IntegerField(verbose_name="اليوم")
    day_of_year = models.IntegerField(verbose_name="يوم السنة")
    
    # بيانات الإشعاع الشمسي (من NASA POWER)
    solar_radiation = models.FloatField(verbose_name="الإشعاع الشمسي (كيلوواط/م²/يوم)")
    solar_radiation_monthly_avg = models.FloatField(null=True, blank=True, verbose_name="المتوسط الشهري")
    solar_radiation_annual_avg = models.FloatField(null=True, blank=True, verbose_name="المتوسط السنوي")
    
    # درجات الحرارة
    temperature_avg = models.FloatField(verbose_name="درجة الحرارة المتوسطة (°C)")
    temperature_max = models.FloatField(verbose_name="درجة الحرارة القصوى (°C)")
    temperature_min = models.FloatField(verbose_name="درجة الحرارة الدنيا (°C)")
    
    # رطوبة ورياح
    relative_humidity = models.FloatField(verbose_name="الرطوبة النسبية (%)")
    wind_speed = models.FloatField(verbose_name="سرعة الرياح (م/ث)")
    
    # عوامل مصرية خاصة
    dust_index = models.FloatField(default=0, verbose_name="مؤشر الغبار (0-1)")
    cloud_cover = models.FloatField(null=True, blank=True, verbose_name="غطاء السحب (%)")
    
    # جودة البيانات
    data_quality = models.CharField(max_length=20, choices=[
        ('EXCELLENT', 'ممتاز'),
        ('GOOD', 'جيد'),
        ('FAIR', 'متوسط'),
        ('POOR', 'ضعيف'),
    ], default='GOOD', verbose_name="جودة البيانات")
    
    # التحقق
    is_verified = models.BooleanField(default=False, verbose_name="تم التحقق")
    verification_date = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ التحقق")
    
    class Meta:
        verbose_name = "بيانات مناخية"
        verbose_name_plural = "البيانات المناخية"
        ordering = ['sampling_point', 'date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['year', 'month']),
            models.Index(fields=['solar_radiation']),
            models.Index(fields=['temperature_avg']),
        ]
        unique_together = ['sampling_point', 'date']
    
    def __str__(self):
        return f"{self.sampling_point} - {self.date}"

class SolarPotentialAnalysis(models.Model):
    """تحليل الإمكانات الشمسية للمدن"""
    
    analysis_id = models.AutoField(primary_key=True)
    city = models.ForeignKey(EgyptianCity, on_delete=models.CASCADE, related_name='solar_analyses')
    
    # الإحصائيات السنوية
    annual_solar_avg = models.FloatField(verbose_name="متوسط الإشعاع الشمسي السنوي (كيلوواط/م²/يوم)")
    annual_solar_min = models.FloatField(verbose_name="أقل إشعاع سنوي")
    annual_solar_max = models.FloatField(verbose_name="أعلى إشعاع سنوي")
    
    # التحليل الشهري
    best_month = models.IntegerField(verbose_name="أفضل شهر (رقم)")
    best_month_radiation = models.FloatField(verbose_name="إشعاع أفضل شهر")
    worst_month = models.IntegerField(verbose_name="أسوأ شهر (رقم)")
    worst_month_radiation = models.FloatField(verbose_name="إشعاع أسوأ شهر")
    
    # تحليل المواسم
    summer_avg = models.FloatField(verbose_name="متوسط الصيف (يونيو-أغسطس)")
    winter_avg = models.FloatField(verbose_name="متوسط الشتاء (ديسمبر-فبراير)")
    
    # تقييم الغبار (مهم لمصر)
    dust_impact_percentage = models.FloatField(verbose_name="تأثير الغبار (%)")
    cleaning_frequency_recommended = models.IntegerField(verbose_name="تكرار التنظيف المقترح (يوم)")
    
    # تحليل الطاقة المتوقعة
    estimated_energy_kwh_per_kw = models.FloatField(verbose_name="الطاقة المتوقعة (كيلوواط/كيلوواط)")  # لكل كيلوواط مركب
    capacity_factor = models.FloatField(verbose_name="عامل السعة (%)")
    
    # التصنيف
    solar_potential_class = models.CharField(max_length=20, choices=[
        ('EXCELLENT', 'ممتاز (>6 kWh/m²/day)'),
        ('VERY_GOOD', 'جيد جداً (5.5-6)'),
        ('GOOD', 'جيد (5-5.5)'),
        ('MODERATE', 'متوسط (4.5-5)'),
        ('FAIR', 'مقبول (4-4.5)'),
    ], verbose_name="تصنيف الإمكانات الشمسية")
    
    # بيانات الحساب
    calculation_date = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الحساب")
    calculation_method = models.CharField(max_length=100, default="NASA_POWER_SmartSampling", verbose_name="طريقة الحساب")
    
    class Meta:
        verbose_name = "تحليل إمكانات شمسية"
        verbose_name_plural = "تحليلات الإمكانات الشمسية"
        ordering = ['-annual_solar_avg']
        indexes = [
            models.Index(fields=['solar_potential_class']),
            models.Index(fields=['annual_solar_avg']),
        ]
    
    def __str__(self):
        return f"{self.city.name_ar}: {self.annual_solar_avg:.2f} kWh/m²/day ({self.get_solar_potential_class_display()})"