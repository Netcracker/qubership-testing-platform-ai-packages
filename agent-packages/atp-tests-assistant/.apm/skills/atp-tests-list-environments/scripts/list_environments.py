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
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-tests-common" / "scripts"))
common = importlib.import_module("atp_tests_common")

FOLDER = "environments"
SUFFIX = ".yaml"
SETTINGS = (("url", "GITLAB_URL"), ("project", "GITLAB_PROJECT_ID"), ("ref", "GITLAB_REF"))


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="List the environments of the GitLab pipeline.")
    parser.add_argument("--name", default="", help="part of a name, or a mask with * and ?")
    parser.add_argument("--url", help="base URL of GitLab; overrides GITLAB_URL")
    parser.add_argument("--project", help="numeric ID or path of the pipeline project; overrides GITLAB_PROJECT_ID")
    parser.add_argument("--ref", help="branch to read; overrides GITLAB_REF")
    return parser.parse_args(argv)


def resolve_settings(args, config):
    """Return the GitLab URL, the project, and the branch, or fail naming what is missing."""
    values = {key: str(getattr(args, option) or config.get(key) or "").strip() for option, key in SETTINGS}
    missing = [key for key, value in values.items() if not value]
    if missing:
        common.fail(
            "gitlab_settings_missing",
            "Missing: " + ", ".join(missing) + ". Set them in .tdm-assistant/config.json, "
            "or give --url, --project, and --ref.",
        )
    return values["GITLAB_URL"].rstrip("/"), values["GITLAB_PROJECT_ID"], values["GITLAB_REF"]


def read_folder(base, project, ref, token):
    """Return the entries of the environments folder, or fail with a message for the user."""
    query = {"path": FOLDER, "ref": ref, "per_page": "100"}
    try:
        return common.get_all(base, project, "/repository/tree", query, token)
    except common.GitLabError as exc:
        where = f"{base}, project {project}"
        if exc.status == 404 and "Tree Not Found" in exc.body:
            common.fail(
                "environments_folder_missing",
                f"The folder {FOLDER} does not exist in {where}, branch {ref}, or the branch does not exist.",
            )
        if exc.status in (401, 403, 404):
            remedy = "Check the token." if token else "Set GITLAB_TOKEN or fill .tdm-assistant/gitlab-token."
            common.fail("repo_inaccessible", f"GitLab answered HTTP {exc.status} for {where}. {remedy}")
        return common.fail(exc.code, f"{exc.message} ({where}) {exc.body}".strip())


def environment_names(entries):
    """Return the names of the YAML files among the entries, sorted ignoring case."""
    names = {
        entry["name"][: -len(SUFFIX)]
        for entry in entries
        if entry.get("type") == "blob" and entry.get("name", "").lower().endswith(SUFFIX)
    }
    return sorted(names, key=lambda name: (name.lower(), name))


def describe(chosen, total, where, text):
    """Return the heading line: how many environments were found, and the filter in use."""
    noun = "environment" if total == 1 else "environments"
    masked = "*" in text or "?" in text
    filtered = f' Filter: name {"matches" if masked else "contains"} "{text}".' if text else ""
    if not chosen:
        return f"No {noun} (*{SUFFIX}) found in {where}, {total} in all.{filtered}"
    count = f"{len(chosen)} of {total}" if text else str(len(chosen))
    return f"Found {count} {noun} in {where}.{filtered}"


def main():
    """Read the folder, apply the filter, and print the answer."""
    args = parse_arguments()
    common.use_utf8_output()
    config = common.load_config()
    base, project, ref = resolve_settings(args, config)
    names = environment_names(read_folder(base, project, ref, common.read_token(config)))
    text = args.name.strip()
    passes = common.make_name_filter(text)
    chosen = [name for name in names if passes(name)]
    where = f"{base}, project {project}, branch {ref}, folder {FOLDER}"
    lines = [describe(chosen, len(names), where, text)]
    if chosen:
        lines += ["", *(f"- `{name}`" for name in chosen)]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
