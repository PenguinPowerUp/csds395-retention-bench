"""Lichess: from games to per-player-day activity.

The data hold one row per rated game with its UTC start time and time control,
but no end time before 2017. A game's length is Lichess's own estimate of game
duration, initial + 40 x increment seconds (lichess.org/faq: "the estimated
duration of a 5+3 game is 5 x 60 + 40 x 3 = 420 seconds"). A session is a run of games whose start falls within SESSION_GAP
minutes of the previous game's estimated end. As for WoWAH, session time is cut
at midnight: day d is credited only with the part of a session before the end
of day d.

A day counts as active only if the player starts a rated game on it. A game
that runs past midnight therefore does not make the next day active, unlike a
WoWAH session, which does.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

SESSION_GAP = 30                      # minutes between a game's estimated end and the next start
TIME_CONTROL = re.compile(r"^(\d+)\+(\d+)$")
SPEED = re.compile(r"^Rated (\w+)")

FEATURES = ("sessions", "session_minutes", "games", "wins", "speeds")


def player_games(games: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, game) for real-time games, with estimated end, rating, rating change and win."""
    tc = games["time_control"].str.extract(TIME_CONTROL).astype(float)
    g = games.assign(base=tc[0], inc=tc[1])
    g = g[g["base"].notna() & g["ts"].notna() & (g["white"] != g["black"])]   # drops correspondence and self-play
    g = g.assign(seconds=g["base"] + 40 * g["inc"],
                 speed=g["event"].str.extract(SPEED)[0].str.lower())
    sides = []
    for side, other, win in (("white", "black", "1-0"), ("black", "white", "0-1")):
        sides.append(pd.DataFrame({
            "name": g[side].to_numpy(), "ts": g["ts"].to_numpy(),
            "end": (g["ts"] + pd.to_timedelta(g["seconds"], unit="s")).to_numpy(),
            "elo": g[f"{side}_elo"].to_numpy(), "diff": g[f"{side}_diff"].to_numpy(),
            "win": (g["result"] == win).to_numpy(), "speed": g["speed"].to_numpy(),
        }))
    pg = pd.concat(sides, ignore_index=True)
    pg["player"] = pd.factorize(pg["name"], sort=True)[0]
    return pg.drop(columns="name").sort_values(["player", "ts"], kind="stable").reset_index(drop=True)


def per_player_day(pg: pd.DataFrame) -> pd.DataFrame:
    """One row per (player, day) on which the player started a game."""
    prev_end = pg.groupby("player")["end"].cummax().groupby(pg["player"]).shift()
    new_session = prev_end.isna() | (pg["ts"] > prev_end + pd.Timedelta(minutes=SESSION_GAP))
    pg = pg.assign(session_id=new_session.cumsum(), day=pg["ts"].dt.normalize())
    sess = pg.groupby("session_id").agg(player=("player", "first"), start=("ts", "min"), end=("end", "max"))

    segs = []
    span = int(((sess["end"] - sess["start"].dt.normalize()) // pd.Timedelta(days=1)).max())
    for k in range(span + 1):
        day = sess["start"].dt.normalize() + pd.Timedelta(days=k)
        lo, hi = np.maximum(sess["start"], day), np.minimum(sess["end"], day + pd.Timedelta(days=1))
        keep = lo < hi
        segs.append(pd.DataFrame({"session_id": sess.index[keep], "player": sess["player"][keep].to_numpy(),
                                  "day": day[keep].to_numpy(), "minutes": ((hi - lo)[keep]).dt.total_seconds().div(60).to_numpy(),
                                  "last_ts": hi[keep].to_numpy()}))
    seg = pd.concat(segs, ignore_index=True)
    by_sess = seg.groupby(["player", "day"]).agg(sessions=("session_id", "nunique"), session_minutes=("minutes", "sum"),
                                                 last_ts=("last_ts", "max"))
    starts = sess.assign(day=sess["start"].dt.normalize()).groupby(["player", "day"]).size().rename("sessions_started")
    by_game = pg.groupby(["player", "day"]).agg(games=("ts", "size"), wins=("win", "sum"), speeds=("speed", "nunique"))
    out = by_game.join(by_sess, how="left").join(starts, how="left").fillna({"sessions_started": 0}).reset_index()
    out["sessions_started"] = out["sessions_started"].astype(int)
    out["wins"] = out["wins"].astype(int)
    return out


def first_games(pg: pd.DataFrame) -> pd.DataFrame:
    """Rating, rating change and day of each player's first game."""
    # drop_duplicates, not groupby().first(): first() skips missing values and would mix games
    first = pg.drop_duplicates("player", keep="first").set_index("player")[["ts", "elo", "diff"]]
    first["first_day"] = first["ts"].dt.normalize()
    return first.drop(columns="ts").rename(columns={"elo": "first_elo", "diff": "first_diff"}).reset_index()
