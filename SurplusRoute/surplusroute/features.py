import numpy as np
import pandas as pd

from surplusroute import config

FEATURE_COLUMNS = [
    "arrival_ratio_3d",
    "arrival_ratio_7d",
    "arrival_acceleration",
    "arrival_yoy_ratio",
    "arrival_share_of_state",
    "price_vs_baseline",
    "price_change_3d",
    "price_change_7d",
    "price_volatility_14d",
    "price_spread",
    "log_price",
    "state_arrival_ratio",
    "state_spiking_share",
    "state_price_change_7d",
    "doy_sin",
    "doy_cos",
]


def _district_features(group):
    group = group.sort_values("date").copy()
    arrivals = group["arrival_tonnes"]
    price = group["modal_price"]
    window, min_days = config.BASELINE_WINDOW, config.MIN_BASELINE_DAYS

    arrival_base = arrivals.shift(1).rolling(window, min_periods=min_days).mean()
    arrival_3d = arrivals.rolling(3, min_periods=1).mean()
    arrival_7d = arrivals.rolling(7, min_periods=3).mean()
    group["arrival_baseline"] = arrival_base
    group["arrival_ratio_3d"] = arrival_3d / arrival_base
    group["arrival_ratio_7d"] = arrival_7d / arrival_base
    group["arrival_acceleration"] = (arrival_3d - arrival_3d.shift(4)) / arrival_base
    group["arrival_yoy_ratio"] = arrival_7d / arrival_7d.shift(364)

    price_base = price.shift(1).rolling(window, min_periods=min_days).mean()
    group["price_baseline"] = price_base
    group["price_vs_baseline"] = price / price_base - 1
    group["price_change_3d"] = price / price.shift(3) - 1
    group["price_change_7d"] = price / price.shift(7) - 1
    group["price_volatility_14d"] = price.pct_change(fill_method=None).rolling(14, min_periods=5).std()
    group["price_spread"] = (group["max_price"] - group["min_price"]) / price
    group["log_price"] = np.log(price)
    group["arrival_7d_mean"] = arrival_7d
    return group


def _state_features(panel):
    daily = panel.groupby("date").agg(
        state_arrivals=("arrival_tonnes", "sum"),
        state_price=("modal_price", "median"),
    )
    base = daily["state_arrivals"].shift(1).rolling(config.BASELINE_WINDOW, min_periods=config.MIN_BASELINE_DAYS).mean()
    daily["state_arrival_ratio"] = daily["state_arrivals"].rolling(3, min_periods=1).mean() / base
    daily["state_price_change_7d"] = daily["state_price"] / daily["state_price"].shift(7) - 1
    spiking = panel.assign(spike=panel["arrival_ratio_3d"] >= config.SPIKE_RATIO)
    daily["state_spiking_share"] = spiking.groupby("date")["spike"].mean()
    return daily.reset_index()


def _labels(group):
    group = group.sort_values("date").copy()
    price = group["modal_price"].to_numpy()
    horizon = config.FORECAST_HORIZON
    n = len(price)
    drop = np.full(n, np.nan)
    days_to_bottom = np.full(n, np.nan)
    for i in range(n - 1):
        future = price[i + 1 : i + 1 + horizon]
        if np.isnan(price[i]) or np.count_nonzero(~np.isnan(future)) < horizon // 2:
            continue
        bottom_offset = int(np.nanargmin(future))
        drop[i] = 1 - future[bottom_offset] / price[i]
        days_to_bottom[i] = bottom_offset + 1
    group["future_drop"] = drop
    group["days_to_bottom"] = days_to_bottom
    group["crash_ahead"] = np.where(np.isnan(drop), np.nan, (drop >= config.CRASH_DROP).astype(float))
    return group


def build_features(panel, with_labels=True):
    frame = panel.groupby("district_key", group_keys=False)[panel.columns].apply(_district_features)
    state_arrivals = frame.groupby("date")["arrival_tonnes"].transform("sum")
    frame["arrival_share_of_state"] = frame["arrival_7d_mean"] / state_arrivals.replace(0, np.nan)
    frame = frame.merge(_state_features(frame), on="date", how="left")
    day_of_year = frame["date"].dt.dayofyear
    frame["doy_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    frame["doy_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    if with_labels:
        frame = frame.groupby("district_key", group_keys=False)[frame.columns].apply(_labels)
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    return frame.sort_values(["date", "district_key"]).reset_index(drop=True)
