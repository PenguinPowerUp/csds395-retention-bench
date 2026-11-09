import pandas as pd

from retention_bench.datasets.wowah.sessions import per_avatar_day


def snaps(rows):
    return pd.DataFrame(rows, columns=["avatar", "ts", "level", "zone"]).assign(ts=lambda d: pd.to_datetime(d["ts"]))


def test_session_time_is_split_at_midnight_and_counted_on_both_days():
    s = snaps([
        (1, "2026-01-01 23:40:00", 1, "A"), (1, "2026-01-01 23:50:00", 1, "A"),
        (1, "2026-01-02 00:00:00", 2, "A"), (1, "2026-01-02 00:10:00", 2, "B"),
    ])
    pad = per_avatar_day(s).set_index("day")
    d1, d2 = pad.loc[pd.Timestamp("2026-01-01")], pad.loc[pd.Timestamp("2026-01-02")]
    assert d1["session_minutes"] == 20 and d1["snapshots"] == 2 and d1["sessions"] == 1   # 23:40 -> 00:00, clipped
    assert d2["session_minutes"] == 20 and d2["snapshots"] == 2 and d2["sessions"] == 1   # 00:00 -> 00:20
    assert d2["zones"] == 2


def test_gap_over_twenty_minutes_starts_a_new_session():
    s = snaps([(1, "2026-01-01 10:00:00", 1, "A"), (1, "2026-01-01 10:10:00", 1, "A"), (1, "2026-01-01 11:00:00", 1, "A")])
    pad = per_avatar_day(s)
    assert pad.loc[0, "sessions"] == 2 and pad.loc[0, "session_minutes"] == 30


def test_sessions_started_counts_only_sessions_beginning_that_day():
    s = snaps([
        (1, "2026-01-01 23:50:00", 1, "A"), (1, "2026-01-02 00:00:00", 1, "A"),   # one session crossing midnight
        (1, "2026-01-02 09:00:00", 1, "A"),                                          # a new session on day 2
    ])
    pad = per_avatar_day(s).set_index("day")
    assert pad.loc[pd.Timestamp("2026-01-01"), "sessions_started"] == 1
    assert pad.loc[pd.Timestamp("2026-01-02"), "sessions_started"] == 1
    assert pad.loc[pd.Timestamp("2026-01-02"), "sessions"] == 2
