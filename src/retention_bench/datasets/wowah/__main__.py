"""WoWAH end to end: download and verify, parse the logs, write the canonical tables."""

import argparse
from pathlib import Path

from . import download, parse, prepare

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--data", type=Path, required=True)
a = ap.parse_args()
for step in (download, parse, prepare):
    step.main(["--data", str(a.data)])
