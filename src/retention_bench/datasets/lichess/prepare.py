"""Lichess: parsed games -> canonical tables (activity, players, dataset.json)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ... import canonical
from . import sessions

START_RATING = 1500             # every new Lichess rating starts here (lichess.org/faq)
MIN_FIRST_SWING = 50            # a new, high-deviation rating moves this much or more on its first game
BURN_IN_END = pd.Timestamp("2013-04-01")
STRICT_BURN_IN_END = pd.Timestamp("2013-07-01")
LAST_COHORT = pd.Timestamp("2014-05-31")    # 2014-06 is the next-day buffer

META = {
    "name": "lichess",
    "title": "retention-bench: day-one return on the Lichess open database (rated games, 2013-01 to 2014-06), new accounts, temporal split",
    "dataset": {
        "name": "Lichess open database, standard rated games",
        "citation": "Lichess open database, https://database.lichess.org/, CC0, files 2013-01 to 2014-06.",
        "source": "https://database.lichess.org/standard/",
        "unit": "account (username); activity is rated real-time games only",
        "clock": "UTC; days are UTC calendar days",
    },
    "new_player_rule": ("first rated game on or after 2013-04-01 and by 2014-05-31, rated exactly 1500 with a rating change "
                        "of at least 50 points; strict: first game on or after 2013-07-01"),
    "features": list(sessions.FEATURES),
    "single_feature": "session_minutes",
    "midnight_window_minutes": 10,
    "sensitivity": [
        {"key": "six_month_burn_in", "strict_new": True},
        {"key": "strict_return_new_session_next_day", "strict_return": True},
        {"key": "drop_players_online_at_midnight", "drop_online_at_midnight": True},
    ],
    "drop_feature_runs": [],
}


def load_games(data: Path) -> pd.DataFrame:
    parts = sorted((data / "games").glob("*.parquet"))
    return pd.concat((pd.read_parquet(p) for p in parts), ignore_index=True)


def new_player_flags(first: pd.DataFrame) -> pd.DataFrame:
    in_window = (first["first_day"] >= BURN_IN_END) & (first["first_day"] <= LAST_COHORT)
    fresh = (first["first_elo"] == START_RATING) & (first["first_diff"].abs() >= MIN_FIRST_SWING)
    return first.assign(is_new=in_window & fresh,
                        is_new_strict=in_window & fresh & (first["first_day"] >= STRICT_BURN_IN_END))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args(argv)
    games = load_games(a.data)
    print(f"games: {len(games):,}")
    pg = sessions.player_games(games)
    del games
    print(f"player-games after dropping correspondence and self-play: {len(pg):,}")
    activity = sessions.per_player_day(pg)
    players = new_player_flags(sessions.first_games(pg))
    canonical.write(a.data, activity[["player", "day", "sessions", "session_minutes", "sessions_started", "last_ts", *sessions.FEATURES[2:]]],
                    players[["player", "first_day", "is_new", "is_new_strict", "first_elo", "first_diff"]], META)


if __name__ == "__main__":
    main()
