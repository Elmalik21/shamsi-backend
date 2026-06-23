# solar_data/models.py
"""
Shamsi Smart - Core Data Models
Based on Project Documentation: System Design & Implementation
"""
from django.db import models
from django.db.models import Avg, Max, Min, Count, Sum, Q, StdDev
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
import uuid
import logging
import math
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ============================================
# 1. ABSTRACT BASE MODEL (Moved from core)
# ============================================

class BaseModel(models.Model):
    """
    Base model providing UUID, timestamps, and soft-delete capability.
    Aligned with 'Entity-Relationship Diagram' requirements.
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Creation Date"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active Record"))

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def delete(self, *args, **kwargs):
        """Soft delete implementation"""
        self.is_active = False
        self.save()

# ============================================
# 2. MAIN ENTITIES (Governorate & Location)
# ============================================

class Governorate(BaseModel):
    """
    Represents Administrative Governorates (e.g., Cairo, Aswan).
    """
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, blank=True)
    
    # Geographic Centroid (Simplified for non-GIS DBs)
    centroid_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    centroid_lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    area_sqkm = models.FloatField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Location(BaseModel):
    """
    Specific Site/City for Solar Analysis.
    Linked to Climate Data.
    """
    location_id = models.IntegerField(unique=True, help_text="Unique ID from source dataset")
    name = models.CharField(max_length=200)
    governorate = models.ForeignKey(Governorate, on_delete=models.CASCADE, related_name='locations')
    
    latitude = models.FloatField()
    longitude = models.FloatField()
    elevation = models.FloatField(null=True, blank=True)
    
    location_type = models.CharField(
        max_length=50, 
        default='CITY',
        choices=[('CITY', 'City'), ('STATION', 'Solar Station'), ('PROPOSED', 'Proposed Site')]
    )

    # Source and Description
    data_source = models.CharField(max_length=50, default='NASA_POWER')
    description = models.TextField(blank=True, default='')

    # Cached Statistics (Updated via Signals/Jobs)
    avg_solar_radiation = models.FloatField(null=True, blank=True)
    avg_temperature = models.FloatField(null=True, blank=True)
    solar_potential_score = models.FloatField(null=True, blank=True)
    solar_potential_category = models.CharField(max_length=20, default='UNKNOWN')

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['solar_potential_score']),
        ]

    def __str__(self):
        return f"{self.name} ({self.governorate.name})"

    def calculate_statistics(self, force_recalculate=False):
        """
        Refreshes the cached statistics for this location based on DailyClimateData.
        Critical for the Dashboard performance.
        """
        # (نفس منطق الحساب الذي كتبناه سابقاً لكن بشكل مختصر ونظيف)
        data = self.climate_data.filter(is_active=True)
        if not data.exists():
            return

        stats = data.aggregate(
            avg_rad=Avg('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            avg_wind=Avg('ws2m')
        )

        self.avg_solar_radiation = stats['avg_rad']
        self.avg_temperature = stats['avg_temp']
        
        # Simple Scoring Logic (Placeholder for AI Model)
        # Score = (Rad/7 * 60%) + (1 - |Temp-25|/50 * 40%)
        if self.avg_solar_radiation:
            rad_score = min(self.avg_solar_radiation / 7.0, 1.0) * 100
            temp_score = max(0, 100 - abs((self.avg_temperature or 25) - 25) * 2)
            self.solar_potential_score = (rad_score * 0.6) + (temp_score * 0.4)
        
        # Set Category
        score = self.solar_potential_score or 0
        if score >= 80: self.solar_potential_category = 'EXCELLENT'
        elif score >= 60: self.solar_potential_category = 'GOOD'
        elif score >= 40: self.solar_potential_category = 'MODERATE'
        else: self.solar_potential_category = 'POOR'

        self.save()

# ============================================
# 3. CLIMATE DATA (Time Series)
# ============================================

class DailyClimateData(BaseModel):
    """
    Time-series data for weather parameters.
    Source: NASA POWER / PVLib outputs.
    """
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='climate_data')
    date = models.DateField(db_index=True)

    # Core Parameters
    allsky_sfc_sw_dwn = models.FloatField(verbose_name="Solar Radiation (kWh/m²/day)")
    t2m = models.FloatField(verbose_name="Avg Temperature (°C)")
    t2m_max = models.FloatField(null=True)
    t2m_min = models.FloatField(null=True)
    rh2m = models.FloatField(verbose_name="Relative Humidity (%)")
    ws2m = models.FloatField(verbose_name="Wind Speed (m/s)")
    prectotcorr = models.FloatField(verbose_name="Precipitation (mm)", default=0)
    
    # Advanced Parameters (for AI Analysis)
    cloud_amt = models.FloatField(null=True, blank=True, help_text="Cloud amount (%)")
    solar_efficiency_factor = models.FloatField(null=True, help_text="Calculated efficiency impact (0-1)")
    dust_risk_score = models.FloatField(null=True, help_text="Risk of soiling (0-1)")

    class Meta:
        unique_together = ['location', 'date']
        ordering = ['-date']

    def save(self, *args, **kwargs):
        # Calculate Efficiency Factor (Simplified Model)
        # Efficiency drops ~0.5% per degree above 25°C
        temp_loss = max(0, ((self.t2m or 25) - 25) * 0.005)
        self.solar_efficiency_factor = 1.0 - temp_loss
        
        super().save(*args, **kwargs)

# ============================================
# 4. AGGREGATES (For Fast Dashboarding)
# ============================================

class MonthlySummary(BaseModel):
    """
    Pre-aggregated monthly stats to speed up dashboard loading.
    """
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='monthly_summaries')
    year = models.IntegerField()
    month = models.IntegerField()

    avg_radiation = models.FloatField()
    avg_temperature = models.FloatField()
    total_precipitation = models.FloatField()
    days_count = models.IntegerField(default=30)
    clear_days = models.IntegerField(default=0)

    # AI/Decision Support Metrics
    solar_grade = models.CharField(max_length=2, default='C', help_text="Grade A-F")

    class Meta:
        unique_together = ['location', 'year', 'month']
        ordering = ['-year', '-month']

    def calculate_from_daily_data(self, daily_qs):
        # Custom logic using Python statistics for SQLite compatibility
        import statistics
        
        if not daily_qs.exists():
            return

        # Use Django aggregates for basic stats
        aggs = daily_qs.aggregate(
            avg_rad=Avg('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            sum_rain=Sum('prectotcorr')
        )
        
        self.avg_radiation = aggs['avg_rad'] or 0
        self.avg_temperature = aggs['avg_temp'] or 0
        self.total_precipitation = aggs['sum_rain'] or 0
        
        # Calculate Grade
        if self.avg_radiation > 6.0: self.solar_grade = 'A'
        elif self.avg_radiation > 5.0: self.solar_grade = 'B'
        elif self.avg_radiation > 4.0: self.solar_grade = 'C'
        else: self.solar_grade = 'D'
        
        self.save()

# ============================================
# 5. ELECTRICITY TARIFFS (EGYPTERA August 2024)
# ============================================

class ElectricityTariff(models.Model):
    USAGE_TYPES = [
        ('RESIDENTIAL',       'Residential'),
        ('COMMERCIAL',        'Commercial'),
        ('IRRIGATION_LV',     'Irrigation Low Voltage'),
        ('OTHER_LV',          'Other Low Voltage'),
        ('MEDIUM_VOLTAGE',    'Medium Voltage'),
        ('HIGH_VOLTAGE',      'High Voltage'),
        ('EXTRA_HIGH_VOLTAGE','Extra High Voltage'),
    ]
    usage_type               = models.CharField(max_length=30, choices=USAGE_TYPES)
    tier_min_kwh             = models.IntegerField()
    tier_max_kwh             = models.IntegerField(null=True, blank=True)
    consumption_bracket_min  = models.IntegerField(default=0)
    consumption_bracket_max  = models.IntegerField(null=True, blank=True)
    price_piasters           = models.DecimalField(max_digits=6, decimal_places=1)
    customer_service_fee     = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    effective_date           = models.DateField()
    source_url               = models.URLField(default='https://egyptera.org/ar/TarrifAug2024.aspx')
    notes                    = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['usage_type', 'consumption_bracket_min', 'tier_min_kwh']
        indexes  = [models.Index(fields=['usage_type', 'consumption_bracket_min'])]

    def __str__(self):
        return (f"{self.usage_type} bracket {self.consumption_bracket_min}-"
                f"{self.consumption_bracket_max} tier {self.tier_min_kwh}-"
                f"{self.tier_max_kwh}: {self.price_piasters}pt")

    @property
    def price_egp_per_kwh(self):
        return float(self.price_piasters) / 100


# ============================================
# 6. SOLAR EQUIPMENT (Market Data 2026)
# ============================================

class SolarPanel(models.Model):
    brand               = models.CharField(max_length=100)
    model               = models.CharField(max_length=100)
    capacity_w          = models.IntegerField()
    panel_type          = models.CharField(max_length=20)   # MONO, POLY, BIFACIAL
    technology          = models.CharField(max_length=50)   # TOPCon, PERC, HPBC
    efficiency_pct      = models.FloatField()
    temp_coefficient_pct= models.FloatField()               # %/°C  (negative value)
    degradation_rate_pct= models.FloatField(default=0.45)   # %/year
    warranty_years      = models.IntegerField(default=25)
    price_egp           = models.FloatField()
    price_per_watt_egp  = models.FloatField()
    supplier            = models.CharField(max_length=100, blank=True)
    governorate         = models.CharField(max_length=50, default='Cairo')
    data_date           = models.DateField()
    in_stock            = models.BooleanField(default=True)

    class Meta:
        ordering = ['price_per_watt_egp']

    def __str__(self):
        return f"{self.brand} {self.model} {self.capacity_w}W"

    @property
    def area_m2(self):
        """Estimated panel area based on wattage."""
        if self.capacity_w >= 600:
            return 2.56   # ~2.1m × 1.22m
        elif self.capacity_w >= 400:
            return 2.0
        else:
            return 1.7


class Inverter(models.Model):
    INVERTER_TYPES = [
        ('ON_GRID',  'On-Grid String Inverter'),
        ('HYBRID',   'Hybrid Inverter'),
        ('OFF_GRID', 'Off-Grid Inverter'),
        ('MICRO',    'Micro Inverter'),
    ]
    brand          = models.CharField(max_length=100)
    model          = models.CharField(max_length=100)
    capacity_kw    = models.FloatField()
    inverter_type  = models.CharField(max_length=20, choices=INVERTER_TYPES)
    efficiency_pct = models.FloatField()
    warranty_years = models.IntegerField(default=5)
    price_egp      = models.FloatField()
    supplier       = models.CharField(max_length=100, blank=True)
    data_date      = models.DateField()
    in_stock       = models.BooleanField(default=True)
    notes          = models.TextField(blank=True)

    # ── IEC 62109 Electrical Parameters ───────────────────────────────────────
    max_dc_voltage_v  = models.FloatField(null=True, blank=True,
        help_text="Maximum DC input voltage (V) — IEC 62109 Vmax")
    mppt_min_v        = models.FloatField(null=True, blank=True,
        help_text="MPPT voltage range minimum (V)")
    mppt_max_v        = models.FloatField(null=True, blank=True,
        help_text="MPPT voltage range maximum (V)")
    max_dc_current_a  = models.FloatField(null=True, blank=True,
        help_text="Maximum DC input current per MPPT string (A)")
    mppt_channels     = models.IntegerField(default=1,
        help_text="Number of independent MPPT channels")
    max_strings       = models.IntegerField(default=1,
        help_text="Maximum number of PV strings")

    class Meta:
        ordering = ['capacity_kw', 'price_egp']

    def __str__(self):
        return f"{self.brand} {self.model} {self.capacity_kw}kW ({self.inverter_type})"


class InstallationCost(models.Model):
    item_name      = models.CharField(max_length=100)
    item_name_ar   = models.CharField(max_length=100)
    unit           = models.CharField(max_length=30)
    price_min_egp  = models.FloatField()
    price_max_egp  = models.FloatField()
    price_avg_egp  = models.FloatField()
    governorate    = models.CharField(max_length=50, default='Cairo')
    data_date      = models.DateField()
    notes          = models.TextField(blank=True)

    def __str__(self):
        return f"{self.item_name} ({self.unit}): avg {self.price_avg_egp} EGP"

    @property
    def price_avg(self):
        return (self.price_min_egp + self.price_max_egp) / 2


# ============================================
# 7. DESIGN PROJECTS
# ============================================

class DesignProject(models.Model):
    STATUS_CHOICES = [
        ('DRAFT',       'Draft'),
        ('OPTIMIZING',  'Optimizing'),
        ('COMPLETED',   'Completed'),
        ('ARCHIVED',    'Archived'),
    ]
    project_id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user                   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_name            = models.CharField(max_length=100)
    location               = models.ForeignKey('Location', on_delete=models.PROTECT)
    available_area_m2      = models.FloatField()
    monthly_consumption_kwh= models.FloatField()
    load_input_mode        = models.CharField(max_length=10, default='kwh')
    monthly_bill_egp       = models.FloatField(null=True, blank=True)
    usage_type             = models.CharField(max_length=30)
    budget_egp             = models.FloatField()
    shading_loss_pct       = models.FloatField(default=5.0)
    include_battery        = models.BooleanField(default=False)
    status                 = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    optimization_run_id    = models.CharField(max_length=20, blank=True)
    pareto_solutions       = models.JSONField(default=list)
    selected_design        = models.JSONField(null=True, blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return "Project {} - {} ({})".format(self.project_id, self.client_name, self.status)
