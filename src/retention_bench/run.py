"""The pipeline: snapshots -> label -> split -> features -> four models -> results.

Writes results/<name>/results.json and model.json. Every published number is an
aggregate; see evaluate.published_tables for the suppression rule.
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

from . import evaluate, model, sessions
from .features import fit_scaler
from .labels import build_labels
from .split import FRACTIONS, random_split, temporal_split

SEED = 395
TRACE_START = pd.Timestamp("2006-01-01")


def load_snapshots(path: Path) -> pd.DataFrame:
    snap = pd.read_parquet(path, columns=["ts", "avatar", "level", "cls", "zone", "day_dir", "sample"])
    for c in ("cls", "zone", "day_dir", "sample"):
        snap[c] = snap[c].astype("category")
    snap = snap[snap["ts"] >= TRACE_START]  # the first sampling round reaches a few seconds into the previous day
    before = len(snap)
    snap = snap.drop_duplicates(subset=["ts", "avatar"])
    print(f"snapshots: {before:,} rows, {len(snap):,} after dropping duplicate (ts, avatar)")
    return snap


def samples_per_day(snap: pd.DataFrame) -> pd.Series:
    """Distinct sampling rounds (log files) per day directory, for the partial-outage sensitivity."""
    rounds = snap[["day_dir", "sample"]].drop_duplicates()
    spd = rounds.groupby("day_dir", observed=True).size()
    spd.index = pd.to_datetime(spd.index.astype(str))
    return spd


def build_population(pad: pd.DataFrame, first: pd.DataFrame, spd: pd.Series, max_first_level: int,
                     min_next_day_samples: int = 0, strict_return: bool = False, drop_online_at_midnight: bool = False) -> dict:
    """Label rows for new avatars, with the exclusion counts taken on new avatars only."""
    lab = build_labels(sessions.activity_days(pad))
    rows = lab.all_rows.merge(first[["avatar", "first_level"]], left_on="player", right_on="avatar")
    rows = rows[rows["first_level"] <= max_first_level]
    n_new = len(rows)
    censored = int((rows["exclusion"] == "censored").sum())
    outage = int((rows["exclusion"] == "outage").sum())
    frame = rows[rows["exclusion"] == ""].drop(columns=["exclusion", "first_level"])
    dropped_partial = 0
    if min_next_day_samples > 0:
        nxt = frame["cohort_date"] + pd.Timedelta(days=1)
        ok = nxt.map(spd).fillna(0) >= min_next_day_samples
        dropped_partial = int((~ok).sum())
        frame = frame[ok]
    dropped_midnight = 0
    if drop_online_at_midnight:
        late = pad.loc[late_on_day(pad), ["avatar", "day"]]
        is_late = pd.MultiIndex.from_arrays([frame["player"], frame["cohort_date"]]).isin(pd.MultiIndex.from_frame(late))
        dropped_midnight = int(is_late.sum())
        frame = frame[~is_late]
    if strict_return:
        started = pad.loc[pad["sessions_started"] > 0, ["avatar", "day"]]
        key = pd.MultiIndex.from_frame(started)
        nxt = pd.MultiIndex.from_arrays([frame["player"], frame["cohort_date"] + pd.Timedelta(days=1)])
        frame = frame.assign(returned=nxt.isin(key).astype(int))
    feats = sessions.day_zero_features(pad, frame[["player", "cohort_date", "returned"]], first)
    return {
        "features": feats.reset_index(drop=True),
        "counts": {
            "new_avatars": n_new,
            # Right-censored and outage-day exclusions are published only as their sum: the
            # censored group alone is a handful of avatars and must not appear as its own count.
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


def late_on_day(pad: pd.DataFrame) -> pd.Series:
    """True where the avatar's last snapshot of that day falls in the final 10 minutes."""
    return (pad["last_ts"] - pad["day"]).dt.total_seconds() >= 86400 - 60 * sessions.SAMPLE_MINUTES


def midnight_stats(pad: pd.DataFrame, feats: pd.DataFrame) -> dict:
    late = pad.loc[late_on_day(pad), ["avatar", "day"]]
    m = pd.MultiIndex.from_arrays([feats["player"], feats["cohort_date"]]).isin(pd.MultiIndex.from_frame(late))
    y = feats["returned"].to_numpy()
    return {"share_online_in_last_10_min_of_cohort_day": round(float(m.mean()), 4),
            "return_rate_online_at_midnight": round(float(y[m].mean()), 4),
            "return_rate_others": round(float(y[~m].mean()), 4)}


def rate_by_year(feats: pd.DataFrame) -> dict:
    g = feats.groupby(feats["cohort_date"].dt.year)["returned"].agg(["size", "mean"])
    return {str(y): {"eligible": int(n), "returning_rate": round(float(m), 4)} for y, (n, m) in g.iterrows()}


def fit_and_evaluate(feats: pd.DataFrame, split_part: pd.Series, features: tuple[str, ...]) -> dict:
    y = feats["returned"].to_numpy(dtype=int)
    tr, va, te = (split_part.to_numpy() == k for k in ("train", "validation", "test"))
    scaler = fit_scaler(feats[tr], features)
    X = scaler.transform(feats)
    Xtr, Xva, Xte = X[tr], X[va], X[te]
    ytr, yva, yte = y[tr], y[va], y[te]

    m_major = model.majority(ytr, va.sum(), te.sum())
    si = features.index("session_minutes")
    m_single = model.single_feature(Xtr, ytr, Xva, Xte, si, "session_minutes")
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
    ap.add_argument("--max-first-level", type=int, default=sessions.MAX_FIRST_LEVEL)
    ap.add_argument("--no-sensitivity", action="store_true")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    snap = load_snapshots(a.data / "snapshots.parquet")
    features = sessions.FEATURES
    pad = sessions.per_avatar_day(snap)
    first = sessions.first_sightings(snap)
    spd = samples_per_day(snap)
    del snap

    pop = build_population(pad, first, spd, a.max_first_level)
    feats = pop["features"]
    split = temporal_split(feats["cohort_date"])
    res = fit_and_evaluate(feats, split.part, features)
    print("main:", headline(res))

    # leakage sanity check: same model, rows shuffled instead of split by date
    rnd = random_split(len(feats), FRACTIONS, SEED)
    res_rnd = fit_and_evaluate(feats, rnd.part, features)

    sensitivity = {}
    if not a.no_sensitivity:
        runs = {
            "first_level_1_only": dict(max_first_level=1),
            "drop_half_empty_next_day": dict(max_first_level=a.max_first_level, min_next_day_samples=72),
            "strict_return_new_session_next_day": dict(max_first_level=a.max_first_level, strict_return=True),
            "drop_avatars_online_at_midnight": dict(max_first_level=a.max_first_level, drop_online_at_midnight=True),
        }
        for name, kw in runs.items():
            p = build_population(pad, first, spd, **kw)
            f = p["features"]
            r = fit_and_evaluate(f, temporal_split(f["cohort_date"]).part, features)
            sensitivity[name] = {"eligible": int(len(f)), "returning_rate": round(float(f["returned"].mean()), 4), **headline(r),
                                 "counts": {k: v for k, v in p["counts"].items() if k != "empty_days"}}
            print(f"sensitivity {name}:", sensitivity[name])
        sub = tuple(f for f in features if f != "snapshots")
        r = fit_and_evaluate(feats, split.part, sub)
        sensitivity["without_snapshots_feature"] = {"features": list(sub), **headline(r),
                                                    "standardized_coefficients": r["standardized_coefficients"]}
        print("sensitivity without_snapshots_feature:", sensitivity["without_snapshots_feature"])

    y = feats["returned"]
    results = {
        "title": "retention-bench: day-one return on WoWAH (Lee et al., MMSys 2011), new avatars, temporal split",
        "dataset": {
            "name": "World of Warcraft Avatar History (WoWAH)",
            "citation": "Y.-T. Lee, K.-T. Chen, Y.-M. Cheng, C.-L. Lei. World of Warcraft Avatar History Dataset. Proc. ACM MMSys 2011.",
            "source": "https://web.cs.wpi.edu/~claypool/mmsys-dataset/2011/wow/",
            "unit": "avatar (character), one realm, Horde; a new avatar is not necessarily a new player",
            "clock": "dataset-native query time; days are calendar days in that clock",
        },
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "pandas": pd.__version__, "numpy": np.__version__},
        "label": {"max_first_level": a.max_first_level, "horizon_days": 1},
        "features": list(features),
        "positive_class": "returned = 1",
        "population": {
            "eligible": int(len(feats)),
            "returning": int(y.sum()),
            "returning_rate": round(float(y.mean()), 4),
            "returning_rate_by_cohort_year": rate_by_year(feats),
            "returning_rate_by_split": {k: round(float(y[split.part == k].mean()), 4) for k in ("train", "validation", "test")},
            "midnight": midnight_stats(pad, feats),
            "counts": pop["counts"],
            "split": split.ranges(feats["cohort_date"]),
        },
        **{k: v for k, v in res.items() if not k.startswith("_")},
        "leakage_check": {
            "method": "identical features and model, rows assigned to train/validation/test uniformly at random with the same fractions; a large gain over the temporal split indicates time-correlated information the temporal split correctly withholds",
            "random_split": {**headline(res_rnd), "pr_auc_over_floor": round(res_rnd["models"][2]["pr_auc"] / res_rnd["models"][2]["pr_auc_floor"], 3)},
            "temporal_split": {**headline(res), "pr_auc_over_floor": round(res["models"][2]["pr_auc"] / res["models"][2]["pr_auc_floor"], 3)},
        },
        "sensitivity": sensitivity,
    }
    check_published_counts(results)
    (a.out / "results.json").write_text(json.dumps(results, indent=2))

    sc, pl, l2 = res["_scaler"], res["_platt"], res["_l2"]
    model_json = {
        "model_version": f"wowah-{results['generated_at'][:10]}",
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
