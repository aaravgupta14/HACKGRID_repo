import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, mean_absolute_error, precision_score, recall_score, roc_auc_score

from surplusroute import config
from surplusroute.features import FEATURE_COLUMNS, build_features
from surplusroute.prepare import load_panel, panel_path


def model_path(commodity, state):
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return config.MODEL_DIR / f"glut_model_{commodity}_{state.replace(' ', '_')}.joblib"


def year_model_path(commodity, state, year):
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return config.MODEL_DIR / f"glut_model_{commodity}_{state.replace(' ', '_')}_before_{year}.joblib"


def train_year_models(frame, commodity, state):
    labelled = frame.dropna(subset=["crash_ahead", "arrival_ratio_3d", "price_vs_baseline"])
    saved = []
    for year in sorted(frame["date"].dt.year.unique())[1:]:
        cutoff = pd.Timestamp(f"{year}-01-01") - pd.Timedelta(days=config.FORECAST_HORIZON)
        history = labelled[labelled["date"] < cutoff]
        if history["crash_ahead"].sum() < 20:
            continue
        GlutForecaster().fit(history).save(year_model_path(commodity, state, int(year)))
        saved.append(int(year))
    return saved


def split_by_time(frame):
    labelled = frame.dropna(subset=["crash_ahead"])
    labelled = labelled[labelled["arrival_ratio_3d"].notna() & labelled["price_vs_baseline"].notna()]
    cutoff = pd.Timestamp(config.TEST_START)
    horizon_gap = pd.Timedelta(days=config.FORECAST_HORIZON)
    train = labelled[labelled["date"] < cutoff - horizon_gap]
    test = labelled[labelled["date"] >= cutoff]
    return train, test


class GlutForecaster:
    def __init__(self):
        self.crash_classifier = HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40,
            l2_regularization=1.0, class_weight="balanced", random_state=7,
        )
        self.drop_regressor = HistGradientBoostingRegressor(
            max_iter=250, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40, random_state=7,
        )
        self.timing_regressor = HistGradientBoostingRegressor(
            loss="absolute_error", max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
            min_samples_leaf=20, random_state=7,
        )
        self.metrics = {}
        self.importance = {}

    def fit(self, train):
        features = train[FEATURE_COLUMNS]
        self.crash_classifier.fit(features, train["crash_ahead"].astype(int))
        self.drop_regressor.fit(features, train["future_drop"].clip(-1, 1))
        crashes = train[train["crash_ahead"] == 1]
        if len(crashes) < 20:
            crashes = train
        self.timing_regressor.fit(crashes[FEATURE_COLUMNS], crashes["days_to_bottom"])
        return self

    def predict(self, frame):
        features = frame[FEATURE_COLUMNS]
        result = pd.DataFrame(index=frame.index)
        result["crash_probability"] = self.crash_classifier.predict_proba(features)[:, 1]
        result["predicted_drop"] = self.drop_regressor.predict(features).clip(0, 0.95)
        days = self.timing_regressor.predict(features)
        result["predicted_days_to_bottom"] = np.clip(np.rint(days), 1, config.FORECAST_HORIZON).astype(int)
        return result

    def evaluate(self, test):
        truth = test["crash_ahead"].astype(int)
        if truth.nunique() < 2:
            self.metrics = {"test_rows": int(len(test)), "test_crash_rate": round(float(truth.mean()), 4),
                            "note": "test period has only one outcome, ranking metrics not defined"}
            return self.metrics
        predicted = self.predict(test)
        probability = predicted["crash_probability"]
        alerts = probability >= config.RISK_HIGH
        rule_alerts = test["arrival_ratio_3d"] >= config.SPIKE_RATIO
        crashes = test["crash_ahead"] == 1
        self.metrics = {
            "test_rows": int(len(test)),
            "test_crash_rate": round(float(truth.mean()), 4),
            "roc_auc": round(float(roc_auc_score(truth, probability)), 4),
            "pr_auc": round(float(average_precision_score(truth, probability)), 4),
            "precision_at_high": round(float(precision_score(truth, alerts, zero_division=0)), 4),
            "recall_at_high": round(float(recall_score(truth, alerts, zero_division=0)), 4),
            "rule_precision": round(float(precision_score(truth, rule_alerts, zero_division=0)), 4),
            "rule_recall": round(float(recall_score(truth, rule_alerts, zero_division=0)), 4),
            "drop_mae": round(float(mean_absolute_error(test["future_drop"].clip(-1, 1), predicted["predicted_drop"])), 4),
            "days_to_bottom_mae": round(float(mean_absolute_error(
                test.loc[crashes, "days_to_bottom"], predicted.loc[crashes, "predicted_days_to_bottom"]
            )), 3) if crashes.any() else None,
        }
        sample = test.sample(min(len(test), 4000), random_state=7)
        ranking = permutation_importance(
            self.crash_classifier, sample[FEATURE_COLUMNS], sample["crash_ahead"].astype(int),
            scoring="average_precision", n_repeats=5, random_state=7,
        )
        self.importance = dict(sorted(
            zip(FEATURE_COLUMNS, np.round(ranking.importances_mean, 4).tolist()),
            key=lambda item: item[1], reverse=True,
        ))
        return self.metrics

    STATE_KEYS = ("crash_classifier", "drop_regressor", "timing_regressor", "metrics", "importance")

    def save(self, path):
        joblib.dump({key: getattr(self, key) for key in self.STATE_KEYS}, path)

    @classmethod
    def load(cls, path):
        state = joblib.load(path)
        forecaster = cls()
        for key in cls.STATE_KEYS:
            setattr(forecaster, key, state[key])
        return forecaster


def train(commodity, state):
    frame = build_features(load_panel(commodity, state))
    train_rows, test_rows = split_by_time(frame)
    print(f"{commodity}/{state}: train {len(train_rows)} rows ({train_rows['crash_ahead'].mean():.1%} crash), "
          f"test {len(test_rows)} rows ({test_rows['crash_ahead'].mean():.1%} crash)")
    forecaster = GlutForecaster().fit(train_rows)
    metrics = forecaster.evaluate(test_rows)
    final = GlutForecaster().fit(pd.concat([train_rows, test_rows]))
    final.metrics, final.importance = forecaster.metrics, forecaster.importance
    final.save(model_path(commodity, state))
    years = train_year_models(frame, commodity, state)
    print(f"Year models trained only on earlier data: {years}")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"commodity": commodity, "state": state, "metrics": metrics, "feature_importance": forecaster.importance}
    report_file = config.OUTPUT_DIR / f"model_report_{commodity}_{state.replace(' ', '_')}.json"
    report_file.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return final


def main():
    argparse.ArgumentParser().parse_args()
    for commodity, state in config.TRACKED:
        if not panel_path(commodity, state).exists():
            print(f"{commodity}/{state}: skipped, run prepare first")
            continue
        train(commodity, state)


if __name__ == "__main__":
    main()
