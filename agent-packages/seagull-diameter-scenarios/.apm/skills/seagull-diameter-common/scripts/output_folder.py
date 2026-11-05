"""Choose and protect the output folder of a skill, so that no run mixes its files with old ones.

Usage:
  python output_folder.py next-free PARENT NAME   print PARENT/NAME, or PARENT/NAME-2, -3, ...
                                                  for the first path that does not exist
  python output_folder.py describe FOLDER         print what a folder holds, and exit with
                                                  0 if it is empty or missing, 1 if not

The generator and the extraction skill use the functions below: a folder that the user
did not name is always new, and a folder that is not empty is never written into
without the user's word.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def next_free(parent: Path, name: str) -> Path:
    """Return parent/name, or parent/name-2, name-3, ... for the first free path."""
    candidate = parent / name
    number = 1
    while candidate.exists():
        number += 1
        candidate = parent / f"{name}-{number}"
    return candidate


def is_empty(folder: Path) -> bool:
    """Return True for a missing folder or one without entries."""
    return not folder.exists() or not any(folder.iterdir())


def describe(folder: Path) -> str:
    """Return a one-line summary of a folder: the file count and the dates."""
    files = [p for p in folder.rglob("*") if p.is_file()]
    if not files:
        return f"{folder} holds no files"
    moments = sorted(p.stat().st_mtime for p in files)
    stamp = "%Y-%m-%d %H:%M"
    first = time.strftime(stamp, time.localtime(moments[0]))
    last = time.strftime(stamp, time.localtime(moments[-1]))
    return f"{folder} holds {len(files)} file(s), modified {first} to {last}"


def archive_name(folder: Path) -> Path:
    """Return the sibling path to which the old contents of a folder are moved."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return next_free(folder.parent, f"{folder.name}.previous-{stamp}")


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    if len(argv) == 3 and argv[0] == "next-free":
        sys.stdout.write(f"{next_free(Path(argv[1]), argv[2])}\n")
        return 0
    if len(argv) == 2 and argv[0] == "describe":
        folder = Path(argv[1])
        sys.stdout.write(f"{describe(folder)}\n")
        return 0 if is_empty(folder) else 1
    sys.stderr.write(__doc__.split("\n\n", maxsplit=2)[1] + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
