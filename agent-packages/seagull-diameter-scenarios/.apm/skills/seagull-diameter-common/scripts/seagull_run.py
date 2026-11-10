"""Run the dry run or the check of converted dictionaries with the Seagull that the settings name.

Usage:
  python seagull_run.py dry-run OUTPUT_DIR_OR_SCENARIO [--runner docker|windows] [--seagull-exe PATH]
      [--image IMAGE] [--logs DIR] [--timeout S]
  python seagull_run.py check-converted CONVERTED_DIR [the same options]

For dry-run, a folder is the output folder of a generation and every scenario of it runs. A file is one
client scenario, OUTPUT_DIR/scenario/<name>.client.xml, and only that scenario runs.

The script reads SEAGULL_RUNNER, SEAGULL_WINDOWS_PATH, and SEAGULL_DOCKER_IMAGE the way
seagull_config.py does, so the caller passes only the folder or the file. With windows it runs
seagull_windows_run.py; with docker it runs dry-run.sh or check-converted.sh in the Seagull image
(through wsl on Windows, where the folders are given as /mnt/<drive>/... paths). --runner,
--seagull-exe, and --image override the settings. --logs and --timeout apply to windows only.

It prints what the runner prints and exits with the status of the run. Exit status 2 is for wrong
arguments, and 4 is for a setting that has no value: the runner, or the path of seagull.exe for
windows. The message says so; it is the signal to ask the user, and only then.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
seagull_config = importlib.import_module("seagull_config")
seagull_windows_run = importlib.import_module("seagull_windows_run")

SKILLS = Path(__file__).resolve().parents[2]
DOCKER_SCRIPTS = {
    "dry-run": SKILLS / "seagull-diameter-generate-scenarios" / "scripts" / "dry-run.sh",
    "check-converted": SKILLS / "seagull-diameter-convert-dictionaries" / "scripts" / "check-converted.sh",
}
EXIT_UNSET = seagull_config.EXIT_UNSET


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("command", choices=tuple(DOCKER_SCRIPTS))
    parser.add_argument("folder", type=Path)
    parser.add_argument("--runner", choices=seagull_config.RUNNERS)
    parser.add_argument("--seagull-exe")
    parser.add_argument("--image")
    parser.add_argument("--logs", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args(argv)


def setting(key: str) -> str:
    """Return the value of a setting, looked up from the current folder; empty when it has none."""
    folder = seagull_config.settings_folder(Path.cwd())
    value, _ = seagull_config.resolve(key, folder, Path.home(), dict(os.environ))
    return value


def to_wsl(path: Path) -> str:
    """Return the /mnt/<drive>/... form of a Windows path, which is how wsl sees it."""
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return resolved.as_posix()
    return f"/mnt/{drive}/" + "/".join(resolved.parts[1:])


def run_docker(args: argparse.Namespace) -> int:
    """Run the Docker script of the command; return its exit status."""
    script = DOCKER_SCRIPTS[args.command]
    image = args.image or setting("SEAGULL_DOCKER_IMAGE")
    folder, name = seagull_windows_run.split_target(args.folder) if args.command == "dry-run" else (args.folder, None)
    scenario = [name] if name else []
    if os.name == "nt":
        command = ["wsl", "sh", to_wsl(script), to_wsl(folder), image, *scenario]
    else:
        command = ["sh", str(script), str(folder), image, *scenario]
    return subprocess.run(command, check=False).returncode


def run_windows(args: argparse.Namespace) -> int:
    """Run seagull_windows_run.py; return its exit status, or 4 when the path of seagull.exe is not set."""
    exe = args.seagull_exe or setting("SEAGULL_WINDOWS_PATH")
    if not exe:
        sys.stderr.write("error: SEAGULL_WINDOWS_PATH is not set; ask the user where seagull.exe is\n")
        return EXIT_UNSET
    forwarded = [args.command, str(args.folder), "--seagull-exe", exe, "--timeout", str(args.timeout)]
    if args.logs:
        forwarded += ["--logs", str(args.logs)]
    return int(seagull_windows_run.main(forwarded))


def main(argv: list[str]) -> int:
    """Pick the runner from the arguments or the settings and run it; return the exit status."""
    args = parse_arguments(argv)
    try:
        runner = args.runner or setting("SEAGULL_RUNNER")
        if not runner:
            path = setting("SEAGULL_WINDOWS_PATH")
            windows = f"windows (seagull.exe at {path})" if path else "windows (and where its seagull.exe is)"
            image = setting("SEAGULL_DOCKER_IMAGE")
            options = f"docker (image {image}) or {windows}"
            sys.stderr.write(f"error: SEAGULL_RUNNER is not set; ask the user which Seagull to use: {options}\n")
            return EXIT_UNSET
        return run_windows(args) if runner == "windows" else run_docker(args)
    except (seagull_config.ConfigError, ValueError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
