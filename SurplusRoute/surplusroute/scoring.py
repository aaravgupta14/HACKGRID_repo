import numpy as np
import pandas as pd

from surplusroute import config

SEVERITY_BANDS = [
    (config.SPIKE_RATIO, 2.0, "1.5x to 2x baseline"),
    (2.0, 3.0, "2x to 3x baseline"),
    (3.0, np.inf, "over 3x baseline"),
]
MIN_CASES = 5


def glut_signals(frame):
    out = frame.copy()
    ratio = out["arrival_ratio_3d"]
    price_move = out["price_vs_baseline"]
    out["glut_flag"] = (ratio >= config.SPIKE_RATIO) & (price_move > -config.CRASH_DROP)
    out["severity_pct"] = (ratio - 1) * 100
    out["severity_score"] = ((ratio - 1) / (config.SEVERITY_CAP - 1)).clip(0, 1) * 100
    out["momentum_pct_per_day"] = -out["price_change_3d"] / 3 * 100
    out["momentum_score"] = (out["momentum_pct_per_day"] / config.MOMENTUM_CAP_PCT).clip(0, 1) * 100
    return out


def glut_score(frame):
    return (
        config.SCORE_WEIGHTS["crash_probability"] * frame["crash_probability"] * 100
        + config.SCORE_WEIGHTS["severity"] * frame["severity_score"].fillna(0)
        + config.SCORE_WEIGHTS["momentum"] * frame["momentum_score"].fillna(0)
    ).round(1)


class CrashProfile:
    def __init__(self, bands, overall):
        self.bands = bands
        self.overall = overall

    @staticmethod
    def _summary(days):
        if len(days) < MIN_CASES:
            return None
        return {
            "low": int(np.floor(days.quantile(0.25))),
            "high": int(np.ceil(days.quantile(0.75))),
            "median": float(days.median()),
            "cases": int(len(days)),
        }

    @classmethod
    def fit(cls, labelled, before):
        cutoff = pd.Timestamp(before) - pd.Timedelta(days=config.FORECAST_HORIZON)
        cases = labelled[
            (labelled["date"] < cutoff)
            & (labelled["crash_ahead"] == 1)
            & (labelled["arrival_ratio_3d"] >= config.SPIKE_RATIO)
        ]
        bands = {}
        for low, high, label in SEVERITY_BANDS:
            in_band = cases[(cases["arrival_ratio_3d"] >= low) & (cases["arrival_ratio_3d"] < high)]
            bands[label] = cls._summary(in_band["days_to_bottom"].dropna())
        return cls(bands, cls._summary(cases["days_to_bottom"].dropna()))

    def buffer(self, ratio):
        if pd.isna(ratio):
            return self.overall
        for low, high, label in SEVERITY_BANDS:
            if low <= ratio < high and self.bands.get(label):
                return self.bands[label]
        return self.overall
