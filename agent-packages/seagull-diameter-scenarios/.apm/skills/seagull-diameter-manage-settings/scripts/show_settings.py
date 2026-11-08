"""Print the settings of the Seagull Diameter skills, under one heading for each source.

Usage:
  python show_settings.py [--folder DIR]

The output has three parts:

  Settings                the keys of .seagull-diameter/config.json, each with its value and where the
                          value came from, and the two files that were read
  Dictionary options      dictionary-options.ini next to the dictionary that SEAGULL_DICTIONARY_PATH names
  Scenario options        one line that says where to find scenario-options.ini

Nothing else is searched: the dictionary options are read only from the folder of the dictionary in the
settings, and the scenario options are not read at all, because a generation writes its own file in its own
folder. The script changes nothing. Exit status 0 even when a part is empty; 2 when a file cannot be read.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"))
seagull_config = importlib.import_module("seagull_config")

DICTIONARY_OPTIONS = "dictionary-options.ini"
SCENARIO_NOTE = "Each generated set of scenarios keeps its options in scenario-options.ini, in the folder of that set."


def settings_part(folder: Path, home: Path, environ: dict[str, str]) -> list[str]:
    """Return the lines of the Settings part."""
    lines = ["## Settings"]
    for key in seagull_config.KEYS:
        value, source = seagull_config.resolve(key, folder, home, environ)
        lines.append(f"- {key}: {value or 'not set'}" + (f" ({source})" if source else ""))
    lines.append("Files read, in this order:")
    for path in seagull_config.config_paths(folder, home):
        lines.append(f"- {path} ({'found' if path.is_file() else 'not found'})")
    return lines


def dictionary_part(folder: Path, home: Path, environ: dict[str, str]) -> list[str]:
    """Return the lines of the Dictionary options part."""
    lines = ["## Dictionary options"]
    value, _ = seagull_config.resolve("SEAGULL_DICTIONARY_PATH", folder, home, environ)
    if not value:
        lines.append("SEAGULL_DICTIONARY_PATH is not set, so there is no dictionary whose options to show.")
        return lines
    path = Path(value).parent / DICTIONARY_OPTIONS
    lines.append(f"Dictionary: {value}")
    if not path.is_file():
        lines.append(f"{DICTIONARY_OPTIONS} was not found next to it.")
        return lines
    lines.append(f"File: {path}")
    lines.extend(path.read_text(encoding="utf-8").rstrip().split("\n"))
    return lines


def scenario_part() -> list[str]:
    """Return the lines of the Scenario options part."""
    return ["## Scenario options", SCENARIO_NOTE]


def build_report(folder: Path, home: Path, environ: dict[str, str]) -> str:
    """Return the whole text of the report."""
    parts = [settings_part(folder, home, environ), dictionary_part(folder, home, environ), scenario_part()]
    return "\n\n".join("\n".join(part) for part in parts) + "\n"


def main(argv: list[str]) -> int:
    """Print the report; return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--folder", type=Path, default=seagull_config.settings_folder(Path.cwd()))
    args = parser.parse_args(argv)
    try:
        report = build_report(args.folder, Path.home(), dict(os.environ))
    except (seagull_config.ConfigError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 2
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
