"""Convert the project's Diameter dictionaries into Seagull dictionaries in a new folder.

Usage:
  python convert_dictionaries.py INPUT_DIR (--out DIR | --out-auto)
      [--combine A,B ...] [--rename OLD=NEW ...] [--keep-tgpp] [--no-comments]

INPUT_DIR holds the project's AVP dictionaries, among them DiameterBaseProtocol.xml. The
conversion itself is dict2seagull.py of seagull-diameter-common, which receives every
argument that this script does not use; see its --help for --combine, --rename,
--keep-tgpp, and --no-comments.

The output folder is always new or empty. --out names it and is refused when the folder
holds files. --out-auto picks the first free Seagull-Dictionary, Seagull-Dictionary-2, ...
next to INPUT_DIR. The exit status is 1 for a refused folder, and dict2seagull.py's
status otherwise.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
COMMON = Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"
sys.path.insert(0, str(COMMON))
dict2seagull = importlib.import_module("dict2seagull")
output_folder = importlib.import_module("output_folder")

DEFAULT_NAME = "Seagull-Dictionary"


class OutputError(Exception):
    """The output folder cannot be used."""


def parse_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    """Parse the arguments of this script; return them and the rest for dict2seagull."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--out-auto", action="store_true")
    return parser.parse_known_args(argv)


def choose_out(args: argparse.Namespace) -> Path:
    """Return the new or empty output folder."""
    if bool(args.out) == bool(args.out_auto):
        raise OutputError("give exactly one of --out and --out-auto")
    if args.out_auto:
        return output_folder.next_free(args.input_dir.parent, DEFAULT_NAME)
    if not output_folder.is_empty(args.out):
        raise OutputError(f"the output folder is not empty: {output_folder.describe(args.out)}")
    return args.out


def main(argv: list[str]) -> int:
    """Convert the dictionaries; return the exit status."""
    args, forwarded = parse_arguments(argv)
    try:
        out = choose_out(args)
    except OutputError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    sys.stdout.write(f"output folder: {out}\n")
    return int(dict2seagull.main([str(args.input_dir), str(out), *forwarded]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
