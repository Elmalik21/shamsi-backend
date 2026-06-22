"""
solar_data/utils.py
Egyptian electricity bill & solar savings calculators.
Uses EGYPTERA August 2024 tariffs stored in ElectricityTariff model.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


_TARIFF_CACHE: dict = {}


def calculate_monthly_bill(monthly_kwh: float, usage_type: str = 'RESIDENTIAL') -> dict:
    """
    Calculate Egyptian electricity bill using EGYPTERA August 2024 tariffs.

    For RESIDENTIAL and COMMERCIAL the tariff is bracket-based:
      1. Determine the consumption bracket the monthly_kwh falls in.
      2. Apply the tiered rates within that bracket.

    For flat-rate types (IRRIGATION_LV, OTHER_LV, MEDIUM_VOLTAGE, HIGH_VOLTAGE,
    EXTRA_HIGH_VOLTAGE) a single rate applies to all kWh.

    Returns
    -------
    dict with keys:
        energy_cost_egp       – cost of energy (EGP)
        customer_service_fee  – fixed monthly fee (EGP)
        total_bill_egp        – energy + fee
        avg_price_per_kwh_egp – effective price per kWh
        tariff_breakdown      – list of dicts describing each tier used
    """
    from solar_data.models import ElectricityTariff  # lazy import to avoid circular

    kwh = float(monthly_kwh)
    if kwh <= 0:
        return {
            'energy_cost_egp': 0.0,
            'customer_service_fee': 0.0,
            'total_bill_egp': 0.0,
            'avg_price_per_kwh_egp': 0.0,
            'tariff_breakdown': [],
        }

    FLAT_TYPES = {'IRRIGATION_LV', 'OTHER_LV', 'MEDIUM_VOLTAGE',
                  'HIGH_VOLTAGE', 'EXTRA_HIGH_VOLTAGE'}

    global _TARIFF_CACHE

    if usage_type in FLAT_TYPES:
        if usage_type in _TARIFF_CACHE:
            rows = _TARIFF_CACHE[usage_type]
        else:
            rows = list(ElectricityTariff.objects.filter(usage_type=usage_type))
            _TARIFF_CACHE[usage_type] = rows
        if not rows:
            return _zero_bill()
        row = rows[0]
        energy_cost = kwh * row.price_egp_per_kwh
        fee = float(row.customer_service_fee)
        return {
            'energy_cost_egp': round(energy_cost, 2),
            'customer_service_fee': round(fee, 2),
            'total_bill_egp': round(energy_cost + fee, 2),
            'avg_price_per_kwh_egp': round(row.price_egp_per_kwh, 4),
            'tariff_breakdown': [{
                'tier': f'0-∞',
                'kwh': kwh,
                'rate_egp': row.price_egp_per_kwh,
                'cost_egp': round(energy_cost, 2),
            }],
        }

    # ── Bracket-based tariffs (RESIDENTIAL / COMMERCIAL) ─────────────────────
    # Find the bracket that contains monthly_kwh
    if usage_type in _TARIFF_CACHE:
        all_rows = _TARIFF_CACHE[usage_type]
    else:
        all_rows = list(
            ElectricityTariff.objects.filter(usage_type=usage_type)
            .order_by('consumption_bracket_min', 'tier_min_kwh')
        )
        _TARIFF_CACHE[usage_type] = all_rows
    if not all_rows:
        return _zero_bill()

    bracket_rows = _find_bracket_rows(all_rows, kwh)
    if not bracket_rows:
        # Fallback: use the highest bracket
        max_bracket = max(r.consumption_bracket_min for r in all_rows)
        bracket_rows = [r for r in all_rows if r.consumption_bracket_min == max_bracket]

    energy_cost = 0.0
    breakdown = []
    remaining = kwh

    for row in sorted(bracket_rows, key=lambda r: r.tier_min_kwh):
        tier_min = row.tier_min_kwh
        tier_max = row.tier_max_kwh if row.tier_max_kwh is not None else float('inf')
        tier_size = tier_max - tier_min
        kwh_in_tier = min(remaining, tier_size)
        if kwh_in_tier <= 0:
            break
        cost_in_tier = kwh_in_tier * row.price_egp_per_kwh
        energy_cost += cost_in_tier
        breakdown.append({
            'tier': f'{tier_min}-{row.tier_max_kwh or "∞"}',
            'kwh': round(kwh_in_tier, 2),
            'rate_egp': round(row.price_egp_per_kwh, 4),
            'cost_egp': round(cost_in_tier, 2),
        })
        remaining -= kwh_in_tier

    fee = float(bracket_rows[0].customer_service_fee)
    avg_rate = energy_cost / kwh if kwh > 0 else 0.0

    return {
        'energy_cost_egp': round(energy_cost, 2),
        'customer_service_fee': round(fee, 2),
        'total_bill_egp': round(energy_cost + fee, 2),
        'avg_price_per_kwh_egp': round(avg_rate, 4),
        'tariff_breakdown': breakdown,
    }


def _find_bracket_rows(all_rows, monthly_kwh: float):
    """Return the tariff rows for the bracket that covers monthly_kwh."""
    # Group rows by (bracket_min, bracket_max)
    brackets: dict[tuple, list] = {}
    for row in all_rows:
        key = (row.consumption_bracket_min, row.consumption_bracket_max)
        brackets.setdefault(key, []).append(row)

    # Find matching bracket
    for (b_min, b_max), rows in sorted(brackets.items()):
        upper = b_max if b_max is not None else float('inf')
        if b_min <= monthly_kwh <= upper:
            return rows

    return []


def _zero_bill() -> dict:
    return {
        'energy_cost_egp': 0.0,
        'customer_service_fee': 0.0,
        'total_bill_egp': 0.0,
        'avg_price_per_kwh_egp': 0.0,
        'tariff_breakdown': [],
    }


def calculate_annual_savings(
    annual_solar_kwh: float,
    usage_type: str,
    monthly_kwh_without_solar: float,
) -> dict:
    """
    Calculate annual savings from a solar system using Egyptian tariffs.
    Used by the NSGA-II fitness function.

    Parameters
    ----------
    annual_solar_kwh          : predicted annual yield from the solar system
    usage_type                : RESIDENTIAL | COMMERCIAL | ...
    monthly_kwh_without_solar : baseline monthly consumption (no solar)

    Returns
    -------
    dict with keys:
        monthly_savings_egp   – average monthly saving
        annual_savings_egp    – total yearly saving
        monthly_bill_without  – full bill without solar
        monthly_bill_with     – bill with solar offset applied
    """
    monthly_solar_kwh = annual_solar_kwh / 12.0
    monthly_net_kwh = max(0.0, monthly_kwh_without_solar - monthly_solar_kwh)

    bill_without = calculate_monthly_bill(monthly_kwh_without_solar, usage_type)
    bill_with = calculate_monthly_bill(monthly_net_kwh, usage_type)

    monthly_saving = bill_without['total_bill_egp'] - bill_with['total_bill_egp']
    annual_saving = monthly_saving * 12

    return {
        'monthly_savings_egp': round(monthly_saving, 2),
        'annual_savings_egp': round(annual_saving, 2),
        'monthly_bill_without': bill_without,
        'monthly_bill_with': bill_with,
    }
