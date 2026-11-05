"""Make generated Seagull scenarios take chosen AVP values from an external data file.

Usage:
  python scenario_to_external.py SCENARIO [SCENARIO ...] (--out DIR | --out-auto)
      [--placeholder AVP=COLUMN ...] [--options FILE] [--select sequential|random]
      [--calls N] [--data-path PATH]

Each SCENARIO is a *.client.xml file of a generation, or the scenario folder of one. The
[placeholders] pairs of the options file (and --placeholder) name the AVPs and, as the
value, the column of the data file that each AVP is read from. For each matched AVP of a
request the script adds a <restore-from-external> to the action before the <command>,
so Seagull takes the value from the data file at run time. Seagull picks one row for
each call: every step of a call uses that row, and the next call takes the next row
(sequential) or a random one (random).

The result is a new folder, never an old one: --out must name a new or empty folder, and
--out-auto picks the first free <source>-external. It holds the changed scenarios, the
untouched stub scenarios, copies of config/ and dictionary/ with the data file named in
the client configurations, and scenario/external-data.csv, whose first row is the
recorded values. Put more rows into that file. --data-path is the path to the file as
Seagull will see it when you run it (default ../scenario/external-data.csv); the dry-run
configuration always uses the path inside the Seagull image.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import unescape

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
COMMON = Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"
sys.path.insert(0, str(COMMON))
output_folder = importlib.import_module("output_folder")
scenario_options = importlib.import_module("scenario_options")
scenario_text = importlib.import_module("scenario_text")

OPTIONS_NAME = "scenario-options.ini"
DATA_NAME = "external-data.csv"
DRY_RUN_DATA_PATH = f"/work/scenario/{DATA_NAME}"
DEFAULT_DATA_PATH = f"../scenario/{DATA_NAME}"
SELECTIONS = ("sequential", "random")


class ExternalError(Exception):
    """The scenarios cannot be changed as asked."""


@dataclass
class External:
    """The AVPs read from the data file, and the columns of the file."""

    rules: dict[str, str]
    used: set[str] = field(default_factory=set)
    columns: list[str] = field(default_factory=list)
    first: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def column(self, holder: str, value: str) -> int:
        """Return the column of a placeholder, adding it; remember its first value."""
        if holder not in self.columns:
            self.columns.append(holder)
        plain = unescape(value, {"&quot;": '"'})
        known = self.first.setdefault(holder, plain)
        if known != plain:
            self.notes.append(
                f"{holder}: values {known!r} and {plain!r}; used the first"
            )
        return self.columns.index(holder)


def restore_line(column: int, name: str) -> str:
    """Return the element that reads a field of the data row into an AVP."""
    return f'<restore-from-external field="{column}" entity="{name}"></restore-from-external>'


def blocks(lines: list[str], tag: str, start: int) -> list[tuple[int, int]]:
    """Return (first, last) line numbers of each <tag> element after line start."""
    found = []
    first = None
    for number in range(start, len(lines)):
        stripped = lines[number].strip()
        if stripped.startswith(f"<{tag} ") or stripped == f"<{tag}>":
            first = number
        elif stripped == f"</{tag}>" and first is not None:
            found.append((first, number))
            first = None
    return found


def send_changes(
    lines: list[str],
    block: tuple[int, int],
    external: External,
) -> tuple[set[int], list[tuple[int, list[str]]], set[str]]:
    """Return the lines to delete, the lines to insert, and the AVP names changed."""
    first, last = block
    ranges = [r for r in scenario_text.command_ranges(lines) if first < r[0] < last]
    if not ranges:
        return set(), [], set()
    found = scenario_text.leaves(lines, *ranges[0])
    names = [leaf.name for leaf in found]
    reads = []
    for leaf in found:
        match = scenario_options.lookup(external.rules, leaf.path)
        if match is None:
            continue
        if names.count(leaf.name) > 1:
            where = "/".join(entry[0] for entry in leaf.path)
            message = f"{where} occurs more than once in a request; Seagull reads"
            raise ExternalError(
                f"{message} an AVP by name, so it cannot tell them apart"
            )
        external.used.add(match[0])
        reads.append((external.column(match[1], leaf.value), leaf.name))
    if not reads:
        return set(), [], set()
    return place_reads(lines, (first, ranges[0][0] - 1), sorted(reads))


def place_reads(
    lines: list[str],
    where: tuple[int, int],
    reads: list[tuple[int, str]],
) -> tuple[set[int], list[tuple[int, list[str]]], set[str]]:
    """Return the changes that put the reads into the action before a command."""
    first, command_line = where
    names = {name for _, name in reads}
    action = [n for n in range(first, command_line) if lines[n].strip() == "<action>"]
    if not action:
        indent = lines[command_line][
            : len(lines[command_line]) - len(lines[command_line].lstrip())
        ]
        body = [f"{indent}  {restore_line(c, n)}" for c, n in reads]
        return (
            set(),
            [(command_line, [f"{indent}<action>", *body, f"{indent}</action>"])],
            names,
        )
    close = next(
        n for n in range(action[0], command_line) if lines[n].strip() == "</action>"
    )
    indent = lines[close][: len(lines[close]) - len(lines[close].lstrip())]
    deleted = set()
    for number in range(action[0] + 1, close):
        text = lines[number].strip()
        for name in names:
            if text.startswith(f'<set-value name="{name}"'):
                deleted.add(number)
            elif re.search(rf'<(store|restore) name="[^"]*" entity="{name}"', text):
                message = f"{name} is already set by another tag in the request"
                raise ExternalError(f"{message}; remove that option and generate again")
    body = [f"{indent}  {restore_line(c, n)}" for c, n in reads]
    return deleted, [(close, body)], names


def externalize(text: str, external: External) -> tuple[str, list[str]]:
    """Return the scenario text with its requests reading from the data file."""
    lines = text.split("\n")
    if "restore-from-external" in text:
        raise ExternalError("the scenario already reads from an external data file")
    traffic = next((n for n, line in enumerate(lines) if "<traffic>" in line), None)
    if traffic is None:
        raise ExternalError("the scenario has no <traffic> section")
    deleted: set[int] = set()
    inserted: list[tuple[int, list[str]]] = []
    names: set[str] = set()
    for block in blocks(lines, "send", traffic):
        gone, added, changed = send_changes(lines, block, external)
        deleted |= gone
        inserted += added
        names |= changed
    checks, notes = answer_checks(lines, traffic, names)
    return apply_edits(lines, deleted | checks, dict(inserted)), notes


def answer_checks(
    lines: list[str],
    traffic: int,
    names: set[str],
) -> tuple[set[int], list[str]]:
    """Return the check-value lines of changed AVPs in the answers, and report notes."""
    found: set[int] = set()
    notes = []
    for first, last in blocks(lines, "receive", traffic):
        for number in range(first, last):
            match = re.search(r'<check-value name="([^"]+)"', lines[number])
            if match and match.group(1) in names:
                found.add(number)
                notes.append(f"removed the check of {match.group(1)} in an answer")
    return found, notes


def apply_edits(
    lines: list[str],
    deleted: set[int],
    before: dict[int, list[str]],
) -> str:
    """Return the text without the deleted lines and with lines added before others."""
    result = []
    for number, line in enumerate(lines):
        result += before.get(number, [])
        if number not in deleted:
            result.append(line)
    return "\n".join(result)


def csv_text(external: External, select: str) -> str:
    """Return the data file: field definition, the recorded row, a spare row for random."""
    for value in external.first.values():
        if '"' in value or ";" in value:
            raise ExternalError(f"the value {value!r} has a quote or a semicolon")
    definition = "".join('"string";' for _ in external.columns)
    row = "".join(f'"{external.first[c]}";' for c in external.columns)
    lines = ["# " + "; ".join(external.columns), definition, row]
    if select == "random":
        lines += [
            "# spare row: Seagull 1.8.3 never picks the last row of a random file",
            row,
        ]
    return "\n".join(lines) + "\n"


def client_config(text: str, data_path: str, select: str, calls: int | None) -> str:
    """Return a client configuration that names the data file."""
    if calls is not None:
        text = re.sub(r'(name="number-calls" value=")[^"]*"', rf'\g<1>{calls}"', text)
    pad = '  <define entity="traffic-param" name="%s" value="%s"></define>\n'
    defines = pad % ("external-data-file", data_path)
    defines += pad % ("external-data-select", select)
    return text.replace("</configuration>", defines + "</configuration>")


def copy_context(source: Path, out: Path) -> list[str]:
    """Copy config/, dictionary/, and the stub scenarios of a generation; list them."""
    copied = []
    for name in ("dictionary", "config"):
        if (source / name).is_dir():
            shutil.copytree(source / name, out / name)
            copied.append(name + "/")
    (out / "scenario").mkdir(parents=True, exist_ok=True)
    for stub in sorted((source / "scenario").glob("*.stub-server.xml")):
        shutil.copy2(stub, out / "scenario" / stub.name)
    return copied


def write_configs(out: Path, args: argparse.Namespace) -> list[str]:
    """Add the data file to the client configurations under out/config."""
    changed = []
    for path in sorted((out / "config").glob("conf.*client*.xml")):
        data = DRY_RUN_DATA_PATH if "dry-run" in path.name else args.data_path
        text = path.read_text(encoding="iso-8859-1")
        new = client_config(text, data, args.select, args.calls)
        path.write_text(new, encoding="iso-8859-1", newline="\n")
        changed.append(f"{path.name}: {data}")
    return changed


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("scenarios", type=Path, nargs="+")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--out-auto", action="store_true")
    parser.add_argument("--options", type=Path)
    parser.add_argument(
        "--placeholder", action="append", default=[], metavar="AVP=COLUMN"
    )
    parser.add_argument("--select", choices=SELECTIONS, default="sequential")
    parser.add_argument("--calls", type=int)
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH)
    args = parser.parse_args(argv)
    args.scenarios = scenario_text.client_files(args.scenarios)
    return args


def settings_of(args: argparse.Namespace, source: Path) -> Any:
    """Read the options file of the source and apply the --placeholder pairs."""
    options = scenario_options.load_options(args.options or source / OPTIONS_NAME)
    scenario_options.apply_pairs(options, [], args.placeholder)
    options.validate()
    if not options.placeholders:
        raise ExternalError("no AVP is named: give placeholder=<AVP>=<COLUMN>")
    return options


def choose_out(args: argparse.Namespace, source: Path) -> Path:
    """Return the new or empty output folder."""
    if bool(args.out) == bool(args.out_auto):
        raise ExternalError("give exactly one of --out and --out-auto")
    if args.out_auto:
        return output_folder.next_free(source.parent, f"{source.name}-external")
    if not output_folder.is_empty(args.out):
        summary = output_folder.describe(args.out)
        raise ExternalError(f"the output folder is not empty: {summary}")
    return args.out


def convert_all(
    args: argparse.Namespace,
    external: External,
) -> tuple[dict[str, str], list[str]]:
    """Change every scenario in memory; return {file name: text} and report lines."""
    converted: dict[str, str] = {}
    report: list[str] = []
    for path in args.scenarios:
        text, notes = externalize(path.read_text(encoding="iso-8859-1"), external)
        converted[path.name] = text
        report.append(f"{path.name}: changed")
        report += [f"{path.name}: {note}" for note in sorted(set(notes))]
    return converted, report


def write_output(
    out: Path,
    source: Path,
    converted: dict[str, str],
    data: str,
) -> list[str]:
    """Write the new folder: context, scenarios, and data file; return report lines."""
    report = [f"copied {name}" for name in copy_context(source, out)]
    for name, text in converted.items():
        (out / "scenario" / name).write_text(text, encoding="iso-8859-1", newline="\n")
    (out / "scenario" / DATA_NAME).write_text(data, encoding="ascii", newline="\n")
    return report


def run(args: argparse.Namespace) -> list[str]:
    """Do the work; return the lines of the report. Nothing is written on an error."""
    if not args.scenarios:
        raise ExternalError("no *.client.xml file found")
    first = args.scenarios[0].resolve()
    source = first.parent.parent if first.parent.name == "scenario" else first.parent
    options = settings_of(args, source)
    external = External(options.placeholders)
    out = choose_out(args, source)
    converted, report = convert_all(args, external)
    data = csv_text(external, args.select)
    report = [
        f"output folder: {out}",
        *write_output(out, source, converted, data),
        *report,
    ]
    report.append(
        f"data file: {out / 'scenario' / DATA_NAME} with the columns {', '.join(external.columns)}"
    )
    report += [f"config {line}" for line in write_configs(out, args)]
    unused = sorted(set(options.placeholders) - external.used)
    report += external.notes + [f"placeholder {key}: matched no AVP" for key in unused]
    scenario_options.save_options(out / OPTIONS_NAME, options)
    return report


def main(argv: list[str]) -> int:
    """Run the conversion; return the exit status."""
    args = parse_arguments(argv)
    try:
        report = run(args)
    except (ExternalError, scenario_options.OptionsError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    sys.stdout.write("\n".join(report) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
