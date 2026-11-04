"""Options and placeholders of generated Seagull scenarios.

The options live in a small INI file, scenario-options.ini, that the generator reads
and writes. The file has three sections:

  [output]       mode (scenario or template) and substitution (text or native)
  [tags]         default-dwr, generated-session-id, generated-timestamp, log,
                 check-presence, and wait-ms
  [placeholders] one AVP = PLACEHOLDER pair for each value to parameterize

In a placeholder pair the name is the AVP name as the scenario file spells it. A
name alone matches that AVP at any depth. A path such as
Multiple-Services-Credit-Control/Rating-Group matches only inside that group, and
GGSN-Address[2] matches the second AVP of that name among its siblings. The most
specific key wins. The key wait-ms stands for the pause between steps.

A scenario in template mode holds @@PLACEHOLDER@@ where a value was, and
render() replaces each one from a values dictionary.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

PLACEHOLDER = re.compile(r"@@([A-Za-z][A-Za-z0-9_]*)@@")
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
SEGMENT = re.compile(r"([A-Za-z0-9_-]+)(?:\[(\d+)\])?")
MODES = ("scenario", "template")
SUBSTITUTIONS = ("text", "native")
BOOLEANS = {"true": True, "false": False}
TAGS = (
    "default-dwr",
    "generated-session-id",
    "generated-timestamp",
    "log",
    "check-presence",
)
OPTION_KEYS = ("mode", "substitution", *TAGS, "wait-ms", "time-method")
FILE_HEAD = """# Options of the generated Seagull scenarios.
# mode: scenario writes ready scenarios; template writes scenarios whose chosen
#   values are placeholders.
# substitution: text writes @@NAME@@ for an external substitution (see
#   apply_placeholders.py); native keeps the value in the scenario as a Seagull
#   variable that is set once and restored in the later steps.
# time-method: the Seagull method that returns the current time, for
#   generated-timestamp and for the time part of a generated Session-Id. The Seagull
#   1.8.3 of this image defines none, so it stays empty until the method is known.
# [placeholders] holds AVP-name = PLACEHOLDER pairs. A name may be a path such as
#   Multiple-Services-Credit-Control/Rating-Group, with an index such as
#   GGSN-Address[2] for a repeated AVP. wait-ms is the pause between steps.
"""


class OptionsError(Exception):
    """The options file or an option given on the command line is invalid."""


@dataclass
class Tags:
    """The tags that a scenario may carry, with the defaults of a plain scenario."""

    default_dwr: bool = True
    generated_session_id: bool = False
    generated_timestamp: bool = False
    log: bool = False
    check_presence: bool = False
    wait_ms: int = 0
    time_method: str = ""


@dataclass
class Options:
    """The options of one generation, with the defaults of a ready scenario."""

    mode: str = "scenario"
    substitution: str = "text"
    tags: Tags = field(default_factory=Tags)
    placeholders: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise OptionsError for a value that the generator cannot use."""
        if self.mode not in MODES:
            raise OptionsError(f"mode must be one of {MODES}, not {self.mode!r}")
        if self.substitution not in SUBSTITUTIONS:
            message = f"substitution must be one of {SUBSTITUTIONS}"
            raise OptionsError(f"{message}, not {self.substitution!r}")
        if self.tags.wait_ms < 0:
            raise OptionsError("wait-ms must not be negative")
        if self.tags.generated_timestamp and not self.tags.time_method:
            message = "generated-timestamp needs time-method, the name of a Seagull"
            raise OptionsError(f"{message} method that returns the time")
        for key, holder in self.placeholders.items():
            parse_key(key)
            if not NAME.fullmatch(holder):
                message = f"placeholder {holder!r} of {key} is not a name such as X_Y"
                raise OptionsError(message)

    def rules(self) -> dict[str, str]:
        """Return the placeholder pairs that apply: none in a ready scenario."""
        return dict(self.placeholders) if self.mode == "template" else {}

    def set_option(self, key: str, text: str) -> None:
        """Set one option from its INI key and text."""
        if key not in OPTION_KEYS:
            raise OptionsError(
                f"unknown option {key!r}; known: {', '.join(OPTION_KEYS)}"
            )
        attribute = key.replace("-", "_")
        if key in TAGS:
            if text.strip().lower() not in BOOLEANS:
                raise OptionsError(f"{key} must be true or false, not {text!r}")
            setattr(self.tags, attribute, BOOLEANS[text.strip().lower()])
        elif key == "wait-ms":
            if not text.strip().isdigit():
                raise OptionsError(
                    f"wait-ms must be a number of milliseconds: {text!r}"
                )
            self.tags.wait_ms = int(text)
        elif key == "time-method":
            self.tags.time_method = text.strip()
        else:
            setattr(self, attribute, text.strip())

    def set_placeholder(self, key: str, holder: str) -> None:
        """Add or replace a pair; an empty placeholder removes the pair."""
        parse_key(key)
        holder = holder.strip().strip("@")
        if holder:
            self.placeholders[key] = holder
        else:
            self.placeholders.pop(key, None)


def parse_key(key: str) -> list[tuple[str, int]]:
    """Return the (name, index) segments of a placeholder key; index 0 is any."""
    segments = []
    for part in key.split("/"):
        match = SEGMENT.fullmatch(part.strip())
        if not match:
            raise OptionsError(f"{key!r} is not an AVP name, path, or name[index]")
        segments.append((match.group(1), int(match.group(2) or 0)))
    return segments


def lookup(
    rules: dict[str, str],
    path: list[tuple[str, str, int]],
) -> tuple[str, str] | None:
    """Return the (key, placeholder) of the most specific rule for an AVP path.

    Each path entry is (Seagull name, recorded name, position among the siblings
    of that name, counted from 1). A key matches the end of the path.
    """
    best: tuple[str, str] | None = None
    best_length = 0
    for key, holder in rules.items():
        segments = parse_key(key)
        if len(segments) > len(path) or len(segments) <= best_length:
            continue
        start = len(path) - len(segments)
        tail = path[start:]
        for (name, index), (seagull, recorded, position) in zip(segments, tail):
            if name not in (seagull, recorded) or index not in (0, position):
                break
        else:
            best, best_length = (key, holder), len(segments)
    return best


def apply_pairs(
    options: Options,
    option_pairs: list[str],
    placeholder_pairs: list[str],
) -> None:
    """Apply KEY=VALUE options and AVP=NAME placeholder pairs of a command line."""
    for pair in option_pairs:
        key, separator, value = pair.partition("=")
        if not separator:
            raise OptionsError(f"--option {pair!r}: expected KEY=VALUE")
        options.set_option(key.strip(), value)
    for pair in placeholder_pairs:
        key, separator, holder = pair.partition("=")
        if not separator:
            raise OptionsError(f"--placeholder {pair!r}: expected AVP=NAME")
        options.set_placeholder(key.strip(), holder)


def load_options(path: Path) -> Options:
    """Read an options file; a missing file gives the defaults."""
    options = Options()
    if not path.exists():
        return options
    parser = configparser.ConfigParser(interpolation=None, delimiters=("=",))
    parser.optionxform = str  # type: ignore[assignment,method-assign]
    try:
        parser.read_string(path.read_text(encoding="utf-8"))
    except configparser.Error as error:
        raise OptionsError(f"{path}: {error}") from error
    for section in ("output", "tags"):
        for key, text in parser.items(section) if parser.has_section(section) else []:
            options.set_option(key, text)
    if parser.has_section("placeholders"):
        for key, holder in parser.items("placeholders"):
            options.set_placeholder(key, holder)
    options.validate()
    return options


def save_options(path: Path, options: Options) -> None:
    """Write an options file with LF line endings."""
    lines = [FILE_HEAD, "[output]", f"mode = {options.mode}"]
    lines += [f"substitution = {options.substitution}", "", "[tags]"]
    for key in TAGS:
        value = getattr(options.tags, key.replace("-", "_"))
        lines.append(f"{key} = {'true' if value else 'false'}")
    lines += [f"wait-ms = {options.tags.wait_ms}"]
    lines += [f"time-method = {options.tags.time_method}"]
    lines += ["", "[placeholders]"]
    lines += [f"{key} = {holder}" for key, holder in options.placeholders.items()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def wrap(value: str, holder: str) -> str:
    """Return the value as a placeholder; a 0x prefix stays outside the markers."""
    prefix = "0x" if value.lower().startswith("0x") else ""
    return f"{prefix}@@{holder}@@"


def unwrapped(value: str) -> str:
    """Return the text that a placeholder stands for: the value without 0x."""
    return value[2:] if value.lower().startswith("0x") else value


def read_values(path: Path) -> dict[str, str]:
    """Read NAME=value lines; blank lines and lines starting with # are skipped."""
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or not NAME.fullmatch(name.strip()):
            raise OptionsError(f"{path}:{number}: expected NAME=value")
        values[name.strip()] = value
    return values


def write_values(path: Path, values: dict[str, str]) -> None:
    """Write NAME=value lines with LF line endings."""
    lines = ["# Values of the placeholders of the template next to this file."]
    lines += [f"{name}={value}" for name, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def placeholder_names(text: str) -> list[str]:
    """Return the placeholder names in a text, in order of first use."""
    return list(dict.fromkeys(PLACEHOLDER.findall(text)))


def render(text: str, values: dict[str, str]) -> str:
    """Replace each @@NAME@@ by its value, escaped for XML text.

    Raises OptionsError that names every placeholder without a value.
    """
    missing = [name for name in placeholder_names(text) if name not in values]
    if missing:
        raise OptionsError("no value for placeholder(s) " + ", ".join(missing))
    quote = {'"': "&quot;"}
    return PLACEHOLDER.sub(lambda match: escape(values[match.group(1)], quote), text)
