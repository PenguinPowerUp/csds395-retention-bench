import numpy as np
import pandas as pd

from retention_bench.split import temporal_split


def test_whole_dates_and_time_order():
    dates = pd.to_datetime(["2026-01-%02d" % d for d in range(1, 11)])
    cohort = pd.Series(np.repeat(dates, 10))  # 100 rows, 10 per date
    s = temporal_split(cohort)
    parts = pd.DataFrame({"d": cohort, "p": s.part})
    # one part per date
    assert (parts.groupby("d")["p"].nunique() == 1).all()
    # order: every train date < every validation date < every test date
    tr, va, te = (parts.loc[parts.p == k, "d"] for k in ("train", "validation", "test"))
    assert tr.max() < va.min() < va.max() < te.min()
    assert len(tr) == 60 and len(va) == 20 and len(te) == 20


def test_each_part_gets_a_date_even_when_rows_are_skewed():
    cohort = pd.Series(pd.to_datetime(["2026-01-01"] * 98 + ["2026-01-02", "2026-01-03"]))
    s = temporal_split(cohort)
    assert set(s.part) == {"train", "validation", "test"}
