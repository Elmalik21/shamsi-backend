"""
Shamsi Smart — Dynamic Admin Dashboard Views
"""
import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Max, Min, Count, Sum, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from solar_data.models import (
    Governorate, Location, DailyClimateData,
    MonthlySummary, ElectricityTariff, SolarPanel,
    Inverter, InstallationCost, DesignProject,
)


def is_staff(user):
    return user.is_authenticated and user.is_staff


# ── Auth ──────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dash:home')
    error = None
    if request.method == 'POST':
        user = authenticate(request,
            username=request.POST.get('username', ''),
            password=request.POST.get('password', ''))
        if user and user.is_staff:
            login(request, user)
            return redirect(request.GET.get('next', 'dash:home'))
        error = 'Invalid credentials or insufficient permissions.'
    return render(request, 'dashboard/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('dash:login')


# ── Home ──────────────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def home(request):
    total_locations = Location.objects.count()
    total_govs      = Governorate.objects.count()
    total_climate   = DailyClimateData.objects.count()
    total_projects  = DesignProject.objects.count()

    agg = DailyClimateData.objects.aggregate(
        avg_rad=Avg('allsky_sfc_sw_dwn'),
        avg_tmp=Avg('t2m'),
        max_rad=Max('allsky_sfc_sw_dwn'),
    )
    avg_radiation = round(agg['avg_rad'] or 0, 3)
    avg_temp      = round(agg['avg_tmp'] or 0, 1)
    max_radiation = round(agg['max_rad'] or 0, 3)

    top_locations = (
        Location.objects.select_related('governorate')
        .filter(solar_potential_score__isnull=False)
        .order_by('-solar_potential_score')[:10]
    )

    gov_radiation = (
        DailyClimateData.objects
        .values('location__governorate__name')
        .annotate(avg_rad=Avg('allsky_sfc_sw_dwn'))
        .order_by('-avg_rad')[:15]
    )
    gov_chart = {
        'labels': [r['location__governorate__name'] for r in gov_radiation],
        'values': [round(r['avg_rad'], 3) for r in gov_radiation],
    }

    monthly_trend = (
        DailyClimateData.objects
        .values('date__year', 'date__month')
        .annotate(avg_rad=Avg('allsky_sfc_sw_dwn'), avg_tmp=Avg('t2m'))
        .order_by('date__year', 'date__month')
    )
    trend_chart = {
        'labels':      ["%s-%02d" % (r['date__year'], r['date__month']) for r in monthly_trend],
        'radiation':   [round(r['avg_rad'], 3) for r in monthly_trend],
        'temperature': [round(r['avg_tmp'], 1) for r in monthly_trend],
    }

    cat_dist = (
        Location.objects
        .values('solar_potential_category')
        .annotate(count=Count('id'))
    )
    cat_chart = {
        'labels': [r['solar_potential_category'] or 'UNKNOWN' for r in cat_dist],
        'values': [r['count'] for r in cat_dist],
    }

    context = {
        'page': 'home',
        'total_locations': total_locations,
        'total_govs': total_govs,
        'total_climate': total_climate,
        'total_projects': total_projects,
        'avg_radiation': avg_radiation,
        'avg_temp': avg_temp,
        'max_radiation': max_radiation,
        'top_locations': top_locations,
        'gov_chart': json.dumps(gov_chart),
        'trend_chart': json.dumps(trend_chart),
        'cat_chart': json.dumps(cat_chart),
        'data_years': '2018-2026',
    }
    return render(request, 'dashboard/home.html', context)


# ── Locations ─────────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def locations_view(request):
    gov_filter = request.GET.get('gov', '')
    cat_filter = request.GET.get('cat', '')
    search     = request.GET.get('q', '')

    qs = Location.objects.select_related('governorate').annotate(
        climate_count=Count('climate_data')
    )
    if gov_filter:
        qs = qs.filter(governorate__name=gov_filter)
    if cat_filter:
        qs = qs.filter(solar_potential_category=cat_filter)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(governorate__name__icontains=search))
    qs = qs.order_by('-solar_potential_score')

    govs = Governorate.objects.order_by('name')
    cats = sorted(set(Location.objects.values_list('solar_potential_category', flat=True)))

    context = {
        'page': 'locations',
        'locations': qs,
        'govs': govs,
        'cats': cats,
        'gov_filter': gov_filter,
        'cat_filter': cat_filter,
        'search': search,
        'total': qs.count(),
    }
    return render(request, 'dashboard/locations.html', context)


# ── Location Detail ───────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def location_detail(request, location_id):
    try:
        loc = Location.objects.select_related('governorate').get(location_id=location_id)
    except Location.DoesNotExist:
        return render(request, 'dashboard/home.html', {'error': 'Location not found'}, status=404)

    stats = DailyClimateData.objects.filter(location=loc).aggregate(
        avg_rad=Avg('allsky_sfc_sw_dwn'),
        max_rad=Max('allsky_sfc_sw_dwn'),
        min_rad=Min('allsky_sfc_sw_dwn'),
        avg_tmp=Avg('t2m'),
        max_tmp=Max('t2m_max'),
        min_tmp=Min('t2m_min'),
        avg_hum=Avg('rh2m'),
        avg_wnd=Avg('ws2m'),
        total_rain=Sum('prectotcorr'),
        days=Count('id'),
    )
    for k, v in stats.items():
        if v is not None:
            stats[k] = round(v, 2)

    monthly_agg = (
        DailyClimateData.objects.filter(location=loc)
        .values('date__year', 'date__month')
        .annotate(avg_rad=Avg('allsky_sfc_sw_dwn'), avg_tmp=Avg('t2m'))
        .order_by('date__year', 'date__month')
    )

    last_90 = list(reversed(list(
        DailyClimateData.objects.filter(location=loc).order_by('-date')[:90]
    )))
    daily_chart = {
        'dates':       [str(d.date) for d in last_90],
        'radiation':   [round(float(d.allsky_sfc_sw_dwn or 0), 3) for d in last_90],
        'temperature': [round(float(d.t2m or 0), 1) for d in last_90],
        'humidity':    [round(float(d.rh2m or 0), 1) for d in last_90],
        'wind':        [round(float(d.ws2m or 0), 2) for d in last_90],
        'cloud':       [round(float(d.cloud_amt or 0), 1) for d in last_90],
    }
    monthly_chart = {
        'labels':    ["%s-%02d" % (r['date__year'], r['date__month']) for r in monthly_agg],
        'radiation': [round(r['avg_rad'], 3) for r in monthly_agg],
        'temp':      [round(r['avg_tmp'], 1) for r in monthly_agg],
    }

    score = loc.solar_potential_score or 0
    if score >= 80:
        rating, rating_color = 'Excellent', 'success'
    elif score >= 60:
        rating, rating_color = 'Very Good', 'info'
    elif score >= 40:
        rating, rating_color = 'Good', 'warning'
    else:
        rating, rating_color = 'Moderate', 'secondary'

    context = {
        'page': 'locations',
        'loc': loc,
        'stats': stats,
        'daily_chart': json.dumps(daily_chart),
        'monthly_chart': json.dumps(monthly_chart),
        'rating': rating,
        'rating_color': rating_color,
    }
    return render(request, 'dashboard/location_detail.html', context)


# ── Governorates ──────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def governorates_view(request):
    govs = (
        Governorate.objects
        .annotate(
            loc_count=Count('locations'),
            avg_rad=Avg('locations__climate_data__allsky_sfc_sw_dwn'),
            avg_tmp=Avg('locations__climate_data__t2m'),
        )
        .order_by('-avg_rad')
    )
    map_data = [
        {
            'name': g.name,
            'avg_rad': round(g.avg_rad or 0, 3),
            'avg_tmp': round(g.avg_tmp or 0, 1),
            'loc_count': g.loc_count,
        }
        for g in govs
    ]
    context = {
        'page': 'governorates',
        'govs': govs,
        'map_data': json.dumps(map_data),
    }
    return render(request, 'dashboard/governorates.html', context)


# ── Climate ───────────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def climate_view(request):
    year_filter  = request.GET.get('year', '')
    month_filter = request.GET.get('month', '')
    loc_filter   = request.GET.get('loc', '')

    qs = DailyClimateData.objects.select_related('location', 'location__governorate')
    if year_filter:
        qs = qs.filter(date__year=year_filter)
    if month_filter:
        qs = qs.filter(date__month=month_filter)
    if loc_filter:
        qs = qs.filter(location__location_id=loc_filter)

    agg = qs.aggregate(
        avg_rad=Avg('allsky_sfc_sw_dwn'),
        max_rad=Max('allsky_sfc_sw_dwn'),
        avg_tmp=Avg('t2m'),
        total_rain=Sum('prectotcorr'),
        count=Count('id'),
    )
    for k, v in agg.items():
        if v is not None:
            agg[k] = round(v, 2)

    recent = qs.order_by('-date')[:200]
    locations_list = Location.objects.order_by('name').values('location_id', 'name')

    context = {
        'page': 'climate',
        'recent': recent,
        'agg': agg,
        'locations_list': locations_list,
        'years': list(range(2018, 2027)),
        'months': list(range(1, 13)),
        'year_filter': year_filter,
        'month_filter': month_filter,
        'loc_filter': loc_filter,
    }
    return render(request, 'dashboard/climate.html', context)


# ── Equipment ─────────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def equipment_view(request):
    panels       = SolarPanel.objects.all().order_by('-efficiency_pct')
    inverters    = Inverter.objects.all().order_by('-capacity_kw')
    install_cost = InstallationCost.objects.all()
    tariffs      = ElectricityTariff.objects.all().order_by('usage_type', 'consumption_bracket_min')

    context = {
        'page': 'equipment',
        'panels': panels,
        'inverters': inverters,
        'install_cost': install_cost,
        'tariffs': tariffs,
    }
    return render(request, 'dashboard/equipment.html', context)


# ── Projects ──────────────────────────────────

@login_required(login_url='dash:login')
@user_passes_test(is_staff, login_url='dash:login')
def projects_view(request):
    status_filter = request.GET.get('status', '')
    qs = DesignProject.objects.select_related('location')
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs.order_by('-created_at')

    agg = DesignProject.objects.aggregate(
        total=Count('project_id'),
        total_area=Sum('available_area_m2'),
        avg_consumption=Avg('monthly_consumption_kwh'),
    )
    statuses = sorted(set(DesignProject.objects.values_list('status', flat=True)))

    context = {
        'page': 'projects',
        'projects': qs,
        'agg': agg,
        'statuses': statuses,
        'status_filter': status_filter,
    }
    return render(request, 'dashboard/projects.html', context)


# ── AJAX ──────────────────────────────────────

@login_required(login_url='dash:login')
@require_GET
def ajax_gov_radiation(request):
    data = list(
        DailyClimateData.objects
        .values('location__governorate__name')
        .annotate(avg_rad=Avg('allsky_sfc_sw_dwn'), avg_tmp=Avg('t2m'))
        .order_by('-avg_rad')
    )
    return JsonResponse({'data': data})


@login_required(login_url='dash:login')
@require_GET
def ajax_monthly_trend(request):
    loc_id = request.GET.get('loc')
    qs = DailyClimateData.objects
    if loc_id:
        qs = qs.filter(location__location_id=loc_id)
    data = list(
        qs.values('date__year', 'date__month')
        .annotate(avg_rad=Avg('allsky_sfc_sw_dwn'), avg_tmp=Avg('t2m'))
        .order_by('date__year', 'date__month')
    )
    return JsonResponse({'data': data})


@login_required(login_url='dash:login')
@require_GET
def ajax_top_locations(request):
    data = list(
        Location.objects
        .filter(solar_potential_score__isnull=False)
        .order_by('-solar_potential_score')[:20]
        .values('name', 'governorate__name', 'solar_potential_score',
                'avg_solar_radiation', 'avg_temperature', 'solar_potential_category')
    )
    return JsonResponse({'data': data})
