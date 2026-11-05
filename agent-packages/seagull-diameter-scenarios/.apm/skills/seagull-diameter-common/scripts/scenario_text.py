"""Read the AVP elements of a generated Seagull scenario, line by line.

The generator writes each <avp> on its own lines, so a scenario can be read without an
XML parser, and a script can change one line and leave the rest of the file as it is.
A command_range is the body of a <command> element that spans several lines, and a Leaf
is an <avp> with a value inside it, with the path of the groups around it.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

GROUP = re.compile(r'^(\s*)<avp name="([^"]+)">\s*$')
LEAF = re.compile(r'^(\s*)<avp name="([^"]+)" value="([^"]*)">\s*</avp>\s*$')
END = re.compile(r"^\s*</avp>\s*$")


@dataclass
class Frame:
    """An open group AVP and how many AVPs of each name it has held so far."""

    name: str
    position: int
    counts: dict[str, int] = field(default_factory=dict)

    def next_position(self, name: str) -> int:
        """Count another child of this name and return its position, from 1."""
        self.counts[name] = self.counts.get(name, 0) + 1
        return self.counts[name]


@dataclass
class Leaf:
    """An <avp> element with a value: its line, name, value, and path.

    The path has one (name, name, position) entry for each enclosing group and one for
    the AVP itself, the shape that scenario_options.lookup takes.
    """

    index: int
    indent: str
    name: str
    value: str
    path: list[tuple[str, str, int]]


def client_files(paths: list[Path]) -> list[Path]:
    """Return the files as they are, and the *.client.xml files of each folder."""
    files: list[Path] = []
    for path in paths:
        files += sorted(path.glob("*.client.xml")) if path.is_dir() else [path]
    return files


def command_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Return (first body line, end line) of each <command> that spans lines."""
    ranges = []
    start = None
    for number, line in enumerate(lines):
        if "<command " in line and "</command>" not in line:
            start = number + 1
        elif "</command>" in line and start is not None:
            ranges.append((start, number))
            start = None
    return ranges


def leaves(lines: list[str], start: int, end: int) -> list[Leaf]:
    """Return the <avp> elements with a value in lines[start:end], in order."""
    frames = [Frame("", 1)]
    found = []
    for number in range(start, end):
        line = lines[number]
        group = GROUP.match(line)
        leaf = LEAF.match(line)
        if END.match(line) and len(frames) > 1:
            frames.pop()
        elif group:
            position = frames[-1].next_position(group.group(2))
            frames.append(Frame(group.group(2), position))
        elif leaf:
            indent, name, value = leaf.groups()
            position = frames[-1].next_position(name)
            path = [(f.name, f.name, f.position) for f in frames[1:]]
            found.append(
                Leaf(number, indent, name, value, [*path, (name, name, position)])
            )
    return found
