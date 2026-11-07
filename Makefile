# One command: `make all` downloads the raw archive, parses it, builds the label,
# fits the models and writes results/. Raw data stays under data/, which is not
# committed. Override DATA=... to put it elsewhere.
PY      ?= .venv/bin/python
DATA    ?= data
RESULTS ?= results

.PHONY: all venv download parse run test clean

all: venv download parse run

venv: .venv/bin/python
.venv/bin/python:
	python3 -m venv .venv
	.venv/bin/python -m pip install -q -e ".[dev]"

download: venv
	$(PY) -m retention_bench.download --data $(DATA)

parse: venv
	$(PY) -m retention_bench.parse_wowah --data $(DATA)

run: venv
	$(PY) -m retention_bench.run --data $(DATA) --out $(RESULTS)/wowah

test: venv
	$(PY) -m pytest -q

clean:
	rm -rf $(RESULTS)/wowah

figures: venv
	$(PY) -m pip install -q -e ".[plot]"
	$(PY) scripts/plot_results.py $(RESULTS)/wowah
