"""From 10-minute snapshots to per-avatar-day activity and day-zero features.

A session is a run of consecutive snapshots of one avatar with gaps of at most
SESSION_GAP minutes (one missing sample is tolerated). Session minutes are
(last - first) + SAMPLE_MINUTES, split at midnight so that a day's minutes end
at that day's end. A day is the calendar day of the snapshot in the dataset's
own clock.

A *new* avatar is one whose first snapshot shows level <= MAX_FIRST_LEVEL. The
first days of the trace are a backlog of existing avatars; the level filter is
what separates a new character from a veteran who happened to be offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SAMPLE_MINUTES = 10
SESSION_GAP = 20          # minutes; > this starts a new session
MAX_FIRST_LEVEL = 5       # level at first sighting that still counts as new

FEATURES = ("sessions", "session_minutes", "snapshots", "levels_gained", "zones")


def per_avatar_day(snap: pd.DataFrame) -> pd.DataFrame:
    """One row per (avatar, day): sessions, minutes, snapshots, level range, distinct zones, sessions started.

    Session time is split at midnight: the part of a session that falls on day d
    is credited to day d and the rest to d + 1. Day-d features therefore contain
    nothing observed after the end of day d. A session that crosses midnight
    counts as one session on each of the two days.
    """
    s = snap.sort_values(["avatar", "ts"]).reset_index(drop=True)
    s["day"] = s["ts"].dt.normalize()
    gap = s.groupby("avatar")["ts"].diff().dt.total_seconds().div(60)
    new_session = gap.isna() | (gap > SESSION_GAP)
    s["session_id"] = new_session.cumsum()
    seg = s.groupby(["session_id", "day"], sort=False).agg(avatar=("avatar", "first"), start=("ts", "min"), end=("ts", "max")).reset_index()
    day_end = seg["day"] + pd.Timedelta(days=1)
    seg_end = np.minimum(seg["end"] + pd.Timedelta(minutes=SAMPLE_MINUTES), day_end)
    seg["minutes"] = (seg_end - seg["start"]).dt.total_seconds().div(60)
    by_day_sess = seg.groupby(["avatar", "day"]).agg(sessions=("session_id", "nunique"), session_minutes=("minutes", "sum"))
    starts = seg.groupby("session_id", sort=False).agg(avatar=("avatar", "first"), day=("day", "min"))
    by_day_start = starts.groupby(["avatar", "day"]).size().rename("sessions_started")
    by_day_snap = s.groupby(["avatar", "day"]).agg(
        snapshots=("ts", "size"), max_level=("level", "max"), min_level=("level", "min"), zones=("zone", "nunique"),
        last_ts=("ts", "max"),
    )
    out = (by_day_snap.join(by_day_sess, how="left").join(by_day_start, how="left")
           .fillna({"sessions": 0, "session_minutes": 0.0, "sessions_started": 0}).reset_index())
    out["sessions"] = out["sessions"].astype(int)
    out["sessions_started"] = out["sessions_started"].astype(int)
    return out


def first_sightings(snap: pd.DataFrame) -> pd.DataFrame:
    """Level, class and day at each avatar's first snapshot."""
    s = snap.sort_values(["avatar", "ts"])
    first = s.groupby("avatar").first()[["ts", "level", "cls"]].rename(columns={"level": "first_level", "cls": "first_class"})
    first["first_day"] = first["ts"].dt.normalize()
    return first.drop(columns="ts").reset_index()


def day_zero_features(pad: pd.DataFrame, labels: pd.DataFrame, first: pd.DataFrame) -> pd.DataFrame:
    """Join label rows to their cohort-day activity row. Features use the cohort day only."""
    f = labels.merge(pad, left_on=["player", "cohort_date"], right_on=["avatar", "day"], how="left")
    f = f.merge(first[["avatar", "first_level"]], on="avatar", how="left")
    f["levels_gained"] = (f["max_level"] - f["first_level"]).clip(lower=0)
    for c in FEATURES:
        f[c] = f[c].fillna(0)
    return f[["player", "cohort_date", "returned", *FEATURES]]


def activity_days(pad: pd.DataFrame) -> pd.DataFrame:
    return pad[["avatar", "day"]].rename(columns={"avatar": "player"})
