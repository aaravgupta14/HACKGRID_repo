import argparse

import pandas as pd

from surplusroute import config
from surplusroute.prepare import load_arrivals, load_prices, match_districts


def build_mandi_series(commodity, state):
    prices = load_prices(commodity, state)
    arrivals = load_arrivals(commodity, state)
    mapping, _ = match_districts(prices["district_key"], arrivals["district_key"])
    prices = prices[prices["district_key"].isin(mapping)].copy()
    prices["district_key"] = prices["district_key"].map(mapping)
    prices["market"] = prices["market"].str.strip()

    daily = prices.groupby(["market", "district_key", "date"]).agg(
        modal_price=("modal_price", "median"),
        min_price=("min_price", "median"),
        max_price=("max_price", "median"),
    ).reset_index()

    days = pd.date_range(config.START_DATE, config.END_DATE, freq="D")
    frames = []
    for (market, district_key), group in daily.groupby(["market", "district_key"]):
        series = group.set_index("date").reindex(days)
        series.index.name = "date"
        series["reported"] = series["modal_price"].notna()
        for column in ("modal_price", "min_price", "max_price"):
            series[column] = series[column].ffill(limit=3)
        series["gap_filled"] = ~series["reported"] & series["modal_price"].notna()
        series["market"] = market
        series["district_key"] = district_key
        frames.append(series.reset_index())
    frame = pd.concat(frames, ignore_index=True)
    frame["commodity"] = commodity
    frame["state"] = state
    coverage = frame.groupby("market")["reported"].mean()
    active = coverage[coverage >= 0.1].index
    return frame[frame["market"].isin(active)].reset_index(drop=True)


def mandi_series_path(commodity, state):
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    return config.PROCESSED_DIR / f"mandi_prices_{commodity}_{state.replace(' ', '_')}.csv"


def load_mandi_series(commodity, state):
    path = mandi_series_path(commodity, state)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["date"])


def mandis_by_district(mandi_frame):
    if mandi_frame.empty:
        return {}
    reported = mandi_frame[mandi_frame["reported"]]
    counts = reported.groupby(["district_key", "market"]).size().reset_index(name="days")
    counts = counts.sort_values(["district_key", "days"], ascending=[True, False])
    return counts.groupby("district_key")["market"].apply(list).to_dict()


def main():
    argparse.ArgumentParser().parse_args()
    for commodity, state in config.TRACKED:
        frame = build_mandi_series(commodity, state)
        path = mandi_series_path(commodity, state)
        frame.to_csv(path, index=False)
        summary = frame.groupby(["district_key", "market"]).agg(
            days_reported=("reported", "sum"), days_gap_filled=("gap_filled", "sum"),
            median_price=("modal_price", "median"),
        )
        print(f"{commodity}/{state}: {frame['market'].nunique()} mandis -> {path}")
        print(summary.sort_values("days_reported", ascending=False).head(30).to_string())


if __name__ == "__main__":
    main()
