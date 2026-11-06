"""Read what a scenario generator needs from a dictionary in the Seagull format.

The functions take the root element that read_dictionary returns. They list the AVP names of a
vendor and a code, the vendor and the code that Seagull uses for a name, and the commands.

Requires Python 3.9 or later and nothing outside the standard library.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree


def read_dictionary(path: Path) -> ElementTree.Element:
    """Parse a Seagull dictionary, which may have a comment before the declaration."""
    text = path.read_text(encoding="iso-8859-1")
    _, marker, body = text.partition("<protocol")
    return ElementTree.fromstring(marker + body)


def avp_keys(root: ElementTree.Element) -> list[tuple[str, tuple[int, int]]]:
    """Return the name and the (vendor, code) of every AVP definition, in file order."""
    keys = []
    for define in root.findall("./dictionary/avp/define"):
        fields = {s.get("name"): s.get("value") for s in define.findall("setfield")}
        key = (int(fields.get("Vendor-ID") or 0), int(fields.get("avp-code") or 0))
        keys.append((define.get("name", ""), key))
    return keys


def avp_names_of(root: ElementTree.Element) -> dict[tuple[int, int], list[str]]:
    """Return {(vendor, code): [Seagull AVP names]} of a Seagull dictionary."""
    names: dict[tuple[int, int], list[str]] = {}
    for name, key in avp_keys(root):
        names.setdefault(key, []).append(name)
    return names


def first_definitions(root: ElementTree.Element) -> dict[str, tuple[int, int]]:
    """Return {AVP name: (vendor, code)} of the first definition of each name.

    Seagull finds an AVP by name and uses the first definition of a name for every use of it.
    """
    first: dict[str, tuple[int, int]] = {}
    for name, key in avp_keys(root):
        first.setdefault(name, key)
    return first


def command_names_of(root: ElementTree.Element) -> set[str]:
    """Return the names of the commands that a Seagull dictionary defines."""
    return {d.get("name", "") for d in root.findall("./dictionary/command/define")}
