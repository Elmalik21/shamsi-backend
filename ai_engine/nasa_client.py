import requests
import datetime
import math
import logging

logger = logging.getLogger(__name__)

NASA_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point'

def fetch_nasa_climate_for_coords(lat, lon):
    """
    Fetches the last 365 days of climate data from NASA POWER for given coordinates.
    Uses Django cache to prevent redundant API calls for 24 hours.
    Returns:
        dict: {
            'agg': {
                'avg_ghi': float,
                'avg_temp': float,
                'max_temp': float,
                'avg_hum': float,
                'avg_wind': float
            },
            'daily_records': list of dicts for CNN-LSTM
                [{'allsky_sfc_sw_dwn': float, 't2m': float, 'rh2m': float, 'ws2m': float}, ...]
        }
    """
    # NASA POWER is usually 5-7 days delayed. We fetch the last full year available.
    end_date = datetime.datetime.now() - datetime.timedelta(days=7)
    start_date = end_date - datetime.timedelta(days=364)
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    cache_key = f"nasa_power_{lat:.4f}_{lon:.4f}_{start_str}_{end_str}"
    from django.core.cache import cache
    cached_data = cache.get(cache_key)
    if cached_data:
        logger.info(f"Using cached NASA climate data for {lat},{lon}")
        return cached_data
    
    params = {
        'parameters': 'ALLSKY_SFC_SW_DWN,T2M,T2M_MAX,RH2M,WS2M',
        'community': 'RE',
        'longitude': lon,
        'latitude': lat,
        'start': start_str,
        'end': end_str,
        'format': 'JSON'
    }
    
    try:
        logger.info(f"Fetching NASA climate data for {lat},{lon}...")
        response = requests.get(NASA_URL, params=params, timeout=10)
        if response.status_code != 200:
            logger.error(f"NASA API returned {response.status_code}")
            return None
            
        data = response.json()
        if 'properties' not in data or 'parameter' not in data['properties']:
            return None
            
        params_data = data['properties']['parameter']
        
        # Extract individual dictionaries for each parameter
        ghi_dict = params_data.get('ALLSKY_SFC_SW_DWN', {})
        temp_dict = params_data.get('T2M', {})
        tmax_dict = params_data.get('T2M_MAX', {})
        hum_dict = params_data.get('RH2M', {})
        wind_dict = params_data.get('WS2M', {})
        
        dates = sorted(list(ghi_dict.keys()))
        
        daily_records = []
        valid_ghi, valid_temp, valid_tmax, valid_hum, valid_wind = [], [], [], [], []
        
        for date_key in dates:
            ghi = ghi_dict.get(date_key, -999)
            temp = temp_dict.get(date_key, -999)
            tmax = tmax_dict.get(date_key, -999)
            hum = hum_dict.get(date_key, -999)
            wind = wind_dict.get(date_key, -999)
            
            # NASA uses -999 for missing values. Replace with reasonable defaults if missing
            ghi = ghi if ghi != -999 else 5.5
            temp = temp if temp != -999 else 25.0
            tmax = tmax if tmax != -999 else 35.0
            hum = hum if hum != -999 else 45.0
            wind = wind if wind != -999 else 3.0
            
            daily_records.append({
                'allsky_sfc_sw_dwn': ghi,
                't2m': temp,
                'rh2m': hum,
                'ws2m': wind
            })
            
            valid_ghi.append(ghi)
            valid_temp.append(temp)
            valid_tmax.append(tmax)
            valid_hum.append(hum)
            valid_wind.append(wind)
            
        if not valid_ghi:
            return None
            
        # Calculate aggregates for V2 Predictor
        agg = {
            'avg_ghi': sum(valid_ghi) / len(valid_ghi),
            'avg_temp': sum(valid_temp) / len(valid_temp),
            'max_temp': max(valid_tmax),
            'avg_hum': sum(valid_hum) / len(valid_hum),
            'avg_wind': sum(valid_wind) / len(valid_wind)
        }
        
        result = {
            'agg': agg,
            'daily_records': daily_records
        }
        
        # Cache for 24 hours
        cache.set(cache_key, result, timeout=86400)
        return result
        
    except Exception as e:
        logger.error(f"NASA API connection error: {e}")
        return None

def find_nearest_location(lat, lon):
    """Fallback method: finds the nearest location in the database."""
    from solar_data.models import Location
    
    locations = Location.objects.all()
    if not locations.exists():
        return None
        
    min_dist = float('inf')
    closest = None
    
    for loc in locations:
        if loc.latitude is None or loc.longitude is None:
            continue
        # Simple Euclidean distance is sufficient for fallback
        dist = math.sqrt((loc.latitude - lat)**2 + (loc.longitude - lon)**2)
        if dist < min_dist:
            min_dist = dist
            closest = loc
            
    return closest
