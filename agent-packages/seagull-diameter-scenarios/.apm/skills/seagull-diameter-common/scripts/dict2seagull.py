"""Convert the project's Diameter dictionaries into the dictionary format of Seagull.

The project keeps its Diameter dictionaries in a folder. AVP dictionaries have the
root element <dictionary>. Command dictionaries have the root element
<diameter-command-dictionary>. Seagull reads one dictionary file per run, in its own
format (<protocol> with <dictionary><avp><define> and <command><define>), and takes one
dictionary file for each run. So by default the script writes ONE Seagull dictionary,
diameter-dictionary.xml, made of all the AVP dictionaries and the base protocol.
--combine no writes one dictionary for each AVP dictionary instead, and --combine A,B
writes only one merged from the named dictionaries, in that order, as A+B.xml. When
several dictionaries define the same AVP name, the first one keeps it.

The base protocol is DiameterBaseProtocol.xml when the folder has it; otherwise it is the
dictionary that defines the handshake commands, whatever its file is called. Either way
the folder must define by code the commands 257 (CER) and 280 (DWR) and the AVPs 257, 258,
263, 264, 266, 268, 269, and 296. If something is missing, nothing is written and the exit
status is 2. --seagull-base FILE (base_draft08.xml of Seagull) lets the missing items come
from that Seagull dictionary; the user's dictionaries win wherever they define the name or
the code, and the report says what was added.

Converted:
  * Each <avp> becomes a <define> with avp-code and flags. The V bit comes from
    vendor-specific="yes", M from mandatory="must", and P from protected="must".
    A vendor AVP also gets Vendor-ID.
  * Each <command> of <base> and <application> becomes a request and an answer
    definition (CER and CEA, CCR and CCA, ...) with cmd-code, flags, application-id
    and protocol-version.
  * The <types>, <header> and <body> sections are those of the dictionaries that ship
    with Seagull.

An AVP keeps the name of its type (Time, Address, UTF8String, Enumerated, ...). The output
defines a <typedef> for each type in use, so a reader of the dictionary and the generator of
scenarios still know what the value is. An AVP name that two dictionaries define with
another vendor or code is not renamed: both definitions are written, Seagull uses the first
for every use of the name, and the report says so.

Lost, because Seagull has no place for it: enumeration values, group members and
multiplicities. The first two are kept as XML comments. The *Commands.xml files, which
list the AVPs of each command, are only used to check that no command is missing.

AVP names: the project writes the vendor prefix of 3GPP AVPs as TGPP-, while the 3GPP
specifications and Seagull write 3GPP-. The script writes 3GPP- unless --keep-tgpp is
given.

Flags: the project dictionaries give no flags for a command, so a request gets 128 (R) and an
answer 0, and an AVP gets the M and P bits that its source gives. --command-flags,
--avp-flags, --vendor-mandatory, and --options change that; see dictionary_options.py. The
options in effect are written to dictionary-options.ini in the output folder.

Requires Python 3.9 or later and nothing outside the standard library.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
dictionary_options = importlib.import_module("dictionary_options")

BASE_NAME = "DiameterBaseProtocol"
ALL_NAME = "diameter-dictionary"  # the output made of all the dictionaries
Job = tuple[str, list[str]]  # the name of an output, and the dictionaries it is made from
OPTIONS_NAME = "dictionary-options.ini"
# What the handshake and the header of a Seagull dictionary need of the base protocol (RFC 6733).
# They are found by code, because the file that holds them may have any name.
BASE_AVPS = {
    257: "Host-IP-Address",
    258: "Auth-Application-Id",
    263: "Session-Id",
    264: "Origin-Host",
    266: "Vendor-Id",
    268: "Result-Code",
    269: "Product-Name",
    296: "Origin-Realm",
}
BASE_COMMANDS = {257: "CER/CEA", 280: "DWR/DWA"}
BUNDLED_BASE = "base_draft08.xml"  # in diameter-env/config of Seagull

# How Seagull encodes each type of the project dictionaries: its kind and size in octets. An
# AVP keeps the name of its own type, and the output defines a <typedef> for each type in use,
# as the dictionaries of projects do. Time is an unsigned number: a signed one holds only up
# to 2^31, which is before NTP times of today.
TYPE_KINDS = {
    "Integer32": ("signed", 4),
    "Integer64": ("signed64", 8),
    "Unsigned32": ("number", 4),
    "Unsigned64": ("number64", 8),
    "Enumerated": ("signed", 4),
    "Time": ("number", 4),
    "OctetString": ("string", 4),
    "UTF8String": ("string", 4),
    "DiameterIdentity": ("string", 4),
    "DiameterURI": ("string", 4),
    "IPFilterRule": ("string", 4),
    "QoSFilterRule": ("string", 4),
    "Address": ("string", 4),
    "IPAddress": ("string", 4),
}
FALLBACK_TYPE = "OctetString"  # for an AVP without a type, or with one that is not in TYPE_KINDS

PREFIX_RENAMES = (("TGPP-", "3GPP-"),)

# Command names whose abbreviation cannot be derived from the initials.
COMMAND_ABBREVIATIONS = {"Accounting": "AC"}

HEADER = """<?xml version="1.0" encoding="ISO-8859-1"?>
<!-- Generated by dict2seagull.py from: {sources}. Do not edit; convert again. -->
<protocol name="diameter-v1" type="binary" padding="4">

  <types>
    <!-- Types defined for the AVP -->
{types}  </types>

  <header name="command" length="msg-length" type="cmd-code">
    <fielddef name="protocol-version" size="1" unit="octet"></fielddef>
    <fielddef name="msg-length" size="3" unit="octet"></fielddef>
    <fielddef name="flags" size="1" unit="octet"></fielddef>
    <fielddef name="cmd-code" size="3" unit="octet"></fielddef>
    <fielddef name="application-id" size="4" unit="octet"></fielddef>
    <fielddef name="HbH-id" size="4" unit="octet"></fielddef>
    <fielddef name="EtE-id" size="4" unit="octet"></fielddef>
  </header>

  <body>
    <header name="avp" length="avp-length" type="avp-code">
      <fielddef name="avp-code" size="4" unit="octet"></fielddef>
      <fielddef name="flags" size="1" unit="octet"></fielddef>
      <fielddef name="avp-length" size="3" unit="octet"></fielddef>
      <optional>
        <fielddef name="Vendor-ID" size="4" unit="octet"
                  condition="mask" field="flags" mask="128">
        </fielddef>
      </optional>
    </header>
  </body>

  <dictionary>
    <avp>
"""

MIDDLE = """    </avp>

    <command session-id="Session-Id" out-of-session-id="HbH-id">
"""

FOOTER = """    </command>
  </dictionary>

</protocol>
"""


@dataclass
class Avp:  # pylint: disable=too-many-instance-attributes
    """One AVP of a project dictionary."""

    vendor_id: int
    name: str
    code: int
    source: str
    vendor_specific: bool
    mandatory: bool
    protected: bool
    type_name: str | None
    members: list[str] | None
    enums: list[tuple[str, str]]

    @property
    def flags(self) -> int:
        """Return the AVP flags byte: V is 128, M is 64, P is 32."""
        flags = 128 if self.vendor_specific else 0
        flags += 64 if self.mandatory else 0
        flags += 32 if self.protected else 0
        return flags


@dataclass
class Command:
    """A command code of the base protocol or of an application."""

    application_id: int
    name: str
    code: int

    @property
    def short(self) -> str:
        """Return the prefix of the Seagull names: CC gives CCR and CCA."""
        return abbreviate(self.name)


def abbreviate(name: str) -> str:
    """Return the initials of a hyphenated command name, such as CC for Credit-Control."""
    if name in COMMAND_ABBREVIATIONS:
        return COMMAND_ABBREVIATIONS[name]
    words = name.split("-")
    if len(words) == 1:
        return name.upper()
    return "".join(word[0] for word in words).upper()


def parse_avp(vendor_id: int, element: ElementTree.Element, source: str) -> Avp:
    """Build an Avp from an <avp> element of an AVP dictionary."""
    type_element = element.find("type")
    group = element.find("grouped")
    members = None
    if group is not None:
        members = [g.get("name", "") for g in group.findall("gavp")]
    return Avp(
        vendor_id=vendor_id,
        name=element.get("name", ""),
        code=int(element.get("code", "-1")),
        source=source,
        vendor_specific=element.get("vendor-specific") == "yes",
        mandatory=element.get("mandatory") == "must",
        protected=element.get("protected") == "must",
        type_name=type_element.get("type-name") if type_element is not None else None,
        members=members,
        enums=[(e.get("name", ""), e.get("code", "")) for e in element.findall("enum")],
    )


def load_avp_dictionary(path: Path) -> tuple[list[Avp], list[Command]]:
    """Read an AVP dictionary and return its AVPs and its commands."""
    root = ElementTree.parse(path).getroot()
    if root.tag != "dictionary":
        raise ValueError(f"{path.name}: root element is <{root.tag}>, not <dictionary>")
    avps = [
        parse_avp(int(vendor.get("id", "0")), avp, path.name)
        for vendor in root.findall("vendor")
        for avp in vendor.findall("avp")
    ]
    commands = [
        Command(0, command.get("name", ""), int(command.get("code", "0")))
        for base in root.findall("base")
        for command in base.findall("command")
    ]
    for application in root.findall("application"):
        application_id = int(application.get("id", "0"))
        for command in application.findall("command"):
            name = command.get("name", "")
            code = int(command.get("code", "0"))
            commands.append(Command(application_id, name, code))
    return avps, commands


def load_command_codes(path: Path) -> set[int]:
    """Return the command codes that a *Commands.xml file describes."""
    root = ElementTree.parse(path).getroot()
    return {int(command.get("code", "0")) for command in root.iter("command")}


def load_seagull_dictionary(path: Path) -> tuple[list[Avp], list[Command]]:
    """Read a dictionary in the Seagull format, such as one that ships with Seagull.

    The AVPs come with the flags they have there. Of each request and answer pair, only the
    request is returned, as a command named by its two letters, such as CE for CER and CEA.
    """
    text = path.read_text(encoding="iso-8859-1")
    _, marker, body = text.partition("<protocol")  # a comment may come before the declaration
    root = ElementTree.fromstring(marker + body)
    avps = []
    for define in root.findall("./dictionary/avp/define"):
        fields = {s.get("name", ""): int(s.get("value") or 0) for s in define.findall("setfield")}
        flags = fields.get("flags", 0)
        kind = define.get("type", "")
        avps.append(
            Avp(
                vendor_id=fields.get("Vendor-ID", 0),
                name=define.get("name", ""),
                code=fields.get("avp-code", -1),
                source=path.name,
                vendor_specific=bool(flags & dictionary_options.VENDOR_BIT),
                mandatory=bool(flags & dictionary_options.MANDATORY_BIT),
                protected=bool(flags & 32),
                type_name=None if kind == "Grouped" else kind,
                members=[] if kind == "Grouped" else None,
                enums=[],
            )
        )
    commands = []
    for define in root.findall("./dictionary/command/define"):
        fields = {s.get("name", ""): int(s.get("value") or 0) for s in define.findall("setfield")}
        name = define.get("name", "")
        if name.endswith("R"):
            application, code = fields.get("application-id", 0), fields.get("cmd-code", 0)
            commands.append(Command(application, name[:-1], code))
    return avps, commands


def apply_renames(
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    renames: dict[str, str],
    keep_prefixes: bool,
    report: list[str],
) -> None:
    """Rename AVPs in place: the TGPP- prefix, unless kept, and the OLD=NEW pairs."""

    def new_name(name: str) -> str:
        if name in renames:
            return renames[name]
        if not keep_prefixes:
            for old, new in PREFIX_RENAMES:
                if name.startswith(old):
                    return new + name.removeprefix(old)
        return name

    count = 0
    found = set()
    for avps, _ in loaded.values():
        for avp in avps:
            if avp.name in renames:
                found.add(avp.name)
            renamed = new_name(avp.name)
            count += renamed != avp.name
            avp.name = renamed
            if avp.members is not None:
                avp.members = [new_name(member) for member in avp.members]
    for name in sorted(set(renames) - found):
        report.append(f"WARNING --rename {name}: no AVP has that name")
    prefix = "kept" if keep_prefixes else "3GPP-"
    report.append(f"renamed {count} AVP definitions (TGPP- prefix: {prefix})")


def merge_avps(
    avp_lists: list[list[Avp]],
    warnings: list[str],
) -> tuple[list[Avp], dict[tuple[int, int], Avp]]:
    """Merge AVP lists in order and keep every definition, as the dictionaries of projects do.

    Seagull finds an AVP by name and takes the first definition of a name for every use of it,
    so a later definition of a name with another vendor or code is written, but a scenario
    cannot send it. The warning says which one wins.
    """
    merged: list[Avp] = []
    by_name: dict[str, Avp] = {}
    by_code: dict[tuple[int, int], Avp] = {}
    seen: set[tuple[str, int, int]] = set()
    for avp in (avp for avp_list in avp_lists for avp in avp_list):
        if (avp.name, avp.vendor_id, avp.code) in seen:
            continue
        seen.add((avp.name, avp.vendor_id, avp.code))
        first = by_name.get(avp.name)
        if first is not None:
            warnings.append(
                f"AVP name {avp.name} is defined twice with different identity: "
                f"vendor {first.vendor_id} code {first.code} ({first.source}) and "
                f"vendor {avp.vendor_id} code {avp.code} ({avp.source}); "
                "Seagull sends the first one wherever a scenario uses the name"
            )
        other = by_code.get((avp.vendor_id, avp.code))
        if other is not None:
            warnings.append(
                f"vendor {avp.vendor_id} code {avp.code} has two names: "
                f"{other.name} ({other.source}) and {avp.name} ({avp.source}); "
                "kept both"
            )
        by_name.setdefault(avp.name, avp)
        by_code.setdefault((avp.vendor_id, avp.code), avp)
        merged.append(avp)
    return merged, by_code


def merge_commands(
    command_lists: list[list[Command]],
    warnings: list[str],
) -> list[Command]:
    """Merge command lists in order; a later definition replaces an earlier one."""
    commands: dict[str, Command] = {}
    for command in (c for command_list in command_lists for c in command_list):
        old = commands.get(command.short)
        if old is not None and (old.code, old.application_id) != (
            command.code,
            command.application_id,
        ):
            warnings.append(
                f"command {command.short}R/A: {old.name} (code {old.code}, "
                f"application {old.application_id}) replaced by {command.name} "
                f"(code {command.code}, application {command.application_id})"
            )
        commands[command.short] = command
    return list(commands.values())


def check_avp(avp: Avp, warnings: list[str]) -> None:
    """Report AVP definitions that look inconsistent. The project dictionaries are
    not taken as correct."""
    where = f"{avp.name} ({avp.source})"
    if avp.vendor_specific and avp.vendor_id == 0:
        warnings.append(f"{where}: vendor-specific=yes but the vendor id is 0")
    if not avp.vendor_specific and avp.vendor_id != 0:
        message = f"{where}: vendor-specific=no but the vendor id is {avp.vendor_id}"
        warnings.append(message)
    if avp.members is None and avp.type_name is None:
        warnings.append(f"{where}: neither <type> nor <grouped>; used {FALLBACK_TYPE}")
    if avp.type_name is not None and avp.type_name not in TYPE_KINDS:
        warnings.append(f"{where}: unknown type {avp.type_name}; used {FALLBACK_TYPE}")


def comment(text: str) -> str:
    """Return an XML comment; a run of hyphens would end it early."""
    return "<!-- " + re.sub(r"-{2,}", "-", text) + " -->"


@dataclass
class Render:
    """How the output is written: with comments or without, and with which flags."""

    with_comments: bool
    flags: Any


def seagull_type_of(avp: Avp) -> str:
    """Return the type an AVP gets in the output: its own, when Seagull can encode it."""
    if avp.members is not None:
        return "Grouped"
    return avp.type_name if avp.type_name in TYPE_KINDS else FALLBACK_TYPE


def render_types(avps: list[Avp]) -> str:
    """Return the <typedef> lines for the types that the AVPs use."""
    used = {seagull_type_of(avp) for avp in avps}
    lines = []
    for name, (kind, size) in TYPE_KINDS.items():
        if name in used:
            attributes = f'name="{name}" type="{kind}" size="{size}" unit="octet"'
            lines.append(f"    <typedef {attributes}></typedef>\n")
    lines.append('    <typedef name="Grouped" type="grouped"></typedef>\n')
    return "".join(lines)


def render_avp(avp: Avp, render: Render) -> str:
    """Return the Seagull <define> of an AVP."""
    seagull_type = seagull_type_of(avp)
    lines = []
    if render.with_comments and avp.enums:
        values = ", ".join(f"{name}={code}" for name, code in avp.enums)
        lines.append("      " + comment("values: " + values))
    if render.with_comments and avp.members:
        lines.append("      " + comment("members: " + ", ".join(avp.members)))
    flags = render.flags.avp_flags(avp.name, avp.flags, avp.vendor_specific)
    lines += [
        f"      <define name={quoteattr(avp.name)} type={quoteattr(seagull_type)}>",
        f'        <setfield name="avp-code" value="{avp.code}"></setfield>',
        f'        <setfield name="flags" value="{flags}"></setfield>',
    ]
    if avp.vendor_specific:
        vendor = f'value="{avp.vendor_id}"'
        lines.append(f'        <setfield name="Vendor-ID" {vendor}></setfield>')
    lines.append("      </define>")
    return "\n".join(lines) + "\n"


def render_command(command: Command, answer: bool, render: Render) -> str:
    """Return the Seagull <define> of a request or an answer."""
    name = command.short + ("A" if answer else "R")
    flags = render.flags.command_flags(name, answer)
    lines = [
        f'      <define name="{name}">',
        f'        <setfield name="flags" value="{flags}"></setfield>',
        f'        <setfield name="cmd-code" value="{command.code}"></setfield>',
    ]
    if command.application_id:
        template = '        <setfield name="application-id" value="{}"></setfield>'
        lines.append(template.format(command.application_id))
    lines += [
        '        <setfield name="protocol-version" value="1"></setfield>',
        "      </define>",
    ]
    return "\n".join(lines) + "\n"


def write_dictionary(
    path: Path,
    source_names: list[str],
    avps: list[Avp],
    commands: list[Command],
    render: Render,
) -> None:
    """Write one Seagull dictionary file."""
    text = HEADER.format(sources=", ".join(source_names), types=render_types(avps))
    text += "".join(render_avp(avp, render) for avp in avps)
    text += MIDDLE
    for command in commands:
        text += render_command(command, False, render) + render_command(command, True, render)
    text += FOOTER
    path.write_text(text, encoding="iso-8859-1", newline="\n", errors="replace")


def check_command_files(
    names: list[str],
    input_dir: Path,
    commands: list[Command],
    warnings: list[str],
) -> None:
    """Warn about command codes that a *Commands.xml file lists and no source defines."""
    known = {command.code for command in commands}
    for name in names:
        file_name = f"{name}Commands.xml"
        if name == BASE_NAME:
            file_name = "CER-CEACommands.xml"
        path = input_dir / file_name
        if not path.exists():
            continue
        missing = load_command_codes(path) - known
        if missing:
            warnings.append(
                f"{file_name} describes command codes {sorted(missing)} that no "
                "<command> of the sources defines; they are not in the output"
            )


@dataclass
class Base:
    """Where the base protocol comes from: the dictionaries that hold it, and a fallback."""

    names: list[str]
    fallback: tuple[list[Avp], list[Command]] | None = None
    fallback_name: str = ""

    def sources(self, names: list[str]) -> list[str]:
        """Return the base dictionaries first, then the named ones that are not among them."""
        return self.names + [name for name in names if name not in self.names]


def base_sources(loaded: dict[str, tuple[list[Avp], list[Command]]]) -> list[str]:
    """Return the dictionaries that hold the base protocol, found by their content.

    The file named DiameterBaseProtocol.xml is the base when there is one. Without it, the
    base is every dictionary that defines a command of the handshake in <base>, whatever
    the file is called.
    """
    if BASE_NAME in loaded:
        return [BASE_NAME]
    return [
        name
        for name, (_, commands) in loaded.items()
        if any(c.application_id == 0 and c.code in BASE_COMMANDS for c in commands)
    ]


def base_gaps(avps: list[Avp], commands: list[Command]) -> tuple[list[int], list[int]]:
    """Return the codes of the base AVPs and of the base commands that the lists lack."""
    have_avps = {avp.code for avp in avps if avp.vendor_id == 0}
    have_commands = {command.code for command in commands if command.application_id == 0}
    return sorted(set(BASE_AVPS) - have_avps), sorted(set(BASE_COMMANDS) - have_commands)


def describe_gaps(gaps: tuple[list[int], list[int]]) -> str:
    """Return the missing items as text: the codes with their standard names."""
    items = [f"AVP {code} ({BASE_AVPS[code]})" for code in gaps[0]]
    return ", ".join(items + [f"command {code} ({BASE_COMMANDS[code]})" for code in gaps[1]])


def fill_base(
    avps: list[Avp],
    commands: list[Command],
    base: Base,
    warnings: list[str],
) -> tuple[list[int], list[int]]:
    """Add the base protocol of the Seagull dictionary where the sources lack it; return the gaps.

    It acts when the sources lack a required item. Then it adds every AVP and command of the
    Seagull dictionary, because the messages use more of the base protocol than the handshake.
    The dictionaries of the user win: an item is skipped when its name, or its code, is already
    defined, so a clash never renames or replaces anything of the user's.
    """
    gaps = base_gaps(avps, commands)
    if base.fallback is None or not (gaps[0] or gaps[1]):
        return gaps
    added_avps, added_commands = new_base_items(avps, commands, base.fallback)
    avps[0:0] = added_avps
    commands[0:0] = added_commands
    if added_avps or added_commands:
        source = f"{base.fallback_name} of the Seagull distribution"
        count = f"{len(added_avps)} AVPs and {len(added_commands)} command pairs"
        incomplete = f"the base protocol is incomplete ({describe_gaps(gaps)} missing)"
        warnings.append(f"{incomplete}; added {count} from {source}")
        warnings.append("the dictionaries of the Seagull distribution may be wrong in places")
    return base_gaps(avps, commands)


def new_base_items(
    avps: list[Avp],
    commands: list[Command],
    fallback: tuple[list[Avp], list[Command]],
) -> tuple[list[Avp], list[Command]]:
    """Return the items of the fallback whose name and code the sources do not define yet."""
    names = {avp.name for avp in avps}
    keys = {(avp.vendor_id, avp.code) for avp in avps}
    added_avps: list[Avp] = []
    for avp in fallback[0]:
        if avp.name not in names and (avp.vendor_id, avp.code) not in keys:
            added_avps.append(avp)
            names.add(avp.name)
            keys.add((avp.vendor_id, avp.code))
    shorts = {command.short for command in commands}
    codes = {(command.application_id, command.code) for command in commands}
    added_commands = [
        command
        for command in fallback[1]
        if command.short not in shorts and (command.application_id, command.code) not in codes
    ]
    return added_avps, added_commands


def base_problem(
    jobs: list[Job],
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    base: Base,
) -> str:
    """Return what no output can get, as text, or an empty string when every output is complete."""
    missing: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for _, names in jobs:
        sources = base.sources(names)
        avps, _ = merge_avps([loaded[name][0] for name in sources], [])
        commands = merge_commands([loaded[name][1] for name in sources], [])
        gaps = fill_base(avps, commands, base, [])
        if gaps[0] or gaps[1]:
            missing.add((tuple(gaps[0]), tuple(gaps[1])))
    return "; ".join(describe_gaps((list(a), list(c))) for a, c in sorted(missing))


def flag_notes(avps: list[Avp], commands: list[Command], options: Any) -> list[str]:
    """List where the flags of the output differ from what the converter writes without options."""
    notes = []
    for command in commands:
        for answer in (False, True):
            name = command.short + ("A" if answer else "R")
            flags, default = options.command_flags(name, answer), 0 if answer else 128
            if flags != default:
                notes.append(f"{name}: flags {flags} (the converter's default is {default})")
    for avp in avps:
        flags = options.avps.get(avp.name, avp.flags)
        if flags != avp.flags:
            notes.append(f"{avp.name}: flags {flags} (the source gives {avp.flags})")
    vendor = [avp for avp in avps if avp.vendor_specific and avp.name not in options.avps]
    changed = [avp for avp in vendor if options.avp_flags(avp.name, avp.flags, True) != avp.flags]
    if changed:
        policy = f"vendor-mandatory={options.vendor_mandatory}"
        notes.append(f"{policy}: changed the M bit of {len(changed)} of {len(vendor)} vendor AVPs")
    return notes


def convert(
    job: Job,
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    directories: tuple[Path, Path],
    render: Render,
    base: Base,
) -> tuple[str, int, int, list[str], list[str]]:
    """Write one dictionary built from the sources of the job plus the base protocol.

    Returns the name of the output, the number of AVPs and of command pairs, the warnings
    about the sources, and the notes about flags that differ from the defaults.
    """
    out_name, names = job
    input_dir, output_dir = directories
    warnings: list[str] = []
    sources = base.sources(names)
    avps, _ = merge_avps([loaded[name][0] for name in sources], warnings)
    commands = merge_commands([loaded[name][1] for name in sources], warnings)
    fill_base(avps, commands, base, warnings)
    for avp in avps:
        check_avp(avp, warnings)
    check_command_files(sources, input_dir, commands, warnings)
    target = output_dir / f"{out_name}.xml"
    write_dictionary(target, [n + ".xml" for n in sources], avps, commands, render)
    return out_name, len(avps), len(commands), warnings, flag_notes(avps, commands, render.flags)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--combine",
        action="append",
        default=[],
        metavar="yes|no|A,B",
        help=(
            "yes (the default) writes one dictionary of all the AVP dictionaries; no writes one "
            "for each; A,B writes only one merged from the named ones, in that order (repeatable)"
        ),
    )
    parser.add_argument(
        "--rename",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="rename an AVP, for example to match the names a scenario uses",
    )
    parser.add_argument(
        "--keep-tgpp",
        action="store_true",
        help="keep the TGPP- prefix of AVP names instead of writing 3GPP-",
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="leave enumeration values and group members out",
    )
    parser.add_argument(
        "--options",
        type=Path,
        metavar="FILE",
        help=f"read the flag options of a {OPTIONS_NAME} file, such as an earlier run wrote",
    )
    parser.add_argument(
        "--command-flags",
        action="append",
        default=[],
        metavar="KEY=FLAGS",
        help="flags of requests (request=N), answers (answer=N), or one command (CCR=192)",
    )
    parser.add_argument(
        "--avp-flags",
        action="append",
        default=[],
        metavar="NAME=FLAGS",
        help="flags of one AVP by its name in the output, for example PDP-Address=128",
    )
    parser.add_argument(
        "--vendor-mandatory",
        choices=dictionary_options.POLICIES,
        help="the M bit of every vendor AVP: as the source says (default), always set, or clear",
    )
    parser.add_argument(
        "--seagull-base",
        type=Path,
        metavar="FILE",
        help=f"a Seagull dictionary ({BUNDLED_BASE}) to take missing base items from; yours win",
    )
    parser.add_argument(
        "--xsd-dir",
        metavar="DIR",
        help="the folder of the XSD files; recorded in the options file for the validation step",
    )
    parser.add_argument(
        "--validate-commands",
        choices=("yes", "no"),
        help="whether the validation step checks the *Commands.xml files; recorded as well",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="print the file of each dictionary the outputs would be made of; write nothing",
    )
    return parser.parse_args(argv)


def load_dictionaries(input_dir: Path) -> dict[str, tuple[list[Avp], list[Command]]]:
    """Read every AVP dictionary of a folder, by file name without the extension."""
    loaded = {}
    for path in sorted(input_dir.glob("*.xml")):
        if ElementTree.parse(path).getroot().tag == "dictionary":
            loaded[path.stem] = load_avp_dictionary(path)
    return loaded


def check_flag_names(
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    options: Any,
    report: list[str],
) -> None:
    """Report options that name nothing; refuse flags that contradict the V bit of an AVP."""
    avps = {avp.name: avp for avp_list, _ in loaded.values() for avp in avp_list}
    commands = [command for _, command_list in loaded.values() for command in command_list]
    messages = {command.short + suffix for command in commands for suffix in "RA"}
    for name in sorted(set(options.commands) - messages):
        report.append(f"WARNING --command-flags {name}: no command has that name")
    for name, flags in sorted(options.avps.items()):
        avp = avps.get(name)
        if avp is None:
            report.append(f"WARNING --avp-flags {name}: no AVP has that name")
        elif bool(flags & dictionary_options.VENDOR_BIT) != avp.vendor_specific:
            state = "a vendor" if avp.vendor_specific else "not a vendor"
            raise dictionary_options.DictionaryOptionsError(
                f"avp-flags {name}: flags {flags} contradict the V bit; the AVP is {state} AVP"
            )


def load_fallback(path: Path | None) -> tuple[tuple[list[Avp], list[Command]] | None, str]:
    """Read the Seagull dictionary given by --seagull-base; return it and its file name."""
    if path is None:
        return None, ""
    return load_seagull_dictionary(path), path.name


def base_message(problem: str, base: Base, folder: Path) -> str:
    """Return the message for a folder whose dictionaries lack the base protocol."""
    lines = [
        f"error: the dictionaries in {folder} do not define the base protocol: missing {problem}.",
        "The check is by code, over every .xml dictionary of the folder; file names do not matter.",
    ]
    if base.fallback is None:
        lines += [
            "Put the files that define them into the folder, or allow the dictionary of the",
            "Seagull distribution for the missing items with --seagull-base FILE",
            f"({BUNDLED_BASE} of Seagull; it may be wrong in places, and your dictionaries win",
            "wherever they define the same name or code).",
        ]
    else:
        lines.append(f"The Seagull dictionary {base.fallback_name} does not supply them either.")
    return "\n".join(lines) + "\n"


def choose_base(
    args: argparse.Namespace,
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    jobs: list[Job],
    report: list[str],
) -> Base | None:
    """Find the base protocol; return None, after the message, when an output cannot get it."""
    base = Base(base_sources(loaded), *load_fallback(args.seagull_base))
    problem = base_problem(jobs, loaded, base)
    if problem:
        sys.stderr.write(base_message(problem, base, args.input_dir))
        return None
    if base.names and base.names != [BASE_NAME]:
        found = ", ".join(base.names)
        report.append(f"NOTE the base protocol is taken from {found} (found by its commands)")
    return base


def write_outputs(
    jobs: list[Job],
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    directories: tuple[Path, Path],
    how: tuple[Render, Base],
) -> list[str]:
    """Write one dictionary for each job; return the lines of the report."""
    report: list[str] = []
    for job in jobs:
        result = convert(job, loaded, directories, *how)
        out_name, avp_count, command_count, warnings, notes = result
        counts = f"{avp_count} AVPs, {command_count} command pairs"
        report.append(f"{out_name}.xml: {counts}, {len(warnings)} warnings")
        report += [f"    WARNING {warning}" for warning in warnings]
        report += [f"    NOTE {note}" for note in notes]
    return report


def plan_jobs(combine: list[str], loaded: dict[str, tuple[list[Avp], list[Command]]]) -> list[Job]:
    """Return the outputs to write, each as its name and the dictionaries it is made from.

    Without --combine, or with yes, every AVP dictionary goes into one output. With no, each
    goes into its own, and a list of names makes one output from them, in that order.
    """
    if not combine or combine == ["yes"]:
        return [(ALL_NAME, list(loaded))]
    if combine == ["no"]:
        separate = [(name, [name]) for name in loaded if name != BASE_NAME]
        return separate or [(BASE_NAME, [BASE_NAME])]
    jobs = [(spec.replace(",", "+"), spec.split(",")) for spec in combine]
    unknown = [name for _, names in jobs for name in names if name not in loaded]
    if unknown:
        message = f"unknown dictionary in --combine: {unknown}"
        raise dictionary_options.DictionaryOptionsError(message)
    return jobs


def convert_all(
    args: argparse.Namespace,
    loaded: dict[str, tuple[list[Avp], list[Command]]],
    render: Render,
) -> int:
    """Write every output and the report; return the exit status."""
    report: list[str] = []
    renames = dict(pair.split("=", 1) for pair in args.rename)
    apply_renames(loaded, renames, args.keep_tgpp, report)
    check_flag_names(loaded, render.flags, report)
    jobs = plan_jobs(args.combine, loaded)
    base = choose_base(args, loaded, jobs, report)
    if base is None:
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report += write_outputs(jobs, loaded, (args.input_dir, args.output_dir), (render, base))
    text = "\n".join(report) + "\n"
    (args.output_dir / "conversion-report.txt").write_text(text, encoding="utf-8")
    dictionary_options.save_options(args.output_dir / OPTIONS_NAME, render.flags)
    sys.stdout.write(text)
    return 0


def list_sources(args: argparse.Namespace, loaded: dict[str, tuple[list[Avp], list[Command]]]) -> int:
    """Print the file of each dictionary that the outputs are made of, base protocol first."""
    base = Base(base_sources(loaded))
    names: list[str] = []
    for _, job_names in plan_jobs(args.combine, loaded):
        names += [name for name in base.sources(job_names) if name not in names]
    sys.stdout.write("".join(f"{name}.xml\n" for name in names))
    return 0


def main(argv: list[str]) -> int:
    """Convert every AVP dictionary of the input folder; return the exit status."""
    args = parse_arguments(argv)
    loaded = load_dictionaries(args.input_dir)
    if not loaded:
        sys.stderr.write(f"error: no AVP dictionary in {args.input_dir}\n")
        return 2
    try:
        if args.list_sources:
            return list_sources(args, loaded)
        flags = dictionary_options.load_options(args.options)
        pairs = (args.command_flags, args.avp_flags)
        dictionary_options.apply_pairs(flags, *pairs, args.vendor_mandatory)
        flags.xsd = args.xsd_dir or flags.xsd
        if args.validate_commands:
            flags.validate_commands = args.validate_commands == "yes"
        return convert_all(args, loaded, Render(not args.no_comments, flags))
    except dictionary_options.DictionaryOptionsError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
