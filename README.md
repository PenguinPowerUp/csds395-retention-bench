# retention-bench

Day-one return prediction on public game telemetry, from raw download to a results table in one command. The question it answers: on a public dataset, with a label constructed from behaviour, how far does first-day activity predict whether a new player comes back the next day, and is the predicted probability honest?

Everything here is Pengjun Lu's own work on public data, under the MIT licence. It contains no code, data or figure from any private project.

## Dataset

World of Warcraft Avatar History (WoWAH): Y.-T. Lee, K.-T. Chen, Y.-M. Cheng and C.-L. Lei, "World of Warcraft Avatar History Dataset", *Proceedings of ACM MMSys 2011*. Downloaded at run time from the ACM MMSys dataset track mirror at WPI and verified by SHA-256. The archive is never committed or redistributed. See `docs/LICENSE-MEMO.md` for why this dataset and not the other candidates.

## One command

```bash
./run.sh
```

This creates `.venv`, downloads and extracts the archive (577 MB) into `data/raw/`, parses the 10-minute snapshot logs into `data/snapshots.parquet`, builds the label and features, fits the four models, writes `results/wowah/`, recounts the population by an independent route and checks it against the results, renders the two figures and runs the unit tests. Requirements: Python 3.11+, `bsdtar` (libarchive) or `unrar` or `7z`, about 5 GB of disk and network access to the WPI host on the first run. Set `DATA=/some/path` to keep the raw data elsewhere. A `Makefile` with the same steps exists for those who have `make`.

## Method

`docs/algorithm.md` defines the data, the unit, the clock, the new-avatar rule, the label and the exclusions, and gives the full method: temporal split by cohort date, log1p and standardization with train statistics, majority and single-feature baselines, L2 logistic regression, Platt scaling on validation, max-F1 threshold on validation, metrics on test, and the joint suppression that keeps every published cell at ten or more of each class.

## Results

`docs/RESULTS.md` reads the headline numbers: on 79,497 new avatars, the L2 logistic model reaches PR-AUC 0.558 against a floor of 0.207 on a 2008 test window, top-decile lift 3.2, with sensitivity runs for the new-avatar rule, outage days, a strict label, avatars online at midnight, the feature set, and a random-split leakage check.

## Outputs

- `results/wowah/results.json`: population and split, the four-model metric table, calibration, reliability bins, decile lift, the threshold confusion matrix, the random-split leakage check, and sensitivity runs.
- `results/wowah/model.json`: features, transform statistics, coefficients, intercept, Platt parameters and threshold, enough to score a row without this code.

## Layout

```
src/retention_bench/
  download.py      fetch + checksum + extract
  parse_wowah.py   raw logs -> snapshots.parquet
  sessions.py      snapshots -> per-avatar-day activity and day-zero features
  labels.py        cohort date, label, exclusions
  split.py         temporal split by whole cohort date
  features.py      log1p + train-statistics standardization
  model.py         majority, single feature, L2 logistic, Platt, threshold
  evaluate.py      metrics, reliability, deciles, joint suppression
  run.py           the pipeline
tests/             unit tests on invented rows
docs/              licence memo, label definition, algorithm
```

## Citation

If you use the results, cite Lee et al. (MMSys 2011) for the data and this repository for the benchmark.
