"""Turn Seagull scenarios with fixed values into templates with @@NAME@@ placeholders.

Usage:
  python scenario_to_template.py SCENARIO [SCENARIO ...] [--options FILE]
      [--option KEY=VALUE ...] [--placeholder AVP=NAME ...] [--out DIR]

Each SCENARIO is a scenario file, or a folder whose *.client.xml files are converted.
A file's AVP elements must stand on one line each, as the generator writes them. The
script replaces the value of every AVP that a [placeholders] pair of the options file
matches, in the <command> elements of the scenario, and writes SCENARIO.tpl and
SCENARIO.values next to it (or into --out). The values file holds the replaced values,
so apply_placeholders.py with it reproduces the original scenario. --option and
--placeholder change the options file, which the script writes back. Without --options
the file is scenario-options.ini in the folder of the first scenario.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import unescape

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
COMMON = Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"
sys.path.insert(0, str(COMMON))
scenario_options = importlib.import_module("scenario_options")
scenario_text = importlib.import_module("scenario_text")

OPTIONS_NAME = "scenario-options.ini"


@dataclass
class Conversion:
    """The replacement of values in the commands of one scenario file."""

    rules: dict[str, str]
    used: set[str]
    values: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def text(self, text: str) -> str:
        """Return the scenario text with the matching values replaced."""
        lines = text.split("\n")
        for start, end in scenario_text.command_ranges(lines):
            for leaf in scenario_text.leaves(lines, start, end):
                lines[leaf.index] = self.leaf(leaf, lines[leaf.index])
        return "\n".join(lines)

    def leaf(self, leaf: Any, line: str) -> str:
        """Return an <avp> line, with a placeholder if a rule matches its path."""
        found = scenario_options.lookup(self.rules, leaf.path)
        if found is None:
            return line
        key, holder = found
        self.used.add(key)
        plain = scenario_options.unwrapped(unescape(leaf.value, {"&quot;": '"'}))
        known = self.values.setdefault(holder, plain)
        if known != plain:
            self.notes.append(f"{holder}: values {known!r} and {plain!r}; used the first")
        wrapped = scenario_options.wrap(leaf.value, holder)
        return f'{leaf.indent}<avp name="{leaf.name}" value="{wrapped}"></avp>'


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("scenarios", type=Path, nargs="+")
    parser.add_argument("--options", type=Path)
    parser.add_argument("--option", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--placeholder", action="append", default=[], metavar="AVP=NAME")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    args.scenarios = scenario_text.client_files(args.scenarios)
    return args


def settings_of(args: argparse.Namespace) -> tuple[Path, Any]:
    """Read the options file and apply the command line; template mode is implied."""
    path = args.options or args.scenarios[0].parent / OPTIONS_NAME
    options = scenario_options.load_options(path)
    scenario_options.apply_pairs(options, args.option, args.placeholder)
    options.mode = "template"
    options.validate()
    if options.substitution != "text":
        raise scenario_options.OptionsError("a template file needs substitution = text")
    return path, options


def write_one(scenario: Path, out: Path | None, conversion: Conversion) -> list[str]:
    """Write the template and the values of one scenario; return notes."""
    conversion.values, conversion.notes = {}, []
    template = conversion.text(scenario.read_text(encoding="iso-8859-1"))
    folder = out or scenario.parent
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{scenario.name}.tpl"
    values_file = folder / f"{scenario.name}.values"
    replaced = [p.name for p in (target, values_file) if p.exists()]
    target.write_text(template, encoding="iso-8859-1", newline="\n")
    scenario_options.write_values(values_file, conversion.values)
    count = len(conversion.values)
    summary = f"{scenario.name}: {count} placeholder(s) written to {target.name}"
    notes = list(conversion.notes)
    if replaced:
        notes.append(f"replaced existing {' and '.join(replaced)}")
    return [summary, *[f"{scenario.name}: {note}" for note in notes]]


def main(argv: list[str]) -> int:
    """Write the templates; return the exit status."""
    args = parse_arguments(argv)
    if not args.scenarios:
        sys.stderr.write("error: no *.client.xml file found\n")
        return 1
    try:
        path, options = settings_of(args)
        conversion = Conversion(options.rules(), set())
        notes: list[str] = []
        for scenario in args.scenarios:
            notes += write_one(scenario, args.out, conversion)
        unused = sorted(set(conversion.rules) - conversion.used)
        notes += [f"placeholder {key}: matched no AVP" for key in unused]
        scenario_options.save_options(path, options)
    except (scenario_options.OptionsError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    sys.stdout.write("\n".join([*notes, f"options: {path}"]) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
