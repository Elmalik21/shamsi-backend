"""
ai_engine/baselines/pvwatts_baseline.py
=========================================
NREL PVWatts v5 DC/AC model implementation.

This is the industry-standard baseline for solar yield estimation.
It does NOT use machine learning — it is a validated physics model
from NREL (National Renewable Energy Laboratory).

Reference
---------
Dobos, A. P. (2014). PVWatts Version 5 Manual.
NREL Technical Report TP-6A20-62641.
https://www.nrel.gov/docs/fy14osti/62641.pdf

Model equations
---------------
DC Power:
    P_dc = P_dc0 × (Ee / E0) × [1 + γ_pdc × (T_cell - T_ref)]

Cell Temperature (Sandia NOCT model):
    T_cell = T_amb + (NOCT - 20) / 800 × POA

AC Power:
    P_ac = η_inv × P_dc

System losses (combined):
    η_sys = (1 - L_soiling) × (1 - L_wiring) × (1 - L_mismatch)
           × (1 - L_avail) × (1 - L_shading)

Egypt-specific default losses:
    Soiling (dust): 5 % (range 2–10 %, higher in desert regions)
    Wiring:         2 %
    Mismatch:       2 %
    Availability:   3 %
    Shading:        3 %

Usage (no Django ORM required):
    >>> from ai_engine.baselines.pvwatts_baseline import PVWattsBaseline
    >>> model = PVWattsBaseline()
    >>> result = model.predict_from_climate(
    ...     avg_ghi=6.2, avg_temp=28.0, system_kw=10.0,
    ...     panel_efficiency=0.22, temp_coefficient=-0.32, dust_loss=0.07
    ... )

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# PVWatts reference conditions
E0_REF    = 1000.0   # Reference irradiance [W/m²]
T0_REF    = 25.0     # STC reference temperature [°C]
NOCT      = 45.0     # Nominal Operating Cell Temperature [°C]

# Default Egypt system losses
EGYPT_SOILING_LOSS    = 0.05   # 5% dust soiling
EGYPT_WIRING_LOSS     = 0.02
EGYPT_MISMATCH_LOSS   = 0.02
EGYPT_AVAIL_LOSS      = 0.03
EGYPT_SHADING_LOSS    = 0.03
INVERTER_EFFICIENCY   = 0.96   # Modern string inverter

# Monthly weights (Egypt) for distributing annual → monthly
_MONTHLY_WEIGHTS = [
    0.062, 0.068, 0.088, 0.095, 0.102, 0.105,
    0.107, 0.103, 0.090, 0.079, 0.063, 0.058,
]


class PVWattsBaseline:
    """
    NREL PVWatts v5 implementation for Egyptian conditions.

    Serves as the industry benchmark to compare against AI models.
    """

    def predict_from_climate(
        self,
        avg_ghi:          float,
        avg_temp:         float,
        system_kw:        float = 10.0,
        panel_efficiency: float = 0.22,
        temp_coefficient: float = -0.32,  # %/°C
        dust_loss:        float = EGYPT_SOILING_LOSS,
        tilt_angle:       float = 25.0,
        inverter_eff:     float = INVERTER_EFFICIENCY,
    ) -> Dict:
        """
        Predict annual yield from annual-average climate parameters.

        Parameters
        ----------
        avg_ghi          : Annual average GHI [kWh/m²/day]
        avg_temp         : Annual average ambient temperature [°C]
        system_kw        : DC nameplate capacity [kW]
        panel_efficiency : STC panel efficiency [decimal]
        temp_coefficient : Power temperature coefficient [%/°C, negative]
        dust_loss        : Soiling/dust loss fraction [0–1]
        tilt_angle       : Panel tilt from horizontal [degrees]
        inverter_eff     : Inverter CEC efficiency [decimal]

        Returns
        -------
        dict with keys:
            specific_yield_kwh_per_kwp, predicted_annual_kwh,
            predicted_monthly, performance_ratio, system_losses_pct
        """
        # ── 1. Plane-of-array irradiance (simplified, annual average) ─────────
        # For tilted surface, apply a tilt factor (simplified isotropic model)
        # POA ≈ GHI × cos(tilt - latitude_tilt_offset) correction ~ 1.00–1.08
        tilt_rad = math.radians(tilt_angle)
        poa_w_per_m2 = avg_ghi * 1000 / 24.0   # convert to hourly average W/m²

        # ── 2. Cell temperature ───────────────────────────────────────────────
        # Sandia NOCT model: T_cell = T_amb + (NOCT-20)/800 * POA
        t_cell = avg_temp + (NOCT - 20.0) / 800.0 * (avg_ghi * 1000 / 24.0)

        # ── 3. DC power output (normalised to 1 kWp) ─────────────────────────
        # Effective irradiance ratio
        irrad_ratio = (avg_ghi * 1000 / 24.0) / E0_REF

        # Temperature derating: P = P0 × [1 + γ × (Tc - T0)]
        gamma = temp_coefficient / 100.0   # convert %/°C → fraction/°C
        temp_factor = 1.0 + gamma * (t_cell - T0_REF)
        temp_factor = max(0.5, temp_factor)   # physical floor

        # DC specific yield [kWh/kWp/day]
        dc_yield_daily = avg_ghi * temp_factor

        # ── 4. System losses ──────────────────────────────────────────────────
        total_loss = (
            (1 - dust_loss) *
            (1 - EGYPT_WIRING_LOSS) *
            (1 - EGYPT_MISMATCH_LOSS) *
            (1 - EGYPT_AVAIL_LOSS) *
            (1 - EGYPT_SHADING_LOSS)
        )

        # ── 5. AC specific yield [kWh/kWp/year] ──────────────────────────────
        specific_yield = dc_yield_daily * 365 * total_loss * inverter_eff

        # Performance ratio (industry KPI)
        # PR = specific_yield / (GHI_annual / 1000)
        ghi_annual = avg_ghi * 365   # kWh/m²/year
        pr = specific_yield / ghi_annual if ghi_annual > 0 else 0.75

        annual_kwh = specific_yield * system_kw
        monthly    = [round(annual_kwh * w, 1) for w in _MONTHLY_WEIGHTS]

        return {
            'specific_yield_kwh_per_kwp': round(specific_yield, 1),
            'predicted_annual_kwh':       round(annual_kwh, 1),
            'predicted_monthly':          monthly,
            'performance_ratio':          round(pr, 3),
            'system_losses_pct':          round((1 - total_loss * inverter_eff) * 100, 1),
            'cell_temp_avg_c':            round(t_cell, 1),
            'temp_derating_pct':          round((1 - temp_factor) * 100, 1),
        }

    def predict_location(self, location_id: int, system_kw: float = 10.0,
                          panel_efficiency: float = 0.22) -> Dict:
        """
        Predict for a Django Location by querying DailyClimateData.

        Parameters
        ----------
        location_id       : Location.location_id (integer)
        system_kw         : System size [kW]
        panel_efficiency  : Panel STC efficiency

        Returns
        -------
        Same dict as predict_from_climate()
        """
        try:
            from solar_data.models import Location, DailyClimateData
            from django.db.models import Avg, Max
            loc = Location.objects.get(location_id=location_id)
            qs  = DailyClimateData.objects.filter(location=loc)
            agg = qs.aggregate(
                avg_ghi=Avg('allsky_sfc_sw_dwn'),
                avg_temp=Avg('t2m'),
                avg_dust=Avg('dust_risk_score'),
            )
            avg_ghi  = agg['avg_ghi']  or 5.5
            avg_temp = agg['avg_temp'] or 25.0
            dust     = agg['avg_dust'] or 0.07
            tilt     = float(loc.latitude)
        except Exception as exc:
            logger.warning("ORM query failed (%s) — using defaults.", exc)
            avg_ghi, avg_temp, dust, tilt = 5.5, 25.0, 0.07, 25.0

        return self.predict_from_climate(
            avg_ghi=avg_ghi,
            avg_temp=avg_temp,
            system_kw=system_kw,
            panel_efficiency=panel_efficiency,
            dust_loss=dust,
            tilt_angle=tilt,
        )

    def batch_predict(self, location_features: List[Dict]) -> List[Dict]:
        """
        Predict for a list of feature dicts (same format as RF V2 features).

        Parameters
        ----------
        location_features : list of dicts with keys:
            avg_ghi, avg_temperature, system_kw, panel_efficiency,
            temp_coefficient, dust_risk_score, tilt_angle

        Returns
        -------
        list of result dicts
        """
        results = []
        for feat in location_features:
            r = self.predict_from_climate(
                avg_ghi          = feat.get('avg_ghi', 5.5),
                avg_temp         = feat.get('avg_temperature', 25.0),
                system_kw        = feat.get('system_kw', 10.0),
                panel_efficiency = feat.get('panel_efficiency', 0.22),
                temp_coefficient = feat.get('temp_coefficient', -0.32),
                dust_loss        = feat.get('dust_risk_score', 0.07),
                tilt_angle       = feat.get('tilt_angle', 25.0),
            )
            results.append(r)
        return results
