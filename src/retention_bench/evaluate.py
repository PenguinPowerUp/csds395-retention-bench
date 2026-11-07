"""Metrics on the test rows, and the suppression that every published cell obeys.

Every cell in the reliability table, the decile table and the threshold
confusion matrix holds at least MIN_CELL returned and MIN_CELL churned players.
The three tables are checked jointly: the union of all their cut points
partitions the score axis into bands, and cuts are removed until every band
satisfies the minimum. A table then uses only its surviving cuts, so no cell
smaller than the minimum can be recovered by subtracting one table from another.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

MIN_CELL = 10
BIN_EDGES = tuple(round(0.1 * k, 1) for k in range(1, 10))  # interior edges of ten bins


def basic_metrics(y: np.ndarray, p: np.ndarray) -> dict:
    return {
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "pr_auc_floor": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, p)), 4) if len(np.unique(p)) > 1 else 0.5,
        "brier": round(float(brier_score_loss(y, p)), 4),
    }


def decile_cuts(p: np.ndarray) -> list[float]:
    """Score values splitting p into ten rank groups, decile 1 the highest. Tied scores share a group."""
    order = np.sort(p)[::-1]
    n = len(order)
    cuts = []
    for k in range(1, 10):
        idx = int(np.floor(k * n / 10))
        if 0 < idx < n:
            cuts.append(float(order[idx - 1]))  # lowest score inside the top k deciles
    return cuts


def band_index(p: np.ndarray, cuts: list[float]) -> np.ndarray:
    """Band k = {cuts[k-1] <= p < cuts[k]}, with band 0 below the first cut. Higher band = higher score."""
    return np.searchsorted(np.asarray(cuts), p, side="right")


def band_counts(y: np.ndarray, p: np.ndarray, cuts: list[float]) -> tuple[np.ndarray, np.ndarray]:
    b = band_index(p, cuts)
    nb = len(cuts) + 1
    pos = np.bincount(b, weights=y, minlength=nb)
    tot = np.bincount(b, minlength=nb)
    return pos, tot - pos


def prune_cuts(y: np.ndarray, p: np.ndarray, cuts: list[float], protected: set[float], min_cell: int = MIN_CELL) -> list[float]:
    """Remove cuts until every band has >= min_cell positives and negatives. Protected cuts go last."""
    cuts = sorted(set(cuts))
    while cuts:
        pos, neg = band_counts(y, p, cuts)
        bad = np.where((pos < min_cell) | (neg < min_cell))[0]
        if len(bad) == 0:
            return cuts
        k = int(bad[0])
        # candidate cuts bounding band k: cuts[k-1] (lower) and cuts[k] (upper)
        cands = [c for c in (cuts[k - 1] if k > 0 else None, cuts[k] if k < len(cuts) else None) if c is not None]
        unprotected = [c for c in cands if c not in protected]
        drop = unprotected[0] if unprotected else cands[0]
        cuts.remove(drop)
    return cuts


def table(y: np.ndarray, p: np.ndarray, cuts: list[float], label: str) -> list[dict]:
    """One row per band, highest score first for deciles and lowest first for bins; caller orders."""
    b = band_index(p, cuts)
    rows = []
    edges = [-np.inf] + list(cuts) + [np.inf]
    for k in range(len(cuts) + 1):
        m = b == k
        if m.sum() == 0:
            continue
        rows.append({
            label: f"{max(edges[k], 0.0):.4g}-{min(edges[k + 1], 1.0):.4g}",
            "players": int(m.sum()),
            "returning": int(y[m].sum()),
            "not_returning": int((1 - y[m]).sum()),
            "mean_predicted": round(float(p[m].mean()), 4),
            "observed_returning": round(float(y[m].mean()), 4),
        })
    return rows


def confusion(y: np.ndarray, p: np.ndarray, t: float) -> dict:
    pred = (p >= t).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    return {
        "accuracy": round((tp + tn) / len(y), 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(2 * prec * rec / max(prec + rec, 1e-12), 4),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def published_tables(y: np.ndarray, p: np.ndarray, threshold: float, min_cell: int = MIN_CELL) -> dict:
    """Reliability bins, decile lift and the threshold confusion, after joint suppression."""
    bins = [c for c in BIN_EDGES if p.min() < c <= p.max()]
    decs = decile_cuts(p)
    all_cuts = sorted(set(bins) | set(decs) | {threshold})
    kept = set(prune_cuts(y, p, all_cuts, protected={threshold}, min_cell=min_cell))

    rel_cuts = sorted(c for c in bins if c in kept)
    dec_cuts = sorted(c for c in decs if c in kept)
    overall = float(y.mean())

    reliability = table(y, p, rel_cuts, "bin")
    deciles_rows = table(y, p, dec_cuts, "score_band")[::-1]  # highest first
    # name decile groups by rank position: compute which original deciles each band spans
    n = len(p)
    ranks_desc = np.argsort(np.argsort(-p, kind="stable"), kind="stable")
    rank_cuts = [int(np.floor(k * n / 10)) for k in range(1, 10)]  # decile k = ranks [cut_{k-1}, cut_k)
    decile_of = np.searchsorted(rank_cuts, ranks_desc, side="right") + 1
    b = band_index(p, dec_cuts)
    for row, k in zip(deciles_rows, sorted(np.unique(b), reverse=True)):
        d = decile_of[b == k]
        lo, hi = int(d.min()), int(d.max())
        row["deciles"] = f"{lo}" if lo == hi else f"{lo}-{hi}"
        row["return_rate"] = row.pop("observed_returning")
        row["lift"] = round(row["return_rate"] / overall, 4) if overall > 0 else None
        row.pop("mean_predicted")

    thr = confusion(y, p, threshold) if threshold in kept else {"suppressed": True}
    return {
        "min_cell": min_cell,
        "suppression": (
            "every cut used by the reliability bins, the decile groups and the threshold is checked together; "
            f"each band between consecutive cuts holds at least {min_cell} returning and {min_cell} not-returning "
            "players, so no count under the minimum is recoverable by differencing tables"
        ),
        "reliability_test": reliability,
        "lift_test": {
            "method": "deciles of calibrated P(return) on test, decile 1 the highest; adjacent deciles merged until every count meets the minimum, jointly with the other tables; lift = group return rate / test return rate",
            "deciles": deciles_rows,
            "top": {"deciles": deciles_rows[0]["deciles"], "lift": deciles_rows[0]["lift"]} if deciles_rows else None,
        },
        "threshold_test": thr,
    }
