import numpy as np

from retention_bench.model import fit_platt, max_f1_threshold, sigmoid


def test_platt_is_near_identity_on_calibrated_scores():
    rng = np.random.default_rng(2)
    z = rng.normal(-1.5, 1.2, size=20000)
    p = sigmoid(z)
    y = (rng.random(20000) < p).astype(int)
    pl = fit_platt(p, y)
    assert abs(pl.a - 1) < 0.1 and abs(pl.c) < 0.1


def test_max_f1_threshold_is_a_score_value_and_maximizes_f1():
    p = np.array([0.9, 0.8, 0.7, 0.4, 0.3, 0.2, 0.1])
    y = np.array([1, 1, 0, 1, 0, 0, 0])
    t = max_f1_threshold(p, y)
    assert t in set(p)
    # F1 at 0.4: tp=3 fp=1 fn=0 -> 0.857; at 0.8: tp=2 fn=1 -> 0.8
    assert t == 0.4
