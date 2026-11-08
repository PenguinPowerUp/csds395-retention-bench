#!/usr/bin/env bash
# Raw download to results. Run inside an activated environment with this package
# installed; README.md shows how to set it up.
set -euo pipefail
cd "$(dirname "$0")"
python -m retention_bench.download --data data
python -m retention_bench.parse_wowah --data data
python -m retention_bench.run --data data --out results/wowah
python scripts/crosscheck_label.py data results/wowah/results.json
python -m pytest -q
echo "done: results/wowah/results.json, results/wowah/model.json"
