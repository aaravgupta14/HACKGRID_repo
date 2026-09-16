import argparse
import json

import pandas as pd

from surplusroute import config
from surplusroute.features import build_features
from surplusroute.model import GlutForecaster
from surplusroute.prepare import load_panel, panel_path


def crash_episodes(frame, merge_gap=3):
    episodes = []
    for district, group in frame.groupby("district"):
        group = group.sort_values("date").reset_index(drop=True)
        flagged = group.index[group["crash_ahead"] == 1].tolist()
        if not flagged:
            continue
        runs, start, previous = [], flagged[0], flagged[0]
        for index in flagged[1:]:
            if index - previous > merge_gap:
                runs.append((start, previous))
                start = index
            previous = index
        runs.append((start, previous))
        for first, last in runs:
            window = group.iloc[first : last + config.FORECAST_HORIZON + 1]
            peak_price = group.at[first, "modal_price"]
            bottom = window.loc[window["modal_price"].idxmin()]
            fell_15 = window[window["modal_price"] <= peak_price * 0.85]
            episodes.append({
                "district": district,
                "risk_window_start": group.at[first, "date"],
                "price_at_start": float(peak_price),
                "bottom_date": bottom["date"],
                "bottom_price": float(bottom["modal_price"]),
                "total_drop_pct": round((1 - bottom["modal_price"] / peak_price) * 100, 1),
                "price_down_15pct_date": fell_15["date"].iloc[0] if not fell_15.empty else bottom["date"],
            })
    return pd.DataFrame(episodes)


def walk_forward_scores(frame, years):
    scored = []
    labelled = frame.dropna(subset=["crash_ahead", "arrival_ratio_3d", "price_vs_baseline"])
    for year in years:
        cutoff = pd.Timestamp(f"{year}-01-01") - pd.Timedelta(days=config.FORECAST_HORIZON)
        train = labelled[labelled["date"] < cutoff]
        if train["crash_ahead"].sum() < 20:
            print(f"{year}: skipped, not enough prior crash history to train")
            continue
        model = GlutForecaster().fit(train)
        target = frame[(frame["date"].dt.year == year) & frame["arrival_ratio_3d"].notna() & frame["modal_price"].notna()]
        scored.append(target.join(model.predict(target)))
        print(f"{year}: trained on {len(train)} rows before {cutoff.date()}, scored {len(target)} rows")
    return pd.concat(scored) if scored else pd.DataFrame()


def evaluate(scored, min_drop_pct):
    episodes = crash_episodes(scored)
    if episodes.empty:
        return episodes, {}
    episodes = episodes[episodes["total_drop_pct"] >= min_drop_pct].copy()
    alerts = scored[scored["crash_probability"] >= config.RISK_HIGH]
    leads = []
    for _, episode in episodes.iterrows():
        search_from = episode["risk_window_start"] - pd.Timedelta(days=config.FORECAST_HORIZON)
        hits = alerts[
            (alerts["district"] == episode["district"])
            & (alerts["date"] >= search_from)
            & (alerts["date"] <= episode["bottom_date"])
        ]
        if hits.empty:
            leads.append((pd.NaT, None, None))
            continue
        first = hits["date"].min()
        leads.append((
            first,
            (episode["bottom_date"] - first).days,
            (episode["price_down_15pct_date"] - first).days,
        ))
    episodes["first_high_alert"] = [lead[0] for lead in leads]
    episodes["lead_days_to_bottom"] = [lead[1] for lead in leads]
    episodes["lead_days_before_15pct_fall"] = [lead[2] for lead in leads]
    caught = episodes["first_high_alert"].notna()
    labelled_alerts = alerts.dropna(subset=["crash_ahead"])
    summary = {
        "crash_episodes": int(len(episodes)),
        "episodes_caught": int(caught.sum()),
        "catch_rate": round(float(caught.mean()), 3) if len(episodes) else None,
        "median_lead_days_to_bottom": float(episodes.loc[caught, "lead_days_to_bottom"].median()) if caught.any() else None,
        "median_lead_days_before_15pct_fall": float(episodes.loc[caught, "lead_days_before_15pct_fall"].median()) if caught.any() else None,
        "high_alert_days": int(len(alerts)),
        "false_alarm_rate": round(float((labelled_alerts["crash_ahead"] == 0).mean()), 3) if len(labelled_alerts) else None,
    }
    return episodes, summary


def district_timeline(scored, district, start, end):
    view = scored[(scored["district"] == district) & scored["date"].between(start, end)]
    return view[["date", "arrival_tonnes", "arrival_ratio_3d", "modal_price", "price_vs_baseline",
                 "crash_probability", "predicted_drop", "predicted_days_to_bottom", "future_drop", "days_to_bottom"]].round(3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025, 2026])
    parser.add_argument("--min-drop", type=float, default=40.0)
    parser.add_argument("--district")
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for commodity, state in config.TRACKED:
        if not panel_path(commodity, state).exists():
            print(f"{commodity}/{state}: skipped, run prepare first")
            continue
        frame = build_features(load_panel(commodity, state))
        scored = walk_forward_scores(frame, args.years)
        episodes, summary = evaluate(scored, args.min_drop)
        tag = f"{commodity}_{state.replace(' ', '_')}"
        episodes.to_csv(config.OUTPUT_DIR / f"backtest_episodes_{tag}.csv", index=False)
        scored.to_csv(config.OUTPUT_DIR / f"backtest_scores_{tag}.csv", index=False)
        (config.OUTPUT_DIR / f"backtest_summary_{tag}.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        if not episodes.empty:
            print(episodes.sort_values("total_drop_pct", ascending=False).head(15).to_string(index=False))
        if args.district and args.start and args.end:
            print(district_timeline(scored, args.district, args.start, args.end).to_string(index=False))


if __name__ == "__main__":
    main()
