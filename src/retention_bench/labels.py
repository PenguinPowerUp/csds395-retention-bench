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

HORIZON_DAYS = 1


@dataclass(frozen=True)
class LabelResult:
    frame: pd.DataFrame          # kept rows: player, cohort_date, returned (0/1)
    all_rows: pd.DataFrame       # every player: player, cohort_date, returned, exclusion ("", "censored", "outage")
    last_day: pd.Timestamp
    empty_days: list[pd.Timestamp]
    excluded_censored: int       # players dropped by right-censoring
    excluded_outage: int         # players dropped because day d+1 was empty


def empty_days_between(active_days: pd.Series, first: pd.Timestamp, last: pd.Timestamp) -> list[pd.Timestamp]:
    """Calendar days in [first, last] with no activity from any player."""
    seen = set(pd.to_datetime(active_days.unique()).normalize())
    return [d for d in pd.date_range(first, last, freq="D") if d not in seen]


def build_labels(activity: pd.DataFrame, player: str = "player", day: str = "day") -> LabelResult:
    """activity: one row per (player, day) with activity. Days are datetime64 at midnight."""
    act = activity[[player, day]].drop_duplicates()
    act = act.assign(**{day: pd.to_datetime(act[day]).dt.normalize()})
    first_day, last_day = act[day].min(), act[day].max()
    empties = empty_days_between(act[day], first_day, last_day)
    empty_set = set(empties)

    cohort = act.groupby(player, as_index=False)[day].min().rename(columns={day: "cohort_date"})
    next_day = cohort["cohort_date"] + pd.Timedelta(days=HORIZON_DAYS)

    censored = next_day > last_day
    outage = next_day.isin(empty_set) & ~censored
    keep = ~(censored | outage)

    # returned: active on exactly cohort_date + 1
    key = act.set_index([player, day]).index
    returned = pd.MultiIndex.from_arrays([cohort[player], next_day]).isin(key).astype(int)

    reason = pd.Series("", index=cohort.index).mask(censored, "censored").mask(outage, "outage")
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
