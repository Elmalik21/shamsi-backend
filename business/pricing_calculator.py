"""
pricing_calculator.py
=====================
Financial model for Shamsi Smart's SaaS pricing.

Calculates:
- MRR projections under different conversion assumptions
- LTV / CAC ratios per tier
- Break-even analysis
- Sensitivity analysis (churn and conversion rate)
- Monthly cashflow table (18 months)

Usage:
    python business/pricing_calculator.py
    python business/pricing_calculator.py --months 24
    python business/pricing_calculator.py --churn-pro 0.02 --conv 0.06
    python business/pricing_calculator.py --csv > projections.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Model parameters
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PricingModel:
    # Tier prices (USD/month)
    price_pro:        float = 29.0
    price_enterprise: float = 499.0

    # Unit economics
    variable_cost_per_user: float = 0.20   # USD/month
    fixed_cost_monthly:     float = 27.0   # hosting, domain, email
    payroll_monthly:        float = 0.0    # add when funded

    # Conversion and churn
    new_free_per_month:     int   = 30     # organic + paid free signups
    conv_free_to_pro:       float = 0.05   # 5% of free convert to Pro
    conv_free_to_ent:       float = 0.005  # 0.5% convert to Enterprise
    churn_pro:              float = 0.03   # 3% monthly Pro churn
    churn_enterprise:       float = 0.01   # 1% monthly Enterprise churn

    # Customer acquisition cost
    cac_pro:        float = 40.0
    cac_enterprise: float = 200.0


@dataclass
class MonthlyState:
    month:        int
    free_users:   int
    pro_users:    int
    ent_users:    int
    new_pro:      int
    new_ent:      int
    churned_pro:  int
    churned_ent:  int
    mrr:          float
    costs:        float
    profit:       float
    cumulative_revenue: float
    cumulative_costs:   float


# ─────────────────────────────────────────────────────────────────────────────
# Core model
# ─────────────────────────────────────────────────────────────────────────────

def run_projection(model: PricingModel, months: int = 18) -> List[MonthlyState]:
    """
    Simulate monthly user and revenue growth.
    Returns list of MonthlyState records.
    """
    states: List[MonthlyState] = []
    free    = 0
    pro     = 0
    ent     = 0
    cum_rev = 0.0
    cum_cos = 0.0

    for m in range(1, months + 1):
        # New signups grow 10% month-over-month after month 3
        growth_factor = 1.0 + max(0, m - 3) * 0.10
        new_free = int(model.new_free_per_month * growth_factor)

        # Conversions from free pool
        new_pro = int((free + new_free) * model.conv_free_to_pro)
        new_ent = int((free + new_free) * model.conv_free_to_ent)

        # Churn
        churned_pro = int(pro * model.churn_pro)
        churned_ent = int(ent * model.churn_enterprise)

        # Update counts
        free = free + new_free - new_pro - new_ent
        pro  = pro + new_pro - churned_pro
        ent  = ent + new_ent - churned_ent

        # Revenue
        mrr = (pro * model.price_pro) + (ent * model.price_enterprise)

        # Costs
        total_users = free + pro + ent
        variable = total_users * model.variable_cost_per_user
        total_costs = model.fixed_cost_monthly + model.payroll_monthly + variable

        profit = mrr - total_costs
        cum_rev += mrr
        cum_cos += total_costs

        states.append(MonthlyState(
            month=m,
            free_users=free, pro_users=pro, ent_users=ent,
            new_pro=new_pro, new_ent=new_ent,
            churned_pro=churned_pro, churned_ent=churned_ent,
            mrr=mrr, costs=total_costs, profit=profit,
            cumulative_revenue=cum_rev,
            cumulative_costs=cum_cos,
        ))

    return states


def compute_unit_economics(model: PricingModel) -> dict:
    """LTV, CAC, payback period per tier."""
    ltv_pro = model.price_pro / model.churn_pro
    ltv_ent = model.price_enterprise / model.churn_enterprise

    payback_pro = model.cac_pro / (model.price_pro - model.variable_cost_per_user)
    payback_ent = model.cac_enterprise / (model.price_enterprise - model.variable_cost_per_user)

    return {
        'ltv_pro':          round(ltv_pro, 0),
        'ltv_ent':          round(ltv_ent, 0),
        'cac_pro':          model.cac_pro,
        'cac_ent':          model.cac_enterprise,
        'ltv_cac_pro':      round(ltv_pro / model.cac_pro, 1),
        'ltv_cac_ent':      round(ltv_ent / model.cac_enterprise, 1),
        'payback_pro_months': round(payback_pro, 1),
        'payback_ent_months': round(payback_ent, 1),
        'gross_margin_pro': round((model.price_pro - model.variable_cost_per_user) / model.price_pro * 100, 1),
        'gross_margin_ent': round((model.price_enterprise - model.variable_cost_per_user) / model.price_enterprise * 100, 1),
    }


def sensitivity_analysis(model: PricingModel) -> dict:
    """
    Vary churn and conversion rate to show MRR at Month 12 under different scenarios.
    Returns a 3×3 matrix (pessimistic / base / optimistic).
    """
    scenarios = {
        'pessimistic': {'conv_free_to_pro': 0.03, 'churn_pro': 0.05},
        'base':        {'conv_free_to_pro': 0.05, 'churn_pro': 0.03},
        'optimistic':  {'conv_free_to_pro': 0.08, 'churn_pro': 0.015},
    }
    results = {}
    for name, overrides in scenarios.items():
        m = PricingModel(**{**model.__dict__, **overrides})
        states = run_projection(m, months=12)
        s12 = states[-1]
        results[name] = {
            'mrr_m12': round(s12.mrr, 0),
            'pro_m12': s12.pro_users,
            'ent_m12': s12.ent_users,
            'profit_m12': round(s12.profit, 0),
        }
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Output formatters
# ─────────────────────────────────────────────────────────────────────────────

def print_projection(states: List[MonthlyState], unit_econ: dict) -> None:
    print("\n" + "═" * 80)
    print("  Shamsi Smart — Financial Projections")
    print("═" * 80)

    print(f"\n  Unit Economics")
    print(f"    Pro:        LTV ${unit_econ['ltv_pro']:,.0f}  "
          f"CAC ${unit_econ['cac_pro']}  "
          f"LTV/CAC {unit_econ['ltv_cac_pro']}x  "
          f"Payback {unit_econ['payback_pro_months']} months  "
          f"Margin {unit_econ['gross_margin_pro']}%")
    print(f"    Enterprise: LTV ${unit_econ['ltv_ent']:,.0f}  "
          f"CAC ${unit_econ['cac_ent']}  "
          f"LTV/CAC {unit_econ['ltv_cac_ent']}x  "
          f"Payback {unit_econ['payback_ent_months']} months  "
          f"Margin {unit_econ['gross_margin_ent']}%")

    print(f"\n  {'Mo':>3}  {'Free':>6}  {'Pro':>5}  {'Ent':>4}  "
          f"{'MRR':>8}  {'Costs':>7}  {'Profit':>8}  {'Cum Rev':>9}")
    print("  " + "─" * 68)

    highlights = {3, 6, 9, 12, 18}
    for s in states:
        marker = " ◄" if s.month in highlights else ""
        profit_str = f"${s.profit:+,.0f}"
        print(f"  {s.month:>3}  {s.free_users:>6,}  {s.pro_users:>5,}  {s.ent_users:>4,}  "
              f"${s.mrr:>7,.0f}  ${s.costs:>6,.0f}  {profit_str:>9}  "
              f"${s.cumulative_revenue:>8,.0f}{marker}")

    final = states[-1]
    print("\n  Summary at Month " + str(final.month))
    print(f"    MRR:              ${final.mrr:,.0f}")
    print(f"    ARR:              ${final.mrr * 12:,.0f}")
    print(f"    Cumulative Revenue:${final.cumulative_revenue:,.0f}")
    print(f"    Operating Profit: ${final.profit:+,.0f}/month")


def print_sensitivity(results: dict) -> None:
    print("\n  Sensitivity Analysis — MRR at Month 12")
    print(f"  {'Scenario':15}  {'MRR':>8}  {'Pro':>5}  {'Enterprise':>10}  {'Profit':>8}")
    print("  " + "─" * 55)
    for name, r in results.items():
        print(f"  {name:15}  ${r['mrr_m12']:>7,.0f}  {r['pro_m12']:>5,}  "
              f"{r['ent_m12']:>10,}  ${r['profit_m12']:>+7,.0f}")


def export_csv(states: List[MonthlyState]) -> None:
    writer = csv.writer(sys.stdout)
    writer.writerow(['month','free','pro','enterprise','mrr','costs','profit',
                     'cumulative_revenue','cumulative_costs'])
    for s in states:
        writer.writerow([s.month, s.free_users, s.pro_users, s.ent_users,
                         round(s.mrr, 2), round(s.costs, 2), round(s.profit, 2),
                         round(s.cumulative_revenue, 2), round(s.cumulative_costs, 2)])


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description='Shamsi Smart — SaaS Financial Model')
    p.add_argument('--months',       type=int,   default=18,   help='Projection horizon (default 18)')
    p.add_argument('--price-pro',    type=float, default=29.0, help='Pro tier monthly price USD')
    p.add_argument('--price-ent',    type=float, default=499.0,help='Enterprise tier monthly price USD')
    p.add_argument('--conv',         type=float, default=0.05, help='Free→Pro monthly conversion rate')
    p.add_argument('--churn-pro',    type=float, default=0.03, help='Pro monthly churn rate')
    p.add_argument('--new-free',     type=int,   default=30,   help='New free signups per month (base)')
    p.add_argument('--payroll',      type=float, default=0.0,  help='Monthly payroll cost USD')
    p.add_argument('--csv',          action='store_true',      help='Output CSV instead of table')
    p.add_argument('--sensitivity',  action='store_true',      help='Show sensitivity analysis')
    return p.parse_args()


def main():
    args = parse_args()

    model = PricingModel(
        price_pro=args.price_pro,
        price_enterprise=args.price_ent,
        conv_free_to_pro=args.conv,
        churn_pro=args.churn_pro,
        new_free_per_month=args.new_free,
        payroll_monthly=args.payroll,
    )

    states      = run_projection(model, months=args.months)
    unit_econ   = compute_unit_economics(model)

    if args.csv:
        export_csv(states)
        return

    print_projection(states, unit_econ)

    if args.sensitivity:
        sens = sensitivity_analysis(model)
        print_sensitivity(sens)

    print()


if __name__ == '__main__':
    main()
