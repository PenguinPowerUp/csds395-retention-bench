# retention-bench

Day-one return prediction on public game telemetry. The question it answers: on a public dataset, with a label constructed from behaviour, how far does first-day activity predict whether a new player comes back the next day, and is the predicted probability honest?

## Dataset

World of Warcraft Avatar History (WoWAH): Y.-T. Lee, K.-T. Chen, Y.-M. Cheng and C.-L. Lei, "World of Warcraft Avatar History Dataset", *Proceedings of ACM MMSys 2011*. Downloaded at run time from the ACM MMSys dataset track mirror at WPI and verified by SHA-256. The archive is never committed or redistributed. See `docs/LICENSE-MEMO.md` for why this dataset and not the other candidates.

## How to run

Requirements: Python 3.11+, `bsdtar` (from libarchive; `sudo apt install libarchive-tools` on Ubuntu), about 5 GB of disk, and network access to the WPI host on the first run.

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

`./run.sh` first runs the unit tests and stops if any fails. It then downloads and extracts the archive (577 MB) into `data/raw/`, parses the 10-minute snapshot logs into `data/snapshots.parquet`, builds the label and features, fits the four models, writes `results/wowah/`, and recounts the population by an independent route and checks it against the results.

## Method

`docs/ALGORITHM.md` defines the data, the unit, the clock, the new-avatar rule, the label and the exclusions, and gives the full method.

## Results

`docs/RESULTS.md` gives the full result..

`docs/LITERATURE.md` compares the task and the results with published work.

## Outputs

- `results/wowah/results.json`: population and split, the four-model metric table, calibration, reliability bins, decile lift, the threshold confusion matrix, the random-split leakage check, and sensitivity runs.
- `results/wowah/model.json`: the trained model, i.e. its features, transform statistics, coefficients, intercept, Platt parameters and threshold.
- `docs/figures/`: the reliability diagram and the decile lift chart. They are not made by `./run.sh`; after a run, redraw them with `pip install -e ".[plot]"` and then `python docs/figures/scripts/plot_results.py`.

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
docs/              licence memo, algorithm, results, literature comparison
docs/figures/      the two figures; scripts/plot_results.py draws them from results.json
```

## Citation

If you use the results, cite Lee et al. (MMSys 2011) for the data and this repository for the benchmark.
