"""List the environments that the project's GitLab pipeline can run on, sorted by name.

An environment is a YAML file in the environments folder of the pipeline repository, and
its name is the file name without .yaml. The script reads the folder from the GitLab API
and prints the names as a Markdown list. The agent shows that output as written. The value
that selects an environment in the pipeline, PIPELINE_RUNTIME_CONFIG, is
environments/<name>.yaml.

The repository and the branch come from GITLAB_URL, GITLAB_PROJECT_ID, and GITLAB_REF in
.tdm-assistant/config.json, the settings that tdm-generate-test-data uses to start the
pipeline. --url, --project, and --ref override them. The pipeline repository is not the
repository of the tests. The token comes from the environment variable GITLAB_TOKEN (the
config key GITLAB_TOKEN_ENV names another variable) or the first line of
.tdm-assistant/gitlab-token. Without a token the request is anonymous. The token is never
printed.

Filter:
  --name TEXT   Only the names that contain TEXT, ignoring case. TEXT with * or ? is a
                mask for the whole name.

Exit codes: 0 for a result, also an empty one; 1 for an error, described by one JSON
object on stderr; 2 for a wrong command line. Python 3.9+, standard library only.
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
    parser = argparse.ArgumentParser(description="List the environments of the GitLab pipeline.")
    parser.add_argument("--name", default="", help="part of a name, or a mask with * and ?")
    common.add_pipeline_arguments(parser)
    return parser.parse_args(argv)


def describe(chosen, total, where, text):
    """Return the heading line: how many environments were found, and the filter in use."""
    noun = "environment" if total == 1 else "environments"
    masked = "*" in text or "?" in text
    filtered = f' Filter: name {"matches" if masked else "contains"} "{text}".' if text else ""
    if not chosen:
        return f"No {noun} (*{common.ENVIRONMENT_SUFFIX}) found in {where}, {total} in all.{filtered}"
    count = f"{len(chosen)} of {total}" if text else str(len(chosen))
    return f"Found {count} {noun} in {where}.{filtered}"


def main():
    """Read the folder, apply the filter, and print the answer."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    base, project, ref = common.resolve_pipeline(args, config)
    names = list(common.read_environments(base, project, ref, common.read_token(config)))
    text = args.name.strip()
    passes = common.make_name_filter(text)
    chosen = [name for name in names if passes(name)]
    where = f"{base}, project {project}, branch {ref}, folder {common.ENVIRONMENTS_FOLDER}"
    lines = [describe(chosen, len(names), where, text)]
    if chosen:
        lines += ["", *(f"- `{name}`" for name in chosen)]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
