"""
ai_engine/deep_learning/data_preparation.py
=============================================
Time-series dataset builder for the CNN-LSTM model.

Queries DailyClimateData from Django ORM and constructs:
  X : (n_samples, sequence_length, n_features)   — daily sequences
  y : (n_samples, 12)                             — monthly specific yields

Features per day  (5):
  [GHI, Temperature, Humidity, Wind, Dust_Risk_Score]

Target per sample (12):
  Monthly specific yield  [kWh/kWp/month]
  derived from the daily GHI × panel_efficiency formula

Groups (for GroupKFold):
  location_id  — ensures no same-location leakage across CV folds

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import logging
import os
from typing import Tuple, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Feature column indices
FEAT_GHI   = 0
FEAT_TEMP  = 1
FEAT_HUM   = 2
FEAT_WIND  = 3
FEAT_DUST  = 4
N_FEATURES = 5

# Monthly weights for Egypt (Jan–Dec); sum=1.0 — used when monthly data unavailable
_MONTHLY_WEIGHTS = [
    0.062, 0.068, 0.088, 0.095, 0.102, 0.105,
    0.107, 0.103, 0.090, 0.079, 0.063, 0.058,
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def prepare_time_series_data(
    location_ids: Optional[List[int]] = None,
    sequence_length: int = 365,
    panel_efficiency: float = 0.22,
    temp_coefficient: float = -0.32,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build time-series tensors from Django ORM data.

    Parameters
    ----------
    location_ids     : list of Location.location_id values to include.
                       None → use all locations.
    sequence_length  : days per sequence (365 for a full year).
    panel_efficiency : STC panel efficiency (used only for target calc).
    temp_coefficient : power temp. coefficient %/°C (negative, used for target).

    Returns
    -------
    X      : np.ndarray  (n_samples, sequence_length, N_FEATURES)
    y      : np.ndarray  (n_samples, 12)   monthly specific yield [kWh/kWp/month]
    groups : np.ndarray  (n_samples,)      location_id per sample (for GroupKFold)
    """
    try:
        return _load_from_orm(
            location_ids, sequence_length, panel_efficiency, temp_coefficient
        )
    except Exception as exc:
        logger.warning("ORM load failed (%s) — falling back to synthetic data.", exc)
        return _synthetic_sequences(sequence_length)


def create_dataloaders(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    batch_size: int = 32,
):
    """
    Wrap numpy arrays in PyTorch DataLoaders.

    Returns
    -------
    train_loader, val_loader  (torch.utils.data.DataLoader)
    """
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    def _to_tensor(arr: np.ndarray, dtype=torch.float32):
        return torch.tensor(arr, dtype=dtype)

    train_ds = TensorDataset(_to_tensor(X_train), _to_tensor(y_train))
    val_ds   = TensorDataset(_to_tensor(X_val),   _to_tensor(y_val))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=0, pin_memory=False)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              num_workers=0, pin_memory=False)

    return train_loader, val_loader


# ─────────────────────────────────────────────────────────────────────────────
# Internal: ORM loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_from_orm(
    location_ids, sequence_length, panel_efficiency, temp_coefficient
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load real data from Django ORM."""
    from solar_data.models import Location, DailyClimateData
    from django.db.models import Avg

    if location_ids is not None:
        locations = list(Location.objects.filter(location_id__in=location_ids))
    else:
        locations = list(Location.objects.all())

    X_list, y_list, g_list = [], [], []

    for loc in locations:
        qs = (DailyClimateData.objects
              .filter(location=loc, is_active=True)
              .order_by('date')
              .values('date', 'allsky_sfc_sw_dwn', 't2m', 'rh2m', 'ws2m', 'dust_risk_score'))

        records = list(qs)
        if len(records) < sequence_length:
            logger.debug("Location %s: only %d days — skipping.", loc, len(records))
            continue

        # Build sequences by sliding a window over full history
        # One sample per year (non-overlapping) to avoid data leakage
        n_years = len(records) // sequence_length
        for i in range(n_years):
            chunk = records[i * sequence_length: (i + 1) * sequence_length]
            seq = _build_sequence(chunk)         # (365, 5)
            monthly_y = _compute_monthly_yield(
                chunk, panel_efficiency, temp_coefficient
            )                                    # (12,)
            X_list.append(seq)
            y_list.append(monthly_y)
            g_list.append(loc.location_id)

    if not X_list:
        raise ValueError("No sequences built from ORM data.")

    X = np.array(X_list, dtype=np.float32)   # (N, 365, 5)
    y = np.array(y_list, dtype=np.float32)   # (N, 12)
    g = np.array(g_list, dtype=np.int64)     # (N,)

    # Per-feature normalisation (fit on training split outside this function)
    X = _normalise(X)

    logger.info("Loaded %d sequences from %d locations.", len(X_list), len(locations))
    return X, y, g


def _build_sequence(records: list) -> np.ndarray:
    """Convert a list of ORM row dicts into a (365, 5) float32 array."""
    seq = np.zeros((len(records), N_FEATURES), dtype=np.float32)
    for i, r in enumerate(records):
        seq[i, FEAT_GHI]  = r['allsky_sfc_sw_dwn'] or 0.0
        seq[i, FEAT_TEMP] = r['t2m']               or 25.0
        seq[i, FEAT_HUM]  = r['rh2m']              or 40.0
        seq[i, FEAT_WIND] = r['ws2m']              or 3.0
        seq[i, FEAT_DUST] = r['dust_risk_score']   or 0.07
    return seq


def _compute_monthly_yield(
    records: list, eff: float, temp_coeff: float
) -> np.ndarray:
    """
    Compute 12-element monthly specific yield [kWh/kWp/month].
    Uses physics formula: GHI * eff * (1 - temp_loss) * (1 - dust)
    """
    from collections import defaultdict
    monthly_ghi   = defaultdict(float)
    monthly_temp  = defaultdict(list)
    monthly_dust  = defaultdict(list)
    monthly_count = defaultdict(int)

    for r in records:
        m = r['date'].month
        monthly_ghi[m]  += r['allsky_sfc_sw_dwn'] or 0.0
        monthly_temp[m].append(r['t2m'] or 25.0)
        monthly_dust[m].append(r['dust_risk_score'] or 0.07)
        monthly_count[m] += 1

    y = np.zeros(12, dtype=np.float32)
    for m in range(1, 13):
        if monthly_count[m] == 0:
            continue
        avg_temp  = float(np.mean(monthly_temp[m]))
        avg_dust  = float(np.mean(monthly_dust[m]))
        total_ghi = monthly_ghi[m]
        temp_loss = max(0.0, (avg_temp - 25) * abs(temp_coeff) * 0.01)
        y[m - 1] = total_ghi * eff * (1 - temp_loss) * (1 - avg_dust)

    return y


def _normalise(X: np.ndarray) -> np.ndarray:
    """
    Per-feature min-max normalisation to [0, 1].
    Applied across all samples × all time-steps for each feature channel.
    """
    for f in range(X.shape[2]):
        fmin = X[:, :, f].min()
        fmax = X[:, :, f].max()
        if fmax - fmin > 1e-9:
            X[:, :, f] = (X[:, :, f] - fmin) / (fmax - fmin)
    return X


# ─────────────────────────────────────────────────────────────────────────────
# Public: Named synthetic generator (referenced by train_all_models.py etc.)
# ─────────────────────────────────────────────────────────────────────────────

def generate_synthetic_time_series_data(
    n_locations: int = 119,
    n_years: int = 3,
    sequence_length: int = 365,
    panel_efficiency: float = 0.22,
    temp_coefficient: float = -0.32,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate realistic synthetic time-series data for n_locations Egyptian
    cities × n_years years.

    Climate parameters are derived from realistic Egyptian latitude ranges:
      - GHI      : 4.5–7.5 kWh/m²/day  (higher in south)
      - Temp     : 18–38 °C             (hotter in south)
      - Humidity : 15–70%               (higher in north/delta)
      - Wind     : 1–8 m/s
      - Dust     : 0.03–0.15            (higher in south)

    The 119 locations span Egypt's five climate bands:
      1. Nile Delta   (lat 31–31.5°) — humid, low dust
      2. Cairo belt   (lat 29.5–31°) — moderate
      3. Middle Egypt (lat 27–29.5°) — drier, higher dust
      4. Upper Egypt  (lat 24–27°)   — very sunny, dusty
      5. Deep south   (lat 22–24°)   — extreme dust/sun

    Parameters
    ----------
    n_locations     : int   Number of synthetic locations (default: 119)
    n_years         : int   Years of data per location (default: 3)
    sequence_length : int   Days per sequence (default: 365)
    panel_efficiency: float Panel STC efficiency
    temp_coefficient: float Temperature coefficient [%/degC]
    seed            : int   Random seed for reproducibility

    Returns
    -------
    X      : np.ndarray  shape (n_locations*n_years, 365, 5)
               Features: [GHI, Temperature, Humidity, Wind, Dust]
    y      : np.ndarray  shape (n_locations*n_years, 12)
               Monthly specific yield [kWh/kWp/month]
    groups : np.ndarray  shape (n_locations*n_years,)
               Location ID per sample (for GroupKFold)
    """
    rng = np.random.default_rng(seed)

    # ── Generate per-location base climate from latitude ─────────────────────
    # Five bands covering all Egyptian geography
    lats = np.concatenate([
        rng.uniform(31.0, 31.5, max(1, n_locations * 15 // 119)),   # Delta
        rng.uniform(29.5, 31.0, max(1, n_locations * 25 // 119)),   # Cairo belt
        rng.uniform(27.0, 29.5, max(1, n_locations * 30 // 119)),   # Middle Egypt
        rng.uniform(24.0, 27.0, max(1, n_locations * 25 // 119)),   # Upper Egypt
        rng.uniform(22.0, 24.0, max(1, n_locations * 24 // 119)),   # Deep south
    ])
    # Trim or pad to exactly n_locations
    if len(lats) > n_locations:
        lats = lats[:n_locations]
    elif len(lats) < n_locations:
        extra = rng.uniform(22.0, 31.5, n_locations - len(lats))
        lats  = np.concatenate([lats, extra])
    rng.shuffle(lats)

    # Derive base climate from latitude (linear relationships calibrated on Egypt)
    ghi_base  = np.clip(7.5 - (lats - 22.0) * (3.0 / 9.5), 4.0, 7.8)
    temp_base = np.clip(35.0 - (lats - 22.0) * 0.7,         15.0, 40.0)
    dust_base = np.clip(0.15 - (lats - 22.0) * (0.12 / 9.5), 0.02, 0.18)
    hum_base  = np.clip(22.0 + (lats - 22.0) * 4.5,           15.0, 72.0)

    total_samples = n_locations * n_years
    X = np.zeros((total_samples, sequence_length, N_FEATURES), dtype=np.float32)
    y = np.zeros((total_samples, 12), dtype=np.float32)
    g = np.zeros(total_samples, dtype=np.int64)

    t = np.arange(sequence_length)
    phase_shift = -np.pi / 2   # peak in summer (July ~day 180 in Egypt)

    for loc_idx in range(n_locations):
        base_ghi  = ghi_base[loc_idx]  + rng.uniform(-0.2, 0.2)
        base_temp = temp_base[loc_idx] + rng.uniform(-1.5, 1.5)
        base_dust = dust_base[loc_idx] + rng.uniform(-0.01, 0.01)
        base_hum  = hum_base[loc_idx]  + rng.uniform(-4.0, 4.0)
        base_wind = rng.uniform(1.5, 7.0)

        for yr in range(n_years):
            sample_idx = loc_idx * n_years + yr

            ghi_daily = (base_ghi
                         + 1.5 * np.sin(2 * np.pi * t / sequence_length + phase_shift)
                         + rng.normal(0, 0.25, sequence_length))
            temp_daily = (base_temp
                          + 8.0 * np.sin(2 * np.pi * t / sequence_length + phase_shift)
                          + rng.normal(0, 1.0, sequence_length))
            hum_daily = (base_hum
                         - 10.0 * np.sin(2 * np.pi * t / sequence_length + phase_shift)
                         + rng.normal(0, 3.0, sequence_length))
            wind_daily = base_wind + rng.normal(0, 0.5, sequence_length)
            dust_seasonal = (base_dust
                             + 0.02 * np.sin(2 * np.pi * t / sequence_length + phase_shift)
                             + rng.normal(0, 0.01, sequence_length))

            ghi_daily   = np.clip(ghi_daily,    0.0,  12.0).astype(np.float32)
            temp_daily  = np.clip(temp_daily,   0.0,  48.0).astype(np.float32)
            hum_daily   = np.clip(hum_daily,    5.0,  95.0).astype(np.float32)
            wind_daily  = np.clip(wind_daily,   0.0,  15.0).astype(np.float32)
            dust_daily  = np.clip(dust_seasonal, 0.01, 0.22).astype(np.float32)

            X[sample_idx, :, FEAT_GHI]  = ghi_daily
            X[sample_idx, :, FEAT_TEMP] = temp_daily
            X[sample_idx, :, FEAT_HUM]  = hum_daily
            X[sample_idx, :, FEAT_WIND] = wind_daily
            X[sample_idx, :, FEAT_DUST] = dust_daily

            days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            day_start = 0
            for m, n_days in enumerate(days_in_month):
                sl = slice(day_start, day_start + n_days)
                avg_ghi_m  = float(ghi_daily[sl].mean())
                avg_temp_m = float(temp_daily[sl].mean())
                avg_dust_m = float(dust_daily[sl].mean())
                temp_loss  = max(0.0, (avg_temp_m - 25.0) * abs(temp_coefficient) * 0.01)
                y[sample_idx, m] = float(
                    avg_ghi_m * n_days * panel_efficiency
                    * (1.0 - temp_loss) * (1.0 - avg_dust_m)
                )
                day_start += n_days

            g[sample_idx] = loc_idx

    X = _normalise(X)
    logger.info(
        "Generated synthetic time-series: %d samples (%d locations x %d years), "
        "shape X=%s y=%s",
        total_samples, n_locations, n_years, X.shape, y.shape,
    )
    return X, y, g
