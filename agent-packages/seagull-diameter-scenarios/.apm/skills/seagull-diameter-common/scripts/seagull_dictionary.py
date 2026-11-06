"""Read what a scenario generator needs from a dictionary in the Seagull format.

read_dictionary returns the root element, for the commands. read_definitions returns the AVP
definitions of each name: the vendor, the code, the type, and the values of an enumeration. The
converter dict2seagull.py writes the values as a comment above the definition, for example
"values: INITIAL_REQUEST=1, UPDATE_REQUEST=2"; a dictionary that has no such comment has no
values.

Requires Python 3.9 or later and nothing outside the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

VALUES_PREFIX = "values:"


@dataclass
class Definition:
    """One definition of an AVP name in a Seagull dictionary."""

    name: str
    vendor_id: int
    code: int
    type_name: str
    enums: list[tuple[str, str]] = field(default_factory=list)


def _body(path: Path) -> str:
    """Return the text from <protocol on; a comment may come before the declaration."""
    text = path.read_text(encoding="iso-8859-1")
    _, marker, body = text.partition("<protocol")
    return marker + body


def read_dictionary(path: Path) -> ElementTree.Element:
    """Parse a Seagull dictionary, which may have a comment before the declaration."""
    return ElementTree.fromstring(_body(path))


def parse_values(text: str) -> list[tuple[str, str]]:
    """Return the (name, number) pairs of a comment such as 'NAME=1, OTHER=2'."""
    pairs = []
    for item in text.split(","):
        name, separator, number = item.strip().partition("=")
        if separator and name.strip():
            pairs.append((name.strip(), number.strip()))
    return pairs


def read_definitions(path: Path) -> dict[str, list[Definition]]:
    """Return {AVP name: [definitions]} in file order; a repeat of a vendor and code is dropped."""
    parser = ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True))
    parser.feed(_body(path))
    root = parser.close()
    by_name: dict[str, list[Definition]] = {}
    for avp in root.findall("./dictionary/avp"):
        values: list[tuple[str, str]] = []
        for child in avp:
            if child.tag is ElementTree.Comment:
                comment = (child.text or "").strip()
                if comment.startswith(VALUES_PREFIX):
                    values = parse_values(comment.removeprefix(VALUES_PREFIX))
            elif child.tag == "define":
                fields = {s.get("name"): s.get("value") for s in child.findall("setfield")}
                definition = Definition(
                    name=child.get("name", ""),
                    vendor_id=int(fields.get("Vendor-ID") or 0),
                    code=int(fields.get("avp-code") or 0),
                    type_name=child.get("type", ""),
                    enums=values,
                )
                values = []
                known = by_name.setdefault(definition.name, [])
                identities = {(d.vendor_id, d.code) for d in known}
                if (definition.vendor_id, definition.code) not in identities:
                    known.append(definition)
    return by_name


def command_names_of(root: ElementTree.Element) -> set[str]:
    """Return the names of the commands that a Seagull dictionary defines."""
    return {d.get("name", "") for d in root.findall("./dictionary/command/define")}
