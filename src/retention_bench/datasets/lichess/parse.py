"""Lichess: stream each monthly .pgn.zst and keep the game headers as Parquet.

Only header lines are read; move text is skipped and the decompressed PGN is
never written to disk. Output: data/lichess/games/<month>.parquet with columns
ts (UTC start), white, black, result, white_elo, black_elo, white_diff,
black_diff, time_control, event. Usernames stay under data/, which is never
committed.
"""

from __future__ import annotations

import argparse
import io
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import zstandard

FIELDS = ("Event", "White", "Black", "Result", "UTCDate", "UTCTime", "WhiteElo", "BlackElo",
          "WhiteRatingDiff", "BlackRatingDiff", "TimeControl")


def parse_lines(lines) -> dict[str, list]:
    """Collect the header fields of every game in an iterable of PGN lines."""
    cols: dict[str, list] = {f: [] for f in FIELDS}
    game: dict[str, str] = {}

    def emit():
        if game:
            for f in FIELDS:
                cols[f].append(game.get(f))

    for line in lines:
        if not line.startswith("["):
            continue
        q = line.find(' "')
        if q < 0:
            continue
        key = line[1:q]
        if key == "Event":
            emit()
            game = {}
        if key in FIELDS:
            game[key] = line[q + 2:line.rfind('"')]
    emit()
    return cols


def to_int(values: list, missing: float = np.nan) -> np.ndarray:
    return pd.to_numeric(pd.Series(values, dtype="object"), errors="coerce").fillna(missing).to_numpy()


def parse_file(path: Path) -> pd.DataFrame:
    with path.open("rb") as f:
        text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding="utf-8", errors="replace")
        cols = parse_lines(text)
    ts = pd.to_datetime(pd.Series(cols["UTCDate"]) + " " + pd.Series(cols["UTCTime"]), format="%Y.%m.%d %H:%M:%S", errors="coerce")
    return pd.DataFrame({
        "ts": ts,
        "white": cols["White"], "black": cols["Black"], "result": cols["Result"],
        "white_elo": to_int(cols["WhiteElo"]), "black_elo": to_int(cols["BlackElo"]),
        "white_diff": to_int(cols["WhiteRatingDiff"]), "black_diff": to_int(cols["BlackRatingDiff"]),
        "time_control": cols["TimeControl"], "event": cols["Event"],
    })


def parse_one(args: tuple[Path, Path]) -> str:
    src, dst = args
    df = parse_file(src)
    df.to_parquet(dst, index=False)
    return f"{src.name}: {len(df):,} games"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args(argv)
    out = a.data / "games"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(p, out / (p.name.split("_")[-1].removesuffix(".pgn.zst") + ".parquet"))
            for p in sorted((a.data / "raw").glob("*.pgn.zst"))]
    with ProcessPoolExecutor(a.workers) as ex:
        for msg in ex.map(parse_one, jobs):
            print(" ", msg, flush=True)


if __name__ == "__main__":
    main()
