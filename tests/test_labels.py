import pandas as pd

from retention_bench.labels import build_labels


def frame(rows):
    return pd.DataFrame(rows, columns=["player", "day"]).assign(day=lambda d: pd.to_datetime(d["day"]))


def test_return_is_activity_on_exactly_the_next_day():
    act = frame([
        ("a", "2026-01-01"), ("a", "2026-01-02"),          # returns
        ("b", "2026-01-01"), ("b", "2026-01-03"),          # skips a day: churned
        ("c", "2026-01-01"),                               # never back
        ("z", "2026-01-04"),                               # keeps the data alive to Jan 4
        ("z", "2026-01-02"), ("z", "2026-01-03"),
    ])
    res = build_labels(act)
    got = res.frame.set_index("player")["returned"].to_dict()
    assert got["a"] == 1 and got["b"] == 0 and got["c"] == 0


def test_right_censored_cohort_is_excluded_not_labelled_negative():
    act = frame([("a", "2026-01-01"), ("a", "2026-01-02"), ("late", "2026-01-02")])
    res = build_labels(act)
    assert "late" not in set(res.frame["player"])
    assert res.excluded_censored == 1


def test_cohort_whose_next_day_is_empty_is_excluded():
    # Jan 2 has no activity from anyone; the Jan 1 cohort cannot be judged.
    act = frame([("a", "2026-01-01"), ("b", "2026-01-03"), ("b", "2026-01-04")])
    res = build_labels(act)
    assert res.empty_days == [pd.Timestamp("2026-01-02")]
    assert "a" not in set(res.frame["player"])
    assert res.excluded_outage == 1
    assert res.frame.set_index("player").loc["b", "returned"] == 1


def test_cohort_is_the_first_day_only():
    act = frame([("a", "2026-01-05"), ("a", "2026-01-01"), ("a", "2026-01-02"), ("z", "2026-01-06")])
    res = build_labels(act)
    row = res.frame.set_index("player").loc["a"]
    assert row["cohort_date"] == pd.Timestamp("2026-01-01") and row["returned"] == 1


def test_all_rows_carry_the_exclusion_reason():
    act = frame([("a", "2026-01-01"), ("b", "2026-01-03"), ("b", "2026-01-04"), ("late", "2026-01-04")])
    res = build_labels(act)
    reason = res.all_rows.set_index("player")["exclusion"].to_dict()
    assert reason == {"a": "outage", "b": "", "late": "censored"}
