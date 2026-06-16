import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shamsi_smart.settings')
django.setup()

import time
from ai_engine.optimizer import EgyptianSolarOptimizer
from ai_engine.dust_clustering import EgyptianDustClusterer
from solar_data.models import Location, SolarPanel, Inverter

def test_pipeline():
    print("="*80)
    print("1. Testing Dust Clustering (Environmental Classification)")
    print("="*80)
    clusterer = EgyptianDustClusterer()
    # Test for multiple distinct locations
    locations = Location.objects.filter(name__in=['Aswan', 'Alexandria', 'Cairo', 'Giza'])
    
    if locations.exists():
        for loc in locations:
            zone = clusterer.predict_zone(loc.location_id)
            print(f"Location: {loc.name:<15} | Dust Zone: {zone['name']:<10} | Factor: {zone['factor']:<5} | Cleaning Days: {zone['cleaning_days']}")
    else:
        # Fallback to first available location
        loc = Location.objects.first()
        if loc:
            zone = clusterer.predict_zone(loc.location_id)
            print(f"Location: {loc.name:<15} | Dust Zone: {zone['name']:<10} | Factor: {zone['factor']:<5} | Cleaning Days: {zone['cleaning_days']}")


    print("\n" + "="*80)
    print("2. Testing NSGA-II Optimizer Pipeline (Deep Dive)")
    print("="*80)
    
    loc = Location.objects.filter(name__icontains='Cairo').first() or Location.objects.first()
    if not loc:
        print("No locations found in DB!")
        return

    request_data = {
        'location_id': loc.location_id,
        'available_area_m2': 80.0,  # 80 sqm roof
        'monthly_consumption_kwh': 1000, # high consumption
        'budget_egp': 300000, # 300k EGP budget
        'usage_type': 'RESIDENTIAL',
        'shading_loss_pct': 3.0,
        'include_battery': False
    }
    print(f"Request Context: Location={loc.name}, Area={request_data['available_area_m2']}m2, Budget={request_data['budget_egp']} EGP")
    
    optimizer = EgyptianSolarOptimizer()
    
    start_time = time.time()
    
    print("\n[Step 1] Building Optimizer Context...")
    context = optimizer._build_context(request_data)
    print(f"  - Climate: GHI={context['climate']['avg_ghi']:.2f}, Temp={context['climate']['avg_temperature']:.1f}C")
    print(f"  - Dust Zone Applied: {context['dust_zone']['name']}")
    print(f"  - Search Space: {len(context['panels'])} panels x {len(context['inverters'])} inverters = {len(context['panels'])*len(context['inverters'])} combinations")
    print(f"  - Area Constraint: Max {context['max_panels']} panels allowed")
    
    print("\n[Step 2] Building Yield Cache (The Optimizer Bottleneck Fix)...")
    t0 = time.time()
    context['yield_cache'] = optimizer._build_yield_cache(context)
    print(f"  - Success! Built {len(context['yield_cache'])} predictions cache in {time.time()-t0:.2f}s")
    
    print("\n[Step 3] Initializing Genetic Population...")
    pop_size = 20
    n_gens = 10
    pop = [optimizer._make_individual(context) for _ in range(pop_size)]
    for ind in pop:
        ind.fitness = optimizer._evaluate(ind, context)
    
    print(f"  - Initialized Population of {pop_size} PV System Designs.")
    print("  - Evaluating 3 sample solutions from initial population:")
    for i in range(3):
        # individual = [panel_idx, inverter_idx, panel_count, tilt]
        sys_kw = (pop[i][2] * context['panels'][pop[i][0]].capacity_w) / 1000
        print(f"    [Ind {i}] {sys_kw}kW system, Tilt: {pop[i][3]}° -> Fitness(Energy, Cost, Area_Utilized): {pop[i].fitness}")

    print("\n[Step 4] Running Evolution Loop (NSGA-II)...")
    for gen in range(n_gens):
        fronts = optimizer._non_dominated_sort(pop)
        crowding = {}
        for front in fronts:
            crowding.update(optimizer._crowding_distance(front, pop))
            
        offspring = []
        while len(offspring) < pop_size:
            i1 = optimizer._tournament_select(pop, fronts, crowding)
            i2 = optimizer._tournament_select(pop, fronts, crowding)
            c1, c2 = optimizer._crossover(pop[i1], pop[i2], context)
            c1 = optimizer._mutate(c1, context)
            c2 = optimizer._mutate(c2, context)
            c1.fitness = optimizer._evaluate(c1, context)
            c2.fitness = optimizer._evaluate(c2, context)
            offspring.extend([c1, c2])
            
        combined = pop + offspring
        combined_fronts = optimizer._non_dominated_sort(combined)
        combined_cd = {}
        for front in combined_fronts:
            combined_cd.update(optimizer._crowding_distance(front, combined))
            
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
        
        valid = [ind for ind in pop if ind.fitness[1] != float('inf')]
        if valid:
            best_energy = max(valid, key=lambda x: x.fitness[0])
            best_cost = min(valid, key=lambda x: x.fitness[1])
            print(f"  - Gen {gen+1:02d}: Max Energy = {best_energy.fitness[0]:,.0f} kWh | Min Cost = {best_cost.fitness[1]:,.0f} EGP")
        else:
            print(f"  - Gen {gen+1:02d}: No valid solutions (Budget/Area Constraints violated)")

    print("\n[Step 5] Extracting & Formatting Pareto Front...")
    final_fronts = optimizer._non_dominated_sort(pop)
    pareto = [pop[i] for i in final_fronts[0]] if final_fronts else pop
    selected = optimizer._select_diverse_solutions(pareto, context, n=5)
    
    print(f"\nExtracted {len(selected)} optimal solutions on the Pareto Front.")
    if selected:
        print("\n--- TOP RECOMMENDED SOLUTION ---")
        s = selected[0]
        print(f"  Panel Setup  : {s['panel_count']}x {s['panel_brand']} {s['panel_capacity_w']}W ({s['system_kw']} kW total)")
        print(f"  Inverter     : {s['inverter_brand']} {s['inverter_kw']} kW")
        print(f"  Optimal Tilt : {s['tilt_angle']}°")
        print(f"  Performance  : PR = {s['performance_ratio']*100:.1f}%, Yield = {s['annual_yield_kwh']:,.0f} kWh/yr")
        print(f"  Financials   : Total Cost = {s['total_cost_egp']:,.0f} EGP, Payback = {s['payback_years']} yrs")
        print(f"  Area Utilized: {s['space_utilisation_pct']:.1f}% of roof")

    print("\n" + "="*80)
    print(f"Pipeline Test Completed in {time.time()-start_time:.2f} seconds")
    print("="*80)

if __name__ == '__main__':
    test_pipeline()
