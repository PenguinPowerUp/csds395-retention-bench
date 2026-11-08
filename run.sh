#!/usr/bin/env bash
# Unit tests, then raw download to results. Run inside an activated environment
# with this package installed.
set -euo pipefail
cd "$(dirname "$0")"
python -m pytest -q
python -m retention_bench.download --data data
python -m retention_bench.parse_wowah --data data
python -m retention_bench.run --data data --out results/wowah
python scripts/crosscheck_label.py data results/wowah/results.json
echo "done: results/wowah/results.json, results/wowah/model.json"
