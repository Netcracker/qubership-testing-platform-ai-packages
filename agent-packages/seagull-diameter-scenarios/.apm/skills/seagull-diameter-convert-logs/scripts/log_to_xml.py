"""Write each Diameter message of a Seagull log to its own XML file.

Usage:
  python log_to_xml.py LOG [--out FOLDER] [--numbering step|sequence]
                          [--format avp|steps] [--pretty | --no-pretty]
                          [--dictionary FILE]

Seagull logs every message twice: as a tree of AVPs and as hex bytes. This script reads the
tree, the lines that carry the `|M|` mark, and writes one XML file for each message. The file
is named NNN_sent_CCR.xml or NNN_received_CCA.xml: the number, the direction, and the command.

The log shows an answer under the name of its request (CCR), because both share one
dictionary command. The script names an answer by its flags: the R bit is not set, so a name
that ends in R ends in A (CCA).

--numbering step (the default) gives a request and its answer one number. An answer belongs to
the open request of the opposite direction with the same cmd-code, Hop-by-Hop, and End-to-End
identifiers. An answer without such a request, and any request, starts a new number.
--numbering sequence numbers the messages in the order of the log, so a received DWR that
comes before the sent DWA shows in the numbers.

--format avp (the default) writes a <message> element with a <header> and one <avp> element for
each AVP, with its code, flags, vendor, and value as attributes. --format steps writes the form of
the recorded steps that the scenario generator reads: the command is the root element, each AVP is
an element named as in the log, and a grouped AVP holds its members. The leading 3GPP of an AVP
name becomes TGPP, because an XML name cannot start with a digit. The attributes Description and
Service of the root belong to the system that recorded the steps, and the log does not have them.

The values come from the Seagull dictionary, because the log shows them as Seagull printed them:
a Time as seconds since 1900, an Enumerated as a number, an Address as bytes. The dictionary is
the file that the line option_dico_file of the log names, which is the one Seagull ran with; the
script uses it without a word. When that file does not exist on this machine, the script says so
on stderr and takes the file of --dictionary, and says so; without a usable --dictionary it
stops with status 3 and writes nothing. The definition of an AVP is found by its code and
vendor. A Time is written as a date, an Address as an IP address, a UTF8String or a
DiameterIdentity as text, and an Enumerated as the name of its value, when the dictionary lists
the names in a "values:" comment above the definition, as the dictionary converter writes them;
otherwise it stays a number. An OctetString has no rule in the dictionary: printable bytes are
text, any other bytes are 0x followed by hex. An AVP that the dictionary does not define is
written the same way, and the script lists such AVPs on stderr. --dictionary has no effect on
--format avp, or when the dictionary of the log exists, and the script says so.

--pretty (the default) indents the XML; --no-pretty writes it on one line.

--out must be a new or an empty folder. Without it, the script writes a new folder next to
the log, named after the log with the suffix -xml.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import ipaddress
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
COMMON = Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"
sys.path.insert(0, str(COMMON))
output_folder = importlib.import_module("output_folder")
seagull_dictionary = importlib.import_module("seagull_dictionary")

START = re.compile(r"^(\S+)\|M\|(Send|Received) \[\[(\S+)")
BODY = re.compile(r"^\s+\|M\|(.*)$")
HEADER = re.compile(r"^\[([\w-]+)\] = \[\s*(-?\d+)\]$")
AVP_START = re.compile(r"^\[([^\s\]]+)$")
AVP_ATTRS = re.compile(
    r"^\(avp-code = (\d+)\)\(flags = (\d+)\)(?:\(Vendor-ID = (\d+)\))?\] = \[(.*)$",
)
HEX = re.compile(r"^(?:[0-9a-fA-F]{2}\s*)+$")
REQUEST_BIT = 0x80
MIN_DIGITS = 3
DICTIONARY_LINE = re.compile(r"^\s*\|\s*\|option_dico_file\s+\[(.*)\]\s*$")
NTP_EPOCH = datetime(1900, 1, 1, tzinfo=timezone.utc)
ADDRESS_TYPES = frozenset({"Address", "IPAddress"})
TEXT_TYPES = frozenset({"UTF8String", "DiameterIdentity", "DiameterURI", "IPFilterRule"})
IPV4_FAMILY = 1
IPV6_FAMILY = 2
EXIT_NO_MESSAGES = 1
EXIT_BAD_ARGUMENTS = 2
EXIT_NO_DICTIONARY = 3


@dataclass
class Avp:
    """An AVP of the log: its attributes, and a value or children."""

    name: str
    code: str
    flags: str
    vendor: str
    value: str | None = None
    hex_bytes: list[str] = field(default_factory=list)
    children: list[Avp] = field(default_factory=list)


@dataclass
class Message:
    """A message of the log, with the number and the file name it gets."""

    time: str
    direction: str
    logged_name: str
    header: dict[str, str]
    avps: list[Avp]
    step: int = 0
    sequence: int = 0

    @property
    def is_request(self) -> bool:
        """Return True when the R bit of the flags is set."""
        return int(self.header.get("flags", "0")) & REQUEST_BIT != 0

    @property
    def name(self) -> str:
        """Return the command name, with an answer named CCA and not CCR."""
        if not self.is_request and self.logged_name.endswith("R"):
            return self.logged_name[:-1] + "A"
        return self.logged_name


class BodyParser:
    """Read the lines of one message, after the mark `|M|`, into a header and AVPs."""

    def __init__(self) -> None:
        """Start with an empty message."""
        self.header: dict[str, str] = {}
        self.roots: list[Avp] = []
        self.stack: list[Avp] = []
        self.pending = ""

    def feed(self, line: str) -> None:
        """Take one line of the message body."""
        text = line.lstrip(" |").rstrip()
        header = HEADER.match(text)
        start = AVP_START.match(text)
        attrs = AVP_ATTRS.match(text)
        if header:
            self.header[header.group(1)] = header.group(2)
        elif start:
            self.pending = start.group(1)
        elif attrs:
            self.open_avp(attrs.groups())
        elif text and set(text) == {"]"}:
            for _ in text:
                if self.stack:
                    self.stack.pop()
        elif self.stack and HEX.match(text):
            self.stack[-1].hex_bytes.extend(text.split())

    def open_avp(self, attrs: tuple[str, ...]) -> None:
        """Add the AVP whose name came on the line before, and keep it open if it has more."""
        code, flags, vendor, rest = attrs
        avp = Avp(self.pending, code, flags, vendor or "")
        (self.stack[-1].children if self.stack else self.roots).append(avp)
        if rest.strip():
            avp.value = rest.strip().removesuffix("]").strip()
        else:
            self.stack.append(avp)


def read_messages(lines: list[str]) -> Iterator[Message]:
    """Yield the messages of the log in order; a block that has no header is skipped."""
    index = 0
    while index < len(lines):
        start = START.match(lines[index])
        index += 1
        if not start:
            continue
        parser = BodyParser()
        while index < len(lines) and BODY.match(lines[index]):
            parser.feed(BODY.match(lines[index]).group(1))  # type: ignore[union-attr]
            index += 1
        if "flags" not in parser.header or "cmd-code" not in parser.header:
            sys.stderr.write(f"skipped a message without a header at {start.group(1)}\n")
            continue
        direction = "sent" if start.group(2) == "Send" else "received"
        yield Message(start.group(1), direction, start.group(3), parser.header, parser.roots)


def number_messages(messages: list[Message], numbering: str) -> None:
    """Set the step and the sequence number of every message."""
    open_requests: dict[tuple[str, str, str, str], int] = {}
    step = 0
    for sequence, message in enumerate(messages, start=1):
        message.sequence = sequence
        header = message.header
        ids = (header.get("HbH-id", ""), header.get("EtE-id", ""), header["cmd-code"])
        opposite = "received" if message.direction == "sent" else "sent"
        if message.is_request:
            step += 1
            open_requests[(*ids, message.direction)] = step
            message.step = step
        elif (*ids, opposite) in open_requests:
            message.step = open_requests.pop((*ids, opposite))
        else:
            step += 1
            message.step = step
    if numbering == "sequence":
        for message in messages:
            message.step = message.sequence


def safe_name(name: str) -> str:
    """Return the name with every character that a file name dislikes replaced."""
    return re.sub(r"[^\w.-]", "_", name)


def file_name(message: Message, digits: int) -> str:
    """Return NNN_sent_CCR.xml for a message."""
    return f"{message.step:0{digits}d}_{message.direction}_{safe_name(message.name)}.xml"


def printable(hex_bytes: list[str]) -> str | None:
    """Return the bytes as text when every one is a printable ASCII character."""
    data = bytes(int(item, 16) for item in hex_bytes)
    if data and all(0x20 <= byte < 0x7F for byte in data):
        return data.decode("ascii")
    return None


def avp_element(avp: Avp) -> ElementTree.Element:
    """Return the XML element of an AVP, with its children inside."""
    attrs = {"name": avp.name, "code": avp.code, "flags": avp.flags}
    if avp.vendor:
        attrs["vendor-id"] = avp.vendor
    if avp.value is not None:
        attrs["value"] = avp.value
    if avp.hex_bytes:
        attrs["hex"] = " ".join(avp.hex_bytes)
        text = printable(avp.hex_bytes)
        if text is not None:
            attrs["text"] = text
    element = ElementTree.Element("avp", attrs)
    element.extend(avp_element(child) for child in avp.children)
    return element


def message_element(message: Message) -> ElementTree.Element:
    """Return the XML element of a message: its attributes, the header, and the AVPs."""
    root = ElementTree.Element(
        "message",
        {
            "name": message.name,
            "direction": message.direction,
            "step": str(message.step),
            "sequence": str(message.sequence),
            "time": message.time,
        },
    )
    ElementTree.SubElement(root, "header", message.header)
    root.extend(avp_element(avp) for avp in message.avps)
    return root


def steps_name(name: str) -> str:
    """Return an XML element name for an AVP name: 3GPP-X becomes TGPP-X."""
    name = re.sub(r"^3GPP", "TGPP", name)
    return name if re.match(r"[A-Za-z_]", name) else f"_{name}"


def guess_text(hex_bytes: list[str]) -> str:
    """Return bytes as text when all are printable, otherwise as 0x and hex digits."""
    if not hex_bytes:
        return ""
    text = printable(hex_bytes)
    return text if text is not None else "0x" + "".join(hex_bytes).lower()


def decode_address(data: bytes) -> str | None:
    """Return the IP address of an Address value (the family, then the bytes), or None."""
    family = int.from_bytes(data[:2], "big")
    packed = data[2:]
    if (family, len(packed)) in ((IPV4_FAMILY, 4), (IPV6_FAMILY, 16)):
        return str(ipaddress.ip_address(packed))
    return None


def decode_text(data: bytes) -> str | None:
    """Return the UTF-8 text of the bytes, or None when it is not printable text."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text.isprintable() else None


def ntp_date(seconds: int) -> str:
    """Return seconds since 1900 as a date such as 2026-10-27 14:00:52 +0000 UTC."""
    moment = NTP_EPOCH + timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%d %H:%M:%S +0000 UTC")


class Decoder:
    """Write the value of a leaf AVP as the recorded steps do, by its dictionary type."""

    def __init__(self, definitions: dict[tuple[int, int], Any]) -> None:
        """Take the definitions of a Seagull dictionary, by (vendor, code)."""
        self.definitions = definitions
        self.unknown: set[str] = set()

    def text(self, avp: Avp) -> str:
        """Return the value of a leaf AVP."""
        definition = self.definitions.get((int(avp.vendor or 0), int(avp.code)))
        if definition is None:
            self.unknown.add(avp.name)
            return avp.value if avp.value is not None else guess_text(avp.hex_bytes)
        if avp.value is not None:
            return self.number(avp.value, definition)
        data = bytes(int(item, 16) for item in avp.hex_bytes)
        decoded = None
        if definition.type_name in ADDRESS_TYPES:
            decoded = decode_address(data)
        elif definition.type_name in TEXT_TYPES:
            decoded = decode_text(data)
        return decoded if decoded is not None else guess_text(avp.hex_bytes)

    @staticmethod
    def number(value: str, definition: Any) -> str:
        """Return a Time as a date and an Enumerated as its value name, when it has one."""
        if definition.type_name == "Time" and value.isdigit():
            return ntp_date(int(value))
        names = {number: name for name, number in definition.enums}
        return names.get(value, value)


def steps_avp(avp: Avp, decoder: Decoder) -> ElementTree.Element:
    """Return the element of an AVP in the form of the recorded steps."""
    element = ElementTree.Element(steps_name(avp.name))
    if avp.children:
        element.extend(steps_avp(child, decoder) for child in avp.children)
    else:
        element.text = decoder.text(avp)
    return element


def steps_element(message: Message, decoder: Decoder) -> ElementTree.Element:
    """Return the command of a message in the form of the recorded steps."""
    root = ElementTree.Element(steps_name(message.name))
    root.extend(steps_avp(avp, decoder) for avp in message.avps)
    return root


def dictionary_path_of(lines: list[str]) -> str | None:
    """Return the path in the line option_dico_file of the log header, or None."""
    for line in lines:
        found = DICTIONARY_LINE.match(line)
        if found:
            return found.group(1)
        if START.match(line):
            break
    return None


def choose_dictionary(logged: str | None, given: Path | None) -> Path | None:
    """Return the dictionary file for the steps format, or None when there is none.

    The file that the log names is the one Seagull ran with, so it wins and is used without a
    word. Each other case says on stderr what happened.
    """
    if logged and Path(logged).is_file():
        if given:
            sys.stderr.write("--dictionary is ignored: the dictionary of the log exists\n")
        return Path(logged)
    sys.stderr.write(
        f"the dictionary of the log, {logged}, does not exist on this machine\n"
        if logged
        else "the log names no dictionary (option_dico_file)\n"
    )
    if given and given.is_file():
        sys.stderr.write(f"using the dictionary of --dictionary: {given}\n")
        return given
    if given:
        sys.stderr.write(f"--dictionary {given} is not a file\n")
    return None


def write_messages(
    messages: list[Message],
    folder: Path,
    xml_format: str,
    pretty: bool,
    decoder: Decoder | None,
) -> list[Path]:
    """Write one XML file for each message into the folder; return the paths."""
    folder.mkdir(parents=True, exist_ok=True)
    digits = max(MIN_DIGITS, len(str(max(item.step for item in messages))))
    paths = []
    for message in messages:
        root = steps_element(message, decoder) if decoder else message_element(message)
        if pretty:
            ElementTree.indent(root)
        path = folder / file_name(message, digits)
        declaration = xml_format != "steps"
        ElementTree.ElementTree(root).write(path, encoding="utf-8", xml_declaration=declaration)
        paths.append(path)
    return paths


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Return the arguments of the command line."""
    parser = argparse.ArgumentParser(
        description="Write each Diameter message of a Seagull log to an XML file.",
    )
    parser.add_argument("log", type=Path, help="the Seagull log, for example *.client")
    parser.add_argument("--out", type=Path, help="a new or empty folder; default: next to the log")
    parser.add_argument(
        "--numbering",
        choices=("step", "sequence"),
        default="step",
        help="step: a request and its answer share a number; sequence: the log order",
    )
    parser.add_argument(
        "--format",
        choices=("avp", "steps"),
        default="avp",
        help="avp: a message with a header and AVP elements; steps: the form of the recorded steps",
    )
    parser.add_argument(
        "--pretty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="indent the XML (default); --no-pretty writes it on one line",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="steps format: the dictionary to use when the file that the log names is missing",
    )
    return parser.parse_args(argv)


def make_decoder(args: argparse.Namespace, lines: list[str]) -> Decoder | int | None:
    """Return the decoder of the steps format, None for the avp format, or an exit status."""
    if args.format != "steps":
        if args.dictionary:
            sys.stderr.write("--dictionary is ignored: the avp format does not use a dictionary\n")
        return None
    path = choose_dictionary(dictionary_path_of(lines), args.dictionary)
    if path is None:
        sys.stderr.write("no dictionary for --format steps; nothing was written\n")
        return EXIT_NO_DICTIONARY
    return Decoder(seagull_dictionary.read_by_code(path))


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    args = parse_arguments(argv)
    if not args.log.is_file():
        sys.stderr.write(f"{args.log} is not a file\n")
        return EXIT_BAD_ARGUMENTS
    folder = args.out or output_folder.next_free(args.log.parent, f"{args.log.name}-xml")
    if not output_folder.is_empty(folder):
        sys.stderr.write(f"{output_folder.describe(folder)}; give a new or empty one\n")
        return EXIT_BAD_ARGUMENTS
    lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    messages = list(read_messages(lines))
    if not messages:
        sys.stderr.write(f"no Diameter message in {args.log}\n")
        return EXIT_NO_MESSAGES
    decoder = make_decoder(args, lines)
    if isinstance(decoder, int):
        return decoder
    number_messages(messages, args.numbering)
    paths = write_messages(messages, folder, args.format, args.pretty, decoder)
    if decoder and decoder.unknown:
        names = ", ".join(sorted(decoder.unknown))
        sys.stderr.write(f"not in the dictionary, written by their bytes: {names}\n")
    sys.stdout.write(f"wrote {len(paths)} file(s) to {folder}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
