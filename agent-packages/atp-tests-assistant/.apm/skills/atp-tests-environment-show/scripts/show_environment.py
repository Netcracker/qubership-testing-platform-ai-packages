"""Show the YAML file that describes one environment of the project's GitLab pipeline.

An environment is a YAML file in the environments folder of the pipeline repository, and
its name is the file name without .yaml. The script reads the file from the GitLab API and
prints one heading line and the file in a fenced block. The agent shows that output as
written. The file is printed as it is, with any secret it holds.

Without --name the script shows the current environment: the file that
PIPELINE_RUNTIME_CONFIG names, such as environments/dev.yaml, in the variables file that
GENERATE_VARIABLES_FILE names in .tdm-assistant/config.json.

With --name TEXT the script first reads environments/TEXT.yaml. When GitLab has no such
file, the script looks for TEXT in the names of the folder: a name equal to TEXT, ignoring
case, and else the names that contain TEXT (TEXT with * or ? is a mask for the whole
name). It shows the file when one name matches, and lists the names when several do.

The repository and the branch come from GITLAB_URL, GITLAB_PROJECT_ID, and GITLAB_REF in
.tdm-assistant/config.json. --url, --project, and --ref override them. The token comes
from the environment variable GITLAB_TOKEN (the config key GITLAB_TOKEN_ENV names another
variable) or the first line of .tdm-assistant/gitlab-token. Without a token the request is
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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-tests-common" / "scripts"))
common = importlib.import_module("atp_tests_common")

CURRENT_KEY = "PIPELINE_RUNTIME_CONFIG"


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Show the file of one environment of the GitLab pipeline.")
    parser.add_argument("--name", default="", help="name of an environment or a part of it; default: the current one")
    common.add_pipeline_arguments(parser)
    return parser.parse_args(argv)


def current_path(config):
    """Return the file path that PIPELINE_RUNTIME_CONFIG holds, or fail."""
    value = str(common.read_variables(config).get(CURRENT_KEY) or "").strip()
    if not value:
        common.fail(
            "runtime_config_missing",
            f"No current environment. Set {CURRENT_KEY} in the variables file that GENERATE_VARIABLES_FILE "
            "names in .tdm-assistant/config.json, or give --name.",
        )
    return value


def read_file(pipeline, path, token):
    """Return the text of the file, or None when GitLab finds the project and not the file or the branch."""
    base, project, ref = pipeline
    try:
        return common.get_file(base, project, path, ref, token)
    except common.GitLabError as exc:
        if exc.status == 404 and "Project Not Found" not in exc.body:
            return None
        return common.fail_request(exc, f"{base}, project {project}", token)


def environment_name(path):
    """Return the environment name of a file path: the filename without .yaml."""
    return path.rsplit("/", 1)[-1].removesuffix(common.ENVIRONMENT_SUFFIX)


def render_file(title, path, where, text):
    """Return the answer that shows one file: the heading line and the fenced content."""
    longest = max((len(run) for run in re.findall("`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    heading = f"{title} `{environment_name(path)}`: file `{path}` in {where}."
    return "\n".join([heading, "", f"{fence}yaml", *text.splitlines(), fence])


def show_current(pipeline, config, token, where):
    """Return the answer for the current environment, or fail when its file does not exist."""
    path = current_path(config)
    text = read_file(pipeline, path, token)
    if text is None:
        common.fail(
            "environment_file_missing",
            f"{CURRENT_KEY} names the file {path}, which does not exist in {where}, or the branch does not exist.",
        )
    return render_file(f"Current environment ({CURRENT_KEY})", path, where, text)


def show_named(pipeline, wanted, token, where):
    """Return the answer for --name: the file, the names that match, or that none does."""
    path = f"{common.ENVIRONMENTS_FOLDER}/{wanted}{common.ENVIRONMENT_SUFFIX}"
    text = read_file(pipeline, path, token)
    if text is not None:
        return render_file("Environment", path, where, text)
    files = common.read_environments(*pipeline, token)
    exact = [name for name in files if name.lower() == wanted.lower()]
    passes = common.make_name_filter(wanted)
    matches = exact or [name for name in files if passes(name)]
    if not matches:
        return f'No environment matches "{wanted}" in {where}, {len(files)} in all.'
    if len(matches) > 1:
        heading = f'{len(matches)} environments match "{wanted}" in {where}. Specify one of them:'
        return "\n".join([heading, "", *(f"- `{name}`" for name in matches)])
    path = f"{common.ENVIRONMENTS_FOLDER}/{files[matches[0]]}"
    text = read_file(pipeline, path, token)
    if text is None:
        common.fail("environment_file_missing", f"GitLab lists the file {path} in {where} but cannot read it.")
    return render_file(f'The only environment that matches "{wanted}" is', path, where, text)


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
