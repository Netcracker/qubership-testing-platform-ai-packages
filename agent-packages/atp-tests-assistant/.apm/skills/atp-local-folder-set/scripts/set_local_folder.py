"""Set the folder of the local tests, LOCAL_ROOT_FOLDER of the config, or check the current one.

  set_local_folder.py --path FOLDER   check FOLDER and write it to the config
  set_local_folder.py                 check the folder of the config

The folder holds a copy of the test repository, with the same layout. It passes the check
when it has *.ts files in the tests folder (TESTS_FOLDER) and *.json files in the folder of
the environment configurations (ENV_CONFIGURATION_FOLDER). A folder that does not pass
leaves the config as it is. The script reads names only, never the content of a file, and
sends no request.

The output is Markdown, and the agent shows it as written. Exit codes: 0 for a folder that
passes; 1 for an error, described by one JSON object on stderr; 2 for a wrong command line.
Error codes: config_missing, config_unreadable, config_unwritable, invalid_value,
local_root_missing, local_root_invalid (with "problems"). Python 3.9+, standard library
only.
"""

import argparse
import importlib
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
common = importlib.import_module("atp_common")


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Set or check the folder of the local tests.")
    parser.add_argument("--path", help="the folder that holds the copy of the test repository")
    args = parser.parse_args(argv)
    if args.path is not None:
        args.path = args.path.strip()
        if not args.path:
            parser.error("--path must not be empty")
    return args


def check(root, config, unchanged):
    """Return the contents of the folder, or fail with its problems; unchanged ends the message."""
    contents = common.read_local_root(root, config)
    if contents.problems:
        message = " ".join([f"The folder {root} cannot hold the local tests.", *contents.problems, unchanged])
        common.fail("local_root_invalid", message.strip(), problems=contents.problems)
    return contents


def set_folder(text, config):
    """Check the folder, write it to the config, and return it, its contents, and what was done."""
    config_file = config["CONFIG_FILE"]
    root = Path(os.path.abspath(os.path.expanduser(text)))
    contents = check(root, config, "The config was not changed.")
    previous = common.write_setting(Path(config_file), common.LOCAL_ROOT_KEY, str(root))
    if previous == str(root):
        done = f"{common.LOCAL_ROOT_KEY} is already `{root}` in {config_file}. Nothing changed."
    else:
        before = f"`{previous}`" if previous else "not set"
        done = f"Set {common.LOCAL_ROOT_KEY} to `{root}` in {config_file}. It was {before}."
    return contents, done


def describe(contents, config):
    """Return the lines that say what the folder holds."""
    tests = common.read_folder(config, common.TESTS_FOLDER_KEY)
    configurations = common.read_folder(config, common.CONFIGURATION_FOLDER_KEY)
    count = len(contents.tests)
    names = ", ".join(f"`{name}`" for name in contents.configurations)
    return [
        f"- Tests: {count} `*.ts` file{'s' if count != 1 else ''} in `{tests}`.",
        f"- Environment configurations in `{configurations}`: {names}.",
    ]


def main():
    """Set or check the folder of the local tests and print what it holds."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    if "CONFIG_FILE" not in config:
        common.fail(
            "config_missing",
            f"No .atp-assistant/config.json to hold {common.LOCAL_ROOT_KEY}. Create it with /atp-config.",
        )
    if args.path is None:
        root = common.local_root(config)
        contents = check(root, config, "")
        done = f"{common.LOCAL_ROOT_KEY} is `{root}`."
    else:
        contents, done = set_folder(args.path, config)
    print("\n".join([done, "", *describe(contents, config)]))


if __name__ == "__main__":
    main()
