"""Parse the WoWAH log files into one Parquet table of avatar snapshots.

Archive layout (Lee et al. 2011, section 2.2): <season yyyy-fm-lm>/<day yyyy-mm-dd>/<hh-mm-ss>
files, one per 10-minute sample. Each file holds a Lua saved-variable array
``Persistent_Storage`` whose elements are strings of 11 comma-separated fields:
dummy, query time, query sequence number, avatar id, guild, level, race, class,
zone, dummy, dummy.

Output: ``data/snapshots.parquet`` with columns ts, avatar, guild, level, race,
cls, zone, day_dir, sample. ``sample`` is the log file name (hh-mm-ss), one per
10-minute sampling round; records inside one round carry their own query times,
a few seconds to minutes apart. Timestamps are kept in the dataset's own clock (the collector ran
in Taiwan); days are calendar days in that clock throughout the benchmark.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

RECORD = re.compile(r'"((?:[^"\\]|\\.)*)"')
DAY_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_file(path: Path) -> list[tuple]:
    return parse_text(path.read_text(encoding="utf-8", errors="replace"), path.stem)


def parse_text(text: str, sample: str) -> list[tuple]:
    """One tuple per avatar record in a log file's Persistent_Storage array."""
    start = text.find("Persist")
    end = text.find("RoundInfo", start)
    body = text[start:end if end > 0 else None]
    rows = []
    for m in RECORD.finditer(body):
        f = m.group(1).split(",")
        if len(f) < 9:
            continue
        try:
            avatar = int(f[3])
            level = int(f[5])
        except ValueError:
            continue
        guild = int(f[4]) if f[4].strip().lstrip("-").isdigit() else -1
        rows.append((f[1].strip(), avatar, guild, level, f[6].strip(), f[7].strip(), f[8].strip(), sample))
    return rows


def parse_day(day_dir: Path) -> pd.DataFrame:
    rows: list[tuple] = []
    for fp in sorted(day_dir.iterdir()):
        if fp.is_file():
            rows.extend(parse_file(fp))
    df = pd.DataFrame(rows, columns=["qtime", "avatar", "guild", "level", "race", "cls", "zone", "sample"])
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["qtime"], format="%m/%d/%y %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["ts"]).drop(columns="qtime")
    df["day_dir"] = day_dir.name
    return df


def day_dirs(root: Path) -> list[Path]:
    out = []
    for p in root.rglob("*"):
        if p.is_dir() and DAY_DIR.match(p.name):
            out.append(p)
    return sorted(out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args(argv)
    root = a.data / "raw" / "wowah"
    out = a.data / "snapshots.parquet"
    dirs = day_dirs(root)
    if not dirs:
        sys.exit(f"no day directories under {root}; run retention_bench.download first")
    print(f"{len(dirs)} day directories under {root}")
    schema = pa.schema([
        ("ts", pa.timestamp("s")), ("avatar", pa.int32()), ("guild", pa.int32()), ("level", pa.int16()),
        ("race", pa.string()), ("cls", pa.string()), ("zone", pa.string()), ("day_dir", pa.string()),
        ("sample", pa.string()),
    ])
    n = 0
    with pq.ParquetWriter(out, schema, compression="zstd") as w, ProcessPoolExecutor(a.workers) as ex:
        for i, df in enumerate(ex.map(parse_day, dirs, chunksize=4), 1):
            if not df.empty:
                df = df[["ts", "avatar", "guild", "level", "race", "cls", "zone", "day_dir", "sample"]]
                w.write_table(pa.Table.from_pandas(df, schema=schema, preserve_index=False))
                n += len(df)
            if i % 100 == 0:
                print(f"  {i}/{len(dirs)} days, {n:,} rows", flush=True)
    print(f"wrote {out}: {n:,} snapshot rows")


if __name__ == "__main__":
    main()
