"""Show the YAML file that describes one environment of the project's GitLab pipeline.

An environment is a YAML file in the environments folder of the pipeline repository, and
its name is the file name without .yaml. The script reads the file from the GitLab API and
prints one heading line and the file in a fenced block. The agent shows that output as
written. The file is printed as it is, with any secret it holds.

Without --name the script shows the current environment: the file that
PIPELINE_RUNTIME_CONFIG names, such as environments/dev.yaml, in "variables" of
.atp-assistant/config.json.

With --name TEXT the script first reads environments/TEXT.yaml. When GitLab has no such
file, the script looks for TEXT in the names of the folder: a name equal to TEXT, ignoring
case, and else the names that contain TEXT (TEXT with * or ? is a mask for the whole
name). It shows the file when one name matches, and lists the names when several do.

The repository and the branch come from GITLAB_URL, GITLAB_PROJECT_ID, and GITLAB_REF in
the same file. --url, --project, and --ref override them. The token comes from the
environment variable GITLAB_TOKEN (the config key GITLAB_TOKEN_ENV names another
variable) or the first line of .atp-assistant/gitlab-token. Without a token the request is
anonymous. The token is never printed.

Exit codes: 0 for a file, a list of names, or no match; 1 for an error, described by one
JSON object on stderr; 2 for a wrong command line. Python 3.9+, standard library only.
"""

import argparse
import importlib
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
common = importlib.import_module("atp_common")


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Show the file of one environment of the GitLab pipeline.")
    parser.add_argument("--name", default="", help="name of an environment or a part of it; default: the current one")
    common.add_pipeline_arguments(parser)
    return parser.parse_args(argv)


def current_path(config):
    """Return the file path that PIPELINE_RUNTIME_CONFIG holds, or fail."""
    value = str(common.read_variables(config).get(common.CURRENT_KEY) or "").strip()
    if not value:
        common.fail(
            "runtime_config_missing",
            f"No current environment. Set {common.CURRENT_KEY} in 'variables' of .atp-assistant/config.json, "
            "or give --name.",
        )
    return value


def render_file(title, path, where, text):
    """Return the answer that shows one file: the heading line and the fenced content."""
    longest = max((len(run) for run in re.findall("`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    heading = f"{title} `{common.environment_name(path)}`: file `{path}` in {where}."
    return "\n".join([heading, "", f"{fence}yaml", *text.splitlines(), fence])


def show_current(pipeline, config, token, where):
    """Return the answer for the current environment, or fail when its file does not exist."""
    path = current_path(config)
    text = common.read_file_if_any(pipeline, path, token)
    if text is None:
        common.fail(
            "environment_file_missing",
            f"{common.CURRENT_KEY} names the file {path}, which does not exist in {where}, "
            "or the branch does not exist.",
        )
    return render_file(f"Current environment ({common.CURRENT_KEY})", path, where, text)


def show_named(pipeline, wanted, token, where):
    """Return the answer for --name: the file, the names that match, or that none does."""
    search = common.search_environment(pipeline, wanted, token)
    if not search.path:
        return common.describe_unresolved(search, wanted, where)
    if not search.names:
        return render_file("Environment", search.path, where, search.text)
    text = common.read_file_if_any(pipeline, search.path, token)
    if text is None:
        common.fail("environment_file_missing", f"GitLab lists the file {search.path} in {where} but cannot read it.")
    return render_file(f'The only environment that matches "{wanted}" is', search.path, where, text)


def main():
    """Read the file of the current or the named environment and print the answer."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    pipeline = common.resolve_pipeline(args, config)
    token = common.read_token(config)
    base, project, ref = pipeline
    where = f"{base}, project {project}, branch {ref}"
    wanted = args.name.strip()
    if wanted:
        print(show_named(pipeline, wanted, token, where))
    else:
        print(show_current(pipeline, config, token, where))


if __name__ == "__main__":
    main()
