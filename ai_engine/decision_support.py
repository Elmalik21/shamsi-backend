"""
ai_engine/decision_support.py
Rule-based expert system DSS for Egyptian solar engineers.
Model 5 — Decision Support System
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class EgyptianDecisionSupport:
    """
    Rule-based expert system that translates AI outputs into
    human-readable recommendations for Egyptian solar engineers.

    Covers:
      - Best solution recommendation with explanation
      - Site-specific risk warnings
      - Maintenance schedule from dust zone
      - EGYPTERA net metering eligibility check
      - Structural inspection flag (building age > 40 years)
      - System type recommendation (on-grid / hybrid / off-grid)
    """

    # EGYPTERA net metering limits (Egyptian Electricity Law 2019)
    NET_METERING_LIMITS = {
        'RESIDENTIAL':       50,    # kW
        'COMMERCIAL':        500,   # kW
        'IRRIGATION_LV':     50,
        'OTHER_LV':          500,
        'MEDIUM_VOLTAGE':    5000,
        'HIGH_VOLTAGE':      50000,
        'EXTRA_HIGH_VOLTAGE': 50000,
    }

    def generate_recommendation(self, pareto_solutions: list,
                                 site_context: dict,
                                 dust_zone: dict) -> dict:
        """
        Generate a full recommendation package.

        Parameters
        ----------
        pareto_solutions : list of solution dicts from optimizer
        site_context     : dict with location, budget, area, usage_type,
                           building_age, roof_type, grid_reliability
        dust_zone        : dict from EgyptianDustClusterer.predict_zone()

        Returns
        -------
        dict:
            recommended_solution  – best balanced solution
            recommendation_reason – plain-language explanation (English + Arabic hint)
            system_type           – ON_GRID / HYBRID / OFF_GRID
            risks                 – list of risk warning dicts
            maintenance_schedule  – cleaning & service schedule
            net_metering          – eligibility and capacity info
            structural_inspection – bool flag
            financial_summary     – cost / payback / ROI summary
        """
        if not pareto_solutions:
            return {'error': 'No valid solutions found — relax budget or area constraints.'}

        # Pick the recommended solution (best balance of cost & energy)
        recommended = self._pick_balanced(pareto_solutions)

        system_type = self._recommend_system_type(
            site_context, recommended.get('annual_yield_kwh', 0)
        )

        risks = self._detect_site_risks(site_context)

        maintenance = self._generate_maintenance_schedule(dust_zone)

        net_metering = self._check_net_metering_eligibility(
            recommended.get('system_kw', 0),
            site_context.get('usage_type', 'RESIDENTIAL'),
        )

        structural = bool(site_context.get('building_age', 0) > 40)

        reason = self._build_reason(recommended, site_context, dust_zone, system_type)

        return {
            'recommended_solution':  recommended,
            'recommendation_reason': reason.get('en', '') if isinstance(reason, dict) else str(reason),
            'recommendation_reason_ar': reason.get('ar_hint', '') if isinstance(reason, dict) else '',
            'system_type':           system_type,
            'risks':                 risks,
            'maintenance_schedule':  maintenance,
            'net_metering':          net_metering,
            'structural_inspection': structural,
            'financial_summary': {
                'total_cost_egp':    recommended.get('total_cost_egp', 0),
                'payback_years':     recommended.get('payback_years', 0),
                'roi_25yr_egp':      recommended.get('roi_25yr_egp', 0),
                'annual_savings_egp':recommended.get('annual_savings_egp', 0),
            },
        }

    def _pick_balanced(self, solutions: list) -> dict:
        """
        Pick the most balanced solution using a simple weighted score.
        Normalises energy (max), cost (min), payback (min).
        """
        if len(solutions) == 1:
            return solutions[0]

        energies  = [s.get('annual_yield_kwh', 0) for s in solutions]
        costs     = [s.get('total_cost_egp', 1) for s in solutions]
        paybacks  = [s.get('payback_years', 99) for s in solutions]

        max_e, min_e = max(energies), min(energies)
        max_c, min_c = max(costs), min(costs)
        max_p, min_p = max(paybacks), min(paybacks)

        def score(s):
            e_norm = (s.get('annual_yield_kwh', 0) - min_e) / (max_e - min_e + 1e-9)
            c_norm = 1 - (s.get('total_cost_egp', 1) - min_c) / (max_c - min_c + 1e-9)
            p_norm = 1 - (s.get('payback_years', 99) - min_p) / (max_p - min_p + 1e-9)
            return 0.4 * e_norm + 0.3 * c_norm + 0.3 * p_norm

        return max(solutions, key=score)

    def _recommend_system_type(self, site_context: dict, annual_kwh: float) -> str:
        """Recommend ON_GRID / HYBRID / OFF_GRID based on site factors."""
        grid_reliability = site_context.get('grid_reliability', 'GOOD')
        include_battery  = site_context.get('include_battery', False)
        usage_type       = site_context.get('usage_type', 'RESIDENTIAL')

        if grid_reliability == 'POOR' or usage_type in ('IRRIGATION_LV', 'OTHER_LV'):
            return 'OFF_GRID'
        if include_battery or grid_reliability == 'MODERATE':
            return 'HYBRID'
        return 'ON_GRID'

    def _check_net_metering_eligibility(self, system_kw: float, usage_type: str) -> dict:
        """
        Check EGYPTERA net metering eligibility.
        Residential: up to 50 kW | Commercial: up to 500 kW
        Must have bi-directional meter.
        """
        limit = self.NET_METERING_LIMITS.get(usage_type, 50)
        eligible = system_kw <= limit

        return {
            'eligible':             eligible,
            'system_kw':            round(system_kw, 2),
            'max_kw_allowed':       limit,
            'requires_bidi_meter':  True,
            'authority':            'EGYPTERA',
            'notes': (
                'System qualifies for net metering under Egyptian Electricity Law.'
                if eligible
                else f'System ({system_kw:.1f} kW) exceeds the {limit} kW limit for {usage_type}.'
                     ' Consider splitting into multiple connections or upgrading tariff category.'
            ),
        }

    def _generate_maintenance_schedule(self, dust_zone: dict) -> dict:
        """Generate cleaning schedule based on dust zone."""
        zone_name    = dust_zone.get('name', 'MEDIUM')
        clean_days   = dust_zone.get('cleaning_days', 21)
        factor       = dust_zone.get('factor', 0.07)

        annual_cleans = round(365 / clean_days)

        return {
            'dust_zone':             zone_name,
            'dust_loss_factor':      factor,
            'cleaning_interval_days': clean_days,
            'annual_cleanings':      annual_cleans,
            'annual_inspection':     1,
            'tasks': [
                {
                    'task':      'Panel Cleaning',
                    'frequency': f'Every {clean_days} days',
                    'notes':     'Use demineralised water; clean early morning or evening.',
                },
                {
                    'task':      'Visual Inspection',
                    'frequency': 'Monthly',
                    'notes':     'Check for micro-cracks, shading obstructions, bird damage.',
                },
                {
                    'task':      'Inverter Check',
                    'frequency': 'Quarterly',
                    'notes':     'Verify error logs, cooling fan operation, firmware updates.',
                },
                {
                    'task':      'Full System Service',
                    'frequency': 'Annual',
                    'notes':     'Thermal imaging, IV curve trace, ground continuity test.',
                },
            ],
        }

    def _detect_site_risks(self, site_context: dict) -> list:
        """Detect site-specific risks for Egyptian conditions."""
        risks = []
        gov = site_context.get('governorate', '').lower()
        lat = site_context.get('latitude', 30.0)

        # Coastal salt risk
        coastal_govs = {'alexandria', 'matrouh', 'north sinai', 'port said',
                        'damietta', 'red sea', 'suez', 'south sinai', 'beheira',
                        'kafr el sheikh', 'ismailia'}
        if any(cg in gov for cg in coastal_govs):
            risks.append({
                'risk_type': 'COASTAL_SALT',
                'severity': 'HIGH',
                'description': 'Coastal salt air accelerates corrosion on mounting structures and connections.',
                'mitigation': 'Use marine-grade aluminium mounts, anti-corrosion cable glands, and annual connector inspection.',
            })

        # Extreme dust
        if site_context.get('dust_zone') in ('HIGH', 'EXTREME'):
            risks.append({
                'risk_type': 'EXTREME_DUST',
                'severity': 'HIGH',
                'description': 'High soiling rate will significantly reduce yield without frequent cleaning.',
                'mitigation': f'Clean every {site_context.get("cleaning_days", 14)} days; consider automatic cleaning system.',
            })

        # Old building
        if site_context.get('building_age', 0) > 40:
            risks.append({
                'risk_type': 'STRUCTURAL',
                'severity': 'HIGH',
                'description': 'Building is over 40 years old — roof load capacity must be verified.',
                'mitigation': 'Obtain structural engineer sign-off before installation. Consider lightweight mono panels.',
            })

        # Metal roof
        if site_context.get('roof_type', '').upper() == 'METAL':
            risks.append({
                'risk_type': 'METAL_ROOF',
                'severity': 'MEDIUM',
                'description': 'Metal roofs require non-penetration or specialised mounting brackets.',
                'mitigation': 'Use S-5! or equivalent clamp-based mounting system. Ensure thermal expansion gaps.',
            })

        # Extreme south heat
        if lat < 24.0:
            risks.append({
                'risk_type': 'EXTREME_HEAT',
                'severity': 'MEDIUM',
                'description': 'Temperatures above 45°C common — higher temperature derating losses expected.',
                'mitigation': 'Select panels with low temperature coefficient (TOPCon preferred). Ensure rear ventilation gap >= 10 cm.',
            })

        if not risks:
            risks.append({
                'risk_type': 'NONE',
                'severity': 'LOW',
                'description': 'No significant site-specific risks identified.',
                'mitigation': 'Follow standard installation practices.',
            })

        return risks

    def _build_reason(self, solution: dict, site_context: dict,
                      dust_zone: dict, system_type: str) -> dict:
        """Build a plain-language recommendation reason."""
        dust_name = dust_zone.get('name', 'MEDIUM')
        clean_d   = dust_zone.get('cleaning_days', 21)

        return {
            'en': (
                f"Recommended {solution.get('panel_brand')} {solution.get('panel_model')} "
                f"({solution.get('panel_count')} panels, {solution.get('system_kw')} kW) "
                f"with {solution.get('inverter_brand')} {solution.get('inverter_model')} inverter. "
                f"Expected yield: {solution.get('annual_yield_kwh', 0):,.0f} kWh/yr | "
                f"Payback: {solution.get('payback_years')} years | "
                f"25-yr ROI: {solution.get('roi_25yr_egp', 0):,.0f} EGP. "
                f"System type: {system_type}. "
                f"Dust zone: {dust_name} — clean every {clean_d} days."
            ),
            'ar_hint': (
                f"النظام الموصى به: {solution.get('panel_brand')} "
                f"({solution.get('panel_count')} لوح، {solution.get('system_kw')} كيلووات). "
                f"فترة الاسترداد: {solution.get('payback_years')} سنة."
            ),
        }
