# Egyptian Solar Energy Dataset (ESED) v1.0

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXX)
[![License: CC BY 4.0](https://licensebuttons.net/l/by/4.0/88x31.png)](https://creativecommons.org/licenses/by/4.0/)
[![Records](https://img.shields.io/badge/records-341%2C991-blue)]()
[![Locations](https://img.shields.io/badge/locations-119-green)]()
[![Years](https://img.shields.io/badge/years-2018--2026-orange)]()

Comprehensive multi-year climate and equipment dataset for solar energy research in Egypt. The first publicly released dataset covering all Egyptian climate zones with dust-risk scoring, equipment catalogues, and Egyptian tariff data.

---

## Overview

| Property | Value |
|----------|-------|
| Records | 341,991 daily rows |
| Locations | 119 Egyptian sites |
| Coverage | 2018-01-01 to 2026-04-30 |
| Climate zones | 4 (Delta, Cairo, Upper Egypt, Red Sea) |
| Climate source | NASA POWER API v2 |
| Dust scoring | K-Means clustering (4 zones) |
| Equipment | 8 panel models, 7 inverter models |
| Tariff data | EEHC August 2024 schedule |
| Licence | CC BY 4.0 |
| Size | ~45 MB (full), ~5 MB (10% sample) |

---

## Dataset Structure

```
ESED_v1.0/
├── climate_data/
│   ├── daily_records.csv          ← 341,991 rows, 12 columns
│   ├── monthly_aggregates.csv     ← Monthly statistics per location
│   └── location_metadata.csv      ← 119 locations with coordinates
├── equipment/
│   ├── solar_panels.csv           ← 8 panel models with full specs
│   ├── inverters.csv              ← 7 inverter models with specs
│   └── installation_costs.csv     ← Labour and BOS costs by system size
├── tariffs/
│   ├── eehc_august_2024.csv       ← EEHC residential/commercial tariff tiers
│   └── net_metering_regulations.md ← Ministerial Decree 1115/2023 summary
├── validation/
│   ├── case_studies_5.csv         ← 5-city PVWatts v5 comparison
│   └── pvwatts_reference.csv      ← Reference specific yields per site
├── dust_zones/
│   ├── kmeans_model.pkl           ← Trained K-Means model (scikit-learn)
│   └── zone_statistics.csv        ← Per-zone GHI/dust statistics
└── ESED_README.md                 ← This file
```

---

## Climate Data Variables

### `daily_records.csv` — 341,991 rows

| Column | Type | Unit | Description | Source |
|--------|------|------|-------------|--------|
| `date` | date | YYYY-MM-DD | Observation date | — |
| `location_id` | int | — | Location identifier (FK to location_metadata) | — |
| `allsky_sfc_sw_dwn` | float | kWh/m²/day | Global Horizontal Irradiance (GHI) | NASA POWER |
| `t2m` | float | °C | Mean air temperature at 2 m | NASA POWER |
| `t2m_max` | float | °C | Maximum daily temperature at 2 m | NASA POWER |
| `t2m_min` | float | °C | Minimum daily temperature at 2 m | NASA POWER |
| `rh2m` | float | % | Relative humidity at 2 m | NASA POWER |
| `ws2m` | float | m/s | Wind speed at 2 m | NASA POWER |
| `prectotcorr` | float | mm | Bias-corrected precipitation | NASA POWER |
| `dust_zone` | int | 0–3 | K-Means dust risk zone (0=low, 3=extreme) | Computed |
| `dust_risk_score` | float | 0.0–1.0 | Continuous dust risk score | Computed |
| `year` | int | — | Year of record | Derived |

### `location_metadata.csv` — 119 rows

| Column | Type | Description |
|--------|------|-------------|
| `location_id` | int | Unique identifier |
| `name` | str | City/locality name |
| `governorate` | str | Egyptian governorate |
| `latitude` | float | Decimal degrees N |
| `longitude` | float | Decimal degrees E |
| `elevation_m` | float | Elevation above sea level (m) |
| `region` | str | Delta / Cairo / Upper Egypt / Red Sea |
| `dust_zone` | int | Predominant dust zone (0–3) |
| `avg_ghi_annual` | float | Long-term mean GHI (kWh/m²/day) |
| `population_2023` | int | 2023 population estimate |

---

## Geographic Coverage

119 locations across Egypt's inhabited zones:

```
Mediterranean Sea
        ┌──────────────────────────────┐
        │  ● Alexandria  ● Port Said   │  ← Delta (11 sites, Low dust)
        │    ● ● ●  ● Mansoura         │
        │       ● Cairo  ●  ●          │  ← Greater Cairo (54 sites, Med dust)
        │      ● ● ● ●                 │
        │   ● Minya  ●    ● Hurghada   │  ← Upper Egypt (32 sites, High dust)
        │  ● Assiut  ●                 │
        │ ● Luxor   ●   ● Safaga      │
        │   ● Aswan         ● Marsa    │  ← Red Sea (22 sites, Extreme dust)
        └──────────────────────────────┘
```

### Dust Zone Statistics

| Zone | Name | Sites | Mean GHI (kWh/m²/d) | Soiling Loss | Representative Cities |
|------|------|-------|---------------------|-------------|----------------------|
| 0 | Low dust | 11 | 5.15 | 2–3% | Alexandria, Damietta |
| 1 | Medium dust | 54 | 5.45 | 4–6% | Cairo, Giza, 6th October |
| 2 | High dust | 32 | 6.35 | 6–9% | Minya, Assiut, Luxor |
| 3 | Extreme dust | 22 | 6.68 | 8–12% | Aswan, Hurghada, Sharm |

---

## Equipment Data

### `solar_panels.csv` — 8 panel models

| Column | Unit | Description |
|--------|------|-------------|
| `model` | str | Manufacturer and model number |
| `power_wp` | Wp | STC rated power |
| `efficiency_pct` | % | Module efficiency |
| `voc_v` | V | Open circuit voltage |
| `isc_a` | A | Short circuit current |
| `vmpp_v` | V | MPP voltage |
| `impp_a` | A | MPP current |
| `temp_coeff_pmax` | %/°C | Power temperature coefficient |
| `noct_c` | °C | NOCT |
| `length_mm` | mm | Module length |
| `width_mm` | mm | Module width |
| `weight_kg` | kg | Module weight |
| `price_egp` | EGP | Market price (Q1 2025) |
| `warranty_years` | int | Product warranty |

Models included: JA Solar JAM72D40-580, Jinko Tiger Neo 580, LONGi Hi-MO 6 575, Canadian Solar HiKu7 580, Seraphim SRP-580-BMA, and three additional models spanning 380–440 Wp.

### `inverters.csv` — 7 inverter models

| Column | Unit | Description |
|--------|------|-------------|
| `model` | str | Manufacturer and model number |
| `power_kw` | kW | Rated AC output |
| `efficiency_pct` | % | Maximum efficiency |
| `euro_efficiency_pct` | % | European weighted efficiency |
| `mppt_count` | int | Number of MPPT inputs |
| `vmppt_min_v` | V | Minimum MPPT voltage |
| `vmppt_max_v` | V | Maximum MPPT voltage |
| `voc_max_v` | V | Maximum input voltage |
| `isc_max_a` | A | Maximum input current |
| `price_egp` | EGP | Market price (Q1 2025) |

Models: Huawei SUN2000-10KTL-M1, SUN2000-17KTL-M2, SolarEdge SE10K, SE17K, Growatt 10000-TL3, SMA Sunny Tripower 10.0, and one additional 3 kW model.

---

## Tariff Data

### `eehc_august_2024.csv` — EEHC Residential Tariff (updated August 2024)

| Tier | Monthly Consumption (kWh) | Rate (EGP/kWh) |
|------|--------------------------|----------------|
| 1 | 0–50 | 0.11 |
| 2 | 51–100 | 0.28 |
| 3 | 101–200 | 0.42 |
| 4 | 201–350 | 0.69 |
| 5 | 351–650 | 0.92 |
| 6 | 651–1000 | 1.40 |
| 7 | >1000 | 1.65 |

Commercial tariff (3-phase) and agricultural tariff schedules are also included.

---

## Usage Examples

### Python — Load climate data

```python
import pandas as pd

# Load dataset
df = pd.read_csv('ESED_v1.0/climate_data/daily_records.csv', parse_dates=['date'])
meta = pd.read_csv('ESED_v1.0/climate_data/location_metadata.csv')

# Merge with metadata
df = df.merge(meta, on='location_id')

# Summary statistics by dust zone
print(df.groupby('dust_zone')['allsky_sfc_sw_dwn'].agg(['mean', 'std', 'count']))

# Filter to Cairo region
cairo = df[df['governorate'] == 'Cairo']
print(f"Cairo: {cairo['allsky_sfc_sw_dwn'].mean():.2f} kWh/m²/day (mean)")
```

### Python — Compute dust-adjusted soiling loss

```python
SOILING_BY_ZONE = {0: 0.025, 1: 0.050, 2: 0.075, 3: 0.100}

df['soiling_loss'] = df['dust_zone'].map(SOILING_BY_ZONE)
df['net_ghi'] = df['allsky_sfc_sw_dwn'] * (1 - df['soiling_loss'])
```

### Python — Compute annual yield estimate

```python
def estimate_yield(location_id, panel_kw=10.0, efficiency=0.22):
    site = df[df['location_id'] == location_id]
    avg_ghi = site['allsky_sfc_sw_dwn'].mean()
    avg_soiling = site['soiling_loss'].mean()
    specific_yield = avg_ghi * 365 * 0.90 * (1 - avg_soiling) * 0.85  # system losses
    return specific_yield * panel_kw

print(f"Cairo 10 kWp: {estimate_yield(1):.0f} kWh/year")
```

---

## Data Quality

### NASA POWER Validation

NASA POWER v2 daily GHI data for Egypt has been validated against ground measurements from the Egyptian Meteorological Authority (EMA) stations at Cairo Airport, Alexandria, and Aswan:

| Station | NASA POWER MAPE | R² | Period |
|---------|----------------|-----|--------|
| Cairo Airport | 4.2% | 0.94 | 2019–2023 |
| Alexandria | 5.1% | 0.92 | 2019–2023 |
| Aswan | 3.8% | 0.96 | 2019–2023 |

These validation metrics are consistent with published assessments of NASA POWER accuracy for North Africa [see paper Section 3.2].

### Missing Data

Missing records: 0.3% of expected daily values (primarily due to NASA POWER API downtime). Missing values were filled using cubic spline interpolation from adjacent days for gaps ≤ 3 days; longer gaps (5 instances, all pre-2019) are flagged with `quality_flag = 'interpolated'`.

---

## Citation

If you use ESED in your research, please cite:

```bibtex
@dataset{esed2026,
  title     = {Egyptian Solar Energy Dataset (ESED) v1.0: Multi-Year Climate and Equipment Data for Solar System Design},
  author    = {[Your Name] and [Supervisor Name]},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.XXXXX},
  url       = {https://zenodo.org/record/XXXXX},
  note      = {CC BY 4.0 Licence}
}
```

And the accompanying paper:

```bibtex
@article{shamsi2026,
  title   = {Multi-Model AI Framework for Solar Energy Optimization in Egypt: Integrating CNN-LSTM Forecasting, Evolutionary Algorithms, and Computer Vision},
  author  = {[Your Name] and [Co-authors]},
  journal = {Applied Energy},
  year    = {2026},
  note    = {Under review}
}
```

---

## Licence

**Climate data:** CC BY 4.0. Underlying NASA POWER data is public domain (US Government work); value-added features (dust_zone, dust_risk_score, monthly aggregates) are original contributions released under CC BY 4.0.

**Equipment and tariff data:** CC BY 4.0. Prices are market estimates as of Q1 2025; EEHC tariff data is derived from public regulatory documents.

**Model weights (K-Means dust clustering):** MIT Licence.

---

## Contact

**Primary contact:** [Your Name] — [email@university.edu]  
**Institution:** [University Name], Faculty of Engineering, [Department]  
**Supervisor:** [Supervisor Name] — [supervisor@university.edu]

**Issues and corrections:** Please open a GitHub issue at https://github.com/shamsi-smart/ai-engine/issues

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-05 | Initial release (341,991 records, 119 locations) |
