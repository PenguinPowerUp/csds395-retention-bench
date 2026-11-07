"""The four models: majority class, single feature, L2 logistic, Platt-calibrated.

All four are scored on the same rows. Parameters that involve a choice (the
Platt scaling and the threshold) are fit on validation rows only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.linear_model import LogisticRegression

C = 1.0
PLATT_C = 1e6  # effectively unpenalized: two parameters


@dataclass
class Fitted:
    name: str
    coef: dict[str, float] | None
    intercept: float | None
    scores_val: np.ndarray
    scores_test: np.ndarray


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return np.log(p / (1 - p))


def fit_logistic(X: np.ndarray, y: np.ndarray, c: float = C) -> LogisticRegression:
    return LogisticRegression(C=c, solver="lbfgs", max_iter=1000).fit(X, y)  # L2 is the default penalty


def majority(y_train: np.ndarray, n_val: int, n_test: int) -> Fitted:
    rate = float(y_train.mean())
    return Fitted("majority class (everyone churns)", None, None, np.full(n_val, rate), np.full(n_test, rate))


def single_feature(Xtr, ytr, Xva, Xte, feature_index: int, feature_name: str) -> Fitted:
    col = [feature_index]
    m = fit_logistic(Xtr[:, col], ytr)
    return Fitted(
        f"{feature_name} (single feature)",
        {feature_name: float(m.coef_[0, 0])},
        float(m.intercept_[0]),
        m.predict_proba(Xva[:, col])[:, 1],
        m.predict_proba(Xte[:, col])[:, 1],
    )


def l2_logistic(Xtr, ytr, Xva, Xte, features: tuple[str, ...]) -> Fitted:
    m = fit_logistic(Xtr, ytr)
    return Fitted(
        "logistic regression (L2)",
        {f: float(w) for f, w in zip(features, m.coef_[0])},
        float(m.intercept_[0]),
        m.predict_proba(Xva)[:, 1],
        m.predict_proba(Xte)[:, 1],
    )


@dataclass(frozen=True)
class Platt:
    a: float
    c: float

    def apply(self, p: np.ndarray) -> np.ndarray:
        return sigmoid(self.a * logit(p) + self.c)


def fit_platt(p_val: np.ndarray, y_val: np.ndarray) -> Platt:
    z = logit(p_val).reshape(-1, 1)
    m = LogisticRegression(C=PLATT_C, solver="lbfgs", max_iter=1000).fit(z, y_val)
    return Platt(a=float(m.coef_[0, 0]), c=float(m.intercept_[0]))


def calibrated(base: Fitted, platt: Platt) -> Fitted:
    return Fitted(
        "logistic regression (Platt-calibrated)",
        base.coef,
        base.intercept,
        platt.apply(base.scores_val),
        platt.apply(base.scores_test),
    )


def max_f1_threshold(p_val: np.ndarray, y_val: np.ndarray) -> float:
    """The cut maximizing F1 on validation, predicting return at or above it. Ties go to the higher cut."""
    order = np.argsort(-p_val)
    p_sorted, y_sorted = p_val[order], y_val[order]
    tp = np.cumsum(y_sorted)
    fp = np.cumsum(1 - y_sorted)
    fn = y_sorted.sum() - tp
    f1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
    # only evaluate at the last index of each distinct score (predict >= cut)
    last = np.r_[p_sorted[1:] != p_sorted[:-1], True]
    cand = np.where(last)[0]
    best = cand[np.argmax(f1[cand])]
    # ties -> higher cut: argmax returns the first max, which is the highest score
    return float(p_sorted[best])
