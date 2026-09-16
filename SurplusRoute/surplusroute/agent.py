import json
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from surplusroute import config, marketplace
from surplusroute.features import build_features
from surplusroute.mandi_series import build_mandi_series, mandis_by_district
from surplusroute.model import GlutForecaster, model_path, year_model_path
from surplusroute.prepare import load_panel
from surplusroute.scoring import CrashProfile, glut_score, glut_signals


@dataclass
class DistrictAssessment:
    rank: int
    crop: str
    district: str
    mandis: list
    risk_level: str
    reason_code: str
    action_code: str
    glut_flag: bool
    glut_score: float
    crash_probability: float
    glut_stage: str
    arrival_tonnes: float
    arrival_vs_baseline_pct: float
    severity_score: float
    modal_price: float
    price_vs_baseline_pct: float
    price_change_7d_pct: float
    momentum_pct_per_day: float
    momentum_score: float
    buffer_days_low: int
    buffer_days_high: int
    historical_cases: int
    expected_drop_pct: float
    model_days_to_bottom: int
    projected_bottom_price: float
    action: str
    reroute_to: list = field(default_factory=list)
    verdict: str = ""


def _pct(value):
    return None if value is None or pd.isna(value) else round(float(value) * 100, 1)


def _num(value, digits=1):
    return None if value is None or pd.isna(value) else round(float(value), digits)


class SurplusRouteAgent:
    def __init__(self, commodity, state):
        self.commodity = commodity
        self.state = state
        self.final_forecaster = GlutForecaster.load(model_path(commodity, state))
        self.year_forecasters = {}
        self.year_model_years = {
            int(path.stem.rsplit("_", 1)[-1])
            for path in model_path(commodity, state).parent.glob(f"{model_path(commodity, state).stem}_before_*.joblib")
        }
        self.history = build_features(load_panel(commodity, state), with_labels=True)
        try:
            self.mandis = mandis_by_district(build_mandi_series(commodity, state))
        except (FileNotFoundError, ValueError, KeyError):
            self.mandis = {}

    def forecaster_for(self, as_of):
        year = pd.Timestamp(as_of).year
        if year not in self.year_forecasters:
            path = year_model_path(self.commodity, self.state, year)
            self.year_forecasters[year] = GlutForecaster.load(path) if path.exists() else None
        return self.year_forecasters[year] or self.final_forecaster

    def observe(self, as_of):
        as_of = pd.Timestamp(as_of)
        snapshot = self.history[self.history["date"] == as_of]
        return snapshot[snapshot["modal_price"].notna() & snapshot["arrival_ratio_3d"].notna()].copy()

    def analyze(self, snapshot):
        snapshot = glut_signals(snapshot)
        ratio, price_move = snapshot["arrival_ratio_3d"], snapshot["price_vs_baseline"]
        snapshot["glut_stage"] = np.select(
            [
                (ratio >= config.SPIKE_RATIO) & (price_move > -0.15),
                (ratio >= config.SPIKE_RATIO) & (price_move <= -0.15),
                (ratio < config.SPIKE_RATIO) & (price_move <= -config.CRASH_DROP),
                ratio >= 1.2,
            ],
            ["Glut building", "Glut crashing prices", "Post-glut slump", "Arrivals rising"],
            default="Normal supply",
        )
        return snapshot

    def forecast(self, snapshot, as_of):
        snapshot = snapshot.join(self.forecaster_for(as_of).predict(snapshot))
        snapshot["glut_score"] = glut_score(snapshot)
        return snapshot

    def _risk_level(self, probability, flagged):
        if probability >= config.RISK_HIGH:
            return "HIGH"
        if probability >= config.RISK_WATCH or flagged:
            return "WATCH"
        return "NORMAL"

    def _reason_code(self, row):
        if row["glut_flag"] or row["arrival_ratio_3d"] >= 1.2:
            return "supply_rush"
        if pd.notna(row["price_change_3d"]) and row["price_change_3d"] <= -0.10:
            return "price_falling"
        if row["price_vs_baseline"] >= 0.20:
            return "price_high"
        return "pattern"

    def _action_code(self, level, days):
        if level == "HIGH":
            return "sell_now" if days <= 3 else "divert"
        if level == "WATCH":
            return "careful"
        return "none"

    def _reroute_options(self, row, snapshot, limit=3):
        safe = snapshot[
            (snapshot["crash_probability"] < config.RISK_WATCH)
            & (~snapshot["glut_flag"])
            & (snapshot["district_key"] != row["district_key"])
            & (snapshot["modal_price"] > row["modal_price"])
        ].copy()
        safe["price_gap"] = safe["modal_price"] - row["modal_price"]
        safe = safe.sort_values("price_gap", ascending=False).head(limit)
        return [
            {
                "district": r["district"],
                "modal_price": _num(r["modal_price"], 0),
                "price_gap_per_quintal": _num(r["price_gap"], 0),
                "crash_probability": _num(r["crash_probability"], 3),
            }
            for _, r in safe.iterrows()
        ]

    def _action_text(self, code, reroute):
        target = reroute[0]["district"] if reroute else None
        if code == "sell_now":
            move = f" or truck it to {target}" if target else ""
            return f"Sell committed stock within 48 hours{move}; list surplus for nearby small business buyers now."
        if code == "divert":
            move = f"reroute surplus to {target}" if target else "list surplus for nearby small business buyers"
            return f"Line up an outlet for your stock now and {move}; buy here only at the projected lower price."
        if code == "careful":
            return "Buy only against firm orders, keep inventory lean and recheck tomorrow's arrivals."
        return "No glut signal; normal buying and selling."

    def _verdict(self, a):
        arrival_word = "above" if a.arrival_vs_baseline_pct >= 0 else "below"
        price_word = "down" if a.price_vs_baseline_pct < 0 else "up"
        text = (
            f"{a.crop}, {a.district}: arrivals {abs(a.arrival_vs_baseline_pct):.0f}% {arrival_word} baseline, "
            f"price {price_word} {abs(a.price_vs_baseline_pct):.0f}%"
        )
        if a.glut_flag and a.buffer_days_low is not None:
            text += f", historically {a.buffer_days_low} to {a.buffer_days_high} days from bottom"
        text += f". Crash risk {a.crash_probability:.0%}"
        if a.risk_level != "NORMAL":
            text += f", expected fall about {a.expected_drop_pct:.0f}% to near Rs {a.projected_bottom_price:,.0f}/qtl"
        return text + "."

    def decide(self, snapshot, profile):
        assessments = []
        for _, row in snapshot.iterrows():
            flagged = bool(row["glut_flag"])
            level = self._risk_level(row["crash_probability"], flagged)
            reroute = self._reroute_options(row, snapshot) if level != "NORMAL" else []
            model_days = int(row["predicted_days_to_bottom"])
            buffer = profile.buffer(row["arrival_ratio_3d"]) if flagged else None
            action_code = self._action_code(level, buffer["low"] if buffer else model_days)
            assessment = DistrictAssessment(
                rank=0,
                crop=self.commodity,
                district=row["district"],
                mandis=self.mandis.get(row["district_key"], []),
                risk_level=level,
                reason_code=self._reason_code(row),
                action_code=action_code,
                glut_flag=flagged,
                glut_score=_num(row["glut_score"]),
                crash_probability=_num(row["crash_probability"], 3),
                glut_stage=row["glut_stage"],
                arrival_tonnes=_num(row["arrival_tonnes"]),
                arrival_vs_baseline_pct=_pct(row["arrival_ratio_3d"] - 1),
                severity_score=_num(row["severity_score"]),
                modal_price=_num(row["modal_price"], 0),
                price_vs_baseline_pct=_pct(row["price_vs_baseline"]),
                price_change_7d_pct=_pct(row["price_change_7d"]),
                momentum_pct_per_day=_num(row["momentum_pct_per_day"]),
                momentum_score=_num(row["momentum_score"]),
                buffer_days_low=buffer["low"] if buffer else None,
                buffer_days_high=buffer["high"] if buffer else None,
                historical_cases=buffer["cases"] if buffer else 0,
                expected_drop_pct=_pct(row["predicted_drop"]),
                model_days_to_bottom=model_days,
                projected_bottom_price=_num(row["modal_price"] * (1 - row["predicted_drop"]), 0),
                action=self._action_text(action_code, reroute),
                reroute_to=reroute,
            )
            assessment.verdict = self._verdict(assessment)
            assessments.append(assessment)
        order = {"HIGH": 0, "WATCH": 1, "NORMAL": 2}
        assessments.sort(key=lambda a: (order[a.risk_level], -(a.glut_score or 0)))
        for position, assessment in enumerate(assessments, start=1):
            assessment.rank = position
        return assessments

    def run(self, as_of):
        as_of = pd.Timestamp(as_of)
        snapshot = self.observe(as_of)
        if snapshot.empty:
            return {"commodity": self.commodity, "state": self.state, "as_of": str(as_of.date()),
                    "status": "no_data", "alerts": []}
        profile = CrashProfile.fit(self.history, as_of)
        assessments = self.decide(self.forecast(self.analyze(snapshot), as_of), profile)
        honest = self.unseen_by_model(as_of)
        return {
            "commodity": self.commodity,
            "state": self.state,
            "as_of": str(as_of.date()),
            "status": "ok",
            "model_used": "not trained on this date" if honest else "trained on all data",
            "summary": {
                "districts_tracked": len(assessments),
                "high_risk": sum(a.risk_level == "HIGH" for a in assessments),
                "watch": sum(a.risk_level == "WATCH" for a in assessments),
                "glut_flagged": sum(a.glut_flag for a in assessments),
                "state_arrival_vs_baseline_pct": _pct(snapshot["state_arrival_ratio"].iloc[0] - 1),
            },
            "historical_crash_profile": {"by_severity": profile.bands, "overall": profile.overall},
            "alerts": [asdict(a) for a in assessments],
        }

    def match_surplus(self, listing, top_n=5):
        return marketplace.match_buyers(listing, marketplace.load_buyers(), top_n=top_n)

    def unseen_by_model(self, as_of):
        year = pd.Timestamp(as_of).year
        return year in self.year_model_years or (bool(self.year_model_years) and year > max(self.year_model_years))

    def available_dates(self, honest_only=False):
        usable = self.history.dropna(subset=["modal_price", "arrival_ratio_3d"])
        dates = sorted(usable["date"].unique())
        if honest_only:
            dates = [d for d in dates if self.unseen_by_model(d)] or dates
        return dates

    def district_history(self, district, end, days=45):
        end = pd.Timestamp(end)
        view = self.history[(self.history["district"] == district)
                            & self.history["date"].between(end - pd.Timedelta(days=days), end)]
        return view[["date", "arrival_tonnes", "arrival_baseline", "arrival_ratio_3d", "modal_price", "price_baseline"]]

    def latest_date(self):
        return self.available_dates()[-1]

    def save_report(self, report):
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = config.OUTPUT_DIR / f"alerts_{self.commodity}_{self.state.replace(' ', '_')}_{report['as_of']}.json"
        path.write_text(json.dumps(report, indent=2, default=str))
        return path
