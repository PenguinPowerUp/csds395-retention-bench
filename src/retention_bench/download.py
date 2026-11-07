"""Fetch the WoWAH archive from its public host and verify it.

Source: Y.-T. Lee, K.-T. Chen, Y.-M. Cheng, C.-L. Lei, "World of Warcraft Avatar
History Dataset", ACM MMSys 2011. The MMSys dataset track hosts the archive at
WPI; the original Academia Sinica host is offline. The raw archive is never
redistributed by this repository: this module downloads it to the caller's
machine and checks its SHA-256 against the value recorded here.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

URL = "https://web.cs.wpi.edu/~claypool/mmsys-dataset/2011/wow/wowah.rar"
SIZE = 577_556_091
# Filled in from the first verified download; see docs/LICENSE-MEMO.md.
SHA256 = "6aac2a06e40e6e51299206a3dd99db063dd54bd8839fbe233d340f80760d4b73"


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def download(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    rar = dest / "wowah.rar"
    if rar.exists() and rar.stat().st_size == SIZE:
        print(f"already present: {rar}")
    else:
        print(f"downloading {URL} -> {rar}")
        with urllib.request.urlopen(URL) as r, rar.open("wb") as f:
            done, step = 0, 50 << 20
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if done % step < len(chunk) or done == SIZE:
                    print(f"  {done >> 20} / {SIZE >> 20} MB", flush=True)
    digest = sha256_of(rar)
    if SHA256 != "SHA256_PLACEHOLDER" and digest != SHA256:
        sys.exit(f"checksum mismatch: expected {SHA256}, got {digest}")
    (dest / "wowah.rar.sha256").write_text(f"{digest}  wowah.rar\n")
    print(f"sha256 {digest}")
    return rar


def extract(rar: Path, dest: Path) -> Path:
    """Extract with bsdtar (libarchive reads RAR); fall back to unrar/7z."""
    out = dest / "wowah"
    if out.exists() and any(out.iterdir()):
        print(f"already extracted: {out}")
        return out
    out.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["bsdtar", "-xf", str(rar), "-C", str(out)],
        ["unrar", "x", "-o+", str(rar), str(out) + "/"],
        ["7z", "x", "-y", f"-o{out}", str(rar)],
    ):
        if shutil.which(cmd[0]):
            print("extracting with", cmd[0])
            subprocess.run(cmd, check=True)
            return out
    sys.exit("no RAR extractor found: install bsdtar (libarchive), unrar or 7z")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=Path("data"))
    a = ap.parse_args(argv)
    raw = a.data / "raw"
    rar = download(raw)
    extract(rar, raw)


if __name__ == "__main__":
    main()
