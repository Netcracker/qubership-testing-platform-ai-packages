"""Generate Seagull scenarios from a folder of recorded Diameter requests and answers.

Usage:
  python generate_scenarios.py --steps STEPS_DIR --dictionaries-dir DIR
      --dictionaries A,B,C (--out OUT_DIR | --out-auto PARENT) [--replace]
      [--timeout-ms 5000] [--dest HOST:PORT]
      [--host-ip IP] [--check-avps LIST] [--seagull-dictionary FILE] [--seagull-base FILE]
      [--options FILE] [--option KEY=VALUE ...] [--placeholder AVP=NAME ...]

STEPS_DIR holds Step-NNN-request.txt and Step-NNN-response.txt (see the
seagull-diameter-common skill). DIR holds the project's AVP dictionaries: the files named
in --dictionaries, merged in that order, and the file with the base protocol (by default
DiameterBaseProtocol.xml, else the dictionary that defines the handshake commands). When
the folder lacks part of the base protocol, --seagull-base FILE (base_draft08.xml of
Seagull) supplies the missing items; see dict2seagull.py.

Seagull ties an answer to its call by the Session-Id, so a scenario holds one
Diameter session. The steps are cut into sessions at each change of Session-Id.
Every session becomes one client scenario and one stub-OCS scenario for a dry run.
OUT_DIR also gets the client and stub configuration and the merged Seagull
dictionary.

OUT_DIR must be new or empty. --out-auto PARENT picks the first free
PARENT/Seagull-Scenario[-N] instead. A non-empty OUT_DIR is an error, because new
files would mix with old ones; --replace moves its old contents to a sibling folder
named OUT_DIR.previous-<time> first, and keeps the options file.

The options file (default OUT_DIR/scenario-options.ini) says whether to write ready
scenarios or templates, which dynamic tags to add, and which AVP values become
placeholders; see scenario_options.py. --option and --placeholder change it, and
the generator writes the result to OUT_DIR/scenario-options.ini. A new folder starts
from the options file of an older run when --options names it; the older file is
only read.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import copy
import importlib
import io
import ipaddress
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import quoteattr

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
COMMON = Path(__file__).resolve().parents[2] / "seagull-diameter-common" / "scripts"
sys.path.insert(0, str(COMMON))
steps_format = importlib.import_module("steps_format")
dict2seagull = importlib.import_module("dict2seagull")
scenario_options = importlib.import_module("scenario_options")
output_folder = importlib.import_module("output_folder")
seagull_dictionary = importlib.import_module("seagull_dictionary")

NTP_OFFSET = 2208988800
NUMERIC = {"Unsigned32", "Unsigned64", "Integer32", "Integer64", "Enumerated"}
CHECKS = "Result-Code,Session-Id,Auth-Application-Id,CC-Request-Type,CC-Request-Number"
STUB_ADDRESS = "127.0.0.1:3868"  # where the stub OCS of the dry run listens
XML_HEAD = '<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
AVP_LINE = "      <avp name={} value={}></avp>\n"
CHECK_LINE = '      <check-value name={} behaviour="error"></check-value>\n'
PRESENCE_LINE = '      <check-presence name={} behaviour="error"></check-presence>\n'
OPTIONS_NAME = "scenario-options.ini"
WAIT_KEY = "wait-ms"


class GenerationError(Exception):
    """The input cannot be turned into a scenario."""


@dataclass
class Substitution:
    """The placeholders of one scenario file and the values they stand for."""

    rules: dict[str, str]
    native: bool
    used: set[str]
    values: dict[str, str] = field(default_factory=dict)
    hits: list[tuple[str, str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def holder(self, path: list[tuple[str, str, int]]) -> str | None:
        """Return the placeholder for an AVP path, or None; remember the rule used."""
        found = scenario_options.lookup(self.rules, path)
        if found is None:
            return None
        self.used.add(found[0])
        return found[1]

    def record(self, holder: str, value: str) -> None:
        """Remember the value that a placeholder stands for; the first one wins."""
        plain = scenario_options.unwrapped(value)
        known = self.values.setdefault(holder, plain)
        if known != plain:
            self.notes.append(f"{holder}: values {known!r} and {plain!r}; used the first")

    def apply(self, path: list[tuple[str, str, int]], value: str) -> str:
        """Return the text to write for a value; a native hit is queued instead."""
        holder = self.holder(path)
        if holder is None:
            return value
        if self.native:
            if len(path) > 1 or path[-1][2] > 1:
                where = "/".join(entry[0] for entry in path)
                message = f"native substitution cannot address {where}: use text"
                raise GenerationError(message)
            self.hits.append((path[-1][0], holder, value))
            return value
        self.record(holder, value)
        return scenario_options.wrap(value, holder)

    def text(self, name: str, value: str) -> str:
        """Return a top-level value as text; a native placeholder keeps the value."""
        if self.native:
            return value
        return self.apply([(name, name, 1)], value)


@dataclass
class Resolver:
    """Find the Seagull name and the project definition of an AVP in a message."""

    project: dict[str, list[Any]]
    seagull_names: dict[tuple[int, int], list[str]]
    first: dict[str, tuple[int, int]] = field(default_factory=dict)
    notes: set[str] = field(default_factory=set)
    counters: Counter = field(default_factory=Counter)

    def resolve(self, name: str, parent_vendor: int | None) -> tuple[str, Any]:
        """Return the Seagull name and the project definition of an AVP name.

        When the project has several definitions of the name, the one with the
        vendor of the enclosing group wins, and the first one otherwise.
        """
        candidates = self.project.get(name)
        if not candidates:
            message = f"AVP {name} is in none of the project dictionaries given"
            raise GenerationError(message)
        chosen = candidates[0]
        if len(candidates) > 1:
            same = [c for c in candidates if c.vendor_id == parent_vendor]
            chosen = same[0] if same else chosen
            self.notes.add(describe_choice(name, candidates, chosen, bool(same)))
        names = self.seagull_names.get((chosen.vendor_id, chosen.code))
        if not names:
            where = f"vendor {chosen.vendor_id}, code {chosen.code}"
            message = f"AVP {name} ({where}) is not in the Seagull dictionary"
            raise GenerationError(message)
        wanted = name.replace("TGPP-", "3GPP-", 1)
        result = wanted if wanted in names else names[0]
        sent = self.first.get(result)
        if sent is not None and sent != (chosen.vendor_id, chosen.code):
            needed = f"vendor {chosen.vendor_id} code {chosen.code}"
            self.notes.add(
                f"{result}: the message needs {needed}, "
                f"but Seagull sends vendor {sent[0]} code {sent[1]}, "
                "the first definition of the name in the Seagull dictionary"
            )
        return result, chosen


def describe_choice(name: str, candidates: list[Any], chosen: Any, same: bool) -> str:
    """Describe a choice between several definitions of one AVP name."""
    keys = [(c.vendor_id, c.code) for c in candidates]
    why = "the vendor of the enclosing group" if same else "the first definition"
    used = f"vendor {chosen.vendor_id} code {chosen.code}"
    return f"{name}: definitions (vendor, code) {keys}; used {used}, chosen by {why}"


def load_project(paths: list[Path]) -> dict[str, list[Any]]:
    """Return {AVP name: [definitions]} of the project dictionaries, in file order."""
    by_name: dict[str, list[Any]] = {}
    for path in paths:
        avps, _ = dict2seagull.load_avp_dictionary(path)
        for avp in avps:
            known = by_name.setdefault(avp.name, [])
            if (avp.vendor_id, avp.code) not in {(k.vendor_id, k.code) for k in known}:
                known.append(avp)
    return by_name


def load_project_dictionaries(options: argparse.Namespace) -> dict[str, list[Any]]:
    """Load the AVPs of the base protocol and of the named dictionaries.

    The base protocol is the dictionary that dict2seagull.py takes as such. AVPs that only the
    Seagull dictionary of --seagull-base has, such as a base AVP the folder lacks, are added
    last, so every AVP of the project wins over it.
    """
    folder = options.dictionaries_dir
    base = dict2seagull.base_sources(dict2seagull.load_dictionaries(folder))
    names = [*base, *[n for n in options.dictionaries.split(",") if n not in base]]
    project = load_project([folder / f"{n}.xml" for n in names])
    if options.seagull_base:
        for avp in dict2seagull.load_seagull_dictionary(options.seagull_base)[0]:
            known = project.setdefault(avp.name, [])
            if not known:
                known.append(avp)
    return project


def to_ntp_hex(text: str) -> str:
    """Return a UTC time such as 2026-10-27 14:00:52 as 4 bytes of NTP time in hex."""
    match = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", text.strip())
    if not match:
        raise GenerationError(f"{text!r} is not a time like 2026-10-27 14:00:52")
    moment = time.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
    return f"0x{calendar.timegm(moment) + NTP_OFFSET:08X}"


def to_address_hex(text: str) -> str:
    """Return an IP address as the value of an Address AVP: family, then bytes."""
    try:
        address = ipaddress.ip_address(text.strip())
    except ValueError as error:
        raise GenerationError(f"{text!r} is not an IP address or 0x...") from error
    family = 1 if address.version == 4 else 2
    return f"0x{family:04X}{address.packed.hex()}"


def encode_value(avp: Any, text: str, counters: Counter) -> str:
    """Return the Seagull value of an AVP from the text of a recorded message."""
    stripped = text.strip()
    if avp.type_name == "Time":
        counters["time converted to NTP hex"] += 1
        return to_ntp_hex(text)
    if avp.type_name == "Address":
        if stripped.lower().startswith("0x"):
            return stripped
        counters["IP address converted to Address hex"] += 1
        return to_address_hex(text)
    if avp.type_name in NUMERIC:
        codes = dict(avp.enums)
        if stripped in codes:
            counters["enumeration name converted to its number"] += 1
            return codes[stripped]
        if re.fullmatch(r"-?\d+|0x[0-9a-fA-F]+", stripped):
            return stripped
        raise GenerationError(f"AVP {avp.name}: {text!r} is not a number or a name")
    if "$(" in text:
        raise GenerationError(f"{text!r} would be read as a Seagull variable")
    return text


@dataclass
class Layout:
    """Where an <avp> is written.

    It holds the indent, the path of the enclosing AVPs, the vendor of the
    enclosing group, and the placeholders to apply, if any.
    """

    indent: int
    path: tuple = ()
    substitution: Substitution | None = None
    vendor: int | None = None

    def inside(self, step: tuple[str, str, int], vendor: int) -> Layout:
        """Return the layout of the members of the AVP at the end of the path."""
        return Layout(self.indent + 1, (*self.path, step), self.substitution, vendor)


def members_xml(
    elements: list[ElementTree.Element],
    resolver: Resolver,
    layout: Layout,
) -> str:
    """Return the <avp> elements for sibling AVPs, counting repeats of a name."""
    seen: Counter = Counter()
    parts = []
    for element in elements:
        seen[element.tag] += 1
        parts.append(avp_xml(element, resolver, layout, seen[element.tag]))
    return "".join(parts)


def avp_xml(
    element: ElementTree.Element,
    resolver: Resolver,
    layout: Layout,
    position: int = 1,
) -> str:
    """Return the Seagull <avp> element for an AVP of a message and its members."""
    name, avp = resolver.resolve(element.tag, layout.vendor)
    pad = "  " * layout.indent
    step = (name, element.tag, position)
    members = list(element)
    if members:
        parts = members_xml(members, resolver, layout.inside(step, avp.vendor_id))
        return f"{pad}<avp name={quoteattr(name)}>\n{parts}{pad}</avp>\n"
    text = element.text or ""
    if not text.strip():
        raise GenerationError(f"AVP {element.tag} has no value")
    value = encode_value(avp, text, resolver.counters)
    if layout.substitution:
        value = layout.substitution.apply([*layout.path, step], value)
    return f"{pad}<avp name={quoteattr(name)} value={quoteattr(value)}></avp>\n"


def body_xml(
    root: ElementTree.Element,
    resolver: Resolver,
    layout: Layout,
    skip: tuple = (),
) -> str:
    """Return the <avp> elements for the children of a message."""
    return members_xml([c for c in root if c.tag not in skip], resolver, layout)


def command_xml(message: Any, resolver: Resolver, layout: Layout) -> str:
    """Return the <command> element for a recorded message."""
    pad = "  " * layout.indent
    inner = Layout(layout.indent + 1, (), layout.substitution)
    body = body_xml(message.root, resolver, inner)
    return f'{pad}<command name="{message.command}">\n{body}{pad}</command>\n'


def expected_checks(
    step: Any,
    resolver: Resolver,
    names: list[str],
    substitution: Substitution,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Return the (Seagull name, expected value) pairs of an answer and notes."""
    pairs: list[tuple[str, str]] = []
    notes: list[str] = []
    for name in names:
        text = step.session_id if name == "Session-Id" else step.response.avp_text(name)
        if text is None:
            notes.append(f"step {step.number}: no {name} in the answer, not checked")
            continue
        seagull_name, avp = resolver.resolve(name, None)
        value = encode_value(avp, text, resolver.counters)
        pairs.append((seagull_name, substitution.text(seagull_name, value)))
    return pairs, notes


@dataclass
class Context:
    """What the scenarios of one generation share."""

    resolver: Resolver
    options: Any
    check_avps: list[str]
    host_ip: str
    notes: list[str]
    used: set[str]


def lines_xml(lines: list[str], pad: str = "      ") -> str:
    """Return the lines indented, each ending in a newline."""
    return "".join(f"{pad}{line}\n" for line in lines)


def set_value(name: str, format_text: str) -> str:
    """Return a <set-value> element that sets a field to a formatted text."""
    return f"<set-value name={quoteattr(name)} format={quoteattr(format_text)}></set-value>"


def store(name: str, entity: str) -> str:
    """Return a <store> element."""
    return f"<store name={quoteattr(name)} entity={quoteattr(entity)}></store>"


def restore(name: str, entity: str) -> str:
    """Return a <restore> element."""
    return f"<restore name={quoteattr(name)} entity={quoteattr(entity)}></restore>"


class ClientScenario:
    """The client scenario of one Diameter session."""

    def __init__(self, group: list[Any], context: Context) -> None:
        """Prepare the scenario of the steps of one session."""
        self.group = group
        self.context = context
        self.options = context.options
        native = self.options.substitution == "native"
        self.substitution = Substitution(self.options.rules(), native, context.used)
        self.layout = Layout(2, (), self.substitution)
        self.defined: set[str] = set()

    @property
    def values(self) -> dict[str, str]:
        """The values that the placeholders of this scenario stand for."""
        return self.substitution.values

    def request_value(self, name: str, fallback: str) -> str:
        """Return a value of the first request, as a placeholder where one is set."""
        raw = self.group[0].request.avp_text(name) or fallback
        return self.substitution.text(name, raw)

    def cer_block(self) -> str:
        """Return the capabilities exchange of the client, from the first step."""
        host = self.request_value("Origin-Host", "seagull.example.test")
        realm = self.request_value("Origin-Realm", "example.test")
        application = self.request_value("Auth-Application-Id", "4")
        ip_hex = self.substitution.text("Host-IP-Address", to_address_hex(self.context.host_ip))
        return f"""  <send channel="channel-1">
    <command name="CER">
      <avp name="Origin-Host" value={quoteattr(host)}></avp>
      <avp name="Origin-Realm" value={quoteattr(realm)}></avp>
      <avp name="Host-IP-Address" value={quoteattr(ip_hex)}></avp>
      <avp name="Vendor-Id" value="0"></avp>
      <avp name="Product-Name" value="Seagull"></avp>
      <avp name="Auth-Application-Id" value={quoteattr(application)}></avp>
    </command>
  </send>
  <receive channel="channel-1">
    <command name="CEA">
      <avp name="Result-Code" value="2001"></avp>
    </command>
    <action>
      <check-value name="Result-Code" behaviour="error"></check-value>
    </action>
  </receive>
"""

    def default_block(self) -> str:
        """Return the <default> section that answers a Device-Watchdog request."""
        if not self.options.tags.default_dwr:
            return ""
        host = self.request_value("Origin-Host", "seagull.example.test")
        realm = self.request_value("Origin-Realm", "example.test")
        return f"""
<default behaviour="ignore">
  <receive channel="channel-1">
    <command name="DWR"></command>
    <action>
      {store("DWR_HBH", "HbH-id")}
      {store("DWR_E2E", "EtE-id")}
    </action>
  </receive>
  <send channel="channel-1">
    <action>
      {restore("DWR_HBH", "HbH-id")}
      {restore("DWR_E2E", "EtE-id")}
    </action>
    <command name="DWA">
      <avp name="Origin-Host" value={quoteattr(host)}></avp>
      <avp name="Origin-Realm" value={quoteattr(realm)}></avp>
      <avp name="Result-Code" value="2001"></avp>
    </command>
  </send>
</default>
"""

    def session_lines(self, step: Any, first: bool) -> list[str]:
        """Return the actions that set the Session-Id of a request."""
        if not self.options.tags.generated_session_id:
            fixed = self.substitution.text("Session-Id", step.session_id)
            return [set_value("Session-Id", fixed)]
        if not first:
            return [restore("VAR_SESSION_ID", "Session-Id")]
        host = self.request_value("Origin-Host", "seagull.example.test")
        stamp = "$(VAR_TS);" if self.options.tags.time_method else ""
        text = f"{host};{stamp}$(session-counter)"
        return [set_value("Session-Id", text), store("VAR_SESSION_ID", "Session-Id")]

    def time_lines(self, step: Any, first: bool) -> list[str]:
        """Return the actions that set the Event-Timestamp of a request."""
        options = self.options
        needed = options.tags.generated_session_id and first
        has_time = step.request.avp_text("Event-Timestamp") is not None
        wanted = options.tags.generated_timestamp and has_time
        if not options.tags.time_method or not (needed or wanted):
            return []
        method = f'method={quoteattr(options.tags.time_method)} format="startoffset={NTP_OFFSET}"'
        lines = [f'<set-value name="Event-Timestamp" {method}></set-value>']
        if needed:
            lines.append(store("VAR_TS", "Event-Timestamp"))
        return lines

    def native_lines(self) -> list[str]:
        """Return the actions that set or restore the native variables."""
        lines: list[str] = []
        generated: set[str] = set()
        if self.options.tags.generated_session_id:
            generated.update(("Session-Id", "Event-Timestamp"))
        if self.options.tags.generated_timestamp:
            generated.add("Event-Timestamp")
        for name, holder, value in self.substitution.hits:
            if name in generated:
                continue
            if name in self.defined:
                lines.append(restore(holder, name))
                continue
            self.defined.add(name)
            lines += [set_value(name, value), store(holder, name)]
        return lines

    def send_lines(self, step: Any, first: bool) -> list[str]:
        """Return the actions that run before a request is sent."""
        lines = ['<inc-counter name="HbH-counter"></inc-counter>']
        lines.append('<inc-counter name="EtE-counter"></inc-counter>')
        if self.options.tags.generated_session_id and first:
            lines.append('<inc-counter name="session-counter"></inc-counter>')
        lines += [set_value("HbH-id", "$(HbH-counter)")]
        lines += [set_value("EtE-id", "$(EtE-counter)")]
        lines += self.time_lines(step, first)
        lines += self.session_lines(step, first)
        lines += self.native_lines()
        if self.options.tags.log:
            suffix = " $(VAR_SESSION_ID)" if self.options.tags.generated_session_id else ""
            text = f"{step.label} step {step.number}{suffix}"
            lines.append(f"<log format={quoteattr(text)}></log>")
        return lines

    def wait_block(self) -> str:
        """Return the pause between two steps, or nothing."""
        wait = self.options.tags.wait_ms
        mapped = WAIT_KEY in self.substitution.rules and not self.substitution.native
        if not wait and not mapped:
            return ""
        value = self.substitution.text(WAIT_KEY, str(wait))
        return f"  <wait-ms value={quoteattr(value)}></wait-ms>\n\n"

    def receive_block(self, step: Any) -> str:
        """Return the <receive> block that waits for the answer and checks it."""
        options = self.options
        skip_session = options.tags.generated_session_id
        names = [n for n in self.context.check_avps if not (n == "Session-Id" and skip_session)]
        pairs, skipped = expected_checks(step, self.context.resolver, names, self.substitution)
        self.context.notes.extend(skipped)
        avps, checks = "", ""
        for name, value in pairs:
            avps += AVP_LINE.format(quoteattr(name), quoteattr(value))
            if options.tags.check_presence:
                checks += PRESENCE_LINE.format(quoteattr(name))
            checks += CHECK_LINE.format(quoteattr(name))
        if options.tags.log:
            text = f"{step.response.command} step {step.number} checked"
            checks += f"      <log format={quoteattr(text)}></log>\n"
        return f"""  <receive channel="channel-1">
    <command name="{step.response.command}">
{avps}    </command>
    <action>
      <stop-timer></stop-timer>
{checks}    </action>
  </receive>
"""

    def step_block(self, index: int, step: Any) -> str:
        """Return the pause, the send block, and the receive block of one step."""
        self.substitution.hits.clear()
        command = command_xml(step.request, self.context.resolver, self.layout)
        number = step.request.avp_text("CC-Request-Number")
        where = "" if number is None else f", CC-Request-Number {number}"
        title = f"Step {step.number}: {step.label}, session {step.session_id}{where}"
        before = self.wait_block() if index else ""
        actions = lines_xml(self.send_lines(step, index == 0))
        return f"""{before}  <!-- ===== {title} ===== -->
  <send channel="channel-1">
    <action>
{actions}    </action>
{command}    <action>
      <start-timer></start-timer>
    </action>
  </send>

{self.receive_block(step)}
"""

    def text(self) -> str:
        """Return the client scenario."""
        group, options = self.group, self.options
        first = group[0]
        numbers = ", ".join(s.number for s in group)
        labels = ", ".join(s.label for s in group)
        blocks = "".join(self.step_block(i, s) for i, s in enumerate(group))
        counters = '  <counterdef name="HbH-counter" init="1000"></counterdef>\n'
        counters += '  <counterdef name="EtE-counter" init="2000"></counterdef>\n'
        if options.tags.generated_session_id:
            counters += '  <counterdef name="session-counter" init="0"></counterdef>\n'
        body = f"""<scenario>

<counter>
{counters}</counter>

<init>
{self.cer_block()}</init>
{self.default_block()}
<traffic>
{blocks}</traffic>

</scenario>
"""
        return f"""{XML_HEAD}<!-- Generated by generate_scenarios.py. Do not edit; generate again.
     Session {first.session_id}: step file(s) {numbers} ({labels}).
     Mode: {options.mode}, substitution: {options.substitution}. The AVPs are sent as
     recorded unless the options file names a placeholder for them. The Hop-by-Hop and
     End-to-End identifiers come from counters. A time is written as NTP hex and an IP
     address of an Address AVP as Address hex. The response timeout is the
     call-timeout-ms parameter of the configuration: Seagull waits that long for each
     answer. After each answer the scenario checks the fields of its receive block. -->
{body}"""


def stub_step_block(step: Any, resolver: Resolver) -> str:
    """Return the receive and send blocks of the stub OCS for one step."""
    answer = body_xml(step.response.root, resolver, Layout(4), skip=("Session-Id",))
    return f"""  <receive channel="channel-1">
    <command name="{step.request.command}">
      <avp name="Session-Id" value="dont_care"></avp>
    </command>
    <action>
      <store name="HbH" entity="HbH-id"></store>
      <store name="E2E" entity="EtE-id"></store>
      <store name="sid" entity="Session-Id"></store>
    </action>
  </receive>
  <send channel="channel-1">
    <action>
      <restore name="HbH" entity="HbH-id"></restore>
      <restore name="E2E" entity="EtE-id"></restore>
      <restore name="sid" entity="Session-Id"></restore>
    </action>
    <command name="{step.response.command}">
      <avp name="Session-Id" value="will_be_erased"></avp>
{answer}    </command>
  </send>

"""


def stub_scenario(group: list[Any], resolver: Resolver) -> str:
    """Return a stub OCS scenario that answers a session with the recorded answers."""
    blocks = "".join(stub_step_block(s, resolver) for s in group)
    return f"""{XML_HEAD}<!-- Generated by generate_scenarios.py. A stand-in OCS for a dry
     run of the client scenario of session {group[0].session_id}: it answers CER, then
     each request with an answer that carries the AVPs of the recorded one. -->
<scenario>

<init>
  <receive channel="channel-1">
    <command name="CER"></command>
  </receive>
  <send channel="channel-1">
    <command name="CEA">
      <avp name="Result-Code" value="2001"></avp>
      <avp name="Origin-Host" value="ocs.example.test"></avp>
      <avp name="Origin-Realm" value="example.test"></avp>
      <avp name="Host-IP-Address" value="0x0001c000020b"></avp>
      <avp name="Vendor-Id" value="0"></avp>
      <avp name="Product-Name" value="Seagull stub OCS"></avp>
      <avp name="Auth-Application-Id" value="4"></avp>
    </command>
  </send>
</init>

<traffic>
{blocks}</traffic>

</scenario>
"""


TRANSPORT = """  <define entity="transport" name="trans-1" file="libtrans_ip.so"
    create_function="create_cipio_instance"
    delete_function="delete_cipio_instance" init-args="type=tcp"></define>
"""


def param(name: str, value: object) -> str:
    """Return one traffic-param line of a configuration."""
    return f'  <define entity="traffic-param" name="{name}" value="{value}"></define>\n'


def client_config(dest: str, timeout_ms: int) -> str:
    """Return the Seagull configuration of the client."""
    params = {
        "number-calls": 1,
        "call-rate": 1,
        "call-timeout-ms": timeout_ms,
        "display-period": 1,
        "log-stat-period": 1,
        "log-stat-file": "../logs/client-stat.csv",
        "display-scenario-stat": "true",
        "display-protocol-stat": "true",
        "max-send": 200,
        "max-receive": 200,
        "max-simultaneous-calls": 1,
        "select-timeout-ms": 50,
    }
    lines = "".join(param(name, value) for name, value in params.items())
    return f"""{XML_HEAD}<configuration name="Diameter client">

  <!-- Written by generate_scenarios.py. dest is the address and port of the OCS.
       call-timeout-ms is how long Seagull waits for each answer. Each scenario holds
       one session, so number-calls is 1. -->
{TRANSPORT}
  <define entity="channel" name="channel-1" protocol="diameter-v1"
    transport="trans-1" open-args="mode=client;dest={dest}"></define>

{lines}
</configuration>
"""


def stub_config(listen: str) -> str:
    """Return the Seagull configuration of the stub OCS."""
    params = {
        "display-period": 1,
        "log-stat-period": 1,
        "log-stat-file": "../logs/server-stat.csv",
        "call-timeout-ms": 10000,
        "display-scenario-stat": "true",
        "display-protocol-stat": "true",
        "max-send": 2000,
        "max-receive": 2000,
        "max-simultaneous-calls": 2000,
        "select-timeout-ms": 50,
    }
    lines = "".join(param(name, value) for name, value in params.items())
    return f"""{XML_HEAD}<configuration name="Diameter stub OCS">

  <!-- Written by generate_scenarios.py. -->
{TRANSPORT}
  <define entity="channel" name="channel-1" protocol="diameter-v1"
    transport="trans-1" open-args="mode=server;source={listen}"></define>

{lines}
</configuration>
"""


def group_by_session(steps: list[Any]) -> list[list[Any]]:
    """Cut the steps into sessions at each change of Session-Id."""
    groups: list[list[Any]] = []
    for step in steps:
        if groups and groups[-1][0].session_id == step.session_id:
            groups[-1].append(step)
        else:
            groups.append([step])
    return groups


def session_kind(session_id: str) -> str:
    """Return the leading letters of a Session-Id in lower case."""
    match = re.match(r"[A-Za-z]+", session_id)
    return match.group(0).lower() if match else "session"


def build_dictionary(options: argparse.Namespace) -> Path:
    """Convert and merge the project dictionaries; return the Seagull dictionary."""
    names = options.dictionaries.split(",")
    folder = options.out / "dictionary"
    folder.mkdir(parents=True, exist_ok=True)
    argv = [str(options.dictionaries_dir), str(folder), "--combine", ",".join(names)]
    for pair in options.rename:
        argv += ["--rename", pair]
    if options.seagull_base:
        argv += ["--seagull-base", str(options.seagull_base)]
    report, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(report), contextlib.redirect_stderr(errors):
        status = dict2seagull.main(argv)
    if status != 0:
        details = errors.getvalue() + report.getvalue()
        raise GenerationError(f"the dictionary converter failed: {details}")
    final = folder / "diameter-dictionary.xml"
    final.write_bytes((folder / ("+".join(names) + ".xml")).read_bytes())
    for leftover in folder.glob("*.xml"):
        if leftover != final:
            leftover.unlink()
    (folder / "conversion-report.txt").write_text(report.getvalue(), encoding="utf-8", newline="\n")
    return final


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--steps", type=Path, required=True)
    parser.add_argument("--dictionaries-dir", type=Path, required=True)
    parser.add_argument("--dictionaries", required=True, help="names, in merge order")
    parser.add_argument("--out", type=Path, help="a folder that is new or empty")
    parser.add_argument(
        "--out-auto",
        type=Path,
        metavar="PARENT",
        help="write to the first free PARENT/Seagull-Scenario[-N]",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="move the old contents of a non-empty --out aside, then generate",
    )
    parser.add_argument("--seagull-dictionary", type=Path, help="already converted")
    parser.add_argument(
        "--seagull-base",
        type=Path,
        help="base_draft08.xml of Seagull, if the base is missing",
    )
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--dest", default="127.0.0.1:3868", help="address of the OCS")
    parser.add_argument("--host-ip", default="192.0.2.10", help="the CER announces it")
    parser.add_argument("--check-avps", default=CHECKS, type=lambda s: s.split(","))
    parser.add_argument("--rename", action="append", default=[], metavar="OLD=NEW")
    parser.add_argument(
        "--options",
        type=Path,
        help=f"options file to start from (default OUT_DIR/{OPTIONS_NAME}); "
        f"the result is written to OUT_DIR/{OPTIONS_NAME}",
    )
    parser.add_argument("--option", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--placeholder", action="append", default=[], metavar="AVP=NAME")
    return parser.parse_args(argv)


def resolve_options(args: argparse.Namespace) -> tuple[Path, Any]:
    """Read the options file, apply the command line to it, and validate."""
    path = args.options or args.out / OPTIONS_NAME
    try:
        options = scenario_options.load_options(path)
        scenario_options.apply_pairs(options, args.option, args.placeholder)
        options.validate()
    except scenario_options.OptionsError as error:
        raise GenerationError(str(error)) from error
    return path, options


def client_files(label: str, scenario: ClientScenario) -> dict[str, str]:
    """Return the files of a client scenario: ready, or template and its render."""
    text = scenario.text()
    options = scenario.options
    if options.mode != "template" or options.substitution != "text":
        return {f"{label}.client.xml": text}
    try:
        rendered = scenario_options.render(text, scenario.values)
    except scenario_options.OptionsError as error:
        raise GenerationError(f"{label}: {error}") from error
    return {f"{label}.client.xml.tpl": text, f"{label}.client.xml": rendered}


def write_scenarios(
    args: argparse.Namespace,
    groups: list[list[Any]],
    context: Context,
) -> list[str]:
    """Write the scenarios of every session; return notes about them."""
    folder = args.out / "scenario"
    folder.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    for number, group in enumerate(groups, 1):
        kind = session_kind(group[0].session_id)
        steps = "-".join(step.number for step in group)
        label = f"{number:02d}-{kind}-steps-{steps}"
        scenario = ClientScenario(group, context)
        files = client_files(label, scenario)
        files[f"{label}.stub-server.xml"] = stub_scenario(group, context.resolver)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="iso-8859-1", newline="\n")
        if f"{label}.client.xml.tpl" in files:
            values = folder / f"{label}.client.xml.values"
            scenario_options.write_values(values, scenario.values)
        notes.append(f"scenario {label}: {len(group)} step(s)")
        notes += [f"{label}: {note}" for note in scenario.substitution.notes]
    return notes


def write_config(options: argparse.Namespace) -> None:
    """Write the client configuration, the dry-run one, and the stub's."""
    folder = options.out / "config"
    folder.mkdir(parents=True, exist_ok=True)
    files = {
        "conf.client.xml": client_config(options.dest, options.timeout_ms),
        "conf.dry-run.client.xml": client_config(STUB_ADDRESS, options.timeout_ms),
        "conf.stub-server.xml": stub_config(STUB_ADDRESS),
    }
    for name, text in files.items():
        (folder / name).write_text(text, encoding="iso-8859-1", newline="\n")


def repair_notes(steps: list[Any]) -> list[str]:
    """Return one note for each repair that reading the recorded messages needed."""
    notes: list[str] = []
    for step in steps:
        for message in (step.request, step.response):
            notes += [f"{message.path.name}: {note}" for note in message.repairs]
    return notes


def prepare(
    options: argparse.Namespace,
    scenario_settings: Any,
) -> tuple[list[Any], Resolver, list[str]]:
    """Read the steps and the dictionaries; return the steps, resolver, and notes.

    A default-dwr tag is switched off, with a note, when the dictionary lacks DWR.
    """
    steps, problems = steps_format.load_steps(options.steps)
    if problems or not steps:
        raise GenerationError("the steps folder has problems: " + "; ".join(problems))
    notes = repair_notes(steps)
    if options.seagull_dictionary:
        final = options.out / "dictionary" / "diameter-dictionary.xml"
        final.parent.mkdir(parents=True, exist_ok=True)
        final.write_bytes(options.seagull_dictionary.read_bytes())
    else:
        final = build_dictionary(options)
    project = load_project_dictionaries(options)
    root = seagull_dictionary.read_dictionary(final)
    defined = seagull_dictionary.command_names_of(root)
    for step in steps:
        for command in (step.request.command, step.response.command):
            if command not in defined:
                raise GenerationError(f"the command {command} is not in {final}")
    if scenario_settings.tags.default_dwr and not {"DWR", "DWA"} <= defined:
        scenario_settings.tags.default_dwr = False
        notes.append("default-dwr is off: the dictionary has no DWR and DWA")
    names, first = seagull_dictionary.avp_names_of(root), seagull_dictionary.first_definitions(root)
    return steps, Resolver(project, names, first), notes


def choose_output(options: argparse.Namespace) -> list[str]:
    """Settle the output folder; refuse a non-empty one unless --replace is given.

    A folder that was not named is the first free Seagull-Scenario[-N], so it is
    always new. Returns notes for the report.
    """
    if bool(options.out) == bool(options.out_auto):
        raise GenerationError("give exactly one of --out and --out-auto")
    if options.out_auto:
        options.out = output_folder.next_free(options.out_auto, "Seagull-Scenario")
        return [f"output folder: {options.out} (new)"]
    if output_folder.is_empty(options.out) or options.replace:
        return []
    summary = output_folder.describe(options.out)
    raise GenerationError(
        f"the output folder is not empty: {summary}. Generating into it would mix "
        "the new files with the old ones. Use another folder, or pass --replace to "
        "move the old contents aside first"
    )


def archive_old(options: argparse.Namespace) -> list[str]:
    """Move the old contents of the output folder aside when --replace is given."""
    if not options.replace or output_folder.is_empty(options.out):
        return []
    summary = output_folder.describe(options.out)
    target = output_folder.archive_name(options.out)
    options.out.rename(target)
    return [f"replaced the old output: {summary}; moved to {target}"]


def main(argv: list[str]) -> int:
    """Generate everything; return the exit status."""
    options = parse_arguments(argv)
    try:
        early = choose_output(options)
        path, settings = resolve_options(options)
        early += archive_old(options)
        effective = copy.deepcopy(settings)
        steps, resolver, notes = prepare(options, effective)
        notes = early + notes
        used: set[str] = set()
        context = Context(resolver, effective, options.check_avps, options.host_ip, notes, used)
        notes += write_scenarios(options, group_by_session(steps), context)
        write_config(options)
        for key in sorted(set(settings.rules()) - used):
            notes.append(f"placeholder {key}: matched no AVP")
        path = options.out / OPTIONS_NAME
        scenario_options.save_options(path, settings)
    except GenerationError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    notes.append(f"options: {path}")
    notes += sorted(resolver.notes)
    notes += [f"{what}: {count} time(s)" for what, count in resolver.counters.items()]
    report = "\n".join(notes) + "\n"
    path = options.out / "generation-report.txt"
    path.write_text(report, encoding="utf-8", newline="\n")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
