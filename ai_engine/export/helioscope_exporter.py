"""
ai_engine/export/helioscope_exporter.py
=========================================
Export Shamsi Smart designs to HelioScope JSON format.

HelioScope (by Folsom Labs / Aurora Solar) is a cloud-based solar design
platform widely used in the US and internationally.  Exporting to its JSON
format lets engineers import a Shamsi-optimised design and run HelioScope's
irradiance simulation engine on top, providing a second independent validation.

HelioScope API v1 project schema:
  https://helioscope.folsom.com/api/v1/docs

Usage
-----
    from ai_engine.export.helioscope_exporter import HelioScopeExporter
    from ai_engine.export.pvsyst_exporter import make_synthetic_project

    project = make_synthetic_project()
    exp     = HelioScopeExporter(project)
    path    = exp.export_project('/tmp/my_project/helioscope.json')
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# HelioScope loss model defaults (consistent with PVsyst "advanced" losses)
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_LOSSES = {
    'soiling'     : 0.050,   # 5% dust (Egypt-specific)
    'mismatch'    : 0.020,   # 2% string mismatch
    'wiring'      : 0.020,   # 2% DC wiring
    'connections' : 0.005,   # 0.5% connector losses
    'lid'         : 0.015,   # 1.5% light-induced degradation
    'age'         : 0.005,   # 0.5% first-year degradation
    'shading'     : 0.030,   # 3% far shading (default, overridden if known)
    'snow'        : 0.000,   # 0% (no snow in Egypt)
}

_EGYPT_TIMEZONE = 'Africa/Cairo'


class HelioScopeExporter:
    """
    Serialise a Shamsi Smart project to a HelioScope API v1–compatible JSON.

    Parameters
    ----------
    project_data : dict
        Same schema as PVsystExporter (location, panel, inverter,
        system_config, optimization_results, …).
    """

    def __init__(self, project_data: Dict):
        self.project  = project_data
        self.location = project_data['location']
        self.panel    = project_data['panel']
        self.inverter = project_data['inverter']
        self.config   = project_data['system_config']
        self.results  = project_data.get('optimization_results', {})

    # ── Public API ────────────────────────────────────────────────────────────

    def export_project(self, output_file: str) -> str:
        """
        Write HelioScope JSON to *output_file*.

        Returns
        -------
        str  Absolute path of the written file.
        """
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        payload = self._build_payload()

        with open(output_file, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

        return os.path.abspath(output_file)

    def to_dict(self) -> Dict:
        """Return the HelioScope JSON payload as a Python dict (no file I/O)."""
        return self._build_payload()

    # ── JSON construction ─────────────────────────────────────────────────────

    def _build_payload(self) -> Dict:
        loc = self.location
        cfg = self.config
        p   = self.panel
        inv = self.inverter
        res = self.results

        project_name = (
            f"Shamsi_{loc.name.replace(' ', '_')}"
            f"_{datetime.now().strftime('%Y%m%d')}"
        )

        # Resolve losses
        losses = dict(_DEFAULT_LOSSES)
        if 'dust_loss_pct' in self.project:
            losses['soiling'] = float(self.project['dust_loss_pct']) / 100
        if 'shading_loss_pct' in self.project:
            losses['shading'] = float(self.project['shading_loss_pct']) / 100

        # System capacity
        system_kw = cfg['panel_count'] * p.power_rating_w / 1000

        return {
            "project": {
                "name"        : project_name,
                "description" : (
                    f"AI-optimised design by Shamsi Smart "
                    f"(NSGA-II, CNN-LSTM yield model). "
                    f"Project ID: {self.project.get('project_id', 'N/A')}"
                ),
                "created_at"  : datetime.now().isoformat(),
                "source"      : "Shamsi Smart AI",

                # ── Location ──────────────────────────────────────────────────
                "location": {
                    "name"      : loc.name,
                    "country"   : getattr(loc, 'country', 'Egypt'),
                    "latitude"  : loc.latitude,
                    "longitude" : loc.longitude,
                    "elevation" : getattr(loc, 'elevation_m', 0) or 0,
                    "timezone"  : _EGYPT_TIMEZONE,
                },

                # ── System design ─────────────────────────────────────────────
                "design": {
                    "system_type"  : "grid_tied",
                    "system_kw"    : round(system_kw, 3),

                    "arrays": [
                        {
                            "name"    : "Main Array",
                            "tilt"    : cfg['tilt_angle'],
                            "azimuth" : cfg.get('azimuth', 180),  # South = 180°

                            # Module specs
                            "modules": {
                                "manufacturer" : p.manufacturer,
                                "model"        : p.model,
                                "technology"   : p.technology,
                                "count"        : cfg['panel_count'],

                                "configuration": {
                                    "strings"          : cfg.get('strings', 1),
                                    "modules_per_string": cfg.get('panels_per_string', 10),
                                },

                                "specifications": {
                                    "pmax_w"          : p.power_rating_w,
                                    "vmp_v"           : p.vmp_v,
                                    "imp_a"           : p.imp_a,
                                    "voc_v"           : p.voc_v,
                                    "isc_a"           : p.isc_a,
                                    "temp_coeff_pmax" : p.temp_coeff_pmax_percent,
                                    "temp_coeff_voc"  : p.temp_coeff_voc_percent,
                                    "temp_coeff_isc"  : p.temp_coeff_isc_percent,
                                    "efficiency_pct"  : p.efficiency_percent,
                                    "noct_c"          : getattr(p, 'noct_celsius', 45),
                                    "area_m2"         : p.area_m2,
                                    "dimensions_mm"   : {
                                        "length" : p.length_mm,
                                        "width"  : p.width_mm,
                                    },
                                },
                            },

                            # Inverter specs
                            "inverters": [
                                {
                                    "manufacturer" : inv.manufacturer,
                                    "model"        : inv.model,
                                    "type"         : inv.inverter_type,
                                    "count"        : cfg.get('inverter_count', 1),

                                    "specifications": {
                                        "pnom_w"            : inv.power_rating_w,
                                        "pac_max_w"         : inv.max_ac_power_w,
                                        "vac_v"             : inv.output_voltage_v,
                                        "efficiency_pct"    : inv.max_efficiency_percent,
                                        "euro_efficiency_pct": inv.euro_efficiency_percent,
                                        "vdc_max_v"         : inv.max_dc_voltage_v,
                                        "vdc_min_v"         : inv.min_dc_voltage_v,
                                        "vmpp_min_v"        : inv.mppt_voltage_min_v,
                                        "vmpp_max_v"        : inv.mppt_voltage_max_v,
                                        "idc_max_a"         : inv.max_dc_current_a,
                                        "nb_mppt"           : inv.number_of_mppts,
                                    },
                                }
                            ],
                        }
                    ],  # end arrays

                    # ── Loss model ────────────────────────────────────────────
                    "losses": {
                        "soiling"     : losses['soiling'],
                        "shading"     : losses['shading'],
                        "mismatch"    : losses['mismatch'],
                        "wiring"      : losses['wiring'],
                        "connections" : losses['connections'],
                        "lid"         : losses['lid'],
                        "age"         : losses['age'],
                        "snow"        : losses['snow'],
                        "total_estimated_pct": round(
                            (1 - math.prod(1 - v for v in losses.values())) * 100, 2
                        ),
                    },
                },  # end design

                # ── Energy production (from Shamsi AI) ────────────────────────
                "energy_production": {
                    "annual_kwh"             : res.get('annual_yield_kwh'),
                    "monthly_kwh"            : res.get('monthly_yield_kwh', []),
                    "specific_yield_kwh_kwp" : res.get('specific_yield'),
                    "performance_ratio"      : self._estimate_pr(res, system_kw),
                    "source"                 : "Shamsi CNN-LSTM yield model",
                },

                # ── Economics ─────────────────────────────────────────────────
                "economics": {
                    "currency"              : "EGP",
                    "total_cost"            : res.get('total_cost_egp'),
                    "cost_per_watt"         : res.get('cost_per_watt'),
                    "payback_years"         : res.get('payback_years'),
                    "lifetime_savings"      : res.get('lifetime_savings_egp'),
                    "lcoe_egp_per_kwh"      : self._estimate_lcoe(res, system_kw),
                },

                # ── Shamsi metadata ───────────────────────────────────────────
                "shamsi_metadata": {
                    "project_id"   : self.project.get('project_id'),
                    "optimiser"    : "NSGA-II Multi-Objective",
                    "ai_models"    : ["CNN-LSTM", "Random Forest V2", "PVWatts baseline"],
                    "export_date"  : datetime.now().isoformat(),
                    "export_format": "HelioScope JSON v1",
                },
            }
        }

    # ── Derived metrics ───────────────────────────────────────────────────────

    @staticmethod
    def _estimate_pr(results: Dict, system_kw: float) -> Optional[float]:
        """
        Performance Ratio ≈ annual_yield / (system_kw × annual_irradiation).
        Uses specific_yield / reference_yield (1000 h full-sun equivalent).
        """
        sy = results.get('specific_yield')
        if sy is None:
            return None
        # Egypt reference: ~1900 peak-sun-hours/year at best sites
        # PR = specific_yield / peak_sun_hours
        return round(sy / 1900, 3)

    @staticmethod
    def _estimate_lcoe(results: Dict, system_kw: float) -> Optional[float]:
        """
        Levelised Cost of Energy (EGP/kWh) over 25-year lifetime.
        LCOE = total_cost / (annual_kwh × 25 × degradation_factor)
        degradation_factor ≈ 22.4 (sum of (1-0.005)^t for t=1..25 with 0.5%/yr)
        """
        cost = results.get('total_cost_egp')
        kwh  = results.get('annual_yield_kwh')
        if not cost or not kwh:
            return None
        degradation_sum = sum((1 - 0.005) ** t for t in range(1, 26))
        lifetime_kwh    = kwh * degradation_sum
        return round(cost / lifetime_kwh, 3) if lifetime_kwh > 0 else None
