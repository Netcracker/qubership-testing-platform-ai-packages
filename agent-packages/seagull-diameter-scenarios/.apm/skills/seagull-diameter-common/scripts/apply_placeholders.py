"""Replace the @@NAME@@ placeholders of a Seagull scenario template with values.

Usage:
  python apply_placeholders.py TEMPLATE --out SCENARIO [--values FILE ...]
      [--env] [--set NAME=VALUE ...]

A value comes from, in order of precedence: --set, then the process environment
when --env is given, then the --values files (NAME=value lines). The script stops
and names every placeholder that has no value, and every --set name that is not a
placeholder of the template, so that a misspelled name cannot leave the recorded
value in place. The scenario is written in ISO-8859-1
with LF line endings, as Seagull reads it.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
options_module = importlib.import_module("scenario_options")


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("template", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--values", type=Path, action="append", default=[])
    parser.add_argument("--env", action="store_true", help="read values from the environment")
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    return parser.parse_args(argv)


def collect_values(options: argparse.Namespace, names: list[str]) -> dict[str, str]:
    """Return the values of the placeholders, with the precedence of the usage."""
    values: dict[str, str] = {}
    for path in options.values:
        values.update(options_module.read_values(path))
    if options.env:
        values.update({n: os.environ[n] for n in names if n in os.environ})
    for pair in options.set:
        name, separator, value = pair.partition("=")
        if not separator:
            raise options_module.OptionsError(f"--set {pair!r}: expected NAME=VALUE")
        if name not in names:
            known = ", ".join(names) or "none"
            raise options_module.OptionsError(f"--set {name}: the template has no such placeholder (it has {known})")
        values[name] = value
    return values


def main(argv: list[str]) -> int:
    """Render the template; return the exit status."""
    options = parse_arguments(argv)
    try:
        text = options.template.read_text(encoding="iso-8859-1")
        names = options_module.placeholder_names(text)
        rendered = options_module.render(text, collect_values(options, names))
        replaced = options.out.exists()
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(rendered, encoding="iso-8859-1", newline="\n")
    except (options_module.OptionsError, OSError, UnicodeEncodeError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    note = " (an existing file was replaced)" if replaced else ""
    count = f"{len(names)} placeholder(s) replaced"
    sys.stdout.write(f"{count}, written to {options.out}{note}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
