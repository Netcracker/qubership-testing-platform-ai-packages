"""Read and write the settings that tell the skills where Seagull runs.

Usage:
  python seagull_config.py show [--folder DIR]
  python seagull_config.py get KEY [--folder DIR]
  python seagull_config.py set KEY VALUE [--home] [--folder DIR]

The settings are in one JSON file, .seagull-diameter/config.json. Only two paths are read, in
this order: the one in the session folder (DIR, by default the current folder), then the one in
the user's home folder. Nothing else is searched. A value is taken from the environment variable
of the same name first, then from the file, then from the default of the key.

  SEAGULL_RUNNER        docker or windows: where the dry run and the dictionary check start Seagull
  SEAGULL_DOCKER_IMAGE  the Seagull image for docker (default seagull:local)
  SEAGULL_WINDOWS_PATH  the seagull.exe of Seagull for Windows, for windows
  SEAGULL_DICTIONARY_PATH  the one Seagull dictionary file that the scenario generator reads

"get" prints the value and exits with 0, or exits with 4 and prints nothing when the key has no
value, which is the signal to ask the user. "set" writes to the session folder, or to the home
folder with --home, and keeps the other keys of the file. A password or a token is never a setting.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CONFIG_DIR = ".seagull-diameter"
CONFIG_NAME = "config.json"
RUNNERS = ("docker", "windows")
DEFAULTS = {"SEAGULL_DOCKER_IMAGE": "seagull:local"}
KEYS = ("SEAGULL_RUNNER", "SEAGULL_DOCKER_IMAGE", "SEAGULL_WINDOWS_PATH", "SEAGULL_DICTIONARY_PATH")
EXIT_UNSET = 4


class ConfigError(Exception):
    """The key or the value is not valid, or the file cannot be read."""


def config_paths(folder: Path, home: Path) -> list[Path]:
    """Return the two places of the file, the session folder first."""
    return [folder / CONFIG_DIR / CONFIG_NAME, home / CONFIG_DIR / CONFIG_NAME]


def read_file(path: Path) -> dict[str, str]:
    """Return the settings of one file; a missing file gives none."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"{path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: expected a JSON object")
    return {key: str(value) for key, value in data.items()}


def resolve(key: str, folder: Path, home: Path, environ: dict[str, str]) -> tuple[str, str]:
    """Return the value of a key and where it came from; both are empty when it has none."""
    check_key(key)
    if environ.get(key):
        return environ[key], "environment"
    for path in config_paths(folder, home):
        value = read_file(path).get(key, "")
        if value:
            return value, str(path)
    if key in DEFAULTS:
        return DEFAULTS[key], "default"
    return "", ""


def check_key(key: str) -> None:
    """Raise ConfigError unless the key is one of the settings."""
    if key not in KEYS:
        raise ConfigError(f"unknown setting {key!r}; known: {', '.join(KEYS)}")


def check_value(key: str, value: str) -> None:
    """Raise ConfigError unless the value fits the key."""
    check_key(key)
    if key == "SEAGULL_RUNNER" and value not in RUNNERS:
        raise ConfigError(f"SEAGULL_RUNNER must be one of {', '.join(RUNNERS)}, not {value!r}")
    if key == "SEAGULL_WINDOWS_PATH" and not Path(value).is_file():
        raise ConfigError(f"SEAGULL_WINDOWS_PATH: no file {value}")
    if key == "SEAGULL_DICTIONARY_PATH" and not Path(value).is_file():
        raise ConfigError(f"SEAGULL_DICTIONARY_PATH: no file {value}; it must be one file")
    if not value.strip():
        raise ConfigError(f"{key}: the value is empty")


def save(key: str, value: str, folder: Path, home: Path, use_home: bool = False) -> Path:
    """Write one setting to the session file, or to the home file; keep the other keys."""
    check_value(key, value)
    path = config_paths(folder, home)[1 if use_home else 0]
    data = read_file(path)
    data[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("command", choices=("show", "get", "set"))
    parser.add_argument("key", nargs="?")
    parser.add_argument("value", nargs="?")
    parser.add_argument("--home", action="store_true", help="write to the home folder")
    parser.add_argument("--folder", type=Path, default=Path.cwd(), help="the session folder")
    return parser.parse_args(argv)


def run(args: argparse.Namespace, home: Path | None = None) -> int:
    """Do the command; return the exit status. The home folder is the user's, unless given."""
    home = home or Path.home()
    if args.command == "show":
        for key in KEYS:
            value, source = resolve(key, args.folder, home, dict(os.environ))
            sys.stdout.write(f"{key}={value}  ({source or 'not set'})\n")
        return 0
    if not args.key:
        raise ConfigError(f"{args.command} needs a key")
    if args.command == "get":
        value, _ = resolve(args.key, args.folder, home, dict(os.environ))
        sys.stdout.write(value + "\n" if value else "")
        return 0 if value else EXIT_UNSET
    if args.value is None:
        raise ConfigError("set needs a value")
    path = save(args.key, args.value, args.folder, home, args.home)
    sys.stdout.write(f"{args.key} saved in {path}\n")
    return 0


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    args = parse_arguments(argv)
    try:
        return run(args)
    except ConfigError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
