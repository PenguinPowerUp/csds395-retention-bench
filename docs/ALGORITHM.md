# D1 Return Prediction: Algorithm

The method retention-bench runs, end to end. It is written for WoWAH; the same method runs unchanged on the Lichess open database, whose data definitions are in the last section. Written from the public description of the method and the standard literature; no company code, data or figure. Numbers in examples are the fitted values in `results/wowah/model.json`.

# Data

WoWAH is a table of **snapshots**: every 10 minutes from 2006-01-01 to 2009-01-10, one row per avatar online on one realm, with time, avatar id, level and zone. 36.5 million rows. Nothing else exists: no login events, no accounts.

| Term            | Meaning                                                                                                                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Avatar          | One character, an integer id. The unit of prediction. One person may own several                                                                                                             |
| Zone            | A named area of the game map, e.g. Durotar or Orgrimmar; 229 in total, and every snapshot records the avatar's current zone                                                                  |
| Level           | The avatar's character level, 1 to 80, recorded in every snapshot                                                                                                                            |
| Day             | Calendar day in the dataset's own clock (the collector ran in Taiwan)                                                                                                                        |
| Active on a day | Appears in at least one snapshot that day                                                                                                                                                    |
| Session         | Consecutive snapshots of one avatar with gaps ≤ 20 min (one missed sample tolerated); a longer gap starts a new session                                                                      |
| Session minutes | (last snapshot − first snapshot) + 10, per session; minutes after midnight are not credited to the day before                                                                                |
| New avatar      | Level ≤ 5 in its first snapshot. The trace opens with every existing character present; this separates a fresh character from a veteran logging in. Death Knights (start at 55) are excluded |
| Cohort          | All new avatars whose first active day is the same day $d$, the cohort date. Exclusions, labels and the split all act on whole cohorts                                                       |

# Notation

| Symbol                           | What it is                                                                        | How it's built                                                                |
| -------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| $d_i$                          | Cohort date of avatar $i$                                                       | First day on which $i$ is active                                            |
| $y_i \in \{0,1\}$              | Label, "returned"                                                                 | 1 if $i$ is active on $d_i + 1$, else 0                                   |
| raw                              | One feature's original count for one avatar on day $d_i$                        | Table below                                                                   |
| $u$                            | $\log(1 + \text{raw})$                                                          | Compresses the tail: 0→0, 10→2.4, 60→4.1, 600→6.4                         |
| mean_train, std_train            | Mean and standard deviation of $u$, per feature, over **train rows only** | Five pairs, computed once, stored in `model.json`                           |
| $x_i \in \mathbb{R}^5$         | Model input                                                                       | $x = (u - \text{mean}_\text{train}) / \text{std}_\text{train}$, per feature |
| $w, b$                         | Five weights and an intercept                                                     | Fit on train                                                                  |
| $z_i = w \cdot x_i + b$        | Logit                                                                             | Linear score                                                                  |
| $p_i = \sigma(z_i)$            | Predicted P(return)                                                               | $\sigma(z) = 1/(1+e^{-z})$                                                  |
| $\hat p_i = \sigma(a z_i + c)$ | Calibrated P(return)                                                              | $a, c$ fit on validation (Platt)                                            |
| $1 - \hat p_i$                 | Churn probability                                                                 | What an operator would see                                                    |

Five features, all from snapshots on $d_i$ only:

| Feature             | raw =                                                  |
| ------------------- | ------------------------------------------------------ |
| `sessions`        | Number of sessions on $d_i$                          |
| `session_minutes` | Sum of session minutes on $d_i$                      |
| `snapshots`       | Number of snapshots on $d_i$                         |
| `levels_gained`   | Highest level on $d_i$ minus level at first sighting |
| `zones`           | Distinct zones on $d_i$                              |

Positive class is **return** ($y = 1$): it is the minority (27%) and PR-AUC needs the minority class in that role.

# Settings

- **Task.** One avatar, scored once at the end of its first day $d_i$. Label $y_i = 1$ if active on $d_i + 1$.
- **Exclusions.** Cohorts whose $d + 1$ is past the last data day (right-censored) or has zero snapshots from anyone (outage).
- **Split.** Temporal by cohort date: train to 60% of rows, validation to 80%, test the rest. Never random.
- **Features.** The five counts above, log1p, standardized with train statistics.
- **Model.** L2 logistic regression, $C = 1.0$. No class weights, no resampling.
- **Calibration and threshold.** Platt scaling and the max-F1 threshold, both fit on validation.
- **Reporting.** Test only. Every published cell has at least 10 returned and 10 churned avatars.

# Pipeline

```
36.5M snapshots
  -> 1. cohort + label        (per avatar: d_i, y_i; drop excluded cohorts)
  -> 2. temporal split        (train / validation / test by cohort date)
  -> 3. features              (five day-d counts; log1p; standardize with train stats)
  -> 4. fit four models       (majority, single feature, L2 logistic, Platt)
  -> 5. choose threshold      (on validation)
  -> 6. evaluate              (on test; suppress cells < 10)
  -> results.json + model.json
```

# 1. Cohort and label

```
for each avatar i:
    d_i = first day with a snapshot of i
    y_i = 1 if i has a snapshot on d_i + 1 else 0

last_day   = last day with any snapshot
empty_days = days inside the range with no snapshot from anyone   # 24 on WoWAH

drop i if d_i + 1 > last_day          # right-censored: outcome unobserved
drop i if d_i + 1 in empty_days       # collector was down, says nothing about i
keep i only if new avatar             # level <= 5 at first sighting
```

A session running from 23:50 to 00:20 makes the avatar active on both days, so it counts as a return: the rule is "any activity on $d_i + 1$". On WoWAH: 79,659 new avatars, 162 dropped, 79,497 kept, 21,399 returned (26.9%).

# 2. Temporal split

```
dates = sorted distinct d_i;  n = kept avatars;  cum = 0
for date in dates:
    cum += avatars with d_i == date
    part[date] = train if cum <= 0.6n else validation if cum <= 0.8n else test
```

Whole cohorts move together, so every test avatar is later in time than every train avatar. Random assignment would put avatars from the same day, same patch and same outage on both sides, and the model would learn day-specific facts (temporal leakage).

- train: fit $w, b$
- validation: every choice, i.e. Platt's $a, c$ and the threshold
- test: the reported metrics, computed once

WoWAH: train 2006-01-01 to 2007-08-21 (47,655), validation to 2008-06-02 (15,940), test to 2009-01-09 (15,902).

# 3. Features

```
u = log1p(raw)                       # per avatar, per feature
x = (u - mean_train) / std_train     # mean_train, std_train: over train rows, per feature
```

Example, `session_minutes`, mean_train 3.51, std_train 1.14. An avatar with 50 minutes: $u = \log 51 = 3.93$, $x = (3.93 - 3.51)/1.14 = +0.37$, i.e. 0.37 standard deviations above the typical new avatar. With 300 minutes: $u = 5.71$, $x = +1.93$.

Why log1p: raw counts are heavy-tailed (most play 20 minutes, a few play 8 hours); without it the few dominate the fit. Why standardize: it puts the five features on one scale, so the weights are comparable and the L2 penalty treats them equally. Why train rows only: the two numbers are learned from data, so they are part of the model; computing them on all rows would let test avatars shape the ruler every row is measured with.

# 4. Models and training

| Model            | Prediction                                                                                                       | Learned parameters             | Learned from                            | Purpose                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------------ | --------------------------------------- | -------------------------------------- |
| Majority class   | $p_i = r$                                                                                                      | $r$: train return rate       | Train labels, by averaging $y$        | Floor: no use of features              |
| Single feature   | $p_i = \sigma(w x_i^{\text{min}} + b)$, where $x_i^{\text{min}}$ is the `session_minutes` entry of $x_i$ | $w, b$                       | Train rows, by minimizing $J$         | Tests how far session minutes alone go |
| L2 logistic      | $p_i = \sigma(z_i)$, where $z_i = w \cdot x_i + b$                                                           | Five weights $w$, plus $b$ | Train rows, by minimizing $J$         | Main model                             |
| Platt-calibrated | $\hat p_i = \sigma(a z_i + c)$                                                                                 | $a, c$                       | Validation rows, by minimizing log loss | Corrects the probability scale         |

$z_i$ is the logit of the L2 model. $J$ is defined below.

## The loss

For one avatar with label $y$ and prediction $p$:

$$
\ell(y, p) = -\,y \log p \;-\; (1 - y) \log(1 - p)
$$

| $y$ | Active term    | $p$ |  Loss |
| ----- | -------------- | ----: | ----: |
| 1     | $-\log p$    |   0.9 | 0.105 |
| 1     | $-\log p$    |   0.2 | 1.609 |
| 0     | $-\log(1-p)$ |   0.2 | 0.223 |
| 0     | $-\log(1-p)$ |   0.9 | 2.303 |

Confident and right costs almost nothing; confident and wrong costs a lot. Over the $n$ train rows, plus the L2 penalty:

$$
J(w, b) = \sum_{i=1}^{n} \ell\big(y_i, \sigma(w \cdot x_i + b)\big) + \frac{1}{2C}\lVert w \rVert_2^2
$$

$\lVert w \rVert_2^2 = w_1^2 + \dots + w_5^2$ pulls weights toward 0; $C = 1$ makes the strength one half; $b$ is not penalized. This is `LogisticRegression(C=1.0)` in scikit-learn.

## How it is minimized

$J$ is convex. Gradient: $\partial J / \partial w = \sum_i (p_i - y_i)\,x_i + w / C$, $\partial J / \partial b = \sum_i (p_i - y_i)$. Each row pushes the weights toward its features by its error $p_i - y_i$. L-BFGS follows the gradient and converges in tens of iterations. No epochs, batches or learning rate.

# 5. Platt calibration

A model can rank correctly and still say 0.3 for a group of whom 20% return. Platt fits two numbers on **validation** rows, minimizing the same log loss with $z$ as the only input:

$$
\hat p = \sigma(a\, z + c)
$$

$a < 1$ pulls probabilities toward 0.5 (overconfident model), $c$ shifts them; $a = 1, c = 0$ is no change. Not on train (the model already fits train, so it would look calibrated), not on test (reserved). Monotone in $z$, so rankings, PR-AUC and ROC-AUC are unchanged; only Brier and the reliability table move. This run: $a = 0.89$, $c = -0.01$.

# 6. Threshold

Threshold $t$ 只用在最后一步：把概率 $\hat p$ 变成“回流”或“流失”的结论。

```
for t in distinct validation scores:   # predict return if p_hat >= t
    f1[t] = F1 on validation
threshold = argmax f1      # ties -> higher t
```

# 7. Evaluation (test rows only)

| Metric             | Definition                                                                        | Read it as                                  |
| ------------------ | --------------------------------------------------------------------------------- | ------------------------------------------- |
| Precision / recall | Of predicted returners, fraction that returned / of returners, fraction predicted | At the threshold                            |
| F1                 | $2PR/(P+R)$                                                                     | What the threshold maximizes on validation  |
| PR-AUC             | Area under precision-recall as the threshold sweeps from 1 to 0                   | Compare with the floor                      |
| Floor              | Test return rate = no-skill PR-AUC                                                | 0.207 here                                  |
| ROC-AUC            | P(random returner scores above random churner)                                    | Secondary; optimistic under skew            |
| Brier              | mean $(\hat p_i - y_i)^2$, the binary form; half of Brier's (1950) two-class score | Lower is better; ranking and scale together |
| Reliability bins   | Bin by $\hat p$; compare mean $\hat p$ with observed return rate              | "When it says 30%, is it 30%?"              |
| Decile lift        | Ten equal groups by $\hat p$; group rate / overall rate                         | "Top 10% return at k× the base rate"       |
| Confusion          | TP, FP, FN, TN at the threshold, plus majority-class accuracy beside it           |                                             |

**Suppression.** Every cell: ≥ 10 returned and ≥ 10 churned. Merge adjacent bins or deciles until true. Check the three tables jointly: pool all bin and threshold boundaries, require every band between consecutive boundaries to pass, let each table use only its surviving boundaries. Otherwise subtracting one table from another could recover a small cell.

# 8. Outputs

`model.json`: features, mean_train and std_train (10 numbers), $w$ and $b$ (6), $a$ and $c$ (2), threshold (1). Enough to score a new avatar by hand: raw → log1p → subtract mean → divide by std → dot with $w$, add $b$ → $\sigma$ → Platt → compare with the threshold.

`results.json`: the four-model metric table, reliability bins, decile lift, confusion matrix, split ranges, exclusion counts, a random-split check and sensitivity runs. No avatar id, no per-avatar value.

# Leakage checklist

1. No feature uses a snapshot after the end of $d_i$; session minutes are cut at midnight.
2. mean_train and std_train from train rows only.
3. No cohort date in two parts of the split.
4. $a$, $c$ and the threshold fit on validation only.
5. Test rows touched once, in section 7.
6. Right-censored and outage cohorts dropped, never labelled 0.
7. Sanity check: the same model on a random split should not score far higher than on the temporal split.

The temporal-leak package automates part of this checklist on every run:

- **Checks 1 and 3, and part of check 4.** `check_before_cutoff`, `check_temporal_split` and `check_fit_rows` run on every fit; `check_fit_rows` confirms that no fitted step uses test rows. A violation stops the run.
- **Check 6.** `empty_periods` and `observable` find the cohorts to drop.
- **Check 7.** `shuffle_test` runs the random split; its result is reported in `results.json`.

Checks 2 and 5 are not checked at run time; they hold by how the code is written.

# Lichess

The Lichess files hold one header block per rated game. Everything from section 1 onwards is unchanged; only the data definitions differ.

| Term | Meaning |
| --- | --- |
| Account | One username, the unit of prediction |
| Day | UTC calendar day |
| Game | One rated real-time game; correspondence games and games a player played against themselves are dropped |
| Active on a day | Starts at least one rated game that day. A game running past midnight does not make the next day active |
| Game length | Lichess's own estimate, initial + 40 × increment seconds; the files carry no clock data before April 2017 |
| Session | Consecutive games of one account whose start falls within 30 min of the previous game's estimated end |
| Session minutes | First start to last estimated end, per session; minutes after midnight are not credited to the day before |
| New account | First rated game rated exactly 1500 with a rating change of at least 50, first seen between 2013-04-01 and 2014-05-31. Every new Lichess rating starts at 1500; 2013-01 to 2013-03 is a burn-in that marks existing accounts |

Five features, all from games started on $d_i$:

| Feature | raw = |
| --- | --- |
| `sessions` | Number of sessions on $d_i$ |
| `session_minutes` | Sum of session minutes on $d_i$ |
| `games` | Number of games started on $d_i$ |
| `wins` | Number of those games won |
| `speeds` | Distinct speed classes played (bullet, blitz, classical) |

