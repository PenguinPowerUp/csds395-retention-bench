# retention-bench

Day-one return prediction on two public game datasets. The question it answers: on public data, with a label constructed from behaviour, how far does first-day activity predict whether a new player comes back the next day, and is the predicted probability honest?

## Datasets

- **WoWAH.** World of Warcraft Avatar History: Y.-T. Lee, K.-T. Chen, Y.-M. Cheng and C.-L. Lei, "World of Warcraft Avatar History Dataset", *Proceedings of ACM MMSys 2011*. Downloaded at run time from the ACM MMSys dataset track mirror at WPI.
- **Lichess.** The Lichess open database (https://database.lichess.org/, CC0), standard rated games from 2013-01 to 2014-06, downloaded at run time.

Every file is verified by SHA-256, and no raw file is committed or redistributed. `docs/LICENSE-MEMO.md` explains the choice of both datasets.

## How to run

Requirements: Python 3.11+, git, `bsdtar` (from libarchive; `sudo apt install libarchive-tools` on Ubuntu), about 8 GB of disk, and network access to the two download hosts on the first run. `pip install` also fetches the temporal-leak package from GitHub.

Set up the environment once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Or use conda:
```bash
conda create -n retention-bench python=3.12
conda activate retention-bench
pip install -e ".[dev]"
```

Then, with the environment active:

```bash
./run.sh
```

`./run.sh` first runs the unit tests and stops if any fails. Then, for each dataset, it downloads and verifies the raw files into `data/<dataset>/raw/`, parses them, writes the canonical tables, fits the four models, writes `results/<dataset>/`, and recounts the population by an independent route and checks it against the results.

## Method

`docs/ALGORITHM.md` defines the data, the unit, the clock, the new-avatar rule, the label and the exclusions, and gives the full method.

## Results

`docs/RESULTS-WOWAH.md` and `docs/RESULTS-LICHESS.md` give the full results of each dataset.

`docs/LITERATURE.md` compares the task and the results with published work.

## Outputs

- `results/<dataset>/results.json`: population and split, the four-model metric table, calibration, reliability bins, decile lift, the threshold confusion matrix, the random-split leakage check, and sensitivity runs.
- `results/<dataset>/model.json`: the trained model, i.e. its features, transform statistics, coefficients, intercept, Platt parameters and threshold.
- `docs/figures/`: the reliability diagram and the decile lift chart of each dataset. They are not made by `./run.sh`; after a run, redraw them with `pip install -e ".[plot]"` and then `python docs/figures/scripts/plot_results.py`.

## Layout

```
src/retention_bench/
  datasets/wowah/    download, parse, sessions, prepare, crosscheck
  datasets/lichess/  download, parse, sessions, prepare, crosscheck
  canonical.py       the tables every dataset adapter writes, and their loader
  labels.py          cohort date, label, exclusions
  split.py           temporal split by whole cohort date
  features.py        log1p + train-statistics standardization
  model.py           majority, single feature, L2 logistic, Platt, threshold
  evaluate.py        metrics, reliability, deciles, joint suppression
  run.py             the pipeline, on the canonical tables only
tests/               unit tests on invented rows
docs/                licence memo, algorithm, results, literature comparison
docs/figures/        the figures; scripts/plot_results.py draws them from results.json
```

Adding a dataset means writing one adapter under `datasets/` that produces the canonical tables described in `canonical.py`; nothing else changes.

The leakage checks come from the separate temporal-leak package (https://github.com/PenguinPowerUp/temporal-leak).

## Citation

If you use the results, cite Lee et al. (MMSys 2011) for WoWAH, the Lichess open database for Lichess, and this repository for the benchmark.
