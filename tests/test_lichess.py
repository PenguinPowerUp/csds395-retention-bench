import pandas as pd

from retention_bench.datasets.lichess.parse import parse_lines
from retention_bench.datasets.lichess.prepare import new_player_flags
from retention_bench.datasets.lichess.sessions import per_player_day, player_games

PGN = """[Event "Rated Blitz game"]
[White "a"]
[Black "b"]
[Result "1-0"]
[UTCDate "2013.05.01"]
[UTCTime "23:50:00"]
[WhiteElo "1500"]
[BlackElo "1600"]
[WhiteRatingDiff "+120"]
[BlackRatingDiff "-12"]
[TimeControl "180+0"]

1. e4 e5 1-0

[Event "Rated Correspondence game"]
[White "a"]
[Black "c"]
[Result "0-1"]
[UTCDate "2013.05.01"]
[UTCTime "10:00:00"]
[WhiteElo "1500"]
[BlackElo "1500"]
[TimeControl "-"]

1. d4 0-1
""".splitlines(keepends=True)


def games(rows):
    return pd.DataFrame(rows, columns=["ts", "white", "black", "result", "white_elo", "black_elo",
                                       "white_diff", "black_diff", "time_control", "event"]).assign(ts=lambda d: pd.to_datetime(d["ts"]))


def test_headers_are_read_and_moves_skipped():
    cols = parse_lines(PGN)
    assert cols["White"] == ["a", "a"] and cols["TimeControl"] == ["180+0", "-"]
    assert cols["WhiteRatingDiff"] == ["+120", None]


def test_correspondence_and_self_play_are_dropped_and_wins_assigned():
    g = games([
        ("2013-05-01 10:00", "a", "b", "1-0", 1500, 1600, 120, -12, "180+0", "Rated Blitz game"),
        ("2013-05-01 11:00", "a", "c", "0-1", 1500, 1500, -80, 80, "-", "Rated Correspondence game"),
        ("2013-05-01 12:00", "a", "a", "1-0", 1500, 1500, 0, 0, "60+0", "Rated Bullet game"),
    ])
    pg = player_games(g)
    assert len(pg) == 2 and pg["win"].sum() == 1 and set(pg["speed"]) == {"blitz"}
    assert (pg["end"] - pg["ts"]).dt.total_seconds().unique().tolist() == [180.0]   # 180 + 40 x 0


def test_minutes_are_cut_at_midnight_and_the_next_day_needs_a_new_game():
    g = games([("2013-05-01 23:50", "a", "b", "1-0", 1500, 1600, 120, -12, "600+0", "Rated Blitz game")])
    day = per_player_day(player_games(g)).query("player == 0")
    assert len(day) == 1                                   # the game ends on May 2, but May 2 is not active
    row = day.iloc[0]
    assert row["session_minutes"] == 10 and row["last_ts"] == pd.Timestamp("2013-05-02")


def test_games_within_thirty_minutes_of_the_last_end_share_a_session():
    g = games([
        ("2013-05-01 10:00", "a", "b", "1-0", 1500, 1600, 120, -12, "60+0", "Rated Bullet game"),   # ends 10:01
        ("2013-05-01 10:30", "a", "b", "0-1", 1620, 1588, -10, 10, "60+0", "Rated Bullet game"),   # within 30 min
        ("2013-05-01 12:00", "a", "b", "1-0", 1610, 1598, 9, -9, "60+0", "Rated Bullet game"),     # new session
    ])
    row = per_player_day(player_games(g)).query("player == 0").iloc[0]
    assert row["sessions"] == 2 and row["games"] == 3 and row["wins"] == 2 and row["sessions_started"] == 2


def test_new_player_rule():
    first = pd.DataFrame({"player": [0, 1, 2, 3, 4], "first_elo": [1500, 1500, 1720, 1500, 1500],
                          "first_diff": [120, 20, 30, 150, 150],
                          "first_day": pd.to_datetime(["2013-05-01", "2013-05-01", "2013-05-01", "2013-02-01", "2013-08-01"])})
    f = new_player_flags(first).set_index("player")
    assert f["is_new"].tolist() == [True, False, False, False, True]
    assert f["is_new_strict"].tolist() == [False, False, False, False, True]


def test_first_game_is_the_first_row_even_when_its_rating_change_is_missing():
    from retention_bench.datasets.lichess.sessions import first_games
    g = games([
        ("2013-05-01 10:00", "a", "b", "1-0", 1500, 1600, None, -12, "60+0", "Rated Bullet game"),
        ("2013-05-02 10:00", "a", "b", "1-0", 1500, 1600, 120, -12, "60+0", "Rated Bullet game"),
    ])
    first = first_games(player_games(g)).set_index("player")
    assert pd.isna(first.loc[0, "first_diff"]) and first.loc[0, "first_day"] == pd.Timestamp("2013-05-01")
