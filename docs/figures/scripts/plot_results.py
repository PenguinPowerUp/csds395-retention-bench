"""Draw the reliability diagram and the decile lift chart from results/wowah/results.json.

Run from anywhere after the pipeline has written results.json:
    python docs/figures/scripts/plot_results.py
Writes reliability.png and decile_lift.png into docs/figures/. Reads only the published
aggregates, so the figures obey the same suppression as the tables.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def reliability(res: dict, out: Path) -> None:
    rows = res["calibration"]["reliability_test"]
    x = [r["mean_predicted"] for r in rows]
    y = [r["observed_returning"] for r in rows]
    n = [r["players"] for r in rows]
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], ls="--", c="grey", lw=1, label="perfect calibration")
    ax.plot(x, y, marker="o", c="#1f5fbf", label="Platt-calibrated logistic")
    for xi, yi, ni in zip(x, y, n):
        ax.annotate(f"n={ni}", (xi, yi), textcoords="offset points", xytext=(4, -10), fontsize=7, color="grey")
    lim = max(max(x), max(y)) * 1.1
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("mean predicted P(return)"); ax.set_ylabel("observed return rate")
    ax.set_title(f"Reliability, test split (slope {res['calibration']['slope']}, intercept {res['calibration']['intercept']})", fontsize=9)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(out / "reliability.png", dpi=150); plt.close(fig)


def lift(res: dict, out: Path) -> None:
    rows = res["lift_test"]["deciles"]
    labels = [r["deciles"] for r in rows]
    lifts = [r["lift"] for r in rows]
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.bar(range(len(rows)), lifts, color="#1f5fbf")
    ax.axhline(1.0, c="grey", ls="--", lw=1)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels(labels)
    ax.set_xlabel("decile of calibrated P(return), 1 = highest"); ax.set_ylabel("lift over test return rate")
    floor = res["models"][0]["pr_auc_floor"]
    ax.set_title(f"Decile lift, test split (test return rate {floor:.3f})", fontsize=9)
    fig.tight_layout(); fig.savefig(out / "decile_lift.png", dpi=150); plt.close(fig)


FIGURES = Path(__file__).resolve().parents[1]
RESULTS = FIGURES.parents[1] / "results" / "wowah" / "results.json"


def main() -> None:
    res = json.loads(RESULTS.read_text())
    reliability(res, FIGURES)
    lift(res, FIGURES)
    print("wrote", FIGURES / "reliability.png", FIGURES / "decile_lift.png")


if __name__ == "__main__":
    main()
