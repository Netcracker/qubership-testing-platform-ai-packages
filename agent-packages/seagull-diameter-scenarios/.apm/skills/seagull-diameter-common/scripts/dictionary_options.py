"""Options of the dictionary conversion: the flags of commands and of AVPs.

The project dictionaries give the V, M, and P bits of an AVP but no flags of a command, so
dict2seagull.py writes 128 (R) for a request and 0 for an answer, and takes the M and P bits
of an AVP from the source. This module lets an options file, or the command line, change
that. Without any option the output is what the converter wrote before.

The options file, dictionary-options.ini:

  [command-flags]
  request = 128      flags of every request that no name below overrides
  answer = 0         flags of every answer that no name below overrides
  CCR = 192          flags of one request or answer, by its Seagull name

  [avp-flags]
  vendor-mandatory = source   source, yes, or no: the M bit of every vendor AVP
  PDP-Address = 128           flags of one AVP, by its name in the output

Requires Python 3.9 or later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VENDOR_BIT = 128
MANDATORY_BIT = 64
POLICIES = ("source", "yes", "no")
REQUEST_KEY = "request"
ANSWER_KEY = "answer"
POLICY_KEY = "vendor-mandatory"
HEAD = "# Read by dict2seagull.py (--options). Delete a line to restore the default.\n"


class DictionaryOptionsError(Exception):
    """The options file or an option of the command line is invalid."""


def parse_flags(where: str, text: str) -> int:
    """Return a flags byte from text; raise DictionaryOptionsError unless it is 0 to 255."""
    try:
        value = int(text.strip())
    except ValueError:
        raise DictionaryOptionsError(f"{where}: {text.strip()!r} is not a number") from None
    if not 0 <= value <= 255:
        raise DictionaryOptionsError(f"{where}: {value} is not a flags byte, 0 to 255")
    return value


@dataclass
class FlagOptions:
    """The flags of commands and AVPs, with the converter's defaults."""

    request: int = 128
    answer: int = 0
    commands: dict[str, int] = field(default_factory=dict)
    vendor_mandatory: str = "source"
    avps: dict[str, int] = field(default_factory=dict)

    def command_flags(self, name: str, answer: bool) -> int:
        """Return the flags of the request or answer with the Seagull name, such as CCR."""
        return self.commands.get(name, self.answer if answer else self.request)

    def avp_flags(self, name: str, source: int, vendor_specific: bool) -> int:
        """Return the flags of an AVP, given the flags that its source dictionary implies."""
        if name in self.avps:
            return self.avps[name]
        if vendor_specific and self.vendor_mandatory != "source":
            if self.vendor_mandatory == "yes":
                return source | MANDATORY_BIT
            return source & ~MANDATORY_BIT
        return source

    def set_command(self, key: str, text: str) -> None:
        """Set the flags of requests, answers, or one command, by key."""
        value = parse_flags(f"command-flags {key}", text)
        if key == REQUEST_KEY:
            self.request = value
        elif key == ANSWER_KEY:
            self.answer = value
        else:
            self.commands[key] = value

    def set_avp(self, key: str, text: str) -> None:
        """Set the vendor-mandatory policy, or the flags of one AVP, by key."""
        if key != POLICY_KEY:
            self.avps[key] = parse_flags(f"avp-flags {key}", text)
            return
        policy = text.strip()
        if policy not in POLICIES:
            allowed = ", ".join(POLICIES)
            raise DictionaryOptionsError(f"avp-flags {key}: {policy!r} is not one of {allowed}")
        self.vendor_mandatory = policy


def split_pair(option: str, pair: str) -> tuple[str, str]:
    """Split KEY=VALUE of a command line option."""
    key, separator, value = pair.partition("=")
    if not separator or not key.strip():
        raise DictionaryOptionsError(f"{option} {pair!r}: expected KEY=VALUE")
    return key.strip(), value


def apply_pairs(
    options: FlagOptions,
    command_pairs: list[str],
    avp_pairs: list[str],
    policy: str | None,
) -> None:
    """Apply the --command-flags and --avp-flags pairs and --vendor-mandatory of a command line."""
    for pair in command_pairs:
        options.set_command(*split_pair("--command-flags", pair))
    for pair in avp_pairs:
        options.set_avp(*split_pair("--avp-flags", pair))
    if policy is not None:
        options.set_avp(POLICY_KEY, policy)


def load_options(path: Path | None) -> FlagOptions:
    """Read an options file; no path or a missing file gives the defaults."""
    options = FlagOptions()
    if path is None:
        return options
    if not path.exists():
        raise DictionaryOptionsError(f"{path}: no such options file")
    section = ""
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        key, separator, text = line.partition("=")
        if not separator or section not in ("command-flags", "avp-flags"):
            expected = "[command-flags], [avp-flags], or KEY = VALUE"
            raise DictionaryOptionsError(f"{path}:{number}: expected {expected}")
        if section == "command-flags":
            options.set_command(key.strip(), text)
        else:
            options.set_avp(key.strip(), text)
    return options


def save_options(path: Path, options: FlagOptions) -> None:
    """Write an options file with LF line endings."""
    lines = [HEAD, "[command-flags]"]
    lines += [f"{REQUEST_KEY} = {options.request}", f"{ANSWER_KEY} = {options.answer}"]
    lines += [f"{key} = {value}" for key, value in options.commands.items()]
    lines += ["", "[avp-flags]", f"{POLICY_KEY} = {options.vendor_mandatory}"]
    lines += [f"{key} = {value}" for key, value in options.avps.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
