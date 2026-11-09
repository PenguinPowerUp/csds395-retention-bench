"""WoWAH: snapshots.parquet -> canonical tables (activity, players, coverage, dataset.json)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ... import canonical
from . import sessions

TRACE_START = pd.Timestamp("2006-01-01")
SAMPLES_PER_DAY = 144

META = {
    "name": "wowah",
    "title": "retention-bench: day-one return on WoWAH (Lee et al., MMSys 2011), new avatars, temporal split",
    "dataset": {
        "name": "World of Warcraft Avatar History (WoWAH)",
        "citation": "Y.-T. Lee, K.-T. Chen, Y.-M. Cheng, C.-L. Lei. World of Warcraft Avatar History Dataset. Proc. ACM MMSys 2011.",
        "source": "https://web.cs.wpi.edu/~claypool/mmsys-dataset/2011/wow/",
        "unit": "avatar (character), one realm, Horde; a new avatar is not necessarily a new player",
        "clock": "dataset-native query time; days are calendar days in that clock",
    },
    "new_player_rule": "level at first sighting <= 5; strict: level 1",
    "features": list(sessions.FEATURES),
    "single_feature": "session_minutes",
    "midnight_window_minutes": sessions.SAMPLE_MINUTES,
    "sensitivity": [
        {"key": "first_level_1_only", "strict_new": True},
        {"key": "drop_half_empty_next_day", "min_next_day_coverage": 0.5},
        {"key": "strict_return_new_session_next_day", "strict_return": True},
        {"key": "drop_avatars_online_at_midnight", "drop_online_at_midnight": True},
    ],
    "drop_feature_runs": [{"key": "without_snapshots_feature", "feature": "snapshots"}],
}


def load_snapshots(path: Path) -> pd.DataFrame:
    snap = pd.read_parquet(path, columns=["ts", "avatar", "level", "cls", "zone", "day_dir", "sample"])
    for c in ("cls", "zone", "day_dir", "sample"):
        snap[c] = snap[c].astype("category")
    snap = snap[snap["ts"] >= TRACE_START]  # the first sampling round reaches a few seconds into the previous day
    before = len(snap)
    snap = snap.drop_duplicates(subset=["ts", "avatar"])
    print(f"snapshots: {before:,} rows, {len(snap):,} after dropping duplicate (ts, avatar)")
    return snap


def coverage_by_day(snap: pd.DataFrame) -> pd.DataFrame:
    """Share of the 144 sampling rounds that exist, per day directory."""
    rounds = snap[["day_dir", "sample"]].drop_duplicates()
    n = rounds.groupby("day_dir", observed=True).size()
    return pd.DataFrame({"day": pd.to_datetime(n.index.astype(str)), "observed_fraction": n.to_numpy() / SAMPLES_PER_DAY})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args(argv)
    snap = load_snapshots(a.data / "snapshots.parquet")
    pad = sessions.per_avatar_day(snap)
    first = sessions.first_sightings(snap)
    coverage = coverage_by_day(snap)
    del snap

    activity = pad.merge(first[["avatar", "first_level"]], on="avatar")
    activity["levels_gained"] = (activity["max_level"] - activity["first_level"]).clip(lower=0)
    activity = activity.rename(columns={"avatar": "player"})[
        ["player", "day", "sessions", "session_minutes", "sessions_started", "last_ts", "snapshots", "levels_gained", "zones"]]
    players = first.rename(columns={"avatar": "player"})
    players["is_new"] = players["first_level"] <= sessions.MAX_FIRST_LEVEL
    players["is_new_strict"] = players["first_level"] <= 1
    canonical.write(a.data, activity, players[["player", "first_day", "is_new", "is_new_strict", "first_level"]], META, coverage)


if __name__ == "__main__":
    main()
