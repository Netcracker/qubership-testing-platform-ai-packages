"""Compare the AVP definitions of a converted dictionary with a Seagull dictionary.

Usage: python compare_with_seagull.py CONVERTED.xml SEAGULL.xml

AVPs are matched by name. The script prints those that exist in both and differ in
code, flags, vendor, or in being grouped. It also prints the names that only the
Seagull dictionary has.

Requires Python 3.9 or later and nothing outside the standard library.
"""

import sys
from xml.etree import ElementTree

# code, flags, vendor id, is grouped
Definition = tuple[int, int, int, bool]


def load(path: str) -> dict[str, list[Definition]]:
    """Return the AVP definitions of a Seagull dictionary, by name."""
    # The dictionaries shipped with Seagull put a comment before the XML declaration,
    # which a strict XML parser rejects. Seagull's own parser accepts it, so parse
    # from the root element on.
    with open(path, encoding="iso-8859-1") as source:
        text = source.read()
    _, marker, body = text.partition("<protocol")
    root = ElementTree.fromstring(marker + body)
    avps: dict[str, list[Definition]] = {}
    for define in root.findall("./dictionary/avp/define"):
        fields = {s.get("name"): s.get("value") for s in define.findall("setfield")}
        avps.setdefault(define.get("name", ""), []).append(
            (
                int(fields["avp-code"] or 0),
                int(fields["flags"] or 0),
                int(fields.get("Vendor-ID") or 0),
                define.get("type") == "Grouped",
            )
        )
    return avps


def describe(converted: Definition, seagull: Definition, repeated: int) -> list[str]:
    """Return what differs between two definitions of the same AVP name."""
    notes = []
    for label, index in (("code", 0), ("flags", 1), ("vendor", 2), ("grouped", 3)):
        if converted[index] != seagull[index]:
            notes.append(f"{label} {converted[index]} vs {seagull[index]}")
    if repeated > 1:
        notes.append(f"Seagull defines it {repeated} times")
    return notes


def main(converted_path: str, seagull_path: str) -> None:
    """Print the comparison."""
    converted, seagull = load(converted_path), load(seagull_path)
    common = sorted(set(converted) & set(seagull))
    print(f"converted: {len(converted)} AVPs, Seagull: {len(seagull)} AVPs")
    print(f"in both by name: {len(common)}")
    differences = 0
    for name in common:
        notes = describe(converted[name][0], seagull[name][0], len(seagull[name]))
        if notes:
            differences += 1
            print(f"  {name}: " + "; ".join(notes))
    print(f"AVPs that differ: {differences}")
    only_seagull = sorted(set(seagull) - set(converted))
    print("only in Seagull:", ", ".join(only_seagull) or "none")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
