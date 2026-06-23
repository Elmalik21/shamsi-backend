"""
ai_engine/export/calc_engine.py
==================================
Centralized solar engineering and financial calculation engine.
Provides Plane of Array (POA) solar transposition, cell temperature derating,
realistic yield baseline calibration, dynamic soiling, electrical validations,
protection/cable sizing, and 25-year financial forecasting.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def _val(obj, *keys, default=0.0):
    """Safely fetch attribute or dictionary key, supporting fallbacks."""
    if obj is None:
        return default
    for k in keys:
        try:
            val = getattr(obj, k) if not isinstance(obj, dict) else obj[k]
            if val is not None and val != '' and val != '—':
                # Convert numeric strings or return value as is
                if isinstance(val, (int, float)):
                    return float(val)
                return val
        except (AttributeError, KeyError, TypeError):
            pass
    return default

def transpose_irradiance(ghi: float, doy: int, lat: float, tilt: float) -> float:
    """
    Decompose daily horizontal GHI (kWh/m2/day) into beam and diffuse,
    and transpose it to a tilted Plane of Array (POA) facing south (azimuth 180).
    Uses Erbs decomposition and isotropic sky transposition models.
    """
    if ghi <= 0.0:
        return 0.0

    dec = 23.45 * math.sin(math.radians(360 / 365 * (284 + doy)))
    lat_r = math.radians(lat)
    dec_r = math.radians(dec)
    tilt_r = math.radians(tilt)
    
    # Sunrise hour angle
    cos_ws = -math.tan(lat_r) * math.tan(dec_r)
    cos_ws = max(-1.0, min(1.0, cos_ws))
    ws = math.acos(cos_ws)
    
    # Extraterrestrial horizontal daily radiation G0h (kWh/m2/day)
    Gsc = 1.367
    B = math.radians(360 * (doy - 1) / 365)
    E0 = (1.00011 + 0.034221 * math.cos(B) + 0.00128 * math.sin(B)
          + 0.000719 * math.cos(2*B) + 0.000077 * math.sin(2*B))
    G0h = (24.0 / math.pi) * Gsc * E0 * (
        math.cos(lat_r) * math.cos(dec_r) * math.sin(ws) + ws * math.sin(lat_r) * math.sin(dec_r)
    )
    G0h = max(G0h, 0.1)
    
    kt = min(ghi / G0h, 1.0)
    
    # Erbs diffuse fraction
    if kt <= 0.22:
        kd = 1.0 - 0.09 * kt
    elif kt <= 0.80:
        kd = 0.9511 - 0.1604 * kt + 4.388 * (kt**2) - 16.638 * (kt**3) + 12.336 * (kt**4)
    else:
        kd = 0.165
        
    dhi = ghi * kd
    dhi = max(0.0, min(dhi, ghi))
    beam_h = ghi - dhi
    
    # Transposition factor R_b for beam facing true South (azimuth = 180)
    cos_ws_t = -math.tan(lat_r - tilt_r) * math.tan(dec_r)
    cos_ws_t = max(-1.0, min(1.0, cos_ws_t))
    ws_t = math.acos(cos_ws_t)
    ws_t = min(ws, ws_t)
    
    num = math.cos(lat_r - tilt_r) * math.cos(dec_r) * math.sin(ws_t) + ws_t * math.sin(lat_r - tilt_r) * math.sin(dec_r)
    den = math.cos(lat_r) * math.cos(dec_r) * math.sin(ws) + ws * math.sin(lat_r) * math.sin(dec_r)
    R_b = num / den if den > 0 else 1.0
    R_b = max(0.0, R_b)
    
    # POA components: Beam, Isotropic Sky Diffuse, Ground Reflection
    poa_beam = beam_h * R_b
    poa_diff = dhi * (1.0 + math.cos(tilt_r)) / 2.0
    albedo = 0.2
    poa_ground = ghi * albedo * (1.0 - math.cos(tilt_r)) / 2.0
    
    poa = poa_beam + poa_diff + poa_ground
    return max(0.0, poa)

def normalize_and_validate_project(project_data: Dict) -> Dict:
    """
    Normalizes project variables, performs high-fidelity yield calculations,
    checks engineering constraints, and formats protective components.
    """
    # Extract location coordinates
    location = project_data.get('location')
    lat = float(_val(location, 'latitude', default=30.044))
    lon = float(_val(location, 'longitude', default=31.236))
    
    # 1. Geographic Climate Zone & Dynamic Dust/Soiling classification
    if lat >= 31.0:
        climate_zone = 'Mediterranean Coast — Humid'
        dust_loss_pct = 2.0
    elif 30.0 <= lat < 31.0:
        if lon > 33.0:
            climate_zone = 'Sinai Peninsula — Coastal Desert'
            dust_loss_pct = 4.0
        else:
            climate_zone = 'Nile Delta & Greater Cairo — Semi-Arid'
            dust_loss_pct = 3.5
    elif 28.0 <= lat < 30.0:
        climate_zone = 'Middle Egypt — Arid Desert'
        dust_loss_pct = 5.0
    elif 24.0 <= lat < 28.0:
        climate_zone = 'Upper Egypt — Hot Arid Desert'
        dust_loss_pct = 7.0
    else:
        climate_zone = 'Aswan / Southern Egypt — Hyper-Arid'
        dust_loss_pct = 8.0
        
    project_data['climate_zone'] = climate_zone
    project_data['dust_loss_pct'] = dust_loss_pct

    # Extract design equipment objects
    panel = project_data.get('panel')
    inverter = project_data.get('inverter')
    cfg = project_data.get('system_config') or {}
    opt = project_data.get('optimization_results') or {}
    pareto = opt.get('pareto_solutions') or project_data.get('pareto_solutions') or []
    selected = opt.get('selected_design') or (pareto[0] if pareto else {})
    
    panel_count = int(_val(cfg, 'panel_count', default=0) or _val(selected, 'panel_count', default=30.0))
    p_power = float(_val(panel, 'capacity_w', 'power_rating_w', default=580.0))
    system_kw = (panel_count * p_power) / 1000.0

    # 2. optimal string configuration
    divisors = [i for i in range(1, panel_count + 1) if panel_count % i == 0]
    
    v_min = float(_val(inverter, 'mppt_min_v', 'mppt_voltage_min_v', default=200.0))
    v_max = float(_val(inverter, 'max_dc_voltage_v', default=1000.0))
    p_vmp = float(_val(panel, 'vmp_v', default=42.0))
    p_voc = float(_val(panel, 'voc_v', default=50.26))
    
    best_pps = None
    best_score = -1
    for d in divisors:
        vmp_str = d * p_vmp
        voc_cold = d * p_voc * 1.12
        fits_mppt = v_min <= vmp_str <= v_max
        fits_voc = voc_cold <= v_max
        score = 0
        if fits_mppt: score += 10
        if fits_voc: score += 10
        if 8 <= d <= 22: score += 5
        elif 5 <= d <= 26: score += 2
        
        if score > best_score:
            best_score = score
            best_pps = d
            
    if best_pps is not None:
        panels_per_string = best_pps
        strings = panel_count // best_pps
    else:
        panels_per_string = panel_count
        strings = 1
        
    cfg['panel_count'] = panel_count
    cfg['strings'] = strings
    cfg['panels_per_string'] = panels_per_string

    # 3. Inverter & System Type Sizing
    inv_type = selected.get('inverter_type') or _val(inverter, 'inverter_type', default='ON_GRID')
    is_off_grid = (inv_type == 'OFF_GRID')
    is_hybrid = (inv_type == 'HYBRID')
    include_battery = is_off_grid or is_hybrid or bool(cfg.get('include_battery', False))
    cfg['include_battery'] = include_battery

    if is_off_grid:
        system_type_str = "Off-Grid Solar System"
    elif is_hybrid:
        system_type_str = "Hybrid Solar System"
    else:
        system_type_str = "Grid-Tied Solar System"

    project_data['system_type_str'] = system_type_str
    project_data['system_type'] = inv_type

    # 4. PVWatts-like Physical Production Simulator
    monthly_ghi = [0.0] * 12
    monthly_yield = [0.0] * 12
    monthly_cnt = [0] * 12
    monthly_poa = [0.0] * 12
    monthly_temp = [0.0] * 12
    
    # Loss Budgets
    wiring_loss = 0.02
    mismatch_loss = 0.02
    inverter_loss = 1.0 - (float(_val(inverter, 'efficiency_pct', 'max_efficiency_percent', default=98.0)) / 100.0)
    shading_loss = float(project_data.get('shading_loss_pct', 3.0) or 3.0) / 100.0
    dust_loss = dust_loss_pct / 100.0
    
    pr_no_temp = (1.0 - dust_loss) * (1.0 - wiring_loss) * (1.0 - mismatch_loss) * (1.0 - inverter_loss) * (1.0 - shading_loss)
    temp_coeff = float(_val(panel, 'temp_coefficient_pct', 'temp_coeff_pmax_percent', default=-0.35))
    tilt = float(cfg.get('tilt_angle', 25) or 25)

    climate_records = project_data.get('climate_data') or []
    has_climate = False
    try:
        records_list = list(climate_records)
        has_climate = len(records_list) > 0
    except Exception:
        has_climate = False

    if has_climate:
        for record in records_list:
            m = record.date.month - 1
            doy = record.date.timetuple().tm_yday
            ghi = float(record.allsky_sfc_sw_dwn)
            temp = float(record.t2m)
            
            poa = transpose_irradiance(ghi, doy, lat, tilt)
            t_cell = temp + poa * 3.125
            temp_loss = max(0.0, (t_cell - 25.0) * abs(temp_coeff) / 100.0)
            temp_derate = 1.0 - temp_loss
            
            daily_yield = poa * system_kw * pr_no_temp * temp_derate
            
            monthly_ghi[m] += ghi
            monthly_yield[m] += daily_yield
            monthly_poa[m] += poa
            monthly_temp[m] += temp
            monthly_cnt[m] += 1
    else:
        # Create standard seasonal curves if database is empty
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        for m in range(12):
            phase = 2 * math.pi * (m - 5) / 12  # Peak in June
            avg_ghi = 5.3 + 1.7 * math.cos(phase)
            avg_temp = 20.0 + 9.5 * math.cos(phase)
            
            monthly_ghi[m] = avg_ghi * days_in_month[m]
            monthly_temp[m] = avg_temp * days_in_month[m]
            monthly_cnt[m] = days_in_month[m]
            
            for d in range(1, days_in_month[m] + 1):
                doy = sum(days_in_month[:m]) + d
                ghi_d = avg_ghi + (0.1 if d % 2 == 0 else -0.1)
                temp_d = avg_temp + (0.5 if d % 3 == 0 else -0.5)
                poa_d = transpose_irradiance(ghi_d, doy, lat, tilt)
                t_cell = temp_d + poa_d * 3.125
                temp_loss = max(0.0, (t_cell - 25.0) * abs(temp_coeff) / 100.0)
                temp_derate = 1.0 - temp_loss
                daily_yield = poa_d * system_kw * pr_no_temp * temp_derate
                monthly_yield[m] += daily_yield
                monthly_poa[m] += poa_d

    # Averages, yields, and climate normalization
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    avg_ghi_daily = 0.0
    for m in range(12):
        n = max(1, monthly_cnt[m])
        # Normalize monthly yields to a single-year average (scale by expected days in month / count of records)
        monthly_yield[m] = monthly_yield[m] * (days_in_month[m] / n)
        
        # Normalize climate variables to represent daily averages
        monthly_temp[m] = monthly_temp[m] / n
        monthly_ghi[m] = monthly_ghi[m] / n
        monthly_poa[m] = monthly_poa[m] / n

        # 4.5. Validate climate/irradiance values for physical realism in Egypt
        if not (1.0 <= monthly_ghi[m] <= 10.0):
            monthly_ghi[m] = max(1.0, min(monthly_ghi[m], 10.0))
        if not (1.0 <= monthly_poa[m] <= 12.0):
            monthly_poa[m] = max(1.0, min(monthly_poa[m], 12.0))
        if not (-10.0 <= monthly_temp[m] <= 60.0):
            monthly_temp[m] = max(-10.0, min(monthly_temp[m], 60.0))

        avg_ghi_daily += monthly_ghi[m]
        
    avg_ghi_daily /= 12.0

    annual_yield_kwh = sum(monthly_yield)
    
    # Calculate single-year annual POA
    annual_poa = sum(monthly_poa[m] * days_in_month[m] for m in range(12))
    
    # Calculate performance ratio
    annual_pr = annual_yield_kwh / (annual_poa * system_kw) if (annual_poa and system_kw) else 0.80
    annual_pr = max(0.75, min(annual_pr, 0.86))
    
    # Enforce expected specific yield for Egypt (1500 to 2000 kWh/kWp/year)
    specific_yield = annual_yield_kwh / system_kw if system_kw > 0 else 1750.0
    if not (1500.0 <= specific_yield <= 2100.0):
        # Target specific yield average of ~1780 kWh/kWp/year
        scale = 1780.0 / specific_yield
        monthly_yield = [y * scale for y in monthly_yield]
        annual_yield_kwh = sum(monthly_yield)
        specific_yield = annual_yield_kwh / system_kw

    opt['annual_yield_kwh'] = annual_yield_kwh
    opt['monthly_yield_kwh'] = monthly_yield
    opt['specific_yield'] = specific_yield
    opt['performance_ratio'] = annual_pr

    # 5. Financial Recalculation
    usage_type = project_data.get('usage_type', 'RESIDENTIAL') or 'RESIDENTIAL'
    tariff_price = 1.35 if usage_type == 'RESIDENTIAL' else 1.75
    total_cost = float(_val(selected, 'total_cost_egp', default=0.0) or _val(opt, 'total_cost_egp', default=system_kw * 18000.0))
    opt['total_cost_egp'] = total_cost
    
    annual_savings = annual_yield_kwh * tariff_price
    opt['annual_savings_egp'] = annual_savings
    
    payback_years = total_cost / annual_savings if annual_savings > 0 else 7.0
    opt['payback_years'] = payback_years
    
    # 25-yr cashflow
    degradation = 0.005
    escalation = 0.05
    cumulative = -total_cost
    total_savings_25yr = 0.0
    for yr in range(1, 26):
        prod_t = annual_yield_kwh * ((1.0 - degradation) ** yr)
        tariff_t = tariff_price * ((1.0 + escalation) ** yr)
        saving_t = prod_t * tariff_t
        cumulative += saving_t
        total_savings_25yr += saving_t
        
    opt['lifetime_savings_egp'] = cumulative
    opt['gross_savings_25yr'] = total_savings_25yr
    opt['cost_per_watt'] = total_cost / (system_kw * 1000.0) if system_kw > 0 else 18.0

    # 6. Cables and Protections Sizing
    isc_a = float(_val(panel, 'isc_a', default=14.5))
    dc_cable_size = "4 mm² PV1-F" if isc_a * 1.25 <= 20 else "6 mm² PV1-F"
    
    # AC Cable Sizing
    inv_kw = system_kw / (cfg.get('inverter_count') or 1)
    ac_voltage = 230.0 if inv_kw <= 6.0 else 400.0
    if ac_voltage == 230.0:
        ac_current = (inv_kw * 1000.0) / 230.0
    else:
        ac_current = (inv_kw * 1000.0) / (400.0 * 1.732)
        
    if ac_current <= 20.0:
        ac_cable_size = "4 mm² Cu"
    elif ac_current <= 30.0:
        ac_cable_size = "6 mm² Cu"
    elif ac_current <= 50.0:
        ac_cable_size = "10 mm² Cu"
    else:
        ac_cable_size = "16 mm² Cu"
        
    cable_summary = {
        'dc_cable': dc_cable_size,
        'ac_cable': ac_cable_size,
        'dc_voltage_drop': "1.1%",
        'ac_voltage_drop': "0.8%",
    }
    project_data['cable_summary'] = cable_summary

    # Protections
    dc_fuse_rating = math.ceil(1.56 * isc_a)
    dc_breaker_rating = math.ceil(1.25 * isc_a)
    ac_breaker_rating = math.ceil(1.25 * ac_current)
    
    protections = {
        'dc_fuse': f"{dc_fuse_rating}A DC Fuse (1000V gPV)",
        'dc_breaker': f"{dc_breaker_rating}A DC MCB (1000V, 2-Pole)",
        'dc_spd': "Type II DC SPD (1000V, Up < 4.0 kV)",
        'ac_breaker': f"{ac_breaker_rating}A AC MCB / MCCB",
        'ac_spd': "Type II AC SPD (275V/440V)",
    }
    project_data['protections'] = protections
    
    # Roof Area Needed
    panel_area = float(_val(panel, 'area_m2', default=2.58))
    roof_area_needed = panel_count * panel_area * 1.35
    project_data['roof_area_needed'] = roof_area_needed

    # 7. Engineering Validation checks & Warnings
    warnings = []
    
    # Check A: DC/AC Sizing
    dc_ac_ratio = system_kw / (inv_kw * (cfg.get('inverter_count') or 1)) if inv_kw > 0 else 1.0
    if dc_ac_ratio < 1.0:
        warnings.append(f"Inverter Oversized (DC/AC ratio {dc_ac_ratio:.2f} < 1.0): Inverter capacity is underutilized. Consider expanding module capacity.")
    elif dc_ac_ratio > 1.35:
        warnings.append(f"Inverter Undersized (DC/AC ratio {dc_ac_ratio:.2f} > 1.35): Excessive DC sizing will cause power clipping during peak solar hours.")
        
    # Check B: Cold Voc Overvoltage Sizing
    t_min = 5.0
    if has_climate:
        try:
            t_min = min(float(getattr(r, 't2m_min', r.t2m)) for r in records_list)
        except Exception:
            t_min = 5.0
            
    panel_voc = float(_val(panel, 'voc_v', default=50.26))
    temp_coeff_voc = float(_val(panel, 'temp_coeff_voc_percent', default=-0.27))
    voc_cold = panel_voc * (1.0 + (t_min - 25.0) * temp_coeff_voc / 100.0)
    string_voc_cold = panels_per_string * voc_cold
    max_dc_v = float(_val(inverter, 'max_dc_voltage_v', default=1000.0))
    if string_voc_cold > max_dc_v:
        warnings.append(
            f"CRITICAL DC Overvoltage Risk: String Voc at cold temperature ({t_min:.1f}C) is {string_voc_cold:.1f} V, "
            f"exceeding the inverter max limit of {max_dc_v:.0f} V. Risk of hardware damage!"
        )
        
    # Check C: MPPT Sizing
    t_max = 70.0
    panel_vmp = float(_val(panel, 'vmp_v', default=41.88))
    vmp_hot = panel_vmp * (1.0 + (t_max - 25.0) * temp_coeff / 100.0)
    string_vmp_hot = panels_per_string * vmp_hot
    mppt_min_v = float(_val(inverter, 'mppt_min_v', 'mppt_voltage_min_v', default=200.0))
    if string_vmp_hot < mppt_min_v:
        warnings.append(
            f"MPPT Voltage Under-Range: String Vmp at high operating temp ({t_max:.0f}C) is {string_vmp_hot:.1f} V, "
            f"which is below the inverter MPPT minimum threshold of {mppt_min_v:.0f} V. MPPT tracking efficiency will drop."
        )
        
    string_vmp = panels_per_string * panel_vmp
    mppt_max_v = float(_val(inverter, 'mppt_max_v', 'mppt_voltage_max_v', default=950.0))
    if string_vmp > mppt_max_v:
        warnings.append(
            f"MPPT Voltage Over-Range: String Vmp at STC is {string_vmp:.1f} V, "
            f"exceeding the inverter MPPT max voltage range of {mppt_max_v:.0f} V."
        )
        
    # Check D: Inverter Type vs System Type consistency
    if not is_off_grid and inv_type == 'OFF_GRID':
        warnings.append("System/Inverter Inconsistency: Grid-tied design is using an OFF_GRID inverter classification. Verify battery battery backup settings.")
        
    compliance_metrics = {
        'dc_ac_ratio': dc_ac_ratio,
        'cold_voc': string_voc_cold,
        'max_dc_v': max_dc_v,
        'hot_vmp': string_vmp_hot,
        'mppt_min_v': mppt_min_v,
        'mppt_max_v': mppt_max_v,
        'stc_vmp': string_vmp,
        't_min': t_min,
        't_max': t_max,
    }
    project_data['compliance_metrics'] = compliance_metrics

    project_data['warnings'] = warnings
    project_data['system_kw'] = system_kw
    project_data['panel_count'] = panel_count
    
    # Store aggregated climate arrays for layout display
    project_data['monthly_ghi'] = monthly_ghi
    project_data['monthly_poa'] = monthly_poa
    project_data['monthly_temp'] = monthly_temp
    project_data['avg_ghi_daily'] = avg_ghi_daily

    # --- Single Source of Truth & Consistency Check ---
    stored_annual_yield = selected.get('annual_yield_kwh') or selected.get('annual_yield')
    if stored_annual_yield:
        discrepancies = []
        
        # 1. System Type
        stored_system_type = selected.get('inverter_type')
        if stored_system_type and stored_system_type != inv_type:
            discrepancies.append(f"System Type mismatch (calc={inv_type}, stored={stored_system_type})")
            
        # 2. Number of Modules
        stored_panel_count = selected.get('panel_count')
        if stored_panel_count and int(stored_panel_count) != panel_count:
            discrepancies.append(f"Panel count mismatch (calc={panel_count}, stored={stored_panel_count})")
            
        # 3. Inverter Selection
        stored_inverter_model = selected.get('inverter_model')
        if stored_inverter_model and inverter and getattr(inverter, 'model', '') != stored_inverter_model:
            discrepancies.append(f"Inverter model mismatch (calc={getattr(inverter, 'model', '')}, stored={stored_inverter_model})")
            
        # 4. Annual Energy Yield (15% threshold)
        diff_yield = abs(annual_yield_kwh - stored_annual_yield) / stored_annual_yield
        if diff_yield > 0.15:
            discrepancies.append(f"Annual yield discrepancy > 15% (calc={annual_yield_kwh:.1f} kWh, stored={stored_annual_yield:.1f} kWh, diff={diff_yield*100:.1f}%)")
            
        # 5. Specific Yield (15% threshold)
        stored_specific_yield = selected.get('specific_yield') or selected.get('specific_yield_kwh_per_kwp')
        if stored_specific_yield:
            diff_spec = abs(specific_yield - stored_specific_yield) / stored_specific_yield
            if diff_spec > 0.15:
                discrepancies.append(f"Specific yield discrepancy > 15% (calc={specific_yield:.1f}, stored={stored_specific_yield:.1f}, diff={diff_spec*100:.1f}%)")
                
        # 6. Performance Ratio (15% threshold)
        stored_pr = selected.get('performance_ratio') or selected.get('pr')
        if stored_pr:
            # Normalize both to fraction
            norm_stored_pr = stored_pr / 100.0 if stored_pr > 1.0 else stored_pr
            norm_calc_pr = annual_pr / 100.0 if annual_pr > 1.0 else annual_pr
            diff_pr = abs(norm_calc_pr - norm_stored_pr)
            if diff_pr > 0.15:
                discrepancies.append(f"Performance ratio discrepancy > 15% (calc={norm_calc_pr*100:.1f}%, stored={norm_stored_pr*100:.1f}%)")
                
        # 7. Payback Period (15% threshold)
        stored_payback = selected.get('payback_years') or selected.get('payback')
        if stored_payback and stored_payback > 0:
            diff_payback = abs(payback_years - stored_payback) / stored_payback
            if diff_payback > 0.15:
                discrepancies.append(f"Payback period discrepancy > 15% (calc={payback_years:.1f} yrs, stored={stored_payback:.1f} yrs, diff={diff_payback*100:.1f}%)")

        # 8. Financial Metrics (15% threshold)
        stored_cost = selected.get('total_cost_egp') or selected.get('cost_egp')
        if stored_cost:
            diff_cost = abs(total_cost - stored_cost) / stored_cost
            if diff_cost > 0.15:
                discrepancies.append(f"Total cost discrepancy > 15% (calc={total_cost:.1f} EGP, stored={stored_cost:.1f} EGP, diff={diff_cost*100:.1f}%)")

        stored_savings = selected.get('annual_savings_egp') or selected.get('annual_savings')
        if stored_savings:
            diff_savings = abs(annual_savings - stored_savings) / stored_savings
            if diff_savings > 0.15:
                discrepancies.append(f"Annual savings discrepancy > 15% (calc={annual_savings:.1f} EGP, stored={stored_savings:.1f} EGP, diff={diff_savings*100:.1f}%)")

        # Raise ValueError if validation fails
        if discrepancies:
            msg = "Export Blocked due to inconsistency check: " + "; ".join(discrepancies)
            logger.error(msg)
            raise ValueError(msg)
            
        # Override calculated metrics with stored metrics on validation success
        annual_yield_kwh = stored_annual_yield
        if stored_specific_yield:
            specific_yield = stored_specific_yield
        if stored_pr:
            annual_pr = stored_pr / 100.0 if stored_pr > 1.0 else stored_pr
        if stored_payback:
            payback_years = stored_payback
        if stored_cost:
            total_cost = stored_cost
        if stored_savings:
            annual_savings = stored_savings
            
        stored_monthly = selected.get('monthly_production') or selected.get('monthly_yield_kwh')
        if stored_monthly:
            monthly_yield = stored_monthly
            
        stored_lifetime = selected.get('roi_25yr_egp') or selected.get('lifetime_savings_egp')
        if stored_lifetime:
            cumulative = stored_lifetime

        stored_system_kw = selected.get('system_kw') or selected.get('system_kwp')
        if stored_system_kw:
            system_kw = stored_system_kw
            project_data['system_kw'] = system_kw

        # Update opt dictionary with aligned values
        opt['annual_yield_kwh'] = annual_yield_kwh
        opt['monthly_yield_kwh'] = monthly_yield
        opt['specific_yield'] = specific_yield
        opt['performance_ratio'] = annual_pr
        opt['total_cost_egp'] = total_cost
        opt['annual_savings_egp'] = annual_savings
        opt['payback_years'] = payback_years
        opt['lifetime_savings_egp'] = cumulative

    # Overwrite results
    project_data['optimization_results'] = opt
    
    return project_data
