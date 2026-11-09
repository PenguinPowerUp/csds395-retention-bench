"""Lichess: independent recount of the population and label, by a different route than the pipeline.

Reads the parsed game headers, not the canonical tables, builds per-account sets
of active days with plain Python, applies the written rules, and compares the
counts with results.json.

Usage: python -m retention_bench.datasets.lichess.crosscheck DATA_DIR RESULTS_JSON
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .prepare import BURN_IN_END, LAST_COHORT, MIN_FIRST_SWING, START_RATING

_, data_arg, results_arg = sys.argv
data = Path(data_arg)
res = json.loads(Path(results_arg).read_text())

cols = ["ts", "white", "black", "white_elo", "black_elo", "white_diff", "black_diff", "time_control"]
games = pd.concat((pd.read_parquet(p, columns=cols) for p in sorted((data / "games").glob("*.parquet"))), ignore_index=True)
real_time = games["time_control"].map(lambda t: bool(re.fullmatch(r"\d+\+\d+", t or "")))
games = games[real_time & games["ts"].notna() & (games["white"] != games["black"])].sort_values("ts", kind="stable")

days_of: dict[str, set] = defaultdict(set)
first: dict[str, tuple] = {}
for ts, w, b, we, be, wd, bd in zip(games["ts"], games["white"], games["black"], games["white_elo"],
                                    games["black_elo"], games["white_diff"], games["black_diff"]):
    day = ts.normalize()
    for name, elo, diff in ((w, we, wd), (b, be, bd)):
        days_of[name].add(day)
        if name not in first:
            first[name] = (day, elo, diff)

all_days = set().union(*days_of.values())
last_day = max(all_days)
empty = {d for d in pd.date_range(min(all_days), last_day) if d not in all_days}

eligible = returning = excluded = 0
for name, (day, elo, diff) in first.items():
    if not (BURN_IN_END <= day <= LAST_COHORT and elo == START_RATING and abs(diff) >= MIN_FIRST_SWING):
        continue
    nxt = day + pd.Timedelta(days=1)
    if nxt > last_day or nxt in empty:
        excluded += 1
        continue
    eligible += 1
    returning += nxt in days_of[name]

pop = res["population"]
print(f"empty days        crosscheck={len(empty)}  pipeline={len(pop['counts']['empty_days'])}")
print(f"eligible          crosscheck={eligible}  pipeline={pop['eligible']}")
print(f"returning         crosscheck={returning}  pipeline={pop['returning']}")
print(f"next day not obs. crosscheck={excluded}  pipeline={pop['counts']['excluded_next_day_not_observed']}")
ok = (eligible == pop["eligible"] and returning == pop["returning"] and excluded == pop["counts"]["excluded_next_day_not_observed"]
      and len(empty) == len(pop["counts"]["empty_days"]))
print("MATCH" if ok else "MISMATCH")
sys.exit(0 if ok else 1)
