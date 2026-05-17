"""
ai_engine/baselines/physics_baseline.py
=========================================
Simplified first-principles physics model for solar yield estimation.

This is a pure physics approach — NO machine learning, NO lookup tables.
Uses fundamental solar geometry and electrical equations.

Physical models implemented
---------------------------
1. Solar geometry   : declination, hour angle, zenith angle, sunrise/sunset
2. POA irradiance   : beam + diffuse + ground-reflected components
3. NOCT cell temp   : Sandia model
4. Dust deposition  : linear accumulation with rainfall cleaning
5. DC power output  : STC derating with temperature
6. AC output        : inverter model (constant efficiency)

Key formula for specific yield (kWh/kWp/day):
    yield = POA [kWh/m²/day] * temp_factor * (1 - dust) * inverter_eff
    where temp_factor = 1 + (gamma/100) * (T_cell - 25)
    NOTE: panel_efficiency is NOT applied here — it is already embedded in
    the kWp nameplate rating by definition. 1 kWp delivers 1 kWh when
    POA = 1 kWh/m² at STC (25°C, 1000 W/m²).

References
----------
- Duffie, J. A. & Beckman, W. A. (2013). Solar Engineering of Thermal Processes.
- King, D. L. et al. (2004). Sandia PV Array Performance Model. SAND2004-3535.

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

# Constants
SOLAR_CONSTANT = 1367.0   # W/m² (extraterrestrial irradiance)
NOCT           = 45.0     # °C  (Nominal Operating Cell Temperature)
INVERTER_EFF   = 0.96
ALBEDO         = 0.2      # Ground reflectance (typical Egypt)

_MONTHLY_WEIGHTS = [
    0.062, 0.068, 0.088, 0.095, 0.102, 0.105,
    0.107, 0.103, 0.090, 0.079, 0.063, 0.058,
]
_DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


class SimplifiedPhysicsModel:
    """
    First-principles solar energy model for Egyptian locations.

    This is intentionally simpler than PVWatts to serve as a
    lower-bound baseline that an AI model must beat convincingly.
    """

    # ── Solar geometry ────────────────────────────────────────────────────────

    @staticmethod
    def declination(day_of_year: int) -> float:
        """Solar declination angle [degrees] — Spencer (1971)."""
        B = 360 / 365 * (day_of_year - 81)
        return 23.45 * math.sin(math.radians(B))

    @staticmethod
    def sunset_hour_angle(latitude_deg: float, declination_deg: float) -> float:
        """Sunset hour angle [degrees]."""
        lat = math.radians(latitude_deg)
        dec = math.radians(declination_deg)
        cos_ws = -math.tan(lat) * math.tan(dec)
        cos_ws = max(-1.0, min(1.0, cos_ws))
        return math.degrees(math.acos(cos_ws))

    @staticmethod
    def daily_extraterrestrial_radiation(day_of_year: int, latitude_deg: float) -> float:
        """
        Daily extraterrestrial radiation on a horizontal surface [kWh/m²/day].
        Equation 1.10.3 from Duffie & Beckman.
        """
        dec = SimplifiedPhysicsModel.declination(day_of_year)
        ws  = SimplifiedPhysicsModel.sunset_hour_angle(latitude_deg, dec)
        lat = math.radians(latitude_deg)
        dec_r = math.radians(dec)
        ws_r  = math.radians(ws)

        B = math.radians(360 / 365 * (day_of_year - 1))
        E0 = (1.000110 + 0.034221 * math.cos(B) + 0.001280 * math.sin(B)
              + 0.000719 * math.cos(2 * B) + 0.000077 * math.sin(2 * B))

        H0 = (24 / math.pi * SOLAR_CONSTANT * E0 *
              (ws_r * math.sin(lat) * math.sin(dec_r)
               + math.cos(lat) * math.cos(dec_r) * math.sin(ws_r)))
        return max(0.0, H0 / 1000.0)   # W·h → kWh

    # ── POA irradiance ────────────────────────────────────────────────────────

    @staticmethod
    def calculate_poa_irradiance(
        ghi: float,
        latitude_deg: float,
        tilt_deg: float,
        day_of_year: int,
    ) -> float:
        """
        Plane-of-array irradiance [kWh/m²/day] — isotropic sky model.
        Separates GHI into beam + diffuse using Erbs (1982) correlation.
        """
        H0 = SimplifiedPhysicsModel.daily_extraterrestrial_radiation(
            day_of_year, latitude_deg
        )
        if H0 < 1e-6:
            return 0.0

        Kt = min(ghi / H0, 1.0)

        # Erbs diffuse fraction
        if Kt <= 0.22:
            Hd_ratio = 1.0 - 0.09 * Kt
        elif Kt <= 0.80:
            Hd_ratio = (0.9511 - 0.1604 * Kt + 4.388 * Kt ** 2
                        - 16.638 * Kt ** 3 + 12.336 * Kt ** 4)
        else:
            Hd_ratio = 0.165

        Hd = ghi * Hd_ratio
        Hb = ghi - Hd

        tilt_r = math.radians(tilt_deg)
        lat_r  = math.radians(latitude_deg)
        dec    = SimplifiedPhysicsModel.declination(day_of_year)
        ws     = SimplifiedPhysicsModel.sunset_hour_angle(latitude_deg, dec)
        dec_r  = math.radians(dec)
        ws_r   = math.radians(ws)

        # Rb: beam ratio tilted/horizontal (Liu & Jordan 1963, south-facing)
        latitude_tilt = lat_r - tilt_r
        nom = (math.cos(latitude_tilt) * math.cos(dec_r) * math.sin(ws_r)
               + ws_r * math.sin(latitude_tilt) * math.sin(dec_r))
        den = (math.cos(lat_r) * math.cos(dec_r) * math.sin(ws_r)
               + ws_r * math.sin(lat_r) * math.sin(dec_r))
        Rb = (nom / den) if abs(den) > 1e-6 else 1.0
        Rb = max(0.0, Rb)

        # Isotropic sky model
        poa = (Hb * Rb
               + Hd * (1 + math.cos(tilt_r)) / 2
               + ghi * ALBEDO * (1 - math.cos(tilt_r)) / 2)
        return max(0.0, poa)

    # ── Cell temperature ──────────────────────────────────────────────────────

    @staticmethod
    def calculate_cell_temperature(ambient_temp: float, poa_irradiance_daily: float) -> float:
        """
        Average cell temperature using NOCT model.
        T_cell = T_amb + (NOCT - 20) / 800 * POA_avg [W/m²]
        """
        poa_avg_w = poa_irradiance_daily * 1000.0 / 24.0   # kWh/day → avg W/m²
        return ambient_temp + (NOCT - 20.0) / 800.0 * poa_avg_w

    # ── DC specific yield ─────────────────────────────────────────────────────

    @staticmethod
    def calculate_dc_yield(
        poa: float,
        cell_temp: float,
        panel_efficiency: float,
        temp_coefficient: float,
    ) -> float:
        """
        Daily DC specific yield [kWh/kWp/day].

        By definition, 1 kWp produces 1 kWh when POA = 1 kWh/m²/day at STC.
        panel_efficiency is embedded in the kWp rating — do NOT apply it again.

        Formula: yield = POA * [1 + (gamma/100) * (T_cell - 25)]
        """
        temp_factor = 1.0 + (temp_coefficient / 100.0) * (cell_temp - 25.0)
        temp_factor = max(0.5, temp_factor)
        return poa * temp_factor

    # ── Dust loss ─────────────────────────────────────────────────────────────

    @staticmethod
    def dust_loss_factor(monthly_dust_score: float, monthly_rain_mm: float) -> float:
        """Dust accumulation loss factor [fraction]."""
        rain_cleaning = min(0.8, monthly_rain_mm / 10.0) * 0.5
        return max(0.01, monthly_dust_score - rain_cleaning)

    # ── Annual yield ──────────────────────────────────────────────────────────

    def predict_annual_yield(
        self,
        avg_ghi: float,
        avg_temp: float,
        latitude_deg: float,
        tilt_deg: float,
        panel_efficiency: float = 0.22,
        temp_coefficient: float = -0.32,
        dust_risk: float = 0.07,
        system_kw: float = 10.0,
        avg_rain_mm: float = 5.0,
    ) -> Dict:
        """
        Simulate daily production for a representative year.

        Returns
        -------
        dict: specific_yield_kwh_per_kwp, predicted_annual_kwh,
              predicted_monthly, performance_ratio
        """
        daily_yields = np.zeros(365)

        for doy in range(1, 366):
            month_idx = self._doy_to_month(doy) - 1
            rain = avg_rain_mm / _DAYS_IN_MONTH[month_idx]

            poa      = self.calculate_poa_irradiance(avg_ghi, latitude_deg, tilt_deg, doy)
            t_cell   = self.calculate_cell_temperature(avg_temp, poa)
            dust     = self.dust_loss_factor(dust_risk, rain)
            dc_yield = self.calculate_dc_yield(poa, t_cell, panel_efficiency, temp_coefficient)
            ac_yield = dc_yield * (1 - dust) * INVERTER_EFF
            daily_yields[doy - 1] = max(0.0, ac_yield)

        annual_specific = float(daily_yields.sum())
        annual_kwh      = annual_specific * system_kw

        monthly_kwh = []
        for m, days in enumerate(_DAYS_IN_MONTH):
            start = sum(_DAYS_IN_MONTH[:m])
            monthly_kwh.append(
                round(float(daily_yields[start:start + days].sum()) * system_kw, 1)
            )

        pr = annual_specific / (avg_ghi * 365) if avg_ghi > 0 else 0.75

        return {
            'specific_yield_kwh_per_kwp': round(annual_specific, 1),
            'predicted_annual_kwh':       round(annual_kwh, 1),
            'predicted_monthly':          monthly_kwh,
            'performance_ratio':          round(pr, 3),
        }

    def batch_predict(self, location_features: List[Dict]) -> List[Dict]:
        """Batch predict for a list of feature dicts."""
        results = []
        for feat in location_features:
            r = self.predict_annual_yield(
                avg_ghi          = feat.get('avg_ghi', 5.5),
                avg_temp         = feat.get('avg_temperature', 25.0),
                latitude_deg     = feat.get('latitude', 25.0),
                tilt_deg         = feat.get('tilt_angle', 25.0),
                panel_efficiency = feat.get('panel_efficiency', 0.22),
                temp_coefficient = feat.get('temp_coefficient', -0.32),
                dust_risk        = feat.get('dust_risk_score', 0.07),
                system_kw        = feat.get('system_kw', 10.0),
            )
            results.append(r)
        return results

    @staticmethod
    def _doy_to_month(doy: int) -> int:
        """Convert day-of-year (1-365) to month (1-12)."""
        cumulative = 0
        for m, days in enumerate(_DAYS_IN_MONTH, 1):
            cumulative += days
            if doy <= cumulative:
                return m
        return 12
