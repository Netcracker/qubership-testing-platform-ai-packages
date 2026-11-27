"""Show the config of the package, .atp-assistant/config.json, and change its values.

  manage_config.py                          show the config
  manage_config.py --set KEY=value [...]    change values, then show the config

The config is found from the working directory up. When there is none, the script creates
.atp-assistant/config.json in the working directory, also before --set. The values that
differ from project to project are empty in it. The others hold a default or a sample,
among them the patterns of the search for identifiers and the template of the links to
them. The search stays off until ORCHESTRATOR_URL is filled, and the links until
BUSINESS_IDS_AS_LINKS is true.

KEY is a setting of the package or a variable of the pipeline: a name that "variables"
already holds, or one of the variables the package knows. All values are checked before
anything is written, so a wrong one changes nothing. An empty value removes an optional
setting. The patterns of the search for identifiers, the templates of the links, and
values whose name looks like a secret, are changed by hand only.

The output is Markdown, and the agent shows it as written. A value whose name looks like a
secret, and a password in a URL, are masked. The token is never read into the output: the
script only says whether one is found.

Exit codes: 0 for the shown config; 1 for an error, described by one JSON object on stderr;
2 for a wrong command line. Error codes: bad_argument, unknown_key, invalid_value (with
"problems"), config_unreadable, config_unwritable. Python 3.9+, standard library only.
"""

import argparse
import importlib
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
common = importlib.import_module("atp_common")

REQUIRED = ("GITLAB_URL", "GITLAB_PROJECT_ID", "GITLAB_REF")
OPTIONAL = (
    common.CONFIRM_KEY,
    "GITLAB_TOKEN_ENV",
    *common.DEFAULT_FOLDERS,
    common.LOCAL_ROOT_KEY,
    "ORCHESTRATOR_URL",
    "DOWNSTREAM_STAGE",
    "DISCOVERY_TIMEOUT",
    "DISCOVERY_INTERVAL",
    "DISCOVERY_SLOW_INTERVAL",
    common.LINKS_KEY,
)
BY_HAND = ("RUN_ID_PATTERN", "BUSINESS_ID_PATTERNS", common.LINK_TEMPLATES_KEY)
SETTING_BOOLEANS = (common.CONFIRM_KEY, common.LINKS_KEY)
URLS = ("GITLAB_URL", "ORCHESTRATOR_URL")
NUMBERS = ("DISCOVERY_TIMEOUT", "DISCOVERY_INTERVAL", "DISCOVERY_SLOW_INTERVAL")
BOOLEANS = ("ENABLE_JIRA_INTEGRATION", "SEND_WEBEX_NOTIFICATION")
VARIABLES = {
    "ATP_TESTS_GIT_REPO_URL": "",
    "ATP_TESTS_GIT_REPO_BRANCH": "main",
    "PIPELINE_RUNTIME_CONFIG": "",
    "EXECUTION_TYPE": "test",
    "EXECUTION_NAME": "",
    "ENABLE_JIRA_INTEGRATION": "false",
    "SEND_WEBEX_NOTIFICATION": "false",
}
# The config that the script creates. Nothing that a token is sent to has a sample value.
TEMPLATE = {
    "GITLAB_URL": "",
    "GITLAB_PROJECT_ID": "",
    "GITLAB_REF": "main",
    common.CONFIRM_KEY: True,
    "GITLAB_TOKEN_ENV": "GITLAB_TOKEN",
    **common.DEFAULT_FOLDERS,
    common.LOCAL_ROOT_KEY: "",
    "ORCHESTRATOR_URL": "",
    "DOWNSTREAM_STAGE": "1. Run ATP3 tests",
    "RUN_ID_PATTERN": "Run submitted: id=(?P<value>[0-9a-f-]{36})",
    "BUSINESS_ID_PATTERNS": {"customerId": "^customerId:[ \\t]*(?P<value>\\d+)[ \\t]*$"},
    "DISCOVERY_TIMEOUT": 420,
    "DISCOVERY_INTERVAL": 5,
    "DISCOVERY_SLOW_INTERVAL": 15,
    common.LINKS_KEY: False,
    common.LINK_TEMPLATES_KEY: list(common.DEFAULT_LINK_TEMPLATES),
    "variables": VARIABLES,
}
SECRET_NAME = re.compile(r"PASSWORD|PASSWD|SECRET|PRIVATE_KEY|API_?KEY|TOKEN(?!_ENV)", re.IGNORECASE)
URL_PASSWORD = re.compile(r"(\w+://[^/\s:@]+):[^/\s@]+@")


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Show or change the config of atp-tests-assistant.")
    parser.add_argument("--set", dest="sets", action="append", default=[], help="KEY=value; repeat for more")
    return parser.parse_args(argv)


def parse_changes(items):
    """Split KEY=value strings at the first '=' into (key, value) pairs, or fail."""
    changes = []
    for item in items:
        key, separator, value = item.partition("=")
        if not separator or not key.strip():
            common.fail("bad_argument", f"--set '{item}' is not KEY=value.")
        changes.append((key.strip(), value.strip()))
    return changes


def new_config_file():
    """Create .atp-assistant/config.json from TEMPLATE in the working directory; return its path."""
    path = Path.cwd() / common.CONFIG_PATH
    try:
        path.parent.mkdir(exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(TEMPLATE, indent=2) + "\n")
    except OSError as exc:
        common.fail("config_unwritable", f"Cannot create {path}: {exc}")
    return path


def check_value(key, value):
    """Return (the value to store, "") or (None, the problem) for a new value of a key."""
    if key in BOOLEANS or (key in SETTING_BOOLEANS and value):
        lowered = value.lower()
        if lowered not in ("true", "false"):
            return None, f"'{key}' must be true or false, not '{value}'"
        # A pipeline variable is a string; the setting of the package is a JSON boolean.
        return lowered == "true" if key in SETTING_BOOLEANS else lowered, ""
    if key in URLS and value and not value.lower().startswith(("http://", "https://")):
        return None, f"'{key}' must start with http:// or https://"
    if key in NUMBERS and value:
        try:
            number = float(value)
        except ValueError:
            number = 0
        if not 0 < number < float("inf"):
            return None, f"'{key}' must be a positive number, not '{value}'"
        return int(number) if number.is_integer() else number, ""
    folder, problem = common.parse_folder(value) if key in common.DEFAULT_FOLDERS and value else (value, "")
    return (None, f"'{key}' {problem}") if problem else (folder, "")


def locate(data, key):
    """Return the object of the config that holds KEY, or fail when the key cannot be set."""
    if key in BY_HAND or SECRET_NAME.search(key):
        common.fail("unknown_key", f"'{key}' is not changed by this script. Edit it in the file by hand.")
    if key in REQUIRED or key in OPTIONAL:
        return data
    variables = data.get("variables", {})
    if key in variables or key in VARIABLES:
        return data.setdefault("variables", variables)
    known = ", ".join([*REQUIRED, *OPTIONAL, *dict.fromkeys([*VARIABLES, *variables])])
    return common.fail("unknown_key", f"'{key}' is not a key of the config. Known: {known}.")


def shown(key, value):
    """Return a value as the cell of a table: masked when secret, and marked when empty."""
    if value in ("", None):
        return "not set"
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if SECRET_NAME.search(key):
        return "hidden"
    text = URL_PASSWORD.sub(r"\1:***@", text).replace("\r", " ").replace("\n", " ")
    fence = "``" if "`" in text else "`"
    return f"{fence}{text.replace('|', chr(92) + '|')}{fence}"


def apply_changes(path, changes):
    """Write the new values into the config and return one line for each change, or fail."""
    data, text = common.load_config_file(path)
    problems, lines = [], []
    for key, value in changes:
        target = locate(data, key)
        stored, problem = check_value(key, value)
        if problem:
            problems.append(problem)
            continue
        before = target.get(key)
        if isinstance(before, bool) and stored in ("true", "false"):
            stored = stored == "true"
        if key in OPTIONAL and value == "":
            target.pop(key, None)
            stored = None
        else:
            target[key] = stored
        if before == stored:
            lines.append(f"- `{key}` is already {shown(key, stored)}.")
        else:
            lines.append(f"- `{key}`: {shown(key, before)} → {shown(key, stored)}.")
    if problems:
        common.fail("invalid_value", "; ".join(problems) + ". Nothing was changed.", problems=problems)
    if data != common.load_config_file(path)[0]:
        common.save_config_file(path, data, text)
    return lines


def token_line(config):
    """Return the sentence that says where the token is found, without the token."""
    env_name = config.get("GITLAB_TOKEN_ENV") or common.DEFAULT_TOKEN_ENV
    if (os.environ.get(env_name) or "").strip():
        return f"Token: found in the environment variable `{env_name}`."
    if common.read_token(config):
        return f"Token: found in the file `{common.TOKEN_FILE}` next to the config."
    return (
        f"Token: not found. Set `{env_name}`, or put it on the first line of `{common.TOKEN_FILE}` next to the config."
    )


def table(heading, rows):
    """Return the lines of a two-column table."""
    return [f"| {heading} | Value |", "| --- | --- |", *(f"| `{key}` | {shown(key, value)} |" for key, value in rows)]


def describe(config):
    """Return the lines that show the settings, the variables, and whether a token is found."""
    hidden_keys = ("variables", "CONFIG_FILE", "CONFIG_DIR")
    names = dict.fromkeys([*REQUIRED, common.CONFIRM_KEY, *(key for key in config if key not in hidden_keys)])
    lines = table("Setting", [(key, config.get(key)) for key in names])
    if config.get(common.CONFIRM_KEY) in (None, ""):
        row = next(index for index, line in enumerate(lines) if line.startswith(f"| `{common.CONFIRM_KEY}` |"))
        lines[row] = f"| `{common.CONFIRM_KEY}` | `true` (default) |"
    variables = common.read_variables(config)
    lines += ["", *(table("Variable of the pipeline", variables.items()) if variables else ["No `variables`."])]
    return [*lines, "", token_line(config)]


def main():
    """Create the config when there is none, apply the changes, and print the config."""
    args = parse_arguments()
    common.use_utf8_output()
    changes = parse_changes(args.sets)
    path = common.find_config()
    lines = []
    if path is None:
        path = new_config_file()
        lines += [
            f"Created `{path}`. Fill the values shown as `not set`, and check the samples against your project.",
            "The search for business identifiers is off until `ORCHESTRATOR_URL` is set.",
            f"In a Git repository, keep `{common.CONFIG_PATH.parent / common.TOKEN_FILE}` out of the commits.",
            "",
        ]
    if changes:
        lines += ["Changes:", "", *apply_changes(path, changes), ""]
    config = common.load_config()
    print("\n".join([*lines, f"Config: `{path}`.", "", *describe(config)]))


if __name__ == "__main__":
    main()
