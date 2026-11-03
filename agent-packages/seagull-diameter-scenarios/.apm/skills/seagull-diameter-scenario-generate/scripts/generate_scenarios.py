"""Generate Seagull scenarios from a folder of recorded Diameter requests and answers.

Usage:
  python generate_scenarios.py --steps STEPS_DIR --dictionaries-dir DIR
      --dictionaries A,B,C --out OUT_DIR [--timeout-ms 5000] [--dest HOST:PORT]
      [--host-ip IP] [--check-avps LIST] [--seagull-dictionary FILE]

STEPS_DIR holds Step-NNN-request.txt and Step-NNN-response.txt (see the
seagull-diameter-common skill). DIR holds the project's AVP dictionaries:
DiameterBaseProtocol.xml and the files named in --dictionaries, merged in that order.

Seagull ties an answer to its call by the Session-Id, so a scenario holds one
Diameter session. The steps are cut into sessions at each change of Session-Id.
Every session becomes one client scenario and one stub-OCS scenario for a dry run.
OUT_DIR also gets the client and stub configuration and the merged Seagull
dictionary.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
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

NTP_OFFSET = 2208988800
BASE = "DiameterBaseProtocol"
NUMERIC = {"Unsigned32", "Unsigned64", "Integer32", "Integer64", "Enumerated"}
CHECKS = "Result-Code,Session-Id,Auth-Application-Id,CC-Request-Type,CC-Request-Number"
STUB_ADDRESS = "127.0.0.1:3868"  # where the stub OCS of the dry run listens
XML_HEAD = '<?xml version="1.0" encoding="ISO-8859-1" ?>\n'
AVP_LINE = "      <avp name={} value={}></avp>\n"
CHECK_LINE = '      <check-value name={} behaviour="error"></check-value>\n'


class GenerationError(Exception):
    """The input cannot be turned into a scenario."""


@dataclass
class Resolver:
    """Find the Seagull name and the project definition of an AVP in a message."""

    project: dict[str, list[Any]]
    seagull_names: dict[tuple[int, int], list[str]]
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
        return (wanted if wanted in names else names[0]), chosen


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


def read_seagull_dictionary(path: Path) -> ElementTree.Element:
    """Parse a Seagull dictionary, which may have a comment before the declaration."""
    text = path.read_text(encoding="iso-8859-1")
    _, marker, body = text.partition("<protocol")
    return ElementTree.fromstring(marker + body)


def avp_names_of(root: ElementTree.Element) -> dict[tuple[int, int], list[str]]:
    """Return {(vendor, code): [Seagull AVP names]} of a Seagull dictionary."""
    names: dict[tuple[int, int], list[str]] = {}
    for define in root.findall("./dictionary/avp/define"):
        fields = {s.get("name"): s.get("value") for s in define.findall("setfield")}
        key = (int(fields.get("Vendor-ID") or 0), int(fields.get("avp-code") or 0))
        names.setdefault(key, []).append(define.get("name", ""))
    return names


def command_names_of(root: ElementTree.Element) -> set[str]:
    """Return the names of the commands that a Seagull dictionary defines."""
    return {d.get("name", "") for d in root.findall("./dictionary/command/define")}


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


def avp_xml(
    element: ElementTree.Element,
    parent_vendor: int | None,
    resolver: Resolver,
    indent: int,
) -> str:
    """Return the Seagull <avp> element for an AVP of a message and its members."""
    name, avp = resolver.resolve(element.tag, parent_vendor)
    pad = "  " * indent
    members = list(element)
    if members:
        parts = [avp_xml(m, avp.vendor_id, resolver, indent + 1) for m in members]
        return f"{pad}<avp name={quoteattr(name)}>\n{''.join(parts)}{pad}</avp>\n"
    text = element.text or ""
    if not text.strip():
        raise GenerationError(f"AVP {element.tag} has no value")
    value = encode_value(avp, text, resolver.counters)
    return f"{pad}<avp name={quoteattr(name)} value={quoteattr(value)}></avp>\n"


def body_xml(
    root: ElementTree.Element,
    resolver: Resolver,
    indent: int,
    skip: tuple = (),
) -> str:
    """Return the <avp> elements for the children of a message."""
    parts = [avp_xml(c, None, resolver, indent) for c in root if c.tag not in skip]
    return "".join(parts)


def command_xml(message: Any, resolver: Resolver, indent: int) -> str:
    """Return the <command> element for a recorded message."""
    pad = "  " * indent
    body = body_xml(message.root, resolver, indent + 1)
    return f'{pad}<command name="{message.command}">\n{body}{pad}</command>\n'


def expected_checks(
    step: Any,
    resolver: Resolver,
    names: list[str],
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
        pairs.append((seagull_name, encode_value(avp, text, resolver.counters)))
    return pairs, notes


def receive_block(step: Any, resolver: Resolver, names: list[str], notes: list[str]):
    """Return the <receive> block that waits for the answer and checks it."""
    pairs, skipped = expected_checks(step, resolver, names)
    notes += skipped
    avps, checks = "", ""
    for name, value in pairs:
        avps += AVP_LINE.format(quoteattr(name), quoteattr(value))
        checks += CHECK_LINE.format(quoteattr(name))
    return f"""  <receive channel="channel-1">
    <command name="{step.response.command}">
{avps}    </command>
    <action>
      <stop-timer></stop-timer>
{checks}    </action>
  </receive>
"""


def step_block(step: Any, resolver: Resolver, names: list[str], notes: list[str]):
    """Return the send and receive blocks of one step."""
    number = step.request.avp_text("CC-Request-Number")
    where = "" if number is None else f", CC-Request-Number {number}"
    title = f"Step {step.number}: {step.label}, session {step.session_id}{where}"
    return f"""  <!-- ===== {title} ===== -->
  <send channel="channel-1">
    <action>
      <inc-counter name="HbH-counter"> </inc-counter>
      <inc-counter name="EtE-counter"> </inc-counter>
      <set-value name="HbH-id" format="$(HbH-counter)"></set-value>
      <set-value name="EtE-id" format="$(EtE-counter)"></set-value>
      <set-value name="Session-Id" format={quoteattr(step.session_id)}></set-value>
    </action>
{command_xml(step.request, resolver, 2)}    <action>
      <start-timer></start-timer>
    </action>
  </send>

{receive_block(step, resolver, names, notes)}
"""


def cer_block(first: Any, host_ip: str) -> str:
    """Return the capabilities exchange of a client scenario, from the first step."""
    request = first.request
    host = request.avp_text("Origin-Host") or "seagull.example.test"
    realm = request.avp_text("Origin-Realm") or "example.test"
    application = request.avp_text("Auth-Application-Id") or "4"
    return f"""  <send channel="channel-1">
    <command name="CER">
      <avp name="Origin-Host" value={quoteattr(host)}></avp>
      <avp name="Origin-Realm" value={quoteattr(realm)}></avp>
      <avp name="Host-IP-Address" value="{to_address_hex(host_ip)}"></avp>
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


def client_scenario(
    group: list[Any],
    resolver: Resolver,
    options: argparse.Namespace,
    notes: list[str],
) -> str:
    """Return the client scenario of one session."""
    first = group[0]
    numbers = ", ".join(s.number for s in group)
    labels = ", ".join(s.label for s in group)
    blocks = "".join(step_block(s, resolver, options.check_avps, notes) for s in group)
    return f"""{XML_HEAD}<!-- Generated by generate_scenarios.py. Do not edit; generate again.
     Session {first.session_id}: step file(s) {numbers} ({labels}).
     The AVPs are sent as they were recorded, with fixed values; only the Hop-by-Hop
     and End-to-End identifiers come from counters. A time is written as NTP hex and
     an IP address of an Address AVP as Address hex. The response timeout is the
     call-timeout-ms parameter of the configuration: Seagull waits that long for
     each answer. After each answer the scenario checks the fields of its receive
     block. -->
<scenario>

<counter>
  <counterdef name="HbH-counter" init="1000"> </counterdef>
  <counterdef name="EtE-counter" init="2000"> </counterdef>
</counter>

<init>
{cer_block(first, options.host_ip)}</init>

<traffic>
{blocks}</traffic>

</scenario>
"""


def stub_step_block(step: Any, resolver: Resolver) -> str:
    """Return the receive and send blocks of the stub OCS for one step."""
    answer = body_xml(step.response.root, resolver, 4, skip=("Session-Id",))
    return f"""  <receive channel="channel-1">
    <command name="{step.request.command}">
      <avp name="Session-Id" value="dont_care"> </avp>
    </command>
    <action>
      <store name="HbH" entity="HbH-id"></store>
      <store name="E2E" entity="EtE-id"></store>
      <store name="sid" entity="Session-Id"></store>
    </action>
  </receive>
  <send channel="channel-1">
    <action>
      <restore name="HbH" entity="HbH-id"> </restore>
      <restore name="E2E" entity="EtE-id"> </restore>
      <restore name="sid" entity="Session-Id"> </restore>
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
    <command name="CER">
    </command>
  </receive>
  <send channel="channel-1">
    <command name="CEA">
      <avp name="Result-Code" value="2001"> </avp>
      <avp name="Origin-Host" value="ocs.example.test"> </avp>
      <avp name="Origin-Realm" value="example.test"> </avp>
      <avp name="Host-IP-Address" value="0x0001c000020b"> </avp>
      <avp name="Vendor-Id" value="0"> </avp>
      <avp name="Product-Name" value="Seagull stub OCS"> </avp>
      <avp name="Auth-Application-Id" value="4"> </avp>
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
    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        status = dict2seagull.main(argv)
    if status != 0:
        raise GenerationError(f"the dictionary converter failed: {report.getvalue()}")
    final = folder / "diameter-dictionary.xml"
    final.write_bytes((folder / ("+".join(names) + ".xml")).read_bytes())
    for leftover in folder.glob("*.xml"):
        if leftover != final:
            leftover.unlink()
    (folder / "conversion-report.txt").write_text(
        report.getvalue(),
        encoding="utf-8",
        newline="\n",
    )
    return final


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--steps", type=Path, required=True)
    parser.add_argument("--dictionaries-dir", type=Path, required=True)
    parser.add_argument("--dictionaries", required=True, help="names, in merge order")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seagull-dictionary", type=Path, help="already converted")
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--dest", default="127.0.0.1:3868", help="address of the OCS")
    parser.add_argument("--host-ip", default="192.0.2.10", help="the CER announces it")
    parser.add_argument("--check-avps", default=CHECKS, type=lambda s: s.split(","))
    parser.add_argument("--rename", action="append", default=[], metavar="OLD=NEW")
    return parser.parse_args(argv)


def write_scenarios(
    options: argparse.Namespace,
    groups: list[list[Any]],
    resolver: Resolver,
) -> list[str]:
    """Write the scenarios of every session; return notes about them."""
    folder = options.out / "scenario"
    folder.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    for number, group in enumerate(groups, 1):
        kind = session_kind(group[0].session_id)
        steps = "-".join(step.number for step in group)
        label = f"{number:02d}-{kind}-steps-{steps}"
        files = {
            f"{label}.client.xml": client_scenario(group, resolver, options, notes),
            f"{label}.stub-server.xml": stub_scenario(group, resolver),
        }
        for name, text in files.items():
            (folder / name).write_text(text, encoding="iso-8859-1", newline="\n")
        notes.append(f"scenario {label}: {len(group)} step(s)")
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


def prepare(options: argparse.Namespace) -> tuple[list[Any], Resolver, list[str]]:
    """Read the steps and the dictionaries; return the steps, resolver, and notes."""
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
    names = [BASE, *options.dictionaries.split(",")]
    project = load_project([options.dictionaries_dir / f"{n}.xml" for n in names])
    root = read_seagull_dictionary(final)
    defined = command_names_of(root)
    for step in steps:
        for command in (step.request.command, step.response.command):
            if command not in defined:
                raise GenerationError(f"the command {command} is not in {final}")
    return steps, Resolver(project, avp_names_of(root)), notes


def main(argv: list[str]) -> int:
    """Generate everything; return the exit status."""
    options = parse_arguments(argv)
    try:
        steps, resolver, notes = prepare(options)
        notes += write_scenarios(options, group_by_session(steps), resolver)
        write_config(options)
    except GenerationError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    notes += sorted(resolver.notes)
    notes += [f"{what}: {count} time(s)" for what, count in resolver.counters.items()]
    report = "\n".join(notes) + "\n"
    path = options.out / "generation-report.txt"
    path.write_text(report, encoding="utf-8", newline="\n")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
