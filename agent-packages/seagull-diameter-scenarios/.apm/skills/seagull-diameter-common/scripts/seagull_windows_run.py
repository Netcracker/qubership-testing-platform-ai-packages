"""Run Seagull for Windows for the dry run and for the check of converted dictionaries.

Usage:
  python seagull_windows_run.py dry-run OUTPUT_DIR_OR_SCENARIO --seagull-exe PATH [--logs DIR] [--timeout S]
  python seagull_windows_run.py check-converted CONVERTED_DIR --seagull-exe PATH [--logs DIR]

A folder is the output folder of a generation, and every scenario of it runs. A file is one client
scenario, OUTPUT_DIR/scenario/<name>.client.xml, and only that scenario runs, with the configuration
and the dictionary of its output folder.

It does what dry-run.sh and check-converted.sh do in the Seagull image, with the seagull.exe of
a Seagull for Windows installation, and prints the same lines:
`<name>: successful calls: 1, failed calls: 0`. A stub OCS starts first, then the client; the
script waits until the client ends, then stops the stub. It stops only the processes that it
started, with their children.

The stub listens on the port of the configuration, and the host may have something there. So
the script copies the configurations, gives the copy a free port, and, for the data file of a
scenario that reads one, the path on this machine. Nothing in OUTPUT_DIR is changed.

The logs of every run are kept in DIR/<name> with --logs; without it they are deleted.
The exit status is 0 if every scenario ends with at least one successful call and no failed call,
1 if one does not, and 2 for wrong arguments.

Requires Python 3.9 or later, and Windows to run Seagull.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePath

PORT_PATTERN = re.compile(r"((?:source|dest)=[^;\"':]*:)\d+")
CALLS_PATTERN = re.compile(r'<define[^>]*name="number-calls"[^>]*>(?:</define>)?\s*')
DATA_PATTERN = re.compile(r'(name="external-data-file"\s+value=")[^"]*(")')
ENCODING = "iso-8859-1"
SETTLE_SECONDS = 2
ASSETS = Path(__file__).resolve().parents[2] / "seagull-diameter-convert-dictionaries" / "assets"


@dataclass
class Job:
    """One stub and one client to run against each other."""

    name: str
    dictionary: Path
    server: tuple[Path, Path]
    client: tuple[Path, Path]
    data_file: Path | None = None
    calls: int | None = None


def free_port() -> int:
    """Return a TCP port on 127.0.0.1 that nothing listens on now."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def with_port(text: str, port: int) -> str:
    """Return a configuration with the port of its source= and dest= replaced."""
    return PORT_PATTERN.sub(lambda match: f"{match.group(1)}{port}", text)


def with_calls(text: str, calls: int) -> str:
    """Return a configuration that makes the given number of calls.

    Every earlier number-calls define is removed first, because the one in a configuration of
    Seagull for Windows stands inside an XML comment, where a changed value would do nothing.
    """
    line = f'<define entity="traffic-param" name="number-calls" value="{calls}"></define>'
    return CALLS_PATTERN.sub("", text).replace("</configuration>", f"{line}\n</configuration>")


def with_data_file(text: str, path: PurePath) -> str:
    """Return a configuration whose external-data-file, if it has one, is the given path.

    The path is written with forward slashes. Seagull reads a backslash in a parameter as the start of
    an escape, so `C:\\temp\\data.csv` becomes a tab inside the name, the file does not open, and the
    client stops before the first call. Windows accepts the forward slashes.
    """
    return DATA_PATTERN.sub(lambda match: f"{match.group(1)}{path.as_posix()}{match.group(2)}", text)


def read_stats(logs: Path) -> tuple[int, int] | None:
    """Return the successful and the failed calls of the newest client statistics, if any."""
    files = sorted(logs.glob("client-stat.*"), key=lambda path: path.stat().st_mtime)
    if not files:
        return None
    with files[-1].open(encoding=ENCODING, newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    if not rows:
        return None
    last = rows[-1]
    return int(last["TrafficSuccessfulCall(C)"] or 0), int(last["FailedCall(C)"] or 0)


def error_lines(logs: Path) -> str:
    """Return the first two error lines of the Seagull logs, joined by a space."""
    found: list[str] = []
    for path in sorted(logs.iterdir()):
        if path.suffix == ".csv":
            continue
        for line in path.read_text(encoding=ENCODING, errors="replace").splitlines():
            if "|E|" in line:
                found.append(line.strip())
    return " ".join(found[:2])


def start(exe: str, run_dir: Path, options: list[str]) -> subprocess.Popen[bytes]:
    """Start seagull.exe in a hidden console of its own, in the run folder.

    Seagull sets up the keyboard of its console, and stops with `Keyboard saved configuration
    failure` when it has none, so the process gets a console that nobody sees.
    """
    startup = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    startup.wShowWindow = 0  # SW_HIDE
    command = [exe, *options, "-llevel", "A"]
    return subprocess.Popen(
        command,
        cwd=run_dir,
        startupinfo=startup,
        creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
    )


def stop(process: subprocess.Popen[bytes]) -> None:
    """Stop the process that this script started, with its children, and nothing else."""
    if process.poll() is None:
        command = ["taskkill", "/PID", str(process.pid), "/T", "/F"]
        subprocess.run(command, capture_output=True, check=False)
        process.wait()


def prepare(job: Job, work: Path) -> tuple[Path, Path]:
    """Write the copies of the two configurations with a free port; return their paths."""
    port = free_port()
    server_text = job.server[1].read_text(encoding=ENCODING)
    client_text = with_port(job.client[1].read_text(encoding=ENCODING), port)
    if job.data_file is not None:
        client_text = with_data_file(client_text, job.data_file)
    if job.calls is not None:
        client_text = with_calls(client_text, job.calls)
    server_conf, client_conf = work / "server.xml", work / "client.xml"
    server_conf.write_text(with_port(server_text, port), encoding=ENCODING, newline="\n")
    client_conf.write_text(client_text, encoding=ENCODING, newline="\n")
    return server_conf, client_conf


def arguments(job: Job, conf: Path, scenario: Path, role: str) -> list[str]:
    """Return the seagull.exe arguments of the stub (role stub) or of the client."""
    return [
        "-conf",
        str(conf),
        "-dico",
        str(job.dictionary),
        "-scen",
        str(scenario),
        "-log",
        f"../logs/{job.name}.{role}",
    ]


def run_job(exe: str, job: Job, work: Path, timeout: int) -> tuple[int, int, str] | None:
    """Run the stub and the client; return successful, failed, and errors, or None."""
    run_dir, logs = work / "run", work / "logs"
    run_dir.mkdir(parents=True)
    logs.mkdir()
    server_conf, client_conf = prepare(job, work)
    stub = start(exe, run_dir, arguments(job, server_conf, job.server[0], "stub"))
    try:
        time.sleep(SETTLE_SECONDS)
        client = start(exe, run_dir, arguments(job, client_conf, job.client[0], "client"))
        try:
            client.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop(client)
    finally:
        stop(stub)
    stats = read_stats(logs)
    return None if stats is None else (stats[0], stats[1], error_lines(logs))


def report(name: str, outcome: tuple[int, int, str] | None) -> tuple[str, bool]:
    """Return the output line of a job and whether the job passed."""
    if outcome is None:
        return f"{name}: no statistics file", False
    ok, failed, errors = outcome
    line = f"{name}: successful calls: {ok}, failed calls: {failed}"
    return (f"{line} {errors}".rstrip()), ok >= 1 and failed == 0


def run_jobs(exe: str, jobs: list[Job], logs_dir: Path | None, timeout: int) -> int:
    """Run the jobs one after another, print a line for each, and return the exit status."""
    status = 0
    base = Path(tempfile.mkdtemp(prefix="seagull-run-"))
    try:
        for job in jobs:
            work = (logs_dir or base) / job.name
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
            line, passed = report(job.name, run_job(exe, job, work, timeout))
            sys.stdout.write(line + "\n")
            status = status if passed else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return status


def dry_run_jobs(output: Path) -> list[Job]:
    """Return one job for each client scenario of a generation folder."""
    config = output / "config"
    scenarios = output / "scenario"
    data = scenarios / "external-data.csv"
    jobs = []
    for client in sorted(scenarios.glob("*.client.xml")):
        name = client.name.removesuffix(".client.xml")
        stub = scenarios / f"{name}.stub-server.xml"
        jobs.append(
            Job(
                name=name,
                dictionary=output / "dictionary" / "diameter-dictionary.xml",
                server=(stub, config / "conf.stub-server.xml"),
                client=(client, config / "conf.dry-run.client.xml"),
                data_file=data if data.exists() else None,
            )
        )
    return jobs


def split_target(target: Path) -> tuple[Path, str | None]:
    """Return the output folder and the one scenario to run for the target of a dry run.

    A folder is an output folder, and every scenario runs (the name is None). A file is one client scenario,
    `<output folder>/scenario/<name>.client.xml`, and only that scenario runs.
    """
    if target.is_dir():
        return target, None
    if not target.is_file():
        raise ValueError(f"no such file or folder: {target}")
    if not target.name.endswith(".client.xml"):
        raise ValueError(f"{target} is not a client scenario; a scenario file is named <name>.client.xml")
    return target.parent.parent, target.name.removesuffix(".client.xml")


def select_jobs(jobs: list[Job], name: str | None) -> list[Job]:
    """Return the job of the scenario name, or all jobs when the name is None."""
    if name is None:
        return jobs
    chosen = [job for job in jobs if job.name == name]
    if not chosen:
        raise ValueError(f"no scenario {name} in the output folder; it has {', '.join(j.name for j in jobs) or 'none'}")
    return chosen


def check_jobs(converted: Path, exe: str) -> tuple[list[Job], list[str]]:
    """Return the jobs for the converted dictionaries that define CCR, and lines for the others."""
    config = Path(exe).parent / "diameter-env" / "config"
    jobs: list[Job] = []
    skipped: list[str] = []
    for dictionary in sorted(converted.glob("*.xml")):
        if '<define name="CCR">' not in dictionary.read_text(encoding=ENCODING, errors="replace"):
            skipped.append(f"{dictionary.stem}: skipped, the dictionary defines no CCR")
            continue
        jobs.append(
            Job(
                name=dictionary.stem,
                dictionary=dictionary,
                server=(ASSETS / "stub-ocs.server.xml", config / "conf.server.xml"),
                client=(ASSETS / "client-gy-initial.xml", config / "conf.client.xml"),
                calls=1,
            )
        )
    return jobs, skipped


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("command", choices=("dry-run", "check-converted"))
    parser.add_argument("folder", type=Path)
    parser.add_argument("--seagull-exe", required=True)
    parser.add_argument("--logs", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    """Run the command line; return the exit status."""
    args = parse_arguments(argv)
    if not Path(args.seagull_exe).is_file():
        sys.stderr.write(f"error: no file {args.seagull_exe}\n")
        return 2
    skipped: list[str] = []
    if args.command == "dry-run":
        try:
            folder, name = split_target(args.folder)
            jobs = select_jobs(dry_run_jobs(folder), name)
        except ValueError as error:
            sys.stderr.write(f"error: {error}\n")
            return 2
    elif not args.folder.is_dir():
        sys.stderr.write(f"error: check-converted takes a folder, and {args.folder} is not one\n")
        return 2
    else:
        jobs, skipped = check_jobs(args.folder, args.seagull_exe)
    if not jobs and not skipped:
        sys.stderr.write(f"error: nothing to run in {args.folder}\n")
        return 2
    sys.stdout.write("".join(line + "\n" for line in skipped))
    return run_jobs(args.seagull_exe, jobs, args.logs, args.timeout)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
