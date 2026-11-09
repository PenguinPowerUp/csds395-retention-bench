import numpy as np
import pandas as pd
import pytest
from temporal_leak import LeakageError

from retention_bench.run import day_zero_features, fit_and_evaluate


def test_a_feature_observed_after_midnight_stops_the_pipeline():
    activity = pd.DataFrame({"player": [1], "day": pd.to_datetime(["2026-01-01"]), "x": [3.0],
                             "last_ts": pd.to_datetime(["2026-01-02 00:20"])})   # session minutes not cut at midnight
    labels = pd.DataFrame({"player": [1], "cohort_date": pd.to_datetime(["2026-01-01"]), "returned": [1]})
    with pytest.raises(LeakageError, match="at or after"):
        day_zero_features(activity, labels, ["x"])


def test_a_clipped_feature_passes():
    activity = pd.DataFrame({"player": [1], "day": pd.to_datetime(["2026-01-01"]), "x": [3.0],
                             "last_ts": pd.to_datetime(["2026-01-02 00:00"])})
    labels = pd.DataFrame({"player": [1], "cohort_date": pd.to_datetime(["2026-01-01"]), "returned": [1]})
    assert day_zero_features(activity, labels, ["x"])["x"].tolist() == [3.0]


def test_fit_and_evaluate_runs_on_a_clean_split():
    rng = np.random.default_rng(0)
    n = 3000
    x = rng.gamma(2, 20, size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(np.log1p(x) - 3.5)))).astype(int)
    feats = pd.DataFrame({"session_minutes": x, "returned": y})
    parts = np.array(["train"] * 1800 + ["validation"] * 600 + ["test"] * 600, dtype=object)
    out = fit_and_evaluate(feats, parts, ["session_minutes"], "session_minutes")
    assert out["models"][2]["pr_auc"] > out["models"][0]["pr_auc"]
