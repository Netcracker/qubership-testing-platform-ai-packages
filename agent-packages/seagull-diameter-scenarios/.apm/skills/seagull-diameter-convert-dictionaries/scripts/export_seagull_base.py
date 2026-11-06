"""Copy the base dictionary of the Seagull distribution to a file, for convert_dictionaries.py.

Usage:
  python export_seagull_base.py --runner windows --seagull-exe PATH --out FILE
  python export_seagull_base.py --runner docker [--image IMAGE] --out FILE

Seagull ships base_draft08.xml in diameter-env/config. With the runner windows the script
copies it from next to seagull.exe; with docker it reads it out of the Seagull image. It
prints the path of FILE, which is the value of --seagull-base of the converter.

The dictionaries of the Seagull distribution can be wrong in places, so the converter takes
from this file only what the user's dictionaries lack. The script writes nothing else.
The exit status is 0, or 2 when the file cannot be found or read.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLED_BASE = "base_draft08.xml"
IMAGE_FOLDER = "/opt/seagull/diameter-env/config"


class ExportError(Exception):
    """The base dictionary of Seagull could not be found or read."""


def from_windows(exe: Path, out: Path) -> None:
    """Copy the file from the installation that holds seagull.exe."""
    source = exe.parent / "diameter-env" / "config" / BUNDLED_BASE
    if not source.is_file():
        raise ExportError(f"no file {source}")
    shutil.copyfile(source, out)


def docker_command(image: str) -> list[str]:
    """Return the command that prints the file from the image; without docker, try wsl."""
    path = f"{IMAGE_FOLDER}/{BUNDLED_BASE}"
    command = ["docker", "run", "--rm", "--entrypoint", "cat", image, path]
    if shutil.which("docker") is None and shutil.which("wsl") is not None:
        return ["wsl", *command]
    return command


def from_docker(image: str, out: Path) -> None:
    """Read the file out of the Seagull image."""
    result = subprocess.run(docker_command(image), capture_output=True, check=False)
    if result.returncode != 0 or not result.stdout:
        reason = result.stderr.decode(errors="replace").strip()
        raise ExportError(f"cannot read {BUNDLED_BASE} from the image {image}: {reason}")
    out.write_bytes(result.stdout)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("--runner", choices=("windows", "docker"), required=True)
    parser.add_argument("--seagull-exe", type=Path)
    parser.add_argument("--image", default="seagull:local")
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    args = parse_arguments(argv)
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.runner == "windows":
            if args.seagull_exe is None:
                raise ExportError("--runner windows needs --seagull-exe")
            from_windows(args.seagull_exe, args.out)
        else:
            from_docker(args.image, args.out)
    except (ExportError, OSError) as error:
        sys.stderr.write(f"error: {error}\n")
        return 2
    sys.stdout.write(f"{args.out}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
