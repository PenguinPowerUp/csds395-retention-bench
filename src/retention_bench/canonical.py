"""The canonical tables every dataset adapter writes, and the shared loader.

An adapter turns its raw data into four files under data/<dataset>/:

  activity.parquet  one row per (player, day) with activity: player, day,
                    sessions, session_minutes, sessions_started, last_ts, and the
                    dataset's feature columns. Session minutes are cut at the end
                    of the day; last_ts is the last observed moment of that day.
  players.parquet   one row per player: player, first_day, is_new, is_new_strict.
  coverage.parquet  optional: day, observed_fraction (share of the day observed).
  dataset.json      metadata: citation, unit, feature list, baseline feature,
                    and which sensitivity runs apply.

The pipeline in run.py reads only these files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ACTIVITY_COLUMNS = ("player", "day", "sessions", "session_minutes", "sessions_started", "last_ts")
PLAYER_COLUMNS = ("player", "first_day", "is_new", "is_new_strict")


@dataclass(frozen=True)
class Dataset:
    meta: dict
    activity: pd.DataFrame
    players: pd.DataFrame
    coverage: pd.Series | None   # observed fraction indexed by day, or None


def write(out: Path, activity: pd.DataFrame, players: pd.DataFrame, meta: dict, coverage: pd.DataFrame | None = None) -> None:
    missing = [c for c in (*ACTIVITY_COLUMNS, *meta["features"]) if c not in activity.columns]
    missing += [c for c in PLAYER_COLUMNS if c not in players.columns]
    if missing:
        raise ValueError(f"canonical tables are missing columns {missing}")
    out.mkdir(parents=True, exist_ok=True)
    activity.to_parquet(out / "activity.parquet", index=False)
    players.to_parquet(out / "players.parquet", index=False)
    if coverage is not None:
        coverage.to_parquet(out / "coverage.parquet", index=False)
    (out / "dataset.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote canonical tables to {out}: {len(activity):,} player-days, {len(players):,} players")


def load(data: Path) -> Dataset:
    meta = json.loads((data / "dataset.json").read_text())
    activity = pd.read_parquet(data / "activity.parquet")
    players = pd.read_parquet(data / "players.parquet")
    cov_path = data / "coverage.parquet"
    coverage = None
    if cov_path.exists():
        c = pd.read_parquet(cov_path)
        coverage = c.set_index("day")["observed_fraction"]
    return Dataset(meta=meta, activity=activity, players=players, coverage=coverage)
