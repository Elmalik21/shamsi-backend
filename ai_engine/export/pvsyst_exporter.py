"""
ai_engine/export/pvsyst_exporter.py
=====================================
Export Shamsi Smart designs to PVsyst file formats.

PVsyst is the industry-standard simulation tool used by banks and energy
consultants for "bankable" solar yield assessments.  By exporting to PVsyst's
native formats, Shamsi designs can be independently verified, making them
credible for project financing.

Files produced
--------------
  .SIT   Site definition   (ASCII text)
  .MET   Meteo data        (ASCII CSV, NASA SSE layout)
  .PAN   Panel database    (ASCII text)
  .OND   Inverter database (ASCII text, OND = "Onduleur" in French)

PVsyst documentation: https://www.pvsyst.com/help/

Usage (standalone / synthetic data)
-------------------------------------
    from ai_engine.export.pvsyst_exporter import PVsystExporter, make_synthetic_project

    project = make_synthetic_project()
    exp     = PVsystExporter(project)
    files   = exp.export_all('/tmp/my_export/')
    print(files)
"""
from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data helpers (so the module works without Django)
# ─────────────────────────────────────────────────────────────────────────────

class _Obj:
    """Simple namespace with attribute access."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    def get(self, key, default=None):
        return getattr(self, key, default)


def make_synthetic_project(location_name: str = 'Cairo') -> Dict:
    """
    Return a synthetic project_data dict for offline testing / CI.

    In production this comes from Django ORM objects (Location, SolarPanel,
    Inverter, DailyClimateData queryset).
    """
    import random, math
    rng = random.Random(42)

    location = _Obj(
        name        = location_name,
        country     = 'Egypt',
        latitude    = 30.044,
        longitude   = 31.236,
        elevation_m = 23,
    )

    panel = _Obj(
        manufacturer              = 'JA Solar',
        model                     = 'JAM72D40-580',
        technology                = 'mono-Si',
        power_rating_w            = 580,
        vmp_v                     = 41.88,
        imp_a                     = 13.86,
        voc_v                     = 50.26,
        isc_a                     = 14.50,
        temp_coeff_pmax_percent   = -0.350,
        temp_coeff_voc_percent    = -0.270,
        temp_coeff_isc_percent    =  0.048,
        length_mm                 = 2278,
        width_mm                  = 1134,
        thickness_mm              = 30,
        weight_kg                 = 28.5,
        efficiency_percent        = 22.5,
        area_m2                   = 2.278 * 1.134,
    )

    inverter = _Obj(
        manufacturer           = 'Huawei',
        model                  = 'SUN2000-10KTL-M1',
        inverter_type          = 'String',
        power_rating_w         = 10_000,
        output_voltage_v       = 230,
        max_ac_power_w         = 11_000,
        max_efficiency_percent = 98.4,
        euro_efficiency_percent= 98.0,
        max_dc_voltage_v       = 1100,
        min_dc_voltage_v       = 200,
        mppt_voltage_min_v     = 200,
        mppt_voltage_max_v     = 950,
        max_dc_current_a       = 22.0,
        number_of_inputs       = 2,
        number_of_mppts        = 2,
        weight_kg              = 10.5,
        dimensions_mm          = '525x470x182 mm',
    )

    # Synthetic daily climate: 365 records, sinusoidal GHI + temperature
    class FakeClimateRecord:
        def __init__(self, day):
            import datetime as dt
            self.date = dt.date(2023, 1, 1) + dt.timedelta(days=day)
            doy   = day + 1
            phase = 2 * math.pi * (doy - 172) / 365   # peak near summer solstice
            self.allsky_sfc_sw_dwn = 5.5 + 2.0 * math.cos(phase) + rng.gauss(0, 0.2)
            self.t2m    = 22.0 + 12.0 * math.cos(phase) + rng.gauss(0, 1.0)
            self.ws2m   = 3.0  + rng.random() * 2
            self.rh2m   = 45.0 + 20.0 * (-math.cos(phase)) + rng.gauss(0, 5.0)

        def order_by(self, *a):      # mimic queryset
            return self

        def __iter__(self):
            return iter([FakeClimateRecord(d) for d in range(365)])

    climate_queryset = FakeClimateRecord(0)   # iterable shim

    return {
        'project_id'          : 'SHAMSI-DEMO-001',
        'location'            : location,
        'panel'               : panel,
        'inverter'            : inverter,
        'system_config'       : {
            'panel_count'       : 30,
            'tilt_angle'        : 20.0,
            'azimuth'           : 180.0,
            'strings'           : 3,
            'panels_per_string' : 10,
            'inverter_count'    : 2,
        },
        'climate_data'        : climate_queryset,
        'dust_loss_pct'       : 5.0,
        'shading_loss_pct'    : 3.0,
        'optimization_results': {
            'annual_yield_kwh'      : 24_800,
            'monthly_yield_kwh'     : [1550, 1650, 2100, 2200, 2350, 2400,
                                       2450, 2350, 2100, 1900, 1650, 1550],
            'specific_yield'        : 1427,
            'total_cost_egp'        : 210_000,
            'cost_per_watt'         : 12.1,
            'payback_years'         : 5.8,
            'lifetime_savings_egp'  : 1_230_000,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Solar geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def _declination(doy: int) -> float:
    """Solar declination angle in degrees (Spencer formula)."""
    return 23.45 * math.sin(math.radians(360 / 365 * (284 + doy)))


def _extraterrestrial_irradiance(doy: int) -> float:
    """
    Extraterrestrial solar irradiance on horizontal surface at solar noon
    (kW/m²) using the eccentricity correction factor.
    """
    Gsc = 1.367  # solar constant kW/m²
    B   = math.radians(360 * (doy - 1) / 365)
    E0  = (1.00011 + 0.034221 * math.cos(B) + 0.00128 * math.sin(B)
           + 0.000719 * math.cos(2*B) + 0.000077 * math.sin(2*B))
    return Gsc * E0


def _sin_solar_noon_elevation(doy: int, lat_deg: float) -> float:
    """sin(solar elevation angle) at solar noon — used for DNI estimation."""
    dec = _declination(doy)
    lat = math.radians(lat_deg)
    dec_r = math.radians(dec)
    return max(0.01, math.sin(lat) * math.sin(dec_r) +
               math.cos(lat) * math.cos(dec_r))


def _erbs_diffuse_fraction(kt: float) -> float:
    """
    Erbs (1982) correlation: diffuse fraction kd as a function of
    clearness index kt = GHI / G0h.
    """
    if kt <= 0.22:
        return 1.0 - 0.09 * kt
    elif kt <= 0.80:
        return (0.9511 - 0.1604*kt + 4.388*kt**2
                - 16.638*kt**3 + 12.336*kt**4)
    else:
        return 0.165


def _decompose_ghi(ghi_kwh: float, doy: int, lat_deg: float):
    """
    Split daily GHI (kWh/m²/day) into DNI and DHI using Erbs decomposition.

    Returns (DNI, DHI) in kWh/m²/day.
    """
    # Extraterrestrial daily irradiation: G0h ≈ Gon × sin(elev) × 24/1000
    # (simplified: using noon elevation proxy for daily total)
    G0h = _extraterrestrial_irradiance(doy) * _sin_solar_noon_elevation(doy, lat_deg) * 24
    G0h = max(G0h, 0.5)           # avoid division-by-zero near poles or night

    kt  = min(ghi_kwh / G0h, 1.0)
    kd  = _erbs_diffuse_fraction(kt)

    dhi = ghi_kwh * kd
    dhi = max(0.0, min(dhi, ghi_kwh))
    # DNI from geometry: DNI = (GHI - DHI) / sin(solar_elevation)
    sin_elev = _sin_solar_noon_elevation(doy, lat_deg)
    dni = (ghi_kwh - dhi) / sin_elev
    dni = max(0.0, dni)
    return round(dni, 3), round(dhi, 3)


# ─────────────────────────────────────────────────────────────────────────────
# Main exporter
# ─────────────────────────────────────────────────────────────────────────────

class PVsystExporter:
    """
    Export a Shamsi Smart project to PVsyst-compatible files.

    Parameters
    ----------
    project_data : dict
        Must contain:
          'location'         – object with .name, .country, .latitude,
                               .longitude, .elevation_m
          'panel'            – object with electrical + physical specs
          'inverter'         – object with electrical specs
          'system_config'    – dict (panel_count, tilt_angle, azimuth,
                               strings, panels_per_string, inverter_count)
          'climate_data'     – iterable of daily records with .date,
                               .allsky_sfc_sw_dwn, .t2m, .ws2m, .rh2m
          'optimization_results' – dict (annual_yield_kwh, etc.)
          'project_id'       – str (optional)
    """

    _TIMEZONE_MAP = {
        'Egypt'   : 'UT+2.0',
        'Libya'   : 'UT+2.0',
        'Tunisia' : 'UT+1.0',
        'Morocco' : 'UT+1.0',
        'Algeria' : 'UT+1.0',
    }

    def __init__(self, project_data: Dict):
        self.project  = project_data
        self.location = project_data['location']
        self.panel    = project_data['panel']
        self.inverter = project_data['inverter']
        self.config   = project_data['system_config']

    # ── Public API ────────────────────────────────────────────────────────────

    def export_all(self, output_dir: str) -> Dict[str, str]:
        """
        Generate all four PVsyst files and return their paths.

        Parameters
        ----------
        output_dir : str
            Directory to write files into (created if necessary).

        Returns
        -------
        dict
            {'sit_file': ..., 'met_file': ..., 'pan_file': ..., 'ond_file': ...}
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        return {
            'sit_file' : self._write_sit_file(out),
            'met_file' : self._write_met_file(out),
            'pan_file' : self._write_pan_file(out),
            'ond_file' : self._write_ond_file(out),
        }

    # ── .SIT file ─────────────────────────────────────────────────────────────

    def _write_sit_file(self, out: Path) -> str:
        loc   = self.location
        tz    = self._TIMEZONE_MAP.get(getattr(loc, 'country', 'Egypt'), 'UT+2.0')
        lat_s = f"{abs(loc.latitude):.3f} °{'N' if loc.latitude >= 0 else 'S'}"
        lon_s = f"{abs(loc.longitude):.3f} °{'E' if loc.longitude >= 0 else 'W'}"
        safe  = loc.name.replace(' ', '_')

        content = (
            f"PVsyst Site data\n"
            f"{'*'*60}\n\n"
            f"Country             {getattr(loc, 'country', 'Egypt')}\n"
            f"Site                {loc.name}\n"
            f"Latitude            {lat_s}\n"
            f"Longitude           {lon_s}\n"
            f"Altitude            {getattr(loc, 'elevation_m', 0) or 0} m\n"
            f"Time zone           {tz}\n"
            f"Meteo file          {safe}.MET\n\n"
            f"Albedo              0.20\n"
            f"Albedo monthly      0.20 0.20 0.20 0.20 0.20 0.20 "
            f"0.20 0.20 0.20 0.20 0.20 0.20\n\n"
            f"Horizon profile     0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,"
            f"0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0\n\n"
            f"Comment:\n"
            f"Generated by Shamsi Smart AI\n"
            f"Project ID          {self.project.get('project_id', 'N/A')}\n"
            f"Optimiser           NSGA-II multi-objective\n"
            f"System size         "
            f"{self.config['panel_count'] * self.panel.power_rating_w / 1000:.2f} kWp\n"
            f"Export date         {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        )

        path = out / f"{safe}.SIT"
        path.write_text(content, encoding='utf-8')
        return str(path)

    # ── .MET file ─────────────────────────────────────────────────────────────

    def _write_met_file(self, out: Path) -> str:
        loc  = self.location
        safe = loc.name.replace(' ', '_')
        lat  = loc.latitude

        lines: List[str] = []
        # Header block
        lines.append(
            f"# Shamsi Smart meteo export — NASA POWER source\n"
            f"# Site: {loc.name}  Lat: {lat:.3f}  Lon: {loc.longitude:.3f}\n"
            f"# Elevation: {getattr(loc, 'elevation_m', 0) or 0} m  TZ: UT+2.0\n"
            f"-{loc.longitude:.3f},{lat:.3f},{getattr(loc, 'elevation_m', 0) or 0},2.0\n"
            f"date,GHI,DNI,DHI,Tdry,Wspd,RH\n"
            f"# Units: GHI/DNI/DHI kWh/m2/day  Tdry degC  Wspd m/s  RH %\n"
        )

        for record in self.project['climate_data']:
            doy = record.date.timetuple().tm_yday
            ghi = max(0.0, float(record.allsky_sfc_sw_dwn))
            t   = float(record.t2m)
            ws  = max(0.0, float(record.ws2m))
            rh  = max(0.0, min(100.0, float(record.rh2m)))

            dni, dhi = _decompose_ghi(ghi, doy, lat)

            lines.append(
                f"{record.date.strftime('%Y-%m-%d')},"
                f"{ghi:.3f},{dni:.3f},{dhi:.3f},"
                f"{t:.1f},{ws:.1f},{rh:.0f}"
            )

        path = out / f"{safe}.MET"
        path.write_text('\n'.join(lines), encoding='utf-8')
        return str(path)

    # ── .PAN file ─────────────────────────────────────────────────────────────

    def _write_pan_file(self, out: Path) -> str:
        p    = self.panel
        safe = f"{p.manufacturer}_{p.model}".replace(' ', '_')

        # Derive NOCT if not stored (typical default 45°C)
        noct_val = getattr(p, 'noct_celsius', None)
        noct = float(noct_val) if noct_val is not None else 45.0

        content = (
            f"PVsyst Panel database  Version 1.0\n"
            f"{'*'*60}\n\n"
            f"Manufacturer        {p.manufacturer}\n"
            f"Model               {p.model}\n"
            f"Technology          {p.technology}\n\n"
            f"Pnom                {p.power_rating_w:.1f} W\n"
            f"Vmpp                {p.vmp_v:.2f} V\n"
            f"Impp                {p.imp_a:.2f} A\n"
            f"Voc                 {p.voc_v:.2f} V\n"
            f"Isc                 {p.isc_a:.2f} A\n\n"
            f"muPmpp              {p.temp_coeff_pmax_percent:.3f} %/°C\n"
            f"muVoc               {p.temp_coeff_voc_percent:.3f} %/°C\n"
            f"muIsc               {p.temp_coeff_isc_percent:.3f} %/°C\n"
            f"NOCT                {noct:.1f} °C\n\n"
            f"Length              {p.length_mm:.0f} mm\n"
            f"Width               {p.width_mm:.0f} mm\n"
            f"Thickness           {p.thickness_mm:.0f} mm\n"
            f"Weight              {p.weight_kg:.1f} kg\n\n"
            f"Efficiency          {p.efficiency_percent:.2f} %\n"
            f"Area                {p.area_m2:.4f} m²\n\n"
            f"Comment:\n"
            f"Exported from Shamsi Smart AI\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        )

        path = out / f"{safe}.PAN"
        path.write_text(content, encoding='utf-8')
        return str(path)

    # ── .OND file ─────────────────────────────────────────────────────────────

    def _write_ond_file(self, out: Path) -> str:
        inv  = self.inverter
        cfg  = self.config
        safe = f"{inv.manufacturer}_{inv.model}".replace(' ', '_')

        content = (
            f"PVsyst Inverter database  Version 1.0\n"
            f"{'*'*60}\n\n"
            f"Manufacturer        {inv.manufacturer}\n"
            f"Model               {inv.model}\n"
            f"Type                {inv.inverter_type}\n\n"
            f"Pnom                {inv.power_rating_w:.0f} W\n"
            f"VacNom              {inv.output_voltage_v:.0f} V\n"
            f"PacMax              {inv.max_ac_power_w:.0f} W\n\n"
            f"Efficiency          {inv.max_efficiency_percent:.1f} %\n"
            f"EuroEff             {inv.euro_efficiency_percent:.1f} %\n\n"
            f"Vdcmax              {inv.max_dc_voltage_v:.0f} V\n"
            f"Vdcmin              {inv.min_dc_voltage_v:.0f} V\n"
            f"VmppMin             {inv.mppt_voltage_min_v:.0f} V\n"
            f"VmppMax             {inv.mppt_voltage_max_v:.0f} V\n\n"
            f"IdcMax              {inv.max_dc_current_a:.1f} A\n"
            f"NbInputs            {inv.number_of_inputs}\n"
            f"NbMPPT              {inv.number_of_mppts}\n\n"
            f"Weight              {inv.weight_kg:.1f} kg\n"
            f"Dimensions          {getattr(inv, 'dimensions_mm', 'N/A')}\n\n"
            f"Comment:\n"
            f"Exported from Shamsi Smart AI\n"
            f"NSGA-II selected this inverter for the optimised design\n"
            f"Strings:            {cfg.get('strings', 'N/A')}\n"
            f"Inverters in system:{cfg.get('inverter_count', 1)}\n"
            f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        )

        path = out / f"{safe}.OND"
        path.write_text(content, encoding='utf-8')
        return str(path)
