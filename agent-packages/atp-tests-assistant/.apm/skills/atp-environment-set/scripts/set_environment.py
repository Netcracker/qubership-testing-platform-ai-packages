"""Select the environment of the project's GitLab pipeline in the variables file.

The script searches the environments folder of the pipeline repository for the text of
--name, as show_environment.py does: it reads environments/TEXT.yaml, and without that
file it looks for a name equal to TEXT, ignoring case, and else for the names that
contain TEXT (TEXT with * or ? is a mask for the whole name). When one environment is
found, the script sets PIPELINE_RUNTIME_CONFIG to environments/<filename> in the
variables file that GENERATE_VARIABLES_FILE names in .tdm-assistant/config.json. When
none or several are found, it prints that and leaves the file as it is. The output is
Markdown, and the agent shows it as written.

The repository and the branch come from GITLAB_URL, GITLAB_PROJECT_ID, and GITLAB_REF in
.tdm-assistant/config.json. --url, --project, and --ref override them. The token comes
from the environment variable GITLAB_TOKEN (the config key GITLAB_TOKEN_ENV names another
variable) or the first line of .tdm-assistant/gitlab-token. Without a token the request is
anonymous. The token is never printed.

Exit codes: 0 for a set value, a value that was already set, a list of names, or no match;
1 for an error, described by one JSON object on stderr; 2 for a wrong command line.
Python 3.9+, standard library only.
"""

import argparse
import importlib
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
common = importlib.import_module("atp_common")


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Set the environment of the GitLab pipeline.")
    parser.add_argument("--name", required=True, help="name of an environment or a part of it")
    common.add_pipeline_arguments(parser)
    args = parser.parse_args(argv)
    args.name = args.name.strip()
    if not args.name:
        parser.error("--name must not be empty")
    return args


def require_variables_file(config):
    """Return the path of a readable variables file, or fail before any GitLab request."""
    path = common.variables_path(config)
    if path is None:
        common.fail(
            "variables_file_missing",
            f"No variables file to hold {common.CURRENT_KEY}. "
            "Set GENERATE_VARIABLES_FILE in .tdm-assistant/config.json.",
        )
    common.load_variables_file(path)
    return path


def select(search, wanted, variables_file):
    """Write the found environment into the variables file and return the answer."""
    previous = common.write_variable(variables_file, common.CURRENT_KEY, search.path)
    lines = []
    if search.names:
        lines.append(f'The only environment that matches "{wanted}" is `{common.environment_name(search.path)}`.')
    if previous == search.path:
        lines.append(f"{common.CURRENT_KEY} is already `{search.path}` in {variables_file}. Nothing changed.")
    else:
        before = f"`{previous}`" if previous else "not set"
        lines.append(f"Set {common.CURRENT_KEY} to `{search.path}` in {variables_file}. It was {before}.")
    return "\n".join(lines)


def main():
    """Search for the environment, set it when one is found, and print the answer."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    variables_file = require_variables_file(config)
    pipeline = common.resolve_pipeline(args, config)
    base, project, ref = pipeline
    search = common.search_environment(pipeline, args.name, common.read_token(config))
    if search.path:
        print(select(search, args.name, variables_file))
    else:
        where = f"{base}, project {project}, branch {ref}"
        print(common.describe_unresolved(search, args.name, where))
        print(f"\n{common.CURRENT_KEY} was not changed.")


if __name__ == "__main__":
    main()
