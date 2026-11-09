"""The pipeline: canonical tables -> label -> split -> features -> four models -> results.

Reads data/<dataset>/ as written by a dataset adapter (see canonical.py) and writes
results/<dataset>/results.json and model.json. Every published number is an
aggregate; see evaluate.published_tables for the suppression rule. The temporal
leakage checks come from the temporal-leak package and run on every fit.
"""

from __future__ import annotations

import argparse
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import temporal_leak as tl

from . import canonical, evaluate, model
from .features import fit_scaler
from .labels import build_labels
from .split import FRACTIONS, random_split, temporal_split

SEED = 395
DAY = pd.Timedelta(days=1)


def day_zero_features(activity: pd.DataFrame, labels: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Join label rows to their cohort-day activity row. Features use the cohort day only."""
    f = labels.merge(activity, left_on=["player", "cohort_date"], right_on=["player", "day"], how="left")
    tl.check_before_cutoff(f["last_ts"], f["cohort_date"] + DAY, strict=False)
    for c in features:
        f[c] = f[c].fillna(0)
    return f[["player", "cohort_date", "returned", *features]]


def late_on_day(activity: pd.DataFrame, window_minutes: int) -> pd.Series:
    """True where the player's last observed moment of that day falls in the final window."""
    return (activity["last_ts"] - activity["day"]).dt.total_seconds() >= 86400 - 60 * window_minutes


def build_population(ds: canonical.Dataset, strict_new: bool = False, min_next_day_coverage: float = 0.0,
                     strict_return: bool = False, drop_online_at_midnight: bool = False) -> dict:
    """Label rows for new players, with the exclusion counts taken on new players only."""
    act, meta = ds.activity, ds.meta
    lab = build_labels(act[["player", "day"]])
    new_col = "is_new_strict" if strict_new else "is_new"
    rows = lab.all_rows.merge(ds.players[["player", new_col]], on="player")
    rows = rows[rows[new_col]]
    n_new = len(rows)
    censored = int((rows["exclusion"] == "censored").sum())
    outage = int((rows["exclusion"] == "outage").sum())
    frame = rows[rows["exclusion"] == ""].drop(columns=["exclusion", new_col])
    dropped_partial = 0
    if min_next_day_coverage > 0:
        nxt = frame["cohort_date"] + DAY
        ok = nxt.map(ds.coverage).fillna(0) >= min_next_day_coverage
        dropped_partial = int((~ok).sum())
        frame = frame[ok]
    dropped_midnight = 0
    if drop_online_at_midnight:
        late = act.loc[late_on_day(act, meta["midnight_window_minutes"]), ["player", "day"]]
        is_late = pd.MultiIndex.from_arrays([frame["player"], frame["cohort_date"]]).isin(pd.MultiIndex.from_frame(late))
        dropped_midnight = int(is_late.sum())
        frame = frame[~is_late]
    if strict_return:
        started = act.loc[act["sessions_started"] > 0, ["player", "day"]]
        key = pd.MultiIndex.from_frame(started)
        nxt = pd.MultiIndex.from_arrays([frame["player"], frame["cohort_date"] + DAY])
        frame = frame.assign(returned=nxt.isin(key).astype(int))
    feats = day_zero_features(act, frame[["player", "cohort_date", "returned"]], meta["features"])
    return {
        "features": feats.reset_index(drop=True),
        "counts": {
            "new_players": n_new,
            # Right-censored and outage-day exclusions are published only as their sum: the
            # censored group alone can be a handful of players and must not appear as its own count.
            "excluded_next_day_not_observed": censored + outage,
            "excluded_partial_outage": dropped_partial,
            "excluded_online_at_midnight": dropped_midnight,
            "eligible": int(len(feats)),
            "empty_days": [str(d.date()) for d in lab.empty_days],
        },
    }


MIN_PUBLISHED_COUNT = 10


def check_published_counts(results: dict) -> None:
    """Refuse to write a population count between 1 and 9 anywhere in the counts blocks."""
    blocks = [results["population"]["counts"]] + [v["counts"] for v in results["sensitivity"].values() if "counts" in v]
    for block in blocks:
        for k, v in block.items():
            if isinstance(v, int) and 0 < v < MIN_PUBLISHED_COUNT:
                raise SystemExit(f"refusing to publish count {k}={v}: below {MIN_PUBLISHED_COUNT}")


def midnight_stats(ds: canonical.Dataset, feats: pd.DataFrame) -> dict:
    act = ds.activity
    late = act.loc[late_on_day(act, ds.meta["midnight_window_minutes"]), ["player", "day"]]
    m = pd.MultiIndex.from_arrays([feats["player"], feats["cohort_date"]]).isin(pd.MultiIndex.from_frame(late))
    y = feats["returned"].to_numpy()
    w = ds.meta["midnight_window_minutes"]
    return {f"share_online_in_last_{w}_min_of_cohort_day": round(float(m.mean()), 4),
            "return_rate_online_at_midnight": round(float(y[m].mean()), 4) if m.any() else None,
            "return_rate_others": round(float(y[~m].mean()), 4)}


def rate_by_year(feats: pd.DataFrame) -> dict:
    g = feats.groupby(feats["cohort_date"].dt.year)["returned"].agg(["size", "mean"])
    return {str(y): {"eligible": int(n), "returning_rate": round(float(m), 4)} for y, (n, m) in g.iterrows()}


def fit_and_evaluate(feats: pd.DataFrame, split_part, features: list[str], single: str) -> dict:
    y = feats["returned"].to_numpy(dtype=int)
    part = np.asarray(split_part)
    tr, va, te = (part == k for k in ("train", "validation", "test"))
    tl.check_fit_rows(tr | va, ~te)  # the scaler, Platt scaling and the threshold never see test rows
    scaler = fit_scaler(feats[tr], features)
    X = scaler.transform(feats)
    Xtr, Xva, Xte = X[tr], X[va], X[te]
    ytr, yva, yte = y[tr], y[va], y[te]

    m_major = model.majority(ytr, va.sum(), te.sum())
    m_single = model.single_feature(Xtr, ytr, Xva, Xte, list(features).index(single), single)
    m_l2 = model.l2_logistic(Xtr, ytr, Xva, Xte, features)
    platt = model.fit_platt(m_l2.scores_val, yva)
    m_cal = model.calibrated(m_l2, platt)
    threshold = model.max_f1_threshold(m_cal.scores_val, yva)

    rows = []
    for m in (m_major, m_single, m_l2, m_cal):
        r = {"name": m.name, **evaluate.basic_metrics(yte, m.scores_test)}
        if m is m_major:
            r["accuracy"] = round(float((yte == 0).mean()), 4)
        rows.append(r)

    pub = evaluate.published_tables(yte, m_cal.scores_test, threshold)
    return {
        "models": rows,
        "calibration": {
            "method": "Platt (sigmoid) on the logistic model's logit, fit on validation",
            "slope": round(platt.a, 4),
            "intercept": round(platt.c, 4),
            "brier_before": rows[2]["brier"],
            "brier_after": rows[3]["brier"],
            "reliability_test": pub["reliability_test"],
        },
        "threshold": {
            "model": m_cal.name,
            "rule": "the calibrated P(return) cut that maximises F1 on the validation split, predicting returning at or above it; test labels never reach the choice",
            "chosen_on": "validation",
            "value": round(threshold, 4),
            "majority_accuracy": rows[0]["accuracy"],
            "test": pub["threshold_test"],
        },
        "lift_test": pub["lift_test"],
        "min_cell": pub["min_cell"],
        "suppression": pub["suppression"],
        "standardized_coefficients": {k: round(v, 4) for k, v in m_l2.coef.items()},
        "intercept": round(m_l2.intercept, 4),
        "hyperparameters": {"penalty": "l2", "C": model.C, "inputs": "log1p, standardized with train statistics"},
        "_scaler": scaler,
        "_platt": platt,
        "_threshold": threshold,
        "_l2": m_l2,
    }


def headline(res: dict) -> dict:
    l2 = res["models"][2]
    return {"pr_auc": l2["pr_auc"], "pr_auc_floor": l2["pr_auc_floor"], "roc_auc": l2["roc_auc"], "brier_calibrated": res["models"][3]["brier"]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    ds = canonical.load(a.data)
    meta = ds.meta
    features, single = meta["features"], meta["single_feature"]

    pop = build_population(ds)
    feats = pop["features"]
    split = temporal_split(feats["cohort_date"])
    tl.check_temporal_split(feats["cohort_date"], split.part)

    # leakage sanity check: same model, rows shuffled instead of split by date
    def run_parts(parts):
        return fit_and_evaluate(feats, parts, features, single)

    def over_floor(r):
        return r["models"][2]["pr_auc"] / r["models"][2]["pr_auc_floor"]

    rnd = random_split(len(feats), FRACTIONS, SEED)
    shuffled = tl.shuffle_test(run_parts, split.part.to_numpy(), rnd.part.to_numpy(), metric=over_floor)
    res, res_rnd = shuffled["temporal"], shuffled["random"]
    print("main:", headline(res))

    sensitivity = {}
    for run in meta["sensitivity"]:
        kw = {k: v for k, v in run.items() if k != "key"}
        p = build_population(ds, **kw)
        f = p["features"]
        r = fit_and_evaluate(f, temporal_split(f["cohort_date"]).part, features, single)
        sensitivity[run["key"]] = {"eligible": int(len(f)), "returning_rate": round(float(f["returned"].mean()), 4), **headline(r),
                                   "counts": {k: v for k, v in p["counts"].items() if k != "empty_days"}}
        print(f"sensitivity {run['key']}:", sensitivity[run["key"]])
    for run in meta["drop_feature_runs"]:
        sub = [f for f in features if f != run["feature"]]
        r = fit_and_evaluate(feats, split.part, sub, single)
        sensitivity[run["key"]] = {"features": sub, **headline(r), "standardized_coefficients": r["standardized_coefficients"]}
        print(f"sensitivity {run['key']}:", sensitivity[run["key"]])

    y = feats["returned"]
    results = {
        "title": meta["title"],
        "dataset": meta["dataset"],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__},
        "label": {"horizon_days": 1, "new_player_rule": meta["new_player_rule"]},
        "features": list(features),
        "positive_class": "returned = 1",
        "population": {
            "eligible": int(len(feats)),
            "returning": int(y.sum()),
            "returning_rate": round(float(y.mean()), 4),
            "returning_rate_by_cohort_year": rate_by_year(feats),
            "returning_rate_by_split": {k: round(float(y[split.part == k].mean()), 4) for k in ("train", "validation", "test")},
            "midnight": midnight_stats(ds, feats),
            "counts": pop["counts"],
            "split": split.ranges(feats["cohort_date"]),
        },
        **{k: v for k, v in res.items() if not k.startswith("_")},
        "leakage_check": {
            "method": "identical features and model, rows assigned to train/validation/test uniformly at random with the same fractions; a large gain over the temporal split indicates time-correlated information the temporal split correctly withholds",
            "random_split": {**headline(res_rnd), "pr_auc_over_floor": round(over_floor(res_rnd), 3)},
            "temporal_split": {**headline(res), "pr_auc_over_floor": round(over_floor(res), 3)},
        },
        "sensitivity": sensitivity,
    }
    check_published_counts(results)
    (a.out / "results.json").write_text(json.dumps(results, indent=2))

    sc, pl, l2 = res["_scaler"], res["_platt"], res["_l2"]
    model_json = {
        "model_version": f"{meta['name']}-{results['generated_at'][:10]}",
        "features": list(features),
        "transform": "log1p, then (u - mean) / scale with the train statistics below",
        "mean": {k: round(v, 6) for k, v in sc.mean.items()},
        "scale": {k: round(v, 6) for k, v in sc.scale.items()},
        "coefficients": {k: round(v, 6) for k, v in l2.coef.items()},
        "intercept": round(l2.intercept, 6),
        "calibration": {"method": "platt", "a": round(pl.a, 6), "c": round(pl.c, 6), "applies_to": "logit of P(return)"},
        "threshold": {"value": round(res["_threshold"], 6), "rule": "max-F1 on validation", "predict_return_if": ">= value"},
        "output": "P(return); churn probability is 1 - P(return)",
        "split": results["population"]["split"],
        "test": headline(res),
    }
    (a.out / "model.json").write_text(json.dumps(model_json, indent=2))
    print(f"wrote {a.out}/results.json and model.json")


if __name__ == "__main__":
    main()
