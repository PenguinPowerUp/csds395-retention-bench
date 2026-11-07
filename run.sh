#!/usr/bin/env bash
# One command, raw download to results. Needs python3 (3.11+), network access to
# the WPI host on the first run, and bsdtar/unrar/7z to open the archive.
#   ./run.sh                # data under ./data, results under ./results/wowah
#   DATA=/big/disk ./run.sh # keep the 4 GB of raw data elsewhere
set -euo pipefail
cd "$(dirname "$0")"
DATA="${DATA:-data}"
OUT="${OUT:-results/wowah}"
PY=.venv/bin/python
[ -x "$PY" ] || { python3 -m venv .venv; "$PY" -m pip install -q -e ".[dev,plot]"; }
"$PY" -m retention_bench.download --data "$DATA"
"$PY" -m retention_bench.parse_wowah --data "$DATA"
"$PY" -m retention_bench.run --data "$DATA" --out "$OUT"
"$PY" scripts/crosscheck_label.py "$DATA" "$OUT/results.json"
"$PY" scripts/plot_results.py "$OUT"
"$PY" -m pytest -q
echo "done: $OUT/results.json, model.json, reliability.png, decile_lift.png"
