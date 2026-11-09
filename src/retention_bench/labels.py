"""Cohort date and the day-one return label.

Input is one row per (player, day) on which the player was active. Everything
here works on calendar dates in the dataset's own clock; the caller decides
what a "day" is before calling.

Rules
-----
cohort_date(i)  = the first day on which player i is active.
label(i)        = 1 if i is active on cohort_date(i) + 1, else 0.
Excluded        : cohorts whose next day lies past the last day of the data
                  (right-censored), and cohorts whose next day has zero
                  activity from anyone (a collection outage, not a behaviour).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import temporal_leak as tl

HORIZON_DAYS = 1


@dataclass(frozen=True)
class LabelResult:
    frame: pd.DataFrame          # kept rows: player, cohort_date, returned (0/1)
    all_rows: pd.DataFrame       # every player: player, cohort_date, returned, exclusion ("", "censored", "outage")
    last_day: pd.Timestamp
    empty_days: list[pd.Timestamp]
    excluded_censored: int       # players dropped by right-censoring
    excluded_outage: int         # players dropped because day d+1 was empty


def build_labels(activity: pd.DataFrame, player: str = "player", day: str = "day") -> LabelResult:
    """activity: one row per (player, day) with activity. Days are datetime64 at midnight."""
    act = activity[[player, day]].drop_duplicates()
    act = act.assign(**{day: pd.to_datetime(act[day]).dt.normalize()})
    last_day = act[day].max()
    empties = tl.empty_periods(act[day], freq="D")

    cohort = act.groupby(player, as_index=False)[day].min().rename(columns={day: "cohort_date"})
    next_day = cohort["cohort_date"] + pd.Timedelta(days=HORIZON_DAYS)

    why = tl.observable(cohort["cohort_date"], pd.Timedelta(days=HORIZON_DAYS), last_day, empties)
    censored = (why == "censored").to_numpy()
    outage = (why == "empty").to_numpy()
    keep = ~(censored | outage)

    # returned: active on exactly cohort_date + 1
    key = act.set_index([player, day]).index
    returned = pd.MultiIndex.from_arrays([cohort[player], next_day]).isin(key).astype(int)

    reason = why.replace({"empty": "outage"}).to_numpy()
    all_rows = cohort.assign(returned=returned, exclusion=reason)
    frame = all_rows[keep].drop(columns="exclusion").reset_index(drop=True)
    return LabelResult(
        frame=frame,
        all_rows=all_rows,
        last_day=last_day,
        empty_days=empties,
        excluded_censored=int(censored.sum()),
        excluded_outage=int(outage.sum()),
    )
