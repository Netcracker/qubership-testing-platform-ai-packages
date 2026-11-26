"""Run a test case or a scope in the project's GitLab pipeline, and wait until it ends.

The pipeline checks out the test cases and runs them. Test cases that generate test data
are run the same way. The script takes the pipeline variables from "variables" of
.atp-assistant/config.json, replaces the ones given with --set, and starts the pipeline
with POST /api/v4/projects/<id>/pipeline. It then polls the pipeline until it ends.
Progress lines go to stderr, and the result is one JSON object on stdout, also for an
error.

  run_tests.py [--set VARIABLE=value ...]        show the variables only
  run_tests.py [--set VARIABLE=value ...] --yes  start and wait

Config keys: GITLAB_URL, GITLAB_PROJECT_ID, and GITLAB_REF (the branch to run the pipeline
from). The token comes from the environment variable named by GITLAB_TOKEN_ENV (default
GITLAB_TOKEN) or, when that variable is empty, from the first line of
.atp-assistant/gitlab-token. The token is never printed.

The variables are checked before anything is sent: --set names an existing variable;
ATP_TESTS_GIT_REPO_URL, EXECUTION_TYPE, and EXECUTION_NAME are not empty;
ENABLE_JIRA_INTEGRATION and SEND_WEBEX_NOTIFICATION are true or false. The values of
EXECUTION_TYPE and EXECUTION_NAME are not checked.

While it waits, the script can also search the logs for business identifiers and report
each one as soon as it appears, with a progress line "FOUND <name>=<value>". The search is
described in downstream_ids.py, and the config keys that switch it on are ORCHESTRATOR_URL,
DOWNSTREAM_STAGE, RUN_ID_PATTERN, and BUSINESS_ID_PATTERNS. A search that cannot go on
never stops the wait for the pipeline.

Without --yes:
  {"ok": true, "started": false, "ref": "main", "variables": {...},
   "changed": ["EXECUTION_NAME"],
   "discovery": {"enabled": true, "searches": ["customerId"], "timeout_seconds": 420}}
With --yes, when the pipeline ends:
  {"ok": true, "started": true, "succeeded": false,
   "pipeline": {"id": 7, "status": "failed", "web_url": "..."},
   "variables": {...}, "waited_seconds": 190,
   "failed_jobs": [{"name": "...", "stage": "...", "web_url": "..."}],
   "found": {"customerId": ["9177834604613948718"]},
   "discovery": {"reached": "runner_log", "downstream_pipeline_id": 8,
                 "run_id": "bed125d0-..."}}
The last two fields are there only when the search is on. "reached" is the last step that
worked: start, downstream_pipeline, job, run_id, or runner_log. A search that stopped adds
"stopped" (timeout or errors) and "message" to "discovery".

Error codes: config_missing, config_unreadable, config_incomplete, invalid_pattern,
gitlab_settings_missing, bad_argument, invalid_variables (with "problems"), token_missing,
http_error (with "status"), server_unreachable, timeout and poll_failed (both with
"pipeline", and with "found" and "discovery" when the search is on; the pipeline keeps
running). A wrong command line exits with 2. Python 3.9+, standard library only.
"""

import argparse
import importlib
import json
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True  # keep __pycache__ out of the skill folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "atp-common" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script folder out
common = importlib.import_module("atp_common")
ids = importlib.import_module("downstream_ids")

SETTINGS = ("GITLAB_URL", "GITLAB_PROJECT_ID", "GITLAB_REF")
NOT_EMPTY = ("ATP_TESTS_GIT_REPO_URL", "EXECUTION_TYPE", "EXECUTION_NAME")
BOOLEANS = ("ENABLE_JIRA_INTEGRATION", "SEND_WEBEX_NOTIFICATION")
FINISHED = ("success", "failed", "canceled", "skipped", "manual")
POLL_FAILURES_ALLOWED = 3


def parse_arguments(argv=None):
    """Return the parsed command line; exit with 2 on a wrong one."""
    parser = argparse.ArgumentParser(description="Run a test case or a scope in the GitLab pipeline.")
    parser.add_argument("--set", dest="sets", action="append", default=[], help="VARIABLE=value; repeat for more")
    parser.add_argument("--yes", action="store_true", help="start the pipeline; without it only show the variables")
    parser.add_argument("--interval", type=float, default=30, help="seconds between two status requests")
    parser.add_argument("--timeout", type=float, default=1800, help="seconds to wait for the pipeline to end")
    return parser.parse_args(argv)


def progress(line):
    """Print a progress line to stderr."""
    print(line, file=sys.stderr, flush=True)


def parse_overrides(items):
    """Split VARIABLE=value strings at the first '=' into (name, value) pairs, or fail."""
    overrides = []
    for item in items:
        name, separator, value = item.partition("=")
        if not separator or not name:
            common.fail("bad_argument", f"--set '{item}' is not VARIABLE=value.")
        overrides.append((name, value))
    return overrides


def read_config():
    """Return the config with the GitLab settings, or fail naming what is missing."""
    config = common.load_config()
    if not config:
        common.fail("config_missing", "No .atp-assistant/config.json. Create it in the project folder.")
    missing = [key for key in SETTINGS if not str(config.get(key) or "").strip()]
    if missing:
        common.fail("gitlab_settings_missing", f"Missing in .atp-assistant/config.json: {', '.join(missing)}.")
    return config


def as_text(value):
    """Return a JSON value as the string that GitLab receives."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else str(value)


def check_variables(variables):
    """Normalize the booleans in place and return the problems found."""
    problems = []
    for name in BOOLEANS:
        if name in variables:
            lowered = variables[name].strip().lower()
            if lowered in ("true", "false"):
                variables[name] = lowered
            else:
                problems.append(f"'{name}' must be true or false, not '{variables[name]}'")
    for name in NOT_EMPTY:
        if not variables.get(name, "").strip():
            problems.append(f"'{name}' must not be empty")
    return problems


def load_variables(config, overrides):
    """Return (variables, changed names) with the overrides applied, or fail."""
    variables = {str(name): as_text(value) for name, value in common.read_variables(config).items()}
    problems, changed = [], []
    for name, value in overrides:
        if name not in variables:
            known = ", ".join(sorted(variables))
            problems.append(f"'{name}' is not a variable of the config. Known: {known}")
            continue
        if variables[name] != value:
            changed.append(name)
        variables[name] = value
    problems += check_variables(variables)
    if problems:
        common.fail("invalid_variables", "; ".join(problems), problems=problems)
    return variables, changed


@dataclass
class GitLab:
    """The pipeline project of the config and the token that reads and starts its pipelines."""

    config: dict
    token: str

    def send(self, path, body=None, project=None):
        """Request a path of the project and return the bytes of the answer; raise GitLabError.

        The request is a POST of body when body is given. project replaces the configured one.
        """
        base = self.config["GITLAB_URL"].rstrip("/")
        quoted = urllib.parse.quote(str(project or self.config["GITLAB_PROJECT_ID"]), safe="")
        try:
            return common.send(f"{base}/api/v4/projects/{quoted}{path}", self.token, body)[0]
        except common.GitLabError as exc:
            method = "GET" if body is None else "POST"
            message = f"{exc.message} for {method} {path}"
            raise common.GitLabError(exc.code, message, status=exc.status, body=exc.body) from exc

    def json(self, path, body=None, project=None):
        """Request a path of the project and return the decoded JSON; raise GitLabError."""
        answer = self.send(path, body, project)
        try:
            return json.loads(answer.decode("utf-8"))
        except ValueError as exc:
            raise common.GitLabError("http_error", f"The GitLab response is not JSON: {exc}") from exc

    def read(self, path, project=None, text=False):
        """Read a path for the search of downstream_ids; raise its SourceError.

        Return the text of the answer when text is true, and the decoded JSON otherwise.
        """
        try:
            if text:
                return self.send(path, project=project).decode("utf-8", "replace")
            return self.json(path, project=project)
        except common.GitLabError as exc:
            raise ids.SourceError(exc.message, exc.status) from exc


def error_fields(exc):
    """Return the extra fields of the error object for a failed GitLab request."""
    return {} if exc.status is None else {"status": exc.status, "body": exc.body}


def start_pipeline(gitlab, variables):
    """Start the pipeline and return {"id", "status", "web_url"}, or fail."""
    payload = {
        "ref": gitlab.config["GITLAB_REF"],
        "variables": [{"key": name, "value": value} for name, value in variables.items()],
    }
    try:
        created = gitlab.json("/pipeline", payload)
    except common.GitLabError as exc:
        common.fail(exc.code, exc.message, **error_fields(exc))
    return {"id": created.get("id"), "status": created.get("status", "unknown"), "web_url": created.get("web_url", "")}


def failed_jobs(gitlab, pipeline_id):
    """Return the failed jobs of the pipeline, or [] when GitLab does not answer."""
    try:
        jobs = gitlab.json(f"/pipelines/{pipeline_id}/jobs?scope[]=failed&per_page=20")
    except common.GitLabError:
        return []
    return [{field: job.get(field) for field in ("name", "stage", "web_url")} for job in jobs]


@dataclass
class Run:
    """The pipeline that is running, and what is needed to follow it."""

    gitlab: GitLab
    pipeline: dict
    variables: dict
    scout: Any = None  # downstream_ids.Scout when the search is on

    def found(self):
        """Return the result fields of the search for identifiers, or {} when it is off."""
        return self.scout.report() if self.scout else {}


def read_status(run, failures, started):
    """Ask GitLab for the status of the pipeline; return the count of failed asks.

    The count is reset by an answer. It fails with poll_failed when it reaches
    POLL_FAILURES_ALLOWED.
    """
    pipeline = run.pipeline
    try:
        pipeline["status"] = run.gitlab.json(f"/pipelines/{pipeline['id']}").get("status", "unknown")
        failures = 0
    except common.GitLabError as exc:
        failures += 1
        progress(f"Status request failed ({exc.message}), attempt {failures}")
        if failures >= POLL_FAILURES_ALLOWED:
            message = f"{exc.message}. The pipeline may still be running."
            common.fail("poll_failed", message, pipeline=pipeline, variables=run.variables, **run.found())
    elapsed = int(time.monotonic() - started)
    progress(f"Pipeline {pipeline['id']}: {pipeline['status']} after {elapsed} s")
    return failures


def poll_status(run, args):
    """Poll until the pipeline ends; return the seconds waited, or fail.

    The status is read every args.interval seconds. The scout, when there is one, is called
    at its own shorter rate, so that an identifier is reported soon after it appears in a
    log.
    """
    started = time.monotonic()
    next_status, failures = started + args.interval, 0
    while run.pipeline["status"] not in FINISHED:
        now = time.monotonic()
        if now - started >= args.timeout:
            message = f"The pipeline did not end in {int(args.timeout)} s. It keeps running."
            common.fail("timeout", message, pipeline=run.pipeline, variables=run.variables, **run.found())
        wake = next_status
        if run.scout and run.scout.active():
            wake = min(wake, now + run.scout.wait_seconds())
        time.sleep(max(min(wake, started + args.timeout) - now, 0))
        if run.scout and run.scout.active():
            run.scout.advance()
        if time.monotonic() >= next_status:
            failures = read_status(run, failures, started)
            next_status = time.monotonic() + args.interval
    if run.scout:
        run.scout.finish()
    return int(time.monotonic() - started)


def read_discovery(config):
    """Return the settings of the search for identifiers, None when it is off, or fail."""
    try:
        return ids.read_settings(config)
    except ids.SettingsError as exc:
        return common.fail(exc.code, str(exc))


def describe_discovery(settings):
    """Return the plan of the search for the result without --yes."""
    if settings is None:
        return {"enabled": False}
    return {"enabled": True, "searches": list(settings.business), "timeout_seconds": settings.timeout}


def require_token(config):
    """Return the GitLab token, or fail saying where it goes."""
    token = common.read_token(config)
    if not token:
        env_name = config.get("GITLAB_TOKEN_ENV") or common.DEFAULT_TOKEN_ENV
        token_path = Path(config["CONFIG_DIR"]) / common.TOKEN_FILE
        common.fail(
            "token_missing",
            f"No GitLab token. Set the environment variable {env_name}, or put the token on the first line of "
            f"{token_path}. Don't give it to the agent.",
        )
    return token


def main():
    """Show the variables, or start the pipeline and wait for it."""
    args = parse_arguments()
    common.use_utf8_output()
    common.report_errors_on_stdout()
    overrides = parse_overrides(args.sets)
    config = read_config()
    variables, changed = load_variables(config, overrides)
    settings = read_discovery(config)

    if not args.yes:
        common.succeed(
            started=False,
            ref=config["GITLAB_REF"],
            variables=variables,
            changed=changed,
            discovery=describe_discovery(settings),
        )

    gitlab = GitLab(config, require_token(config))
    pipeline = start_pipeline(gitlab, variables)
    progress(f"Pipeline {pipeline['id']} started: {pipeline['web_url']}")
    run = Run(gitlab, pipeline, variables)
    if settings:
        run.scout = ids.Scout(settings, pipeline["id"], gitlab.read, progress)
    waited = poll_status(run, args)

    result = {
        "started": True,
        "succeeded": pipeline["status"] == "success",
        "pipeline": pipeline,
        "variables": variables,
        "waited_seconds": waited,
        **run.found(),
    }
    if pipeline["status"] == "failed":
        result["failed_jobs"] = failed_jobs(gitlab, pipeline["id"])
    common.succeed(**result)


if __name__ == "__main__":
    main()
