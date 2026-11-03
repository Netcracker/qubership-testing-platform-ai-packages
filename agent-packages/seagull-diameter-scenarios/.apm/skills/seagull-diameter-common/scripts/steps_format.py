"""Read a folder of recorded Diameter steps.

The folder holds Step-NNN-request.txt and Step-NNN-response.txt. The text of a
message is a Diameter command as XML: the root element is the command (CCR, CCA,
...) and each child is an AVP, for example:

    <CCR><Session-Id>x</Session-Id><Auth-Application-Id>4</Auth-Application-Id></CCR>

Attributes of the root element are settings of the test platform, not AVPs.

The reader repairs two faults of hand-edited text and reports each repair:
comments (the AVPs inside them were not part of the message) and closing tags
without ">". Run check_steps.py to check a folder.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

FILE_PATTERN = re.compile(r"Step-(\d+)-(request|response)\.txt$")
INDEX_NAME = "Steps-index.csv"
COMMENT_END = re.compile(r"--\s*>|--(?=\s*<)")


@dataclass
class Message:
    """One parsed message and what was repaired to parse it."""

    path: Path
    root: ElementTree.Element
    repairs: list[str] = field(default_factory=list)

    @property
    def command(self) -> str:
        """Return the name of the command: the tag of the root element."""
        return self.root.tag

    def avp_text(self, name: str) -> str | None:
        """Return the text of a top-level AVP, or None when it is absent."""
        element = self.root.find(name)
        return None if element is None else (element.text or "").strip()


@dataclass
class Step:
    """A request with its response."""

    number: str
    request: Message
    response: Message
    platform_number: str = ""

    @property
    def session_id(self) -> str:
        """Return the Session-Id of the request."""
        return self.request.avp_text("Session-Id") or ""

    @property
    def label(self) -> str:
        """Return the Description attribute of the request, such as CCR-I."""
        return self.request.root.get("Description", self.request.command)


def strip_comments(text: str) -> tuple[str, int, int]:
    """Remove comments, also when the closing ">" is missing before the next tag.

    Return the text, the number of comments removed, and how many of them had no
    closing ">".
    """
    out: list[str] = []
    position, removed, broken = 0, 0, 0
    while True:
        start = text.find("<!--", position)
        if start < 0:
            out.append(text[position:])
            break
        out.append(text[position:start])
        end = COMMENT_END.search(text, start + 4)
        if end is None:
            raise ValueError("a comment is never closed")
        broken += not end.group(0).endswith(">")
        removed += 1
        position = end.end()
    return "".join(out), removed, broken


def repair(text: str) -> tuple[str, list[str]]:
    """Return the text as well-formed XML, and a list of what was repaired."""
    repairs: list[str] = []
    text, removed, broken = strip_comments(text)
    if removed:
        note = f"{removed} commented-out AVP(s) left out"
        if broken:
            note += f" ({broken} comment end without '>')"
        repairs.append(note)
    text, closing = re.subn(r"</([A-Za-z0-9_.-]+)(?=\s*<)", r"</\1>", text)
    if closing:
        repairs.append(f"{closing} closing tag(s) without '>' repaired")
    return text, repairs


def parse_message(path: Path) -> Message:
    """Parse a message file; raise ValueError if it is not XML after the repairs."""
    fixed, repairs = repair(path.read_text(encoding="utf-8"))
    try:
        root = ElementTree.fromstring(fixed)
    except ElementTree.ParseError as error:
        raise ValueError(f"{path.name}: not well-formed XML ({error})") from error
    return Message(path, root, repairs)


def find_pairs(folder: Path) -> tuple[dict[str, dict[str, Path]], list[str]]:
    """Return {number: {"request": path, "response": path}} and the file problems."""
    pairs: dict[str, dict[str, Path]] = {}
    problems: list[str] = []
    for path in sorted(folder.iterdir()):
        match = FILE_PATTERN.match(path.name)
        if match:
            pairs.setdefault(match.group(1), {})[match.group(2)] = path
        elif path.name != INDEX_NAME:
            problems.append(f"{path.name}: not a Step-NNN-request/response.txt file")
    for number, files in pairs.items():
        for kind in ("request", "response"):
            if kind not in files:
                problems.append(f"step {number}: the {kind} file is missing")
    return pairs, problems


def read_index(folder: Path) -> dict[str, str]:
    """Return {step file number: number in the source} from the index file."""
    path = folder / INDEX_NAME
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    index: dict[str, str] = {}
    for row in rows:
        if "Step file number" in row:
            index[row["Step file number"]] = row.get("Step number in the scenario", "")
    return index


def load_steps(folder: Path) -> tuple[list[Step], list[str]]:
    """Read every complete pair of the folder; return the steps and the problems."""
    pairs, problems = find_pairs(folder)
    index = read_index(folder)
    steps: list[Step] = []
    for number in sorted(pairs, key=int):
        files = pairs[number]
        if len(files) < 2:
            continue
        try:
            request = parse_message(files["request"])
            response = parse_message(files["response"])
        except ValueError as error:
            problems.append(str(error))
            continue
        steps.append(Step(number, request, response, index.get(number, "")))
    return steps, problems
