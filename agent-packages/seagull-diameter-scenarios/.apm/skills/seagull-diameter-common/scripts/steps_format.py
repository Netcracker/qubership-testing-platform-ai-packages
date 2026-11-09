"""Read a folder of recorded Diameter steps.

The folder holds one request file and one response file for each step. By default they are
Step-NNN-request.txt and Step-NNN-response.txt; two name templates, such as request_NN.xml and
response_NN.xml, say otherwise. The text of a message is a Diameter command as XML: the root element
is the command (CCR, CCA, ...) and each child is an AVP, for example:

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

DEFAULT_REQUEST_NAME = "Step-NNN-request.txt"
DEFAULT_RESPONSE_NAME = "Step-NNN-response.txt"
NUMBER_MARK = re.compile(r"N{2,}")
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


def name_pattern(template: str) -> re.Pattern[str]:
    """Return the regular expression of a file name template.

    The template is a file name with the step number written as two or more capital N, for
    example request_NN.xml. The number may have any width: request_1.xml and request_01.xml
    both match. Every other character stands for itself.
    """
    parts = NUMBER_MARK.split(template)
    if len(parts) != 2:
        raise ValueError(f"{template!r}: write the step number once, as NN (two or more capital N)")
    return re.compile("^" + re.escape(parts[0]) + r"(\d+)" + re.escape(parts[1]) + "$")


def normal(number: str) -> str:
    """Return the number without leading zeros, so that 01 and 1 are one step."""
    return str(int(number)) if number.isdigit() else number


def find_pairs(
    folder: Path,
    request_name: str = DEFAULT_REQUEST_NAME,
    response_name: str = DEFAULT_RESPONSE_NAME,
) -> tuple[dict[str, dict[str, Path]], list[str]]:
    """Return {number: {"request": path, "response": path}} and the file problems.

    The two templates say which files are requests and which are responses, and where the number
    is in the name; see name_pattern. The number in the result is the one in the first file seen.
    """
    if request_name == response_name:
        raise ValueError("the request and the response need different file name templates")
    patterns = {"request": name_pattern(request_name), "response": name_pattern(response_name)}
    pairs: dict[str, dict[str, Path]] = {}
    labels: dict[str, str] = {}
    problems: list[str] = []
    for path in sorted(folder.iterdir()):
        for kind, pattern in patterns.items():
            match = pattern.match(path.name)
            if not match:
                continue
            number = labels.setdefault(normal(match.group(1)), match.group(1))
            if kind in pairs.setdefault(number, {}):
                problems.append(f"{path.name}: step {number} already has the file {pairs[number][kind].name}")
            else:
                pairs[number][kind] = path
            break
        else:
            if path.name != INDEX_NAME:
                problems.append(f"{path.name}: not a {request_name} or {response_name} file")
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
            index[normal(row["Step file number"])] = row.get("Step number in the scenario", "")
    return index


def load_steps(
    folder: Path,
    request_name: str = DEFAULT_REQUEST_NAME,
    response_name: str = DEFAULT_RESPONSE_NAME,
) -> tuple[list[Step], list[str]]:
    """Read every complete pair of the folder; return the steps and the problems."""
    pairs, problems = find_pairs(folder, request_name, response_name)
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
        steps.append(Step(number, request, response, index.get(normal(number), "")))
    return steps, problems
