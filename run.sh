#!/usr/bin/env bash
# Unit tests, then both datasets from raw download to results. Run inside an
# activated environment with this package installed.
set -euo pipefail
cd "$(dirname "$0")"
python -m pytest -q
for ds in wowah lichess; do
    python -m retention_bench.datasets.$ds --data data/$ds
    python -m retention_bench.run --data data/$ds --out results/$ds
    python -m retention_bench.datasets.$ds.crosscheck data/$ds results/$ds/results.json
done
echo "done: results/wowah and results/lichess"
