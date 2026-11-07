import numpy as np

from retention_bench.evaluate import MIN_CELL, band_counts, prune_cuts, published_tables


def test_pruning_removes_cuts_until_every_band_has_ten_of_each():
    rng = np.random.default_rng(0)
    p = rng.beta(1.5, 6, size=800)              # few high scores
    y = (rng.random(800) < p).astype(int)
    cuts = prune_cuts(y, p, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], protected=set())
    pos, neg = band_counts(y, p, cuts)
    assert (pos >= MIN_CELL).all() and (neg >= MIN_CELL).all()


def test_published_tables_never_show_a_small_cell_and_protect_the_threshold():
    rng = np.random.default_rng(1)
    p = rng.beta(1.5, 6, size=1500)
    y = (rng.random(1500) < p).astype(int)
    out = published_tables(y, p, threshold=0.25)
    for row in out["reliability_test"]:
        assert row["returning"] >= MIN_CELL and row["not_returning"] >= MIN_CELL
    for row in out["lift_test"]["deciles"]:
        assert row["returning"] >= MIN_CELL and row["not_returning"] >= MIN_CELL
    assert "confusion" in out["threshold_test"]
    c = out["threshold_test"]["confusion"]
    assert c["tp"] + c["fp"] + c["fn"] + c["tn"] == 1500
