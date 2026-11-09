"""Check a folder of recorded Diameter steps before a scenario is generated from it.

Usage: python check_steps.py FOLDER [--request-name TEMPLATE] [--response-name TEMPLATE]

The templates say how the files of the folder are named, with the step number written as NN
(two or more capital N). They default to Step-NNN-request.txt and Step-NNN-response.txt; for
files named request_01.xml and response_01.xml, pass request_NN.xml and response_NN.xml.

It reports files that do not follow the naming, two files for one step, a missing half of a
pair, messages that are not XML even after the repairs, a request without a Session-Id, a
message whose root element is not a Diameter command, and the repairs that were needed. The exit
status is 1 when there is a problem, and 2 for wrong arguments.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parent))
steps_format = importlib.import_module("steps_format")


def command_problems(step) -> list[str]:
    """Return what is wrong with the commands of a step."""
    problems: list[str] = []
    for message in (step.request, step.response):
        if len(message.command) != 3 or not message.command.isupper():
            problems.append(
                f"{message.path.name}: the root element <{message.command}> is not "
                "a Diameter command such as CCR or CCA"
            )
    if step.request.command[-1:] != "R" or step.response.command[-1:] != "A":
        got = f"{step.request.command} and {step.response.command}"
        problems.append(f"step {step.number}: expected a request and an answer: {got}")
    return problems


def check(
    folder: Path,
    request_name: str = steps_format.DEFAULT_REQUEST_NAME,
    response_name: str = steps_format.DEFAULT_RESPONSE_NAME,
) -> tuple[list[str], list[str]]:
    """Return the problems and the notes about the folder."""
    steps, problems = steps_format.load_steps(folder, request_name, response_name)
    notes: list[str] = [f"{len(steps)} complete step(s) in {folder}"]
    for step in steps:
        problems += command_problems(step)
        if not step.session_id:
            problems.append(f"{step.request.path.name}: no Session-Id in the request")
        for message in (step.request, step.response):
            notes += [f"{message.path.name}: {note}" for note in message.repairs]
    return problems, notes


def main(argv: list[str]) -> int:
    """Print the result and return the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--request-name", default=steps_format.DEFAULT_REQUEST_NAME, metavar="TEMPLATE")
    parser.add_argument("--response-name", default=steps_format.DEFAULT_RESPONSE_NAME, metavar="TEMPLATE")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        sys.stderr.write(f"{args.folder} is not a folder\n")
        return 2
    try:
        problems, notes = check(args.folder, args.request_name, args.response_name)
    except ValueError as error:
        sys.stderr.write(f"error: {error}\n")
        return 2
    for note in notes:
        sys.stdout.write(f"{note}\n")
    for problem in problems:
        sys.stdout.write(f"PROBLEM {problem}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
