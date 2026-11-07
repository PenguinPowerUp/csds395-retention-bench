"""Day-zero features and their transform.

The feature frame has one row per player and only uses behaviour on the
player's cohort date. The transform is log1p followed by standardization with
the TRAIN mean and standard deviation, which the caller supplies.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Scaler:
    mean: dict[str, float]
    scale: dict[str, float]
    features: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        u = np.log1p(frame[list(self.features)].to_numpy(dtype=float))
        m = np.array([self.mean[f] for f in self.features])
        s = np.array([self.scale[f] for f in self.features])
        return (u - m) / s


def fit_scaler(train: pd.DataFrame, features: tuple[str, ...]) -> Scaler:
    u = np.log1p(train[list(features)].to_numpy(dtype=float))
    mean = u.mean(axis=0)
    scale = u.std(axis=0, ddof=0)
    scale = np.where(scale == 0, 1.0, scale)
    return Scaler(
        mean={f: float(m) for f, m in zip(features, mean)},
        scale={f: float(s) for f, s in zip(features, scale)},
        features=tuple(features),
    )
