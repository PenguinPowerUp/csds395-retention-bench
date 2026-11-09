"""Temporal split by whole cohort date.

Dates are taken in order. A date goes to train until the cumulative row count
reaches FRACTIONS[0] of all rows, then to validation until FRACTIONS[1], then
to test. Every player of one cohort date lands in the same part, so every test
player is later in time than every train player. Each part gets at least one
date. Never random.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import temporal_leak as tl

FRACTIONS = (0.6, 0.8)
PARTS = ("train", "validation", "test")


@dataclass(frozen=True)
class Split:
    part: pd.Series  # aligned with the input frame; values in PARTS

    def mask(self, name: str) -> np.ndarray:
        return (self.part == name).to_numpy()

    def ranges(self, cohort_date: pd.Series) -> dict:
        out = {}
        for name in PARTS:
            dates = cohort_date[self.part == name]
            out[name] = {
                "first_cohort_date": str(dates.min().date()),
                "last_cohort_date": str(dates.max().date()),
                "cohort_dates": int(dates.nunique()),
                "rows": int(len(dates)),
            }
        return out


def temporal_split(cohort_date: pd.Series, fractions: tuple[float, float] = FRACTIONS) -> Split:
    counts = cohort_date.value_counts().sort_index()
    n = int(counts.sum())
    cum = counts.cumsum()
    part_of_date = {}
    for i, (d, c) in enumerate(cum.items()):
        remaining = len(cum) - i - 1
        if c <= fractions[0] * n and remaining >= 2:
            part_of_date[d] = "train"
        elif c <= fractions[1] * n and remaining >= 1:
            part_of_date[d] = "validation"
        else:
            part_of_date[d] = "test"
    # guarantee every part has at least one date
    assigned = set(part_of_date.values())
    if "validation" not in assigned or "test" not in assigned:
        dates = list(cum.index)
        part_of_date = {d: "train" for d in dates[:-2]}
        part_of_date[dates[-2]] = "validation"
        part_of_date[dates[-1]] = "test"
    part = cohort_date.map(part_of_date)
    return Split(part=part)


def random_split(n: int, fractions: tuple[float, float], seed: int) -> Split:
    """Only for the leakage sanity check: same fractions, rows shuffled."""
    return Split(part=pd.Series(tl.random_split(n, fractions, seed)))
