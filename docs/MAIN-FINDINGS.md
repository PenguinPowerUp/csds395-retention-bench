# Main Findings

 The same pipeline runs on two public game datasets, World of Warcraft avatars (WoWAH) and Lichess chess accounts. Full results are in [RESULTS-WOWAH.md](RESULTS-WOWAH.md) and [RESULTS-LICHESS.md](RESULTS-LICHESS.md).

In one sentence: first-day playtime reliably predicts whether a new player returns the next day, but the predicted probability can be trusted only while the return rate stays close to the rate the model was calibrated on.

## 1. First-day behaviour predicts next-day return

On test cohorts that start after all data used for training and calibration, the L2 logistic model clearly beats the no-skill floor on both datasets.

|                      |  WoWAH | Lichess |
| -------------------- | -----: | ------: |
| New players          | 79,497 | 118,266 |
| Next-day return rate |  26.9% |   29.4% |
| PR-AUC / floor       |   2.69 |    2.01 |
| ROC-AUC              |  0.803 |   0.755 |

## 2. Playtime carries most of the signal

Session minutes alone reach 2.54 times the PR-AUC floor on WoWAH and 1.89 times on Lichess; the other four features add little. Kim et al. (2017) and Drachen et al. (2016) report the same in other games ([LITERATURE.md](LITERATURE.md)).

## 3. Calibration transfers only when the return rate holds

|         | Validation return rate | Test return rate | Platt scaling on test                   |
| ------- | ---------------------: | ---------------: | --------------------------------------- |
| WoWAH   |                  30.9% |            20.7% | Slightly worse (Brier 0.1245 → 0.1252) |
| Lichess |                  26.4% |            27.0% | Better (Brier 0.1644 → 0.1638)         |

## 4. The label definition shapes the absolute numbers

On WoWAH, avatars still online in the last 10 minutes of their first day return at 89.9%, because a session running past midnight makes the next day active by definition. This inflates WoWAH's absolute scores. Lichess counts a day as active only if a game starts on it, so a game running past midnight does not by itself count as a return. Dropping these players lowers PR-AUC on both datasets but does not lower the multiple of the floor (2.84 on WoWAH, 2.05 on Lichess).

## Context

- **The task is new.** No published study predicts next-day return of new WoWAH avatars; Hossain et al. (2023) exclude every player younger than 30 days.
- **No sign of temporal leakage.** On both datasets a random split scores lower than the temporal split relative to its floor (2.20 against 2.69 on WoWAH, 1.86 against 2.01 on Lichess).
- **Limits.** The units differ (avatar, account), both datasets are from 2006 to 2014, and the results show prediction, not that an intervention would keep players.
