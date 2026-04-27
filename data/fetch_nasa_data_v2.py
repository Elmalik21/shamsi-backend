"""
NASA POWER Data Collector - Enhanced Version
=============================================
Enhanced version with better error diagnostics

Usage:
    python fetch_nasa_data_v2.py
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime
from tqdm import tqdm
import json

# =============================================================================
# Configuration
# =============================================================================

OPTIMAL_PARAMETERS = [
    'ALLSKY_SFC_SW_DWN',   # Total radiation
    'T2M',                  # Average temperature
    'T2M_MAX',              # Maximum temperature
    'T2M_MIN',              # Minimum temperature
    'RH2M',                 # Humidity
    'WS2M',                 # Wind speed
    'ALLSKY_SFC_SW_DNI',    # Direct radiation
    'ALLSKY_SFC_SW_DIFF',   # Diffuse radiation
    'CLOUD_AMT',            # Cloud cover
    'ALLSKY_SRF_ALB',       # Surface albedo
    'PS',                   # Atmospheric pressure
    'PRECTOTCORR',          # Precipitation
]

START_DATE = '20180101'
END_DATE = '20260101'

NASA_URL = 'https://power.larc.nasa.gov/api/temporal/daily/point'
REQUEST_DELAY = 3        # Increased delay to 3 seconds
MAX_RETRIES = 5          # Increased retry attempts

# =============================================================================
# Functions
# =============================================================================

def test_single_location():
    """
    Test fetching a single location (Cairo) to verify API is working
    """
    print("\n🧪 Testing connection to NASA POWER...")
    
    params = {
        'parameters': ','.join(OPTIMAL_PARAMETERS),
        'community': 'RE',
        'longitude': 31.2357,
        'latitude': 30.04444,
        'start': '20240101',  # One month only for testing
        'end': '20240131',
        'format': 'JSON'
    }
    
    try:
        response = requests.get(NASA_URL, params=params, timeout=30)
        
        print(f"📡 HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'properties' in data and 'parameter' in data['properties']:
                print("✅ Connection successful! API is working correctly")
                return True
            else:
                print("⚠️ Unexpected response:")
                print(json.dumps(data, indent=2)[:500])
                return False
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def fetch_location_data(lat, lon, location_info, retries=MAX_RETRIES):
    """
    Fetch data for a single location with detailed diagnostics
    """
    for attempt in range(retries):
        try:
            params = {
                'parameters': ','.join(OPTIMAL_PARAMETERS),
                'community': 'RE',
                'longitude': lon,
                'latitude': lat,
                'start': START_DATE,
                'end': END_DATE,
                'format': 'JSON'
            }
            
            response = requests.get(NASA_URL, params=params, timeout=90)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'properties' in data and 'parameter' in data['properties']:
                    params_data = data['properties']['parameter']
                    
                    # Convert to DataFrame
                    dfs = []
                    for param_name, param_values in params_data.items():
                        df_param = pd.DataFrame(
                            list(param_values.items()),
                            columns=['Date', param_name]
                        )
                        dfs.append(df_param.set_index('Date'))
                    
                    result = pd.concat(dfs, axis=1).reset_index()
                    
                    # Add location information
                    result.insert(0, 'Location_ID', location_info['ID'])
                    result.insert(1, 'Location_Name', location_info['Name'])
                    result.insert(2, 'Governorate', location_info['Gov'])
                    result.insert(3, 'Latitude', lat)
                    result.insert(4, 'Longitude', lon)
                    
                    result['Date'] = pd.to_datetime(result['Date'], format='%Y%m%d')
                    result = result.replace(-999, pd.NA)
                    
                    return result, None
                else:
                    error_msg = "Empty response"
                    if 'messages' in data:
                        error_msg = str(data['messages'])
                    return None, f"Invalid response: {error_msg}"
                    
            elif response.status_code == 429:
                wait_time = 60 * (attempt + 1)
                return None, f"Rate limited (429) - attempt {attempt+1}/{retries}"
                
            elif response.status_code == 400:
                return None, f"Bad request (400): {response.text[:200]}"
                
            else:
                return None, f"HTTP {response.status_code}: {response.text[:200]}"
                
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(10)
                continue
            return None, "Request timeout"
            
        except requests.exceptions.ConnectionError:
            return None, "Internet connection error"
            
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    
    return None, f"All attempts failed ({retries})"


def save_checkpoint(df, location_id):
    """Save checkpoint"""
    os.makedirs('checkpoints', exist_ok=True)
    df.to_csv(f'checkpoints/loc_{location_id}.csv', index=False, encoding='utf-8-sig')


def load_checkpoint(location_id):
    """Load checkpoint"""
    path = f'checkpoints/loc_{location_id}.csv'
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


def main():
    """Main program"""
    
    print("="*70)
    print("🌞 NASA POWER Data Collector - Egypt (Enhanced)")
    print("="*70)
    
    # Test connection first
    if not test_single_location():
        print("\n❌ Test failed! Check:")
        print("  1. Internet connection")
        print("  2. Install libraries: pip install requests pandas tqdm")
        print("  3. Firewall settings")
        print("\nDo you want to continue anyway? (y/n): ", end='')
        if input().lower() != 'y':
            return
    
    print(f"\n📍 Locations: 119")
    print(f"📅 Period: 2018-01-01 to 2026-01-01")
    print(f"📊 Parameters: {len(OPTIMAL_PARAMETERS)}")
    print("="*70)
    
    # Load coordinates
    print("\n📂 Loading coordinates...")
    try:
        coords = pd.read_csv(r'C:\Users\m7md7\Desktop\Shamsi_project\GD_test\data\egypt_coordinates_corrected.csv', encoding='utf-8-sig')
        print(f"✓ Loaded {len(coords)} locations")
    except FileNotFoundError:
        print("❌ Error: egypt_coordinates_corrected.csv not found")
        return
    
    # Create directories
    os.makedirs('output', exist_ok=True)
    os.makedirs('checkpoints', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Open log file
    log_file = open('logs/download_log.txt', 'w', encoding='utf-8')
    log_file.write(f"NASA POWER Download Log - {datetime.now()}\n")
    log_file.write("="*70 + "\n\n")
    
    # Fetch data
    all_data = []
    failed = []
    
    print(f"\n🚀 Starting download...")
    print(f"⏰ Estimated time: ~{len(coords) * 3 / 60:.0f} minutes\n")
    
    pbar = tqdm(total=len(coords), desc="Progress", ncols=100, colour='green')
    
    for idx, row in coords.iterrows():
        location_id = row['#']
        location_name = row['Location']
        
        pbar.set_description(f"📍 {location_name[:25]:25s}")
        
        # Check checkpoint
        checkpoint = load_checkpoint(location_id)
        if checkpoint is not None:
            all_data.append(checkpoint)
            pbar.set_postfix({'Status': '✓ Saved'})
            log_file.write(f"#{location_id} {location_name}: Loaded from checkpoint\n")
            pbar.update(1)
            continue
        
        # Fetch data
        location_info = {
            'ID': location_id,
            'Name': location_name,
            'Gov': row['Governorate']
        }
        
        df, error = fetch_location_data(
            lat=row['Latitude'],
            lon=row['Longitude'],
            location_info=location_info
        )
        
        if df is not None:
            all_data.append(df)
            save_checkpoint(df, location_id)
            pbar.set_postfix({'Status': '✓ Success', 'Rows': len(df)})
            log_file.write(f"#{location_id} {location_name}: Success ({len(df)} rows)\n")
        else:
            failed.append((location_id, location_name, error))
            pbar.set_postfix({'Status': '✗ Failed'})
            log_file.write(f"#{location_id} {location_name}: Failed - {error}\n")
            
            # Print error to console as well
            print(f"\n⚠️ Failed #{location_id} {location_name}: {error}")
        
        pbar.update(1)
        
        # Delay between requests
        if idx < len(coords) - 1:
            time.sleep(REQUEST_DELAY)
    
    pbar.close()
    log_file.close()
    
    # Results
    print("\n" + "="*70)
    print("📊 Summary")
    print("="*70)
    print(f"✅ Success: {len(all_data)} locations")
    print(f"❌ Failed: {len(failed)} locations")
    
    if failed:
        print(f"\n⚠️ Failed locations ({len(failed)}):")
        
        # Analyze error types
        error_types = {}
        for loc_id, loc_name, error in failed:
            error_type = error.split(':')[0] if ':' in error else error
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append((loc_id, loc_name))
        
        print("\n📋 Error analysis:")
        for error_type, locations in error_types.items():
            print(f"\n{error_type} ({len(locations)} locations):")
            for loc_id, loc_name in locations[:5]:
                print(f"  - #{loc_id}: {loc_name}")
            if len(locations) > 5:
                print(f"  ... and {len(locations)-5} more")
        
        print(f"\n💾 Full details in: logs/download_log.txt")
    
    # Merge data
    if all_data:
        print(f"\n📊 Merging successful data...")
        final_df = pd.concat(all_data, ignore_index=True)
        final_df = final_df.sort_values(['Location_ID', 'Date'])
        
        output_file = 'output/egypt_solar_data_2018_2026.csv'
        final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print("\n" + "="*70)
        print("✅ Data saved successfully!")
        print("="*70)
        print(f"📁 File: {output_file}")
        print(f"📊 Rows: {len(final_df):,}")
        print(f"📍 Locations: {final_df['Location_ID'].nunique()}")
        print(f"📅 Period: {final_df['Date'].min()} to {final_df['Date'].max()}")
        print(f"💾 Size: {os.path.getsize(output_file)/(1024*1024):.1f} MB")
        
        # Show sample
        print("\n📋 Data sample:")
        print(final_df.head(3).to_string(max_cols=8))
        
    else:
        print("\n❌ No data downloaded successfully!")
        print("\n🔍 Possible diagnosis:")
        print("  1. Internet connection issue")
        print("  2. NASA POWER API temporarily down")
        print("  3. Your IP was blocked (excessive use)")
        print("  4. Firewall issue")
        print("\n💡 Suggested solutions:")
        print("  1. Check internet connection")
        print("  2. Try again after 30-60 minutes")
        print("  3. Use VPN or different network")
        print("  4. Check logs/download_log.txt for details")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏸ Stopped. You can resume the download later.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()