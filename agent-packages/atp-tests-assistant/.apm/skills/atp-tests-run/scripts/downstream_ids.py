"""Find business identifiers while the GitLab pipeline of run_tests.py runs.

The pipeline starts a downstream pipeline, whose first job runs the test cases. That
job logs the ID of a run in the test orchestrator, and the orchestrator serves the log
of the runner, which holds the identifiers of the data the test cases create. The
identifiers appear long before the pipeline ends, so a Scout follows the chain while
the caller waits, and reports each identifier the moment it is found:

1. the bridge job of the pipeline names the downstream pipeline;
2. the job of the downstream pipeline in the stage DOWNSTREAM_STAGE has a log;
3. RUN_ID_PATTERN finds the run ID in that log;
4. GET <ORCHESTRATOR_URL>/atp3/api/v1/runs/<run ID>/logs returns the runner log, and
   every pattern of BUSINESS_ID_PATTERNS is searched in it.

Each step waits for the data of the step before it, so a Scout does one round of
requests per call to advance() and goes as far down the chain as the data allows.

Config keys, all in .atp-assistant/config.json. The first four switch the search on,
and without all of them the search is off:

  ORCHESTRATOR_URL       base URL of the orchestrator, http or https
  DOWNSTREAM_STAGE       stage of the job whose log holds the run ID
  RUN_ID_PATTERN         regular expression for the run ID in that log
  BUSINESS_ID_PATTERNS   object: identifier name -> regular expression
  DISCOVERY_TIMEOUT      seconds from the start of the pipeline; default 420
  DISCOVERY_INTERVAL     seconds between rounds until the run ID is known; default 5
  DISCOVERY_SLOW_INTERVAL  seconds between rounds after that; default 15

A pattern is matched line by line (re.MULTILINE) and takes the identifier from the
group named "value", or from the first group when it has no such name. Python 3.9+,
standard library only.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

REQUIRED_KEYS = (
    "ORCHESTRATOR_URL",
    "DOWNSTREAM_STAGE",
    "RUN_ID_PATTERN",
    "BUSINESS_ID_PATTERNS",
)
DEFAULT_TIMEOUT = 420
DEFAULT_INTERVAL = 5
DEFAULT_SLOW_INTERVAL = 15
FAILURES_ALLOWED = 5
MAX_VALUE_LENGTH = 200
REQUEST_TIMEOUT = 30
RUNS_PATH = "/atp3/api/v1/runs"
TAIL_LINES = 5000
FOUND_PREFIX = "FOUND"


class SettingsError(ValueError):
    """A discovery setting that is incomplete or wrong, with the error code to report."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class SourceError(Exception):
    """A failed request to GitLab or to the orchestrator.

    status is the HTTP status, or None when no answer came.
    """

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


@dataclass
class Settings:
    """The validated discovery settings."""

    orchestrator_url: str
    stage: str
    run_id: re.Pattern
    business: dict
    timeout: float
    interval: float
    slow_interval: float


@dataclass
class State:
    """What a Scout has learned so far."""

    downstream: dict | None = None
    job_id: int | None = None
    run_id: str | None = None
    found: dict = field(default_factory=dict)
    reached: str = "start"
    stopped: str = ""
    message: str = ""


def compile_pattern(key, pattern):
    """Return the compiled pattern, or raise SettingsError when it cannot be used."""
    if not isinstance(pattern, str):
        raise SettingsError("invalid_pattern", f"{key} must be a string")
    try:
        compiled = re.compile(pattern, re.MULTILINE)
    except re.error as exc:
        raise SettingsError(
            "invalid_pattern",
            f"{key} is not a regular expression: {exc}",
        ) from exc
    if "value" not in compiled.groupindex and compiled.groups < 1:
        raise SettingsError(
            "invalid_pattern",
            f"{key} needs a group that captures the identifier, such as (?P<value>...)",
        )
    return compiled


def read_number(config, key, default):
    """Return the positive number at key, or the default when the key is absent."""
    raw = config.get(key, default)
    try:
        number = float(raw)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        raise SettingsError("config_incomplete", f"{key} must be a positive number")
    return number


def read_settings(config):
    """Return the Settings of the config, None when the search is off, or raise.

    The search is off when none of the required keys is set. A partial set raises
    SettingsError, so a typo does not silently switch the search off.
    """
    if not any(config.get(key) for key in REQUIRED_KEYS):
        return None
    missing = [key for key in REQUIRED_KEYS if not config.get(key)]
    if missing:
        raise SettingsError(
            "config_incomplete",
            "The search for identifiers needs all of "
            f"{', '.join(REQUIRED_KEYS)}. Missing in config: {', '.join(missing)}",
        )
    url = str(config["ORCHESTRATOR_URL"])
    if urllib.parse.urlparse(url).scheme not in ("http", "https"):
        raise SettingsError(
            "config_incomplete",
            "ORCHESTRATOR_URL must start with http:// or https://",
        )
    patterns = config["BUSINESS_ID_PATTERNS"]
    if not isinstance(patterns, dict):
        raise SettingsError(
            "invalid_pattern",
            "BUSINESS_ID_PATTERNS must be an object: name -> regular expression",
        )
    business = {}
    for name, pattern in patterns.items():
        business[str(name)] = compile_pattern(f"BUSINESS_ID_PATTERNS.{name}", pattern)
    return Settings(
        orchestrator_url=url,
        stage=str(config["DOWNSTREAM_STAGE"]),
        run_id=compile_pattern("RUN_ID_PATTERN", config["RUN_ID_PATTERN"]),
        business=business,
        timeout=read_number(config, "DISCOVERY_TIMEOUT", DEFAULT_TIMEOUT),
        interval=read_number(config, "DISCOVERY_INTERVAL", DEFAULT_INTERVAL),
        slow_interval=read_number(
            config,
            "DISCOVERY_SLOW_INTERVAL",
            DEFAULT_SLOW_INTERVAL,
        ),
    )


def find_values(pattern, text):
    """Return the distinct values the pattern captures in the text, in order.

    A log is untrusted, so a value that is empty, longer than MAX_VALUE_LENGTH, or
    holds a character that cannot be printed is left out.
    """
    group = "value" if "value" in pattern.groupindex else 1
    lines = text.replace("\r\n", "\n").replace("\r", "\n")
    values = []
    for match in pattern.finditer(lines):
        value = (match.group(group) or "").strip()
        usable = 0 < len(value) <= MAX_VALUE_LENGTH and value.isprintable()
        if usable and value not in values:
            values.append(value)
    return values


def fetch_runner_log(base_url, run_id):
    """Return the log of the run as text; raise SourceError when it cannot be read."""
    quoted = urllib.parse.quote(run_id, safe="")
    url = f"{base_url.rstrip('/')}{RUNS_PATH}/{quoted}/logs?tail_lines={TAIL_LINES}"
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise SourceError(f"the orchestrator answered HTTP {exc.code}", exc.code) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceError(f"cannot reach the orchestrator: {exc}") from exc


def optional(call):
    """Return what call returns, or None when it fails with HTTP 404.

    A 404 means that the job or the run has no log yet, which is not an error.
    """
    try:
        return call()
    except SourceError as exc:
        if exc.status == 404:
            return None
        raise


class Scout:
    """Follow the chain from a pipeline to the runner log, one round per advance()."""

    def __init__(self, settings, pipeline_id, gitlab_get, say):
        """Create a scout for a pipeline that has just started.

        gitlab_get(path, project=None, text=False) reads a path of the GitLab project
        and returns the decoded JSON, or the text when text is true; it raises
        SourceError. say(line) prints a progress line.
        """
        self.settings, self.pipeline_id = settings, pipeline_id
        self.gitlab_get, self.say = gitlab_get, say
        self.started, self.failures = time.monotonic(), 0
        self.state = State(found={name: [] for name in settings.business})

    def active(self):
        """Return True while the search is on and within DISCOVERY_TIMEOUT."""
        if self.state.stopped:
            return False
        if time.monotonic() - self.started >= self.settings.timeout:
            seconds = int(self.settings.timeout)
            self.stop("timeout", f"No search after {seconds} s from the start")
            return False
        return True

    def wait_seconds(self):
        """Return the seconds to wait before the next round."""
        if self.state.run_id is None:
            return self.settings.interval
        return self.settings.slow_interval

    def stop(self, reason, message):
        """Stop the search and say why."""
        self.state.stopped, self.state.message = reason, message
        self.say(f"Search for identifiers stopped: {message}")

    def advance(self):
        """Do one round: go down the chain as far as the data allows."""
        try:
            self.follow_chain()
            self.failures = 0
        except SourceError as exc:
            self.failures += 1
            attempt = f"attempt {self.failures} of {FAILURES_ALLOWED}"
            self.say(f"Search for identifiers: {exc} ({attempt})")
            if self.failures >= FAILURES_ALLOWED:
                self.stop("errors", str(exc))

    def finish(self):
        """Do the last round after the pipeline ends, unless the search failed."""
        if self.state.stopped != "errors":
            self.advance()

    def report(self):
        """Return the fields for the result: the values found and how far it got."""
        state = self.state
        discovery = {
            "reached": state.reached,
            "downstream_pipeline_id": (state.downstream or {}).get("id"),
            "run_id": state.run_id,
        }
        if state.stopped:
            discovery["stopped"] = state.stopped
            discovery["message"] = state.message
        return {"found": state.found, "discovery": discovery}

    def follow_chain(self):
        """Run each step whose input is known and whose output is not."""
        state = self.state
        if state.downstream is None and not self.find_downstream():
            return
        if state.job_id is None and not self.find_job():
            return
        if state.run_id is None and not self.find_run_id():
            return
        self.read_runner_log()

    def find_downstream(self):
        """Take the downstream pipeline from the bridge jobs; return True if found."""
        bridges = self.gitlab_get(f"/pipelines/{self.pipeline_id}/bridges?per_page=100")
        if not isinstance(bridges, list):
            raise SourceError("GitLab returned no list of bridge jobs")
        for bridge in bridges:
            downstream = bridge.get("downstream_pipeline") or {}
            if downstream.get("id"):
                self.state.downstream = downstream
                self.state.reached = "downstream_pipeline"
                self.say(f"Downstream pipeline {downstream['id']} found")
                return True
        return False

    def find_job(self):
        """Take the first job of the stage in the downstream pipeline."""
        state = self.state
        path = f"/pipelines/{state.downstream['id']}/jobs?per_page=100"
        jobs = self.gitlab_get(path, state.downstream.get("project_id"))
        if not isinstance(jobs, list):
            raise SourceError("GitLab returned no list of jobs")
        named = [job for job in jobs if job.get("stage") == self.settings.stage]
        if not named:
            return False
        job = min(named, key=lambda each: each.get("id", 0))
        state.job_id, state.reached = job["id"], "job"
        self.say(f"Job '{job.get('name')}' of stage '{self.settings.stage}' found")
        return True

    def find_run_id(self):
        """Read the log of the job and take the first run ID in it."""
        state = self.state
        path = f"/jobs/{state.job_id}/trace"
        project = state.downstream.get("project_id")
        text = optional(lambda: self.gitlab_get(path, project, True))
        values = find_values(self.settings.run_id, text) if text else []
        if not values:
            return False
        state.run_id, state.reached = values[0], "run_id"
        self.say(f"Run {values[0]} found in the job log")
        return True

    def read_runner_log(self):
        """Read the runner log and report each identifier that is new."""
        state, settings = self.state, self.settings
        url, run_id = settings.orchestrator_url, state.run_id
        text = optional(lambda: fetch_runner_log(url, run_id))
        if text is None:
            return
        state.reached = "runner_log"
        for name, pattern in settings.business.items():
            known = state.found[name]
            for value in find_values(pattern, text):
                if value not in known:
                    known.append(value)
                    self.say(f"{FOUND_PREFIX} {name}={value}")
