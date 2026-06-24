"""
ai_engine/optimizer.py
NSGA-II Multi-Objective Solar System Optimizer for Egypt.
Model 2 — Core Optimizer

Reference: Deb et al. (2002) IEEE Trans. Evolutionary Computation 6(2):182-197.
"""
from __future__ import annotations
import random
import time
import uuid
import logging
import numpy as np

logger = logging.getLogger(__name__)


class EgyptianSolarOptimizer:
    """
    NSGA-II optimizer for Egyptian solar PV systems.

    Decision Variables: [panel_idx, inverter_idx, panel_count, tilt_angle]

    Objectives:
      f1 (maximize): annual energy yield (kWh)
      f2 (minimize): total system cost (EGP)  — includes 14% VAT
      f3 (maximize): space utilisation (%)

    Egyptian adaptations:
      - Dust loss factor from K-Means dust zone
      - Temperature derating from actual Egyptian climate data
      - EGYPTERA tiered tariffs for financial calculations
      - Real Egyptian market equipment prices (Jan–Mar 2026)
      - Egyptian VAT 14%
      - Tilt angle constrained to latitude ± 5°
    """

    # ── Adaptive parameters ───────────────────────────────────────────────────
    # These are defaults; run() will auto-tune based on search-space size.
    POPULATION_SIZE = 30
    GENERATIONS     = 20
    CROSSOVER_PROB  = 0.7
    MUTATION_PROB   = 0.3
    TOURNAMENT_SIZE = 2

    # Hard wall: never exceed this total wall-clock time (Railway 30s timeout)
    # Stop before 30s to allow response formatting and transmission.
    MAX_WALL_SECONDS = 22

    def __init__(self):
        # Use Model Registry singleton if available (loaded at startup)
        # — avoids re-loading 13 MB .pkl on every request
        try:
            from ai_engine.model_registry import registry
            self.yield_predictor = registry.yield_predictor
            self.dust_clusterer  = registry.dust_clusterer
            
            # If registry failed to load the model (e.g. numpy version mismatch), fallback
            if self.yield_predictor is None:
                from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
                self.yield_predictor = EgyptianYieldPredictorV2()
                
            if self.dust_clusterer is None:
                from ai_engine.dust_clustering import EgyptianDustClusterer
                self.dust_clusterer = EgyptianDustClusterer()
                
        except Exception:
            from ai_engine.yield_predictor_v2 import EgyptianYieldPredictorV2
            from ai_engine.dust_clustering import EgyptianDustClusterer
            self.yield_predictor = EgyptianYieldPredictorV2()
            self.dust_clusterer  = EgyptianDustClusterer()

    # ── Objective functions ───────────────────────────────────────────────────

    # ── Yield cache (pre-computed before evolution) ──────────────────────────

    def _build_yield_cache(self, context: dict) -> dict:
        """
        Pre-compute specific_yield (kWh/kWp) for every (panel_idx, tilt) pair
        that NSGA-II will ever need using highly optimized batch prediction.

        Without cache: 600+ RF calls per optimization run.
        With cache:    n_panels × 11 tilts ≈ 55–110 RF calls, then O(1) lookup.

        The cache stores specific_yield (kWh/kWp) for system_kw=1.
        _f1_energy multiplies by sys_kw at lookup time.
        """
        cache: dict = {}
        lat    = context['location']['latitude']
        tilts  = [round(lat + delta, 1) for delta in range(-5, 6)]  # 11 steps

        dust_factor = context['dust_zone']['factor']
        climate     = context['climate']

        # Pre-build feature list
        keys = []
        features_list = []
        for pi, panel in enumerate(context['panels']):
            for tilt in tilts:
                keys.append((pi, tilt))
                features_list.append({
                    'avg_ghi':          climate['avg_ghi'],
                    'avg_temperature':  climate['avg_temperature'],
                    'max_temperature':  climate['max_temperature'],
                    'avg_humidity':     climate['avg_humidity'],
                    'avg_wind_speed':   climate['avg_wind_speed'],
                    'dust_risk_score':  dust_factor,
                    'latitude':         lat,
                    'tilt_angle':       tilt,
                    'panel_efficiency': panel.efficiency_pct / 100.0,
                    'temp_coefficient': panel.temp_coefficient_pct,
                })

        try:
            # Batch predict
            preds = self.yield_predictor.predict_batch(features_list, system_kw=1.0)
            for key, pred in zip(keys, preds):
                cache[key] = pred
        except Exception as e:
            logger.warning("Batch prediction failed, falling back to individual loop: %s", e)
            # Individual loop fallback
            for key, features in zip(keys, features_list):
                try:
                    result = self.yield_predictor.predict(features, system_kw=1.0, calculate_interval=False)
                    cache[key] = result['predicted_annual_kwh']
                except Exception:
                    # physics fallback if RF unavailable
                    from ai_engine.export.calc_engine import transpose_irradiance
                    pi, tilt = key
                    panel = context['panels'][pi]
                    ghi  = climate['avg_ghi']
                    temp = climate['avg_temperature']
                    tc   = panel.temp_coefficient_pct
                    tl   = max(0.0, (temp - 25) * abs(tc) * 0.01)
                    lat  = context['location']['latitude']
                    # Calculate transposed POA factor using 12 representative days
                    representative_days = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
                    poa_factor = sum(transpose_irradiance(1.0, doy, lat, tilt) for doy in representative_days) / 12.0
                    cache[key] = ghi * poa_factor * 365 * 0.86 * (1 - tl) * (1 - dust_factor)

        logger.debug(
            "Yield cache built: %d entries for %d panels × %d tilts",
            len(cache), len(context['panels']), len(tilts),
        )
        return cache

    def _f1_energy(self, individual, context) -> float:
        """
        Objective 1: Maximise annual energy yield (kWh).

        Uses pre-computed yield_cache for O(1) lookup instead of calling
        the RF model on every evaluation — 10-20× faster than the old approach.
        """
        panel    = context['panels'][individual[0]]
        count    = individual[2]
        tilt     = round(individual[3], 1)
        sys_kw   = (count * panel.capacity_w) / 1000.0

        # O(1) cache lookup ─────────────────────────────────────────────────────
        yield_cache = context.get('yield_cache', {})
        cache_key   = (individual[0], tilt)
        specific_yield = yield_cache.get(cache_key)

        if specific_yield is None:
            # Nearest cached tilt (should rarely happen — only for mutated tilts
            # that fall outside the pre-computed grid)
            lat = context['location']['latitude']
            nearest_tilt = min(
                (k[1] for k in yield_cache if k[0] == individual[0]),
                key=lambda t: abs(t - tilt),
                default=lat,
            )
            specific_yield = yield_cache.get((individual[0], nearest_tilt))

        if specific_yield is None:
            # Absolute fallback — physics formula
            from ai_engine.export.calc_engine import transpose_irradiance
            c  = context['climate']
            d  = context['dust_zone']['factor']
            tc = panel.temp_coefficient_pct
            tl = max(0.0, (c['avg_temperature'] - 25) * abs(tc) * 0.01)
            # Calculate transposed POA factor using 12 representative days
            lat = context['location']['latitude']
            representative_days = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
            poa_factor = sum(transpose_irradiance(1.0, doy, lat, tilt) for doy in representative_days) / 12.0
            # PR = (1 - temp_loss) * (1 - dust_loss) * (1 - other_system_losses). Let's assume other system losses ~ 14% (so we multiply by 0.86)
            specific_yield = c['avg_ghi'] * poa_factor * 365 * (1 - tl) * (1 - d) * 0.86

        base_yield   = specific_yield * sys_kw
        shading_loss = context['site']['shading_loss_pct'] / 100.0
        return float(base_yield * (1 - shading_loss))

    def _f2_cost(self, individual, context) -> float:
        """Objective 2: Minimise total system cost (EGP) incl. 14% VAT."""
        panel    = context['panels'][individual[0]]
        inverter = context['inverters'][individual[1]]
        count    = individual[2]
        ic       = context['install_costs']
        sys_kw   = (count * panel.capacity_w) / 1000.0

        panel_cost    = count * panel.price_egp
        inverter_cost = inverter.price_egp
        mounting_cost = count * ic['mounting_avg']
        install_cost  = sys_kw * ic['labor_per_kw']
        wiring_cost   = sys_kw * ic['wiring_per_kw']

        subtotal        = panel_cost + inverter_cost + mounting_cost + install_cost + wiring_cost
        total_with_vat  = subtotal * 1.14   # Egyptian VAT 14%
        return float(total_with_vat)

    def _f3_space(self, individual, context) -> float:
        """Objective 3: Maximise space utilisation (%)."""
        panel     = context['panels'][individual[0]]
        count     = individual[2]
        used_area = count * panel.area_m2
        available = context['site']['available_area_m2']
        if used_area > available:
            return 0.0
        return float(used_area / available)

    def _evaluate(self, individual, context):
        """Evaluate all three objectives with hard constraint checks."""
        panel    = context['panels'][individual[0]]
        inverter = context['inverters'][individual[1]]
        count    = individual[2]
        tilt     = individual[3]

        # Hard constraint: panel count vs available area
        max_panels = int(context['site']['available_area_m2'] / panel.area_m2)
        if count > max_panels or count < 2:
            return (0.0, float('inf'), 0.0)

        # Get panel electrical specs
        panel_power = float(getattr(panel, 'capacity_w', 580.0))
        if panel_power >= 600:
            panel_vmp = 45.0
        elif panel_power >= 500:
            panel_vmp = 42.0
        elif panel_power >= 400:
            panel_vmp = 38.0
        else:
            panel_vmp = 34.0
        panel_imp = round(panel_power / panel_vmp, 2)
        panel_voc = round(panel_vmp * 1.2, 2)
        panel_isc = round(panel_imp * 1.05, 2)

        # Get inverter specs
        inverter_kw = float(getattr(inverter, 'capacity_kw', 10.0))
        max_dc_v = float(getattr(inverter, 'max_dc_voltage_v', None) or 1000.0)
        mppt_min_v = float(getattr(inverter, 'mppt_min_v', None) or 200.0)
        mppt_max_v = float(getattr(inverter, 'mppt_max_v', None) or 950.0)
        max_dc_current = float(getattr(inverter, 'max_dc_current_a', None) or 25.0)

        # Hard constraint: DC/AC ratio check (max 1.35)
        sys_kw = (count * panel_power) / 1000.0
        dc_ac = sys_kw / inverter_kw if inverter_kw > 0 else 1.0
        if dc_ac > 1.35:
            return (0.0, float('inf'), 0.0)

        # Calculate optimal string configuration for this individual candidate
        divisors = [i for i in range(1, count + 1) if count % i == 0]
        best_pps = None
        best_score = -1
        for d in divisors:
            vmp_str = d * panel_vmp
            voc_cold = d * panel_voc * 1.12
            fits_mppt = mppt_min_v <= vmp_str <= mppt_max_v
            fits_voc = voc_cold <= max_dc_v
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
            strings = count // best_pps
        else:
            panels_per_string = count
            strings = 1

        # Hard constraint: Parallel String Current overload check
        total_string_isc = strings * panel_isc
        if total_string_isc > max_dc_current:
            return (0.0, float('inf'), 0.0)

        # Hard constraint: Cold Voc Overvoltage check
        voc_cold_total = panels_per_string * panel_voc * 1.12
        if voc_cold_total > max_dc_v:
            return (0.0, float('inf'), 0.0)

        # Hard constraint: MPPT voltage ranges
        string_vmp_stc = panels_per_string * panel_vmp
        if string_vmp_stc < mppt_min_v or string_vmp_stc > mppt_max_v:
            return (0.0, float('inf'), 0.0)

        # Hard constraint: budget
        cost = self._f2_cost(individual, context)
        if cost > context['site']['budget_egp']:
            return (0.0, float('inf'), 0.0)

        # Hard constraint: tilt angle (latitude ± 5°)
        lat = context['location']['latitude']
        if not (lat - 5 <= tilt <= lat + 5):
            return (0.0, float('inf'), 0.0)

        energy = self._f1_energy(individual, context)
        space  = self._f3_space(individual, context)

        # Soft payback constraint: penalise solutions with payback > 15 years.
        # This guides evolution toward economically viable designs without
        # hard-rejecting them (keeps diversity in early generations).
        try:
            from solar_data.utils import calculate_annual_savings
            monthly_kwh = float(context['request'].get('monthly_consumption_kwh', 500))
            usage_type  = context['request'].get('usage_type', 'RESIDENTIAL')
            savings     = calculate_annual_savings(energy, usage_type, monthly_kwh)
            annual_save = savings['annual_savings_egp']
            payback     = (cost / annual_save) if annual_save > 0 else 99.0
            if payback > 15.0:
                # Penalise: reduce apparent energy so NSGA-II favours other solutions
                energy = energy * (15.0 / max(payback, 15.01))
        except Exception:
            pass  # non-fatal — continue with unpenalised objectives

        return (energy, cost, space)

    # ── Context builder ───────────────────────────────────────────────────────

    def _build_context(self, request_data: dict) -> dict:
        """Load all required data and return optimization context dict."""
        from solar_data.models import Location, DailyClimateData, SolarPanel, Inverter, InstallationCost
        from django.db.models import Avg, Max

        # Location & climate
        loc_id = request_data.get('location_id', 1)
        try:
            loc = Location.objects.select_related('governorate').get(location_id=loc_id)
        except Location.DoesNotExist:
            loc = Location.objects.select_related('governorate').first()
            if loc is None:
                raise ValueError("No locations in database. Load fixtures first.")

        agg = DailyClimateData.objects.filter(location=loc).aggregate(
            avg_ghi=Avg('allsky_sfc_sw_dwn'),
            avg_temp=Avg('t2m'),
            max_temp=Max('t2m_max'),
            avg_hum=Avg('rh2m'),
            avg_wind=Avg('ws2m'),
        )

        climate = {
            'avg_ghi':         agg['avg_ghi']  or 5.5,
            'avg_temperature': agg['avg_temp'] or 28.0,
            'max_temperature': agg['max_temp'] or 40.0,
            'avg_humidity':    agg['avg_hum']  or 40.0,
            'avg_wind_speed':  agg['avg_wind'] or 3.5,
        }

        dust_zone  = self.dust_clusterer.predict_zone(loc.location_id)
        panels     = list(SolarPanel.objects.filter(in_stock=True))
        inverters  = list(Inverter.objects.filter(in_stock=True))

        if not panels:
            raise ValueError("No solar panels in database. Load solar_equipment_2026 fixture.")
        if not inverters:
            raise ValueError("No inverters in database. Load solar_equipment_2026 fixture.")

        # Installation cost averages
        ic_qs = InstallationCost.objects.all()
        mounting_avg  = self._ic_avg(ic_qs, 'panel')
        labor_per_kw  = self._ic_avg(ic_qs, 'labor') * 1.43   # convert per-panel → per-kW estimate
        wiring_per_kw = self._ic_avg(ic_qs, 'wiring', default=4250.0)

        install_costs = {
            'mounting_avg':  mounting_avg,
            'labor_per_kw':  labor_per_kw,
            'wiring_per_kw': wiring_per_kw,
        }

        site_area = float(request_data.get('available_area_m2', 100.0))
        budget    = float(request_data.get('budget_egp', 150000.0))
        shading   = float(request_data.get('shading_loss_pct', 5.0))

        # Max panels across all panel types
        min_area  = min(p.area_m2 for p in panels)
        max_panels= max(4, int(site_area / min_area))

        return {
            'location':      {'latitude': loc.latitude, 'longitude': loc.longitude,
                              'name': loc.name, 'id': loc.location_id},
            'climate':       climate,
            'dust_zone':     dust_zone,
            'panels':        panels,
            'inverters':     inverters,
            'install_costs': install_costs,
            'site': {
                'available_area_m2': site_area,
                'budget_egp':        budget,
                'shading_loss_pct':  shading,
                'include_battery':   bool(request_data.get('include_battery', False)),
            },
            'max_panels':    max_panels,
            'request':       request_data,
        }

    def _ic_avg(self, qs, keyword: str, default: float = 700.0) -> float:
        """Lookup install cost average by keyword in item_name."""
        row = qs.filter(item_name__icontains=keyword).first()
        return row.price_avg_egp if row else default

    # ── NSGA-II helper classes ────────────────────────────────────────────────

    class _Individual(list):
        def __init__(self, *args):
            super().__init__(*args)
            self.fitness = None   # tuple (energy, cost, space)

    def _dominates(self, a, b) -> bool:
        """Return True if individual a dominates b (for maximising all objectives)."""
        fa, fb = a.fitness, b.fitness
        # Objectives: energy(max), cost(min→negate), space(max)
        # Normalise: all maximise → negate cost
        va = (fa[0], -fa[1], fa[2])
        vb = (fb[0], -fb[1], fb[2])
        return all(x >= y for x, y in zip(va, vb)) and any(x > y for x, y in zip(va, vb))

    def _non_dominated_sort(self, population):
        """Fast non-dominated sort. Returns list of fronts (lists of indices)."""
        n = len(population)
        S = [[] for _ in range(n)]   # dominated sets
        n_dom = [0] * n              # domination counts
        fronts = [[]]

        for p in range(n):
            for q in range(n):
                if p == q:
                    continue
                if self._dominates(population[p], population[q]):
                    S[p].append(q)
                elif self._dominates(population[q], population[p]):
                    n_dom[p] += 1
            if n_dom[p] == 0:
                fronts[0].append(p)

        i = 0
        while fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in S[p]:
                    n_dom[q] -= 1
                    if n_dom[q] == 0:
                        next_front.append(q)
            i += 1
            fronts.append(next_front)

        return fronts[:-1]   # remove empty last front

    def _crowding_distance(self, front, population):
        """Compute crowding distance for a front (list of indices)."""
        dist = {i: 0.0 for i in front}
        n_obj = 3
        for obj_idx in range(n_obj):
            sorted_f = sorted(front, key=lambda i: population[i].fitness[obj_idx])
            f_min = population[sorted_f[0]].fitness[obj_idx]
            f_max = population[sorted_f[-1]].fitness[obj_idx]
            if f_max == f_min:
                continue
            dist[sorted_f[0]]  = float('inf')
            dist[sorted_f[-1]] = float('inf')
            for k in range(1, len(sorted_f) - 1):
                dist[sorted_f[k]] += (
                    population[sorted_f[k+1]].fitness[obj_idx] -
                    population[sorted_f[k-1]].fitness[obj_idx]
                ) / (f_max - f_min)
        return dist

    def _tournament_select(self, population, fronts, crowding):
        """Binary tournament selection based on rank + crowding distance."""
        front_rank = {}
        for rank, front in enumerate(fronts):
            for idx in front:
                front_rank[idx] = rank

        candidates = random.sample(range(len(population)), self.TOURNAMENT_SIZE)
        best = candidates[0]
        for c in candidates[1:]:
            if front_rank.get(c, 999) < front_rank.get(best, 999):
                best = c
            elif (front_rank.get(c, 999) == front_rank.get(best, 999) and
                  crowding.get(c, 0.0) > crowding.get(best, 0.0)):
                best = c
        return best

    def _crossover(self, p1, p2, context):
        """Simulated binary crossover + panel/inverter uniform cross."""
        c1 = self._Individual(p1)
        c2 = self._Individual(p2)
        if random.random() < self.CROSSOVER_PROB:
            # Uniform crossover for integer genes
            for i in [0, 1]:  # panel_idx, inverter_idx
                if random.random() < 0.5:
                    c1[i], c2[i] = c2[i], c1[i]
            # Blend crossover for count & tilt
            alpha = random.random()
            c1[2] = int(alpha * p1[2] + (1 - alpha) * p2[2])
            c2[2] = int(alpha * p2[2] + (1 - alpha) * p1[2])
            c1[3] = round(alpha * p1[3] + (1 - alpha) * p2[3], 1)
            c2[3] = round(alpha * p2[3] + (1 - alpha) * p1[3], 1)
        return c1, c2

    def _mutate(self, individual, context):
        """Polynomial-like mutation."""
        ind = self._Individual(individual)
        lat = context['location']['latitude']
        if random.random() < self.MUTATION_PROB:
            # panel_idx
            ind[0] = random.randint(0, len(context['panels']) - 1)
        if random.random() < self.MUTATION_PROB:
            # inverter_idx
            ind[1] = random.randint(0, len(context['inverters']) - 1)
        if random.random() < self.MUTATION_PROB:
            # panel_count ±20%
            panel = context['panels'][ind[0]]
            inverter = context['inverters'][ind[1]]
            max_p_area = max(2, int(context['site']['available_area_m2'] / panel.area_m2))
            panel_kw = panel.capacity_w / 1000.0
            max_p_inv = max(2, int(1.35 * inverter.capacity_kw / panel_kw))
            max_p = min(max_p_area, max_p_inv)
            if max_p < 2:
                max_p = 2
            delta = random.randint(-3, 3)
            ind[2] = max(2, min(max_p, ind[2] + delta))
        if random.random() < self.MUTATION_PROB:
            # tilt ±2°
            ind[3] = round(
                max(lat - 5, min(lat + 5, ind[3] + random.uniform(-2, 2))), 1
            )
        return ind

    def _make_individual(self, context) -> '_Individual':
        lat     = context['location']['latitude']
        panel   = random.randint(0, len(context['panels']) - 1)
        inv     = random.randint(0, len(context['inverters']) - 1)
        pa      = context['panels'][panel]
        inverter = context['inverters'][inv]
        
        max_p_area = max(2, int(context['site']['available_area_m2'] / pa.area_m2))
        panel_kw = pa.capacity_w / 1000.0
        max_p_inv = max(2, int(1.35 * inverter.capacity_kw / panel_kw))
        max_p = min(max_p_area, max_p_inv)
        if max_p < 2:
            max_p = 2
            
        count   = random.randint(2, max_p) if max_p >= 2 else 2
        tilt    = round(lat + random.uniform(-5, 5), 1)
        ind     = self._Individual([panel, inv, count, tilt])
        ind.fitness = None
        return ind

    # ── Main optimisation loop ────────────────────────────────────────────────

    def run(self, request_data: dict) -> dict:
        """
        Main NSGA-II entry point — production-optimised.

        Improvements vs original:
          1. Yield cache: RF called ~55× instead of 600+  (10-20× faster)
          2. Adaptive pop/gen: scaled to search space size
          3. Timeout guard: stops early if approaching Railway 30s limit
          4. Soft dust membership: weighted dust factor, not hard cluster

        Args
        ----
        request_data: dict with keys:
            location_id, available_area_m2, monthly_consumption_kwh,
            usage_type, budget_egp, shading_loss_pct, include_battery

        Returns
        -------
        dict: run_id, convergence_time_sec, pareto_solutions, cache_hits
        """
        start  = time.time()
        run_id = str(uuid.uuid4())[:8]

        context = self._build_context(request_data)

        # ── Step 1: Build yield cache ─────────────────────────────────────────
        # All RF calls happen here — the evolution loop uses O(1) lookups.
        t_cache_start = time.time()
        context['yield_cache'] = self._build_yield_cache(context)
        cache_build_sec = round(time.time() - t_cache_start, 2)
        logger.info(
            "Yield cache built in %.2fs: %d entries",
            cache_build_sec, len(context['yield_cache']),
        )

        # ── Step 2: Adaptive population / generation sizing ───────────────────
        # Larger search space → more population needed for coverage
        n_panels    = len(context['panels'])
        n_inverters = len(context['inverters'])
        search_size = n_panels * n_inverters
        # Scale pop between 20 and 50; gens between 15 and 30
        pop_size = max(20, min(50, search_size * 3))
        n_gens   = max(15, min(30, search_size * 2))
        logger.info(
            "Adaptive NSGA-II: %d panels × %d inverters → pop=%d, gens=%d",
            n_panels, n_inverters, pop_size, n_gens,
        )

        # ── Step 3: Initialise population ────────────────────────────────────
        pop = [self._make_individual(context) for _ in range(pop_size)]
        for ind in pop:
            ind.fitness = self._evaluate(ind, context)

        # ── Step 4: Evolution with timeout guard ─────────────────────────────
        timed_out = False
        for gen in range(n_gens):
            # Hard timeout — return whatever we have before Railway kills us
            if time.time() - start > self.MAX_WALL_SECONDS:
                logger.warning(
                    "NSGA-II timeout at gen %d/%d (%.1fs > %.1fs limit)",
                    gen, n_gens, time.time() - start, self.MAX_WALL_SECONDS,
                )
                timed_out = True
                break

            fronts   = self._non_dominated_sort(pop)
            crowding = {}
            for front in fronts:
                crowding.update(self._crowding_distance(front, pop))

            offspring = []
            while len(offspring) < pop_size:
                i1 = self._tournament_select(pop, fronts, crowding)
                i2 = self._tournament_select(pop, fronts, crowding)
                c1, c2 = self._crossover(pop[i1], pop[i2], context)
                c1 = self._mutate(c1, context)
                c2 = self._mutate(c2, context)
                c1.fitness = self._evaluate(c1, context)
                c2.fitness = self._evaluate(c2, context)
                offspring.extend([c1, c2])

            combined = pop + offspring
            combined_fronts = self._non_dominated_sort(combined)
            combined_cd = {}
            for front in combined_fronts:
                combined_cd.update(self._crowding_distance(front, combined))

            new_pop = []
            for front in combined_fronts:
                if len(new_pop) + len(front) <= pop_size:
                    new_pop.extend([combined[i] for i in front])
                else:
                    remaining = pop_size - len(new_pop)
                    sorted_front = sorted(front, key=lambda i: combined_cd.get(i, 0), reverse=True)
                    new_pop.extend([combined[i] for i in sorted_front[:remaining]])
                    break
            pop = new_pop

        # ── Step 5: Extract Pareto front ──────────────────────────────────────
        final_fronts = self._non_dominated_sort(pop)
        pareto = [pop[i] for i in final_fronts[0]] if final_fronts else pop

        selected = self._select_diverse_solutions(pareto, context, n=5)

        elapsed = round(time.time() - start, 2)
        logger.info(
            "NSGA-II run %s complete: %.2fs, %d solutions, cache=%d entries, timed_out=%s",
            run_id, elapsed, len(selected), len(context['yield_cache']), timed_out,
        )

        return {
            'run_id':               run_id,
            'convergence_time_sec': elapsed,
            'cache_build_sec':      cache_build_sec,
            'pareto_solutions':     selected,
            'dust_zone_info':       context['dust_zone'],
            'location_info':        context['location'],
            'timed_out':            timed_out,
            'generations_run':      gen + 1 if not timed_out else gen,
        }

    # ── Solution formatting ───────────────────────────────────────────────────

    def _select_diverse_solutions(self, pareto, context, n: int = 5) -> list:
        """
        Select n diverse solutions from Pareto front.
        Sorts by energy yield descending, picks evenly spaced solutions.
        Enriches each with financial metrics.
        """
        from solar_data.utils import calculate_annual_savings

        # Filter valid solutions only
        valid = [ind for ind in pareto if ind.fitness and ind.fitness[1] != float('inf')]
        if not valid:
            return []

        # Sort by energy descending
        valid.sort(key=lambda ind: ind.fitness[0], reverse=True)

        # ── Brand-diverse selection ───────────────────────────────────────────
        # Pick solutions with diverse panel brands so the user sees real choice.
        # Strategy:
        #   1. Always include the top-energy solution.
        #   2. For remaining slots, prefer solutions with panel brands not yet chosen.
        #   3. If not enough diverse brands, fill remaining slots evenly-spaced.
        chosen: list = []
        seen_panel_brands: set = set()

        # Slot 1: best by energy
        chosen.append(valid[0])
        seen_panel_brands.add(context['panels'][valid[0][0]].brand)

        # Slots 2-n: prefer unseen brands
        for ind in valid[1:]:
            if len(chosen) >= n:
                break
            brand = context['panels'][ind[0]].brand
            if brand not in seen_panel_brands:
                chosen.append(ind)
                seen_panel_brands.add(brand)

        # Fill remaining slots if needed (same-brand fallback, evenly spaced)
        if len(chosen) < n:
            remaining_valid = [ind for ind in valid if ind not in chosen]
            still_need      = n - len(chosen)
            if remaining_valid:
                step   = max(1, len(remaining_valid) // still_need)
                extras = [remaining_valid[i * step]
                          for i in range(still_need)
                          if i * step < len(remaining_valid)]
                chosen.extend(extras)

        solutions = []
        monthly_kwh = float(context['request'].get('monthly_consumption_kwh', 500))
        usage_type  = context['request'].get('usage_type', 'RESIDENTIAL')

        for rank, ind in enumerate(chosen, start=1):
            panel    = context['panels'][ind[0]]
            inverter = context['inverters'][ind[1]]
            count    = ind[2]
            tilt     = ind[3]
            energy   = ind.fitness[0]
            cost     = ind.fitness[1]
            space    = ind.fitness[2]
            sys_kw   = (count * panel.capacity_w) / 1000.0

            savings  = calculate_annual_savings(energy, usage_type, monthly_kwh)
            annual_saving = savings['annual_savings_egp']

            # Calculate realistic payback (17% escalation, 0.45% degradation, 1200 EGP/yr maintenance)
            cumulative_s = 0.0
            payback = 25.0
            s = annual_saving
            for yr in range(1, 26):
                if yr > 1:
                    s *= (1 + 0.17) * (1 - 0.0045)
                else:
                    s *= (1 - 0.0045)
                
                net_saving = s - 1200.0
                cumulative_s += net_saving
                
                if cumulative_s >= cost and payback == 25.0:
                    prev_cum = cumulative_s - net_saving
                    if net_saving > 0:
                        frac = (cost - prev_cum) / net_saving
                        payback = round(yr - 1 + frac, 1)

            # 25-year ROI with 17% tariff escalation, 0.45% degradation
            roi_25yr = 0.0
            cum_saving = 0.0
            s = annual_saving
            for yr in range(1, 26):
                s *= (1 + 0.17)            # tariff escalation
                s *= (1 - 0.0045)          # panel degradation
                cum_saving += s
            roi_25yr = round(cum_saving - cost, 0)

            # Monthly production
            pred    = self.yield_predictor.predict({
                'avg_ghi':           context['climate']['avg_ghi'],
                'avg_temperature':   context['climate']['avg_temperature'],
                'max_temperature':   context['climate']['max_temperature'],
                'avg_humidity':      context['climate']['avg_humidity'],
                'avg_wind_speed':    context['climate']['avg_wind_speed'],
                'dust_risk_score':   context['dust_zone']['factor'],
                'latitude':          context['location']['latitude'],
                'tilt_angle':        tilt,
                'panel_efficiency':  panel.efficiency_pct / 100.0,
                'temp_coefficient':  panel.temp_coefficient_pct,
            }, system_kw=sys_kw, calculate_interval=False)

            # Performance ratio: PR = annual_yield / (system_kWp × GHI_annual)
            # where GHI_annual = avg_ghi (kWh/m²/day) × 365
            # This replaces the old incorrect constant of 1825.
            avg_ghi      = context['climate']['avg_ghi']
            ghi_annual   = avg_ghi * 365          # kWh/m²/yr = "peak sun hours"
            perf_ratio   = round(energy / (sys_kw * ghi_annual), 3) if (sys_kw > 0 and ghi_annual > 0) else 0.0

            solutions.append({
                'rank':                   rank,
                'panel_count':            count,
                'panel_brand':            panel.brand,
                'panel_model':            panel.model,
                'panel_capacity_w':       panel.capacity_w,
                'panel_type':             panel.panel_type,
                'panel_efficiency_pct':   panel.efficiency_pct,
                'inverter_brand':         inverter.brand,
                'inverter_model':         inverter.model,
                'inverter_type':          inverter.inverter_type,
                'inverter_kw':            inverter.capacity_kw,
                'tilt_angle':             tilt,
                'system_kw':              round(sys_kw, 2),
                'annual_yield_kwh':       round(energy, 0),
                'total_cost_egp':         round(cost, 0),
                'space_utilisation_pct':  round(space * 100, 1),
                'payback_years':          payback,
                'annual_savings_egp':     round(annual_saving, 0),
                'roi_25yr_egp':           roi_25yr,
                'monthly_production':     pred['predicted_monthly'],
                'dust_zone':              context['dust_zone']['name'],
                'cleaning_interval_days': context['dust_zone']['cleaning_days'],
                'performance_ratio':      perf_ratio,   # pre-computed, accurate
                'avg_ghi':               round(avg_ghi, 2),
            })

        return solutions
