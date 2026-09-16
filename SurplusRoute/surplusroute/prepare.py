import argparse
import difflib
import json
import re

import numpy as np
import pandas as pd

from surplusroute import config
from surplusroute.collect import cache_path

DISTRICT_ALIASES = {
    "bangalore": "bengaluru",
    "bangalore rural": "bengaluru rural",
    "bengaluru urban": "bengaluru",
    "ramanagar": "bengaluru south",
    "ramanagara": "bengaluru south",
    "kalburgi": "kalaburagi",
    "gulbarga": "kalaburagi",
    "mysore": "mysuru",
    "shimoga": "shivamogga",
    "chamrajnagar": "chamarajanagar",
    "chickmagalur": "chikkamagaluru",
    "chikmagalur": "chikkamagaluru",
    "chikkamagalore": "chikkamagaluru",
    "chikkaballapura": "chikkaballapur",
    "chickballapur": "chikkaballapur",
    "belgaum": "belagavi",
    "bijapur": "vijayapura",
    "bellary": "ballari",
    "tumkur": "tumakuru",
    "hassan": "hassan",
    "davanagere": "davangere",
    "dharwar": "dharwad",
    "mangalore": "dakshina kannada",
    "mangalore(dakshin kannad)": "dakshina kannada",
    "karwar(uttar kannad)": "uttara kannada",
    "uttar kannad": "uttara kannada",
    "madikeri(kodagu)": "kodagu",
    "raichur": "raichur",
    "bidar": "bidar",
}


def _norm(name):
    text = str(name or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return DISTRICT_ALIASES.get(text, text)


def _read_jsonl(path):
    by_date = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entry = json.loads(line)
                by_date[entry["date"]] = entry["records"]
    return pd.DataFrame([row for records in by_date.values() for row in records])


def load_arrivals(commodity, state):
    frame = _read_jsonl(cache_path("arrivals", commodity, state))
    frame["date"] = pd.to_datetime(frame["date"])
    frame["arrival_tonnes"] = pd.to_numeric(frame["arrival_tonnes"], errors="coerce")
    frame["district_key"] = frame["district"].map(_norm)
    frame = frame[frame["arrival_tonnes"] > 0]
    return (
        frame.groupby(["date", "district_key"], as_index=False)
        .agg(district=("district", "first"), arrival_tonnes=("arrival_tonnes", "sum"))
    )


def load_prices(commodity, state):
    frame = _read_jsonl(cache_path("prices", commodity, state))
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ("min_price", "max_price", "modal_price"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[frame["modal_price"] > 0]
    frame["district_key"] = frame["district"].map(_norm)
    return frame


def match_districts(price_keys, arrival_keys):
    mapping, unmatched = {}, []
    arrival_keys = sorted(set(arrival_keys))
    for key in sorted(set(price_keys)):
        if key in arrival_keys:
            mapping[key] = key
            continue
        close = difflib.get_close_matches(key, arrival_keys, n=1, cutoff=0.8)
        if close:
            mapping[key] = close[0]
        else:
            unmatched.append(key)
    return mapping, unmatched


def aggregate_prices(prices):
    grouped = prices.groupby(["date", "district_key"])
    return grouped.agg(
        modal_price=("modal_price", "median"),
        min_price=("min_price", "median"),
        max_price=("max_price", "median"),
        markets_reporting=("market", "nunique"),
    ).reset_index()


def build_panel(commodity, state):
    arrivals = load_arrivals(commodity, state)
    prices = load_prices(commodity, state)
    mapping, unmatched = match_districts(prices["district_key"], arrivals["district_key"])
    if unmatched:
        print(f"Price districts with no arrival match (dropped): {unmatched}")
    prices = prices[prices["district_key"].isin(mapping)].copy()
    prices["district_key"] = prices["district_key"].map(mapping)
    daily_prices = aggregate_prices(prices)

    names = arrivals.groupby("district_key")["district"].agg(lambda s: s.mode().iat[0])
    days = pd.date_range(config.START_DATE, config.END_DATE, freq="D")
    districts = sorted(set(arrivals["district_key"]) & set(daily_prices["district_key"]))
    grid = pd.MultiIndex.from_product([days, districts], names=["date", "district_key"]).to_frame(index=False)

    panel = grid.merge(arrivals.drop(columns="district"), on=["date", "district_key"], how="left")
    panel = panel.merge(daily_prices, on=["date", "district_key"], how="left")
    panel["district"] = panel["district_key"].map(names)
    panel["commodity"] = commodity
    panel["state"] = state
    panel["arrival_reported"] = panel["arrival_tonnes"].notna()
    panel["price_reported"] = panel["modal_price"].notna()

    coverage = panel.groupby("district_key")[["arrival_reported", "price_reported"]].mean().min(axis=1)
    keep = coverage[coverage >= config.MIN_DISTRICT_COVERAGE].index
    dropped = sorted(set(districts) - set(keep))
    if dropped:
        print(f"Districts dropped for low coverage (<{config.MIN_DISTRICT_COVERAGE:.0%}): {dropped}")
    panel = panel[panel["district_key"].isin(keep)].sort_values(["district_key", "date"])

    filled = panel.groupby("district_key", group_keys=False)
    for column in ("modal_price", "min_price", "max_price"):
        panel[column] = filled[column].transform(lambda s: s.ffill(limit=3))
    panel["arrival_tonnes"] = filled["arrival_tonnes"].transform(lambda s: s.ffill(limit=2))
    panel["markets_reporting"] = panel["markets_reporting"].fillna(0).astype(int)
    panel = panel.replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    return panel


def panel_path(commodity, state):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    return config.PROCESSED_DIR / f"panel_{commodity}_{state.replace(' ', '_')}.csv"


def load_panel(commodity, state):
    return pd.read_csv(panel_path(commodity, state), parse_dates=["date"])


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    for commodity, state in config.TRACKED:
        panel = build_panel(commodity, state)
        path = panel_path(commodity, state)
        panel.to_csv(path, index=False)
        summary = panel.groupby("district").agg(
            days_with_arrivals=("arrival_reported", "sum"),
            days_with_prices=("price_reported", "sum"),
            mean_arrival_t=("arrival_tonnes", "mean"),
            median_price=("modal_price", "median"),
        )
        print(f"{commodity}/{state}: {len(panel)} rows, {panel['district'].nunique()} districts -> {path}")
        print(summary.round(1).sort_values("mean_arrival_t", ascending=False).to_string())


if __name__ == "__main__":
    main()
