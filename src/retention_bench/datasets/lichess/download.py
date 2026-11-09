"""Lichess: fetch the monthly rated-game files from database.lichess.org and verify them.

Source: the Lichess open database, released under CC0 ("Use them for research,
commercial purpose, publication, anything you like"). The raw files are never
redistributed by this repository: this module downloads them to the caller's
machine and checks each SHA-256 against the value Lichess publishes.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

BASE = "https://database.lichess.org/standard/"
CHUNK = 1 << 20

# From https://database.lichess.org/standard/sha256sums.txt, months 2013-01 to 2014-06.
SHA256 = {
    "lichess_db_standard_rated_2013-01.pgn.zst": "aa40b3671fa3cf1072eb182892cd90b0e1e003a4a5943492f64b77e7f3fd1635",
    "lichess_db_standard_rated_2013-02.pgn.zst": "c136acdf343293c45252906fee91e3b561fb26a936979f52dbe04bb649a2fd86",
    "lichess_db_standard_rated_2013-03.pgn.zst": "89da64fc3c1fe3bfd571d7f626232189f3259aa728b46ea81e5cb8f3fdb34b9e",
    "lichess_db_standard_rated_2013-04.pgn.zst": "11c795d3c81c49fa97cd958b0984c044410c78ad90f454ed08abb57ab7d00d52",
    "lichess_db_standard_rated_2013-05.pgn.zst": "f044607c9f565831524dbedfd474100c8604dba008600bfaf1b7a48ced74c17b",
    "lichess_db_standard_rated_2013-06.pgn.zst": "fef2a88dcdb386eacf02800d119737079d9be154ed986007fe4f8b5bb76741e8",
    "lichess_db_standard_rated_2013-07.pgn.zst": "51da6cfc0a6aa6e5f71a21691650dad0dc1adcabb5ba9e7de36f559ffb17a1f7",
    "lichess_db_standard_rated_2013-08.pgn.zst": "6202408d1c1cf11b1a9043b84c6bd2c03a01cb31597863857c26ee6ff82eea1b",
    "lichess_db_standard_rated_2013-09.pgn.zst": "d8a3eb5ed205aee5fef9a1a7aa91aecb408daa7faa8e481cdf9a37ed31c30ef3",
    "lichess_db_standard_rated_2013-10.pgn.zst": "4e21bd529150ea21bc68787eba2cf3f71d6745a019c98c707d2a008511143930",
    "lichess_db_standard_rated_2013-11.pgn.zst": "a1a9419694032136d03bec9ceb64a99c43a0b949e551136a2a57f36e0bdf27f4",
    "lichess_db_standard_rated_2013-12.pgn.zst": "a77d132bdf7aece20f7f3b9b3aa69eae891f2a339e59bb148984c1577eba2de9",
    "lichess_db_standard_rated_2014-01.pgn.zst": "f4e9efea9aeb608211a1e1b62aff00b92679eab6b70f957e77a1d7c4d8bfbbc8",
    "lichess_db_standard_rated_2014-02.pgn.zst": "e6063628f7b9e2d85a5d696899f6fe45cd2ea78c648a63c700707a1cccdef052",
    "lichess_db_standard_rated_2014-03.pgn.zst": "03c387eded7d0218bee672052472624576772f130c98cd9c20e8ddeed0735843",
    "lichess_db_standard_rated_2014-04.pgn.zst": "d795efabb88ead3636b1233ed7e53b9e706b917c60862979fafc8bb7c4864dfe",
    "lichess_db_standard_rated_2014-05.pgn.zst": "c2f095da79dcf72fa94d058b5807ef1b8e8bf8d6798f91fd42e8a65efebb569a",
    "lichess_db_standard_rated_2014-06.pgn.zst": "e8e028becace5b88f9dab90b0d3daaaacb41060dbab1c87b7432c9202e8901d1",
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while b := f.read(CHUNK):
            h.update(b)
    return h.hexdigest()


def fetch(name: str, dest: Path) -> None:
    path = dest / name
    if path.exists() and sha256_of(path) == SHA256[name]:
        print(f"already present: {path}")
        return
    print(f"downloading {BASE + name}")
    with urllib.request.urlopen(BASE + name) as r, path.open("wb") as f:
        while chunk := r.read(CHUNK):
            f.write(chunk)
    digest = sha256_of(path)
    if digest != SHA256[name]:
        sys.exit(f"checksum mismatch for {name}: expected {SHA256[name]}, got {digest}")
    print(f"  verified {name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args(argv)
    raw = a.data / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    for name in SHA256:
        fetch(name, raw)


if __name__ == "__main__":
    main()
