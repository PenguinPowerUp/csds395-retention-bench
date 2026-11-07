"""Independent recount of the population and label, by a different route than the pipeline.

Reads only (ts, avatar, level), builds per-avatar sets of active days with plain
Python, applies the written rules, and prints counts to compare with results.json.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

data = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
res = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else "results/wowah/results.json").read_text())
max_first_level = res["label"]["max_first_level"]

snap = pd.read_parquet(data / "snapshots.parquet", columns=["ts", "avatar", "level"])
snap = snap[snap["ts"] >= "2006-01-01"]
snap["day"] = snap["ts"].values.astype("datetime64[D]")
active_days = set(map(pd.Timestamp, np.unique(snap["day"])))
first_day, last_day = min(active_days), max(active_days)
empty = [d for d in pd.date_range(first_day, last_day) if d not in active_days]

snap = snap.sort_values(["avatar", "ts"])
first = snap.groupby("avatar").first()
days_of = defaultdict(set)
for a, d in zip(snap["avatar"].to_numpy(), snap["day"].to_numpy()):
    days_of[a].add(pd.Timestamp(d))

eligible = returning = censored = outage = 0
empty_set = set(empty)
for a, row in first.iterrows():
    if row["level"] > max_first_level:
        continue
    d0 = min(days_of[a]); d1 = d0 + pd.Timedelta(days=1)
    if d1 > last_day:
        censored += 1; continue
    if d1 in empty_set:
        outage += 1; continue
    eligible += 1
    returning += int(d1 in days_of[a])

pop = res["population"]
print(f"empty days        crosscheck={len(empty)}  pipeline={len(pop['counts']['empty_days'])}")
print(f"eligible          crosscheck={eligible}  pipeline={pop['eligible']}")
print(f"returning         crosscheck={returning}  pipeline={pop['returning']}")
print(f"returning rate    crosscheck={returning/eligible:.4f}  pipeline={pop['returning_rate']}")
print(f"right-censored    crosscheck={censored}  pipeline={pop['counts']['excluded_right_censored']}")
print(f"outage-excluded   crosscheck={outage}  pipeline={pop['counts']['excluded_outage_day']}")
ok = (eligible == pop["eligible"] and returning == pop["returning"] and censored == pop["counts"]["excluded_right_censored"] and outage == pop["counts"]["excluded_outage_day"])
print("MATCH" if ok else "MISMATCH")
sys.exit(0 if ok else 1)
