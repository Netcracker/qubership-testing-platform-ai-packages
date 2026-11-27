"""Test run_tests.py against a fake GitLab and a fake orchestrator. selftest.py runs these tests.

The tests cover the plan without --yes, the check of the variables and the settings, the
start of the pipeline and the wait for it, the errors, the search for business
identifiers in the logs, and the links to them.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SCRIPT = Path(__file__).resolve().parents[1] / ".apm" / "skills" / "atp-tests-run" / "scripts" / "run_tests.py"
TOKEN = "secret-run-token"
VARIABLES = {
    "PIPELINE_RUNTIME_CONFIG": "environments/x.yaml",
    "ATP_TESTS_GIT_REPO_URL": "http://g/r.git",
    "ATP_TESTS_GIT_REPO_BRANCH": "main",
    "EXECUTION_TYPE": "scope",
    "EXECUTION_NAME": "regression",
    "ENABLE_JIRA_INTEGRATION": False,
    "SEND_WEBEX_NOTIFICATION": "true",
}
STAGE = "1. Run ATP3 tests"
RUN_ID = "bed125d0-ba78-4b20-872b-a845c3560032"
JOB_LOG = f"[INFO] Run submitted: id={RUN_ID}, phase=Pending\n"
BRIDGE = {"name": "run", "downstream_pipeline": {"id": 43, "project_id": 7}}
STAGE_JOBS = [
    {"id": 502, "name": "second", "stage": STAGE},
    {"id": 400, "name": "other stage", "stage": "2. Report"},
    {"id": 501, "name": "first", "stage": STAGE},
]
FIRST_ID = "9177834604613948718"
LOG_ONE = f"######## createBca ########\ncustomerId: {FIRST_ID}\nname: x\n"
LOG_TWO = LOG_ONE + "customerId: 123\ncustomerId: " + "9" * 300 + "\n"


def run_isolated(script, args, cwd, token):
    """Run a script with python -I in cwd, with GITLAB_TOKEN set to token or unset."""
    env = {key: value for key, value in os.environ.items() if key != "GITLAB_TOKEN"}
    if token:
        env["GITLAB_TOKEN"] = token
    command = [sys.executable, "-I", str(script), *args]
    return subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", check=False)


def next_answer(answers):
    """Return the first answer of a list and drop it, but keep the last one."""
    return answers.pop(0) if len(answers) > 1 else answers[0]


class Fake(ThreadingHTTPServer):
    """A server on localhost that records its requests and gives the prepared answers."""

    def __init__(self, handler):
        super().__init__(("127.0.0.1", 0), handler)
        self.url = f"http://127.0.0.1:{self.server_port}"
        self.requests = []
        self.answers = {}
        threading.Thread(target=self.serve_forever, daemon=True).start()

    def reset(self, **answers):
        """Forget the requests and set the lists of answers; the last answer of a list repeats."""
        defaults = {
            "statuses": ["success"],
            "post": [201],
            "failed": [[]],
            "bridges": [[]],
            "jobs": [[]],
            "trace": [(404, "")],
            "log": [(404, "")],
            "file": [(404, "")],
        }
        self.answers = {key: list(value) for key, value in {**defaults, **answers}.items()}
        self.requests = []


class Handler(BaseHTTPRequestHandler):
    """Send text and JSON answers without a server log."""

    def log_message(self, *args):  # silence the server log
        pass

    def reply(self, status, body):
        """Send a string as it is, and anything else as JSON."""
        data = (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class GitLabHandler(Handler):
    """Answer the requests that start a pipeline and follow it."""

    def do_POST(self):  # pylint: disable=invalid-name
        """Answer the start of a pipeline."""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(("POST", self.path, self.headers.get("PRIVATE-TOKEN"), body))
        status = next_answer(self.server.answers["post"])
        pipeline = {"id": 42, "status": "pending", "web_url": "http://gitlab.test/p/42"}
        self.reply(status, pipeline if status < 400 else {"message": "refused"})

    def do_GET(self):  # pylint: disable=invalid-name
        """Answer the status, the jobs, the bridge jobs, or a job log."""
        self.server.requests.append(("GET", self.path, self.headers.get("PRIVATE-TOKEN"), None))
        answers = self.server.answers
        if "/pipelines/42/bridges" in self.path:
            self.reply(200, next_answer(answers["bridges"]))
        elif "/pipelines/43/jobs" in self.path:
            self.reply(200, next_answer(answers["jobs"]))
        elif "/repository/files/" in self.path:
            self.reply(*next_answer(answers["file"]))
        elif self.path.endswith("/trace"):
            self.reply(*next_answer(answers["trace"]))
        elif "/jobs" in self.path:
            self.reply(200, next_answer(answers["failed"]))
        else:
            self.reply(200, {"id": 42, "status": next_answer(answers["statuses"])})


class OrchestratorHandler(Handler):
    """Answer the requests for the runner log."""

    def do_GET(self):  # pylint: disable=invalid-name
        """Answer the next prepared log."""
        self.server.requests.append(self.path)
        self.reply(*next_answer(self.server.answers["log"]))


class RunScriptCase(unittest.TestCase):
    """Run the script in a temporary project against the fake servers."""

    @classmethod
    def setUpClass(cls):
        cls.gitlab, cls.orchestrator = Fake(GitLabHandler), Fake(OrchestratorHandler)

    @classmethod
    def tearDownClass(cls):
        for server in (cls.gitlab, cls.orchestrator):
            server.shutdown()
            server.server_close()

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.gitlab.reset()
        self.orchestrator.reset()
        self.configure()

    def configure(self, **more):
        """Write the config; a keyword adds a key or replaces one."""
        config = {"GITLAB_URL": self.gitlab.url, "GITLAB_PROJECT_ID": "7", "GITLAB_REF": "main"}
        config = {**config, "variables": VARIABLES, **more}
        folder = self.project / ".atp-assistant"
        folder.mkdir(exist_ok=True)
        (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")

    def run_script(self, *args, token=TOKEN):
        """Return (exit code, the JSON object of stdout, stdout and stderr together)."""
        done = run_isolated(SCRIPT, args, self.project, token)
        return done.returncode, json.loads(done.stdout), done.stderr + done.stdout

    def result(self, *args):
        """Return the result object and the whole output of a run that exits with 0."""
        code, out, text = self.run_script(*args)
        self.assertEqual(code, 0, text)
        return out, text

    def error_of(self, *args, **kwargs):
        """Return the error object of a run that exits with 1; it comes on stdout."""
        code, out, text = self.run_script(*args, **kwargs)
        self.assertEqual(code, 1, text)
        self.assertFalse(out["ok"])
        return out


class RunCase(RunScriptCase):
    """The plan, the start of the pipeline, the wait, and the errors."""

    def test_without_yes_the_plan_is_shown_and_nothing_is_sent(self):
        """The plan holds the variables with the changes applied and names the changed ones."""
        out, _ = self.result("--set", "EXECUTION_TYPE=test", "--set", "EXECUTION_NAME=Gen domestic")
        self.assertFalse(out["started"])
        self.assertEqual(out["variables"]["EXECUTION_NAME"], "Gen domestic")
        self.assertEqual(out["changed"], ["EXECUTION_TYPE", "EXECUTION_NAME"])
        self.assertFalse(out["discovery"]["enabled"])
        self.assertEqual(self.gitlab.requests, [])

    def test_the_plan_says_whether_to_ask_before_the_run(self):
        """RUN_TESTS_CONFIRM is true unless the config says false; another value starts nothing."""
        for value, confirm in ((None, True), ("", True), (True, True), (False, False), ("False", False)):
            self.configure(**({} if value is None else {"RUN_TESTS_CONFIRM": value}))
            self.assertEqual(self.result()[0]["confirm"], confirm, value)
        self.configure(RUN_TESTS_CONFIRM="no")
        self.assertEqual(self.error_of("--yes")["error"], "invalid_value")
        self.assertEqual(self.gitlab.requests, [])

    def test_booleans_are_sent_in_lowercase(self):
        """A JSON boolean and a TRUE of --set become the strings that the pipeline reads."""
        out, _ = self.result("--set", "SEND_WEBEX_NOTIFICATION=TRUE")
        self.assertEqual(out["variables"]["SEND_WEBEX_NOTIFICATION"], "true")
        self.assertEqual(out["variables"]["ENABLE_JIRA_INTEGRATION"], "false")

    def test_wrong_variables_are_refused(self):
        """An unknown name, a wrong boolean, an empty name, and a missing '=' start nothing."""
        for argument in ("NOPE=1", "SEND_WEBEX_NOTIFICATION=yes", "EXECUTION_NAME="):
            self.assertEqual(self.error_of("--set", argument, "--yes")["error"], "invalid_variables", argument)
        self.assertEqual(self.error_of("--set", "EXECUTION_NAME", "--yes")["error"], "bad_argument")
        self.assertEqual(self.gitlab.requests, [])

    def test_missing_settings_are_reported_on_stdout(self):
        """A missing key, a broken config, and no config are errors of the JSON result."""
        self.configure(GITLAB_REF="")
        error = self.error_of()
        self.assertEqual(error["error"], "gitlab_settings_missing")
        self.assertIn("GITLAB_REF", error["message"])
        self.configure(variables=[])
        self.assertEqual(self.error_of()["error"], "config_unreadable")
        shutil.rmtree(self.project / ".atp-assistant")
        self.assertEqual(self.error_of()["error"], "config_missing")

    def test_a_token_is_needed_to_start(self):
        """Without a token, --yes fails before any request."""
        self.assertEqual(self.error_of("--yes", token=None)["error"], "token_missing")
        self.assertEqual(self.gitlab.requests, [])

    def test_the_pipeline_is_started_and_awaited(self):
        """The ref and the variables are posted, and the token goes into the header and no output."""
        self.gitlab.reset(statuses=["pending", "running", "success"])
        out, text = self.result("--yes", "--interval", "0.05", "--set", "EXECUTION_NAME=Gen domestic")
        self.assertTrue(out["succeeded"])
        self.assertEqual(out["pipeline"]["id"], 42)
        method, path, token, body = self.gitlab.requests[0]
        self.assertEqual((method, path, token), ("POST", "/api/v4/projects/7/pipeline", TOKEN))
        self.assertEqual(body["ref"], "main")
        self.assertIn({"key": "EXECUTION_NAME", "value": "Gen domestic"}, body["variables"])
        self.assertNotIn(TOKEN, text)
        self.assertNotIn("found", out)

    def test_a_result_without_the_search_says_so(self):
        """The plan, the result, and a timeout error say that no search is made, and name the keys."""
        self.gitlab.reset(statuses=["success"])
        plan, _ = self.result()
        done, _ = self.result("--yes", "--interval", "0.05")
        self.gitlab.reset(statuses=["running"])
        error = self.error_of("--yes", "--interval", "0.1", "--timeout", "0.3")
        for out in (plan, done, error):
            self.assertFalse(out["discovery"]["enabled"])
            self.assertIn("No search for business identifiers", out["discovery"]["message"])
            self.assertIn("ORCHESTRATOR_URL", out["discovery"]["message"])
            self.assertNotIn("found", out)

    def test_a_project_path_is_quoted(self):
        """GITLAB_PROJECT_ID can be a path of the project."""
        self.configure(GITLAB_PROJECT_ID="group/pipeline")
        self.result("--yes", "--interval", "0.05")
        self.assertEqual(self.gitlab.requests[0][1], "/api/v4/projects/group%2Fpipeline/pipeline")

    def test_a_failed_pipeline_lists_its_failed_jobs(self):
        """A failed pipeline is a result, not an error, with the link and the jobs."""
        job = {"name": "run", "stage": "test", "web_url": "http://gitlab.test/j/1"}
        self.gitlab.reset(statuses=["running", "failed"], failed=[[job]])
        out, _ = self.result("--yes", "--interval", "0.05")
        self.assertFalse(out["succeeded"])
        self.assertEqual(out["failed_jobs"], [job])

    def test_timeout_refusal_and_unreachable_gitlab(self):
        """A timeout keeps the pipeline in the error; HTTP errors carry the status and no token."""
        self.gitlab.reset(statuses=["running"])
        error = self.error_of("--yes", "--interval", "0.1", "--timeout", "0.5")
        self.assertEqual((error["error"], error["pipeline"]["id"]), ("timeout", 42))
        self.gitlab.reset(post=[401])
        error = self.error_of("--yes")
        self.assertEqual((error["error"], error["status"]), ("http_error", 401))
        self.assertIn("POST /pipeline", error["message"])
        self.assertNotIn(TOKEN, json.dumps(error))
        self.configure(GITLAB_URL="http://127.0.0.1:1")
        self.assertEqual(self.error_of("--yes")["error"], "server_unreachable")


class DiscoveryCase(RunScriptCase):
    """The search for business identifiers while the pipeline runs."""

    def discovery(self, **more):
        """Write a config with the search on, at a fast pace; a keyword replaces a key."""
        keys = {
            "ORCHESTRATOR_URL": self.orchestrator.url,
            "DOWNSTREAM_STAGE": STAGE,
            "RUN_ID_PATTERN": r"Run submitted: id=(?P<value>[^,\s]+)",
            "BUSINESS_ID_PATTERNS": {"customerId": r"^customerId:[ \t]*(?P<value>\d+)[ \t]*$"},
            "DISCOVERY_INTERVAL": 0.05,
            "DISCOVERY_SLOW_INTERVAL": 0.05,
        }
        self.configure(**{**keys, **more})

    def chain(self, **answers):
        """Set the answers of a downstream pipeline that is there from the start."""
        self.gitlab.reset(**{"bridges": [[BRIDGE]], "jobs": [STAGE_JOBS], "trace": [(200, JOB_LOG)], **answers})

    def test_the_plan_lists_the_searches(self):
        """Without --yes, the result says what will be searched and for how long."""
        self.discovery()
        out, _ = self.result()
        self.assertEqual(out["discovery"], {"enabled": True, "searches": ["customerId"], "timeout_seconds": 420.0})

    def test_patterns_without_the_url_leave_the_search_off(self):
        """A config that holds the patterns and an empty ORCHESTRATOR_URL runs without the search."""
        self.discovery(ORCHESTRATOR_URL="")
        out, _ = self.result("--yes", "--interval", "0.05")
        self.assertFalse(out["discovery"]["enabled"])
        self.assertEqual(self.orchestrator.requests, [])

    def test_wrong_settings_are_refused(self):
        """A bad pattern, a bad value, a partial set, and a non-http URL start nothing."""
        cases = [
            ("invalid_pattern", {"RUN_ID_PATTERN": "id=(unclosed"}),
            ("invalid_pattern", {"RUN_ID_PATTERN": "Run submitted"}),
            ("invalid_pattern", {"BUSINESS_ID_PATTERNS": ["customerId"]}),
            ("config_incomplete", {"DISCOVERY_TIMEOUT": 0}),
            ("config_incomplete", {"ORCHESTRATOR_URL": "file:///etc/passwd"}),
        ]
        for code, keys in cases:
            self.discovery(**keys)
            self.assertEqual(self.error_of("--yes")["error"], code, keys)
        self.configure(ORCHESTRATOR_URL=self.orchestrator.url)
        error = self.error_of("--yes")
        self.assertEqual(error["error"], "config_incomplete")
        self.assertIn("DOWNSTREAM_STAGE", error["message"])
        self.assertEqual(self.gitlab.requests, [])

    def test_identifiers_are_reported_while_the_pipeline_runs(self):
        """The chain is followed, each usable value is printed once, and the result lists them."""
        self.discovery()
        self.chain(
            statuses=["running"] * 6 + ["success"],
            bridges=[[], [BRIDGE]],
            jobs=[[], STAGE_JOBS],
            trace=[(404, ""), (200, "starting\n"), (200, JOB_LOG)],
        )
        self.orchestrator.reset(log=[(404, ""), (200, LOG_ONE), (200, LOG_TWO)])
        out, text = self.result("--yes", "--interval", "0.3")
        self.assertEqual(out["found"], {"customerId": [FIRST_ID, "123"]})
        info = out["discovery"]
        self.assertEqual((info["reached"], info["run_id"], info["downstream_pipeline_id"]), ("runner_log", RUN_ID, 43))
        self.assertEqual(text.count(f"FOUND customerId={FIRST_ID}"), 1)
        self.assertLess(text.index(f"FOUND customerId={FIRST_ID}"), text.index("success after"))
        self.assertEqual(self.orchestrator.requests[0], f"/atp3/api/v1/runs/{RUN_ID}/logs?tail_lines=5000")
        traces = [path for _, path, _, _ in self.gitlab.requests if path.endswith("/trace")]
        self.assertTrue(traces[0].endswith("/jobs/501/trace"), traces[0])

    def test_a_failing_search_does_not_stop_the_wait(self):
        """Errors of the orchestrator and a missing downstream pipeline end the search only."""
        self.discovery()
        self.chain(statuses=["running"] * 8 + ["success"])
        self.orchestrator.reset(log=[(500, "broken")])
        out, _ = self.result("--yes", "--interval", "0.1")
        self.assertTrue(out["succeeded"])
        self.assertEqual((out["found"], out["discovery"]["stopped"]), ({"customerId": []}, "errors"))
        self.discovery(DISCOVERY_TIMEOUT=0.2)
        self.gitlab.reset(statuses=["running"] * 9 + ["success"])
        out, _ = self.result("--yes", "--interval", "0.1")
        self.assertEqual((out["discovery"]["stopped"], out["discovery"]["reached"]), ("timeout", "start"))

    def test_a_pipeline_timeout_keeps_the_identifiers(self):
        """The error of a timeout holds what the search has found."""
        self.discovery()
        self.chain(statuses=["running"])
        self.orchestrator.reset(log=[(200, LOG_ONE)])
        error = self.error_of("--yes", "--interval", "0.1", "--timeout", "0.6")
        self.assertEqual((error["error"], error["found"]), ("timeout", {"customerId": [FIRST_ID]}))

    def test_a_run_id_from_a_log_is_quoted(self):
        """The text that a log gives as the run ID cannot change the path of the request."""
        self.discovery(RUN_ID_PATTERN="Run submitted: id=(?P<value>[^,]+),")
        log = "Run submitted: id=a/b?c d, phase=Pending\n"
        self.chain(statuses=["running"] * 4 + ["success"], trace=[(200, log)])
        self.orchestrator.reset(log=[(200, LOG_ONE)])
        self.result("--yes", "--interval", "0.1")
        self.assertEqual(self.orchestrator.requests[0], "/atp3/api/v1/runs/a%2Fb%3Fc%20d/logs?tail_lines=5000")


def environment_configuration(url="http://crm.test:1234/"):
    """Return the text of an environment configuration with one system, crm."""
    connections = [{"HTTP": {"url": url, "password": "hunter2"}, "ECA": {"host": "eca.test", "port": 8}}]
    return json.dumps({"systems": [{"crm": {"connections": connections}}]})


class LinkCase(RunScriptCase):
    """The links to the business identifiers."""

    def links(self, templates=None, extra="A=1, ENV_CONFIGURATION_TEMPLATE_FILENAME=x.json", **more):
        """Write a config with the search and the links on; templates replaces the default."""
        keys = {
            "ORCHESTRATOR_URL": self.orchestrator.url,
            "DOWNSTREAM_STAGE": STAGE,
            "RUN_ID_PATTERN": r"Run submitted: id=(?P<value>[^,\s]+)",
            "BUSINESS_ID_PATTERNS": {"customerId": r"^customerId:[ \t]*(?P<value>.+)$"},
            "DISCOVERY_INTERVAL": 0.05,
            "DISCOVERY_SLOW_INTERVAL": 0.05,
            "BUSINESS_IDS_AS_LINKS": True,
            "variables": {**VARIABLES, "ATP_TESTS_GIT_REPO_URL": f"{self.gitlab.url}/g/t.git", "EXTRA_VARS": extra},
        }
        if templates is not None:
            keys["BUSINESS_ID_LINK_TEMPLATES"] = templates
        self.configure(**{**keys, **more})

    def serve(self, text, **answers):
        """Set the content of the configuration file and the answers of the chain."""
        chain = {"bridges": [[BRIDGE]], "jobs": [STAGE_JOBS], "trace": [(200, JOB_LOG)]}
        self.gitlab.reset(**{**chain, "file": [(200, text)], **answers})

    def test_each_template_gives_a_link_for_each_identifier(self):
        """The plan shows the filled templates, and the run reports an encoded link for each."""
        self.links(
            [
                "get_property('crm','HTTP','url')/?ncobject=$ID",
                "http://get_property('crm','ECA','host'):get_property('crm','ECA','port')/c/$ID",
            ]
        )
        self.serve(environment_configuration(), statuses=["running"] * 3 + ["success"])
        plan, _ = self.result()
        shown = plan["discovery"]["links"]
        self.assertEqual(shown["file"], "environment-configuration/x.json")
        self.assertEqual(
            [outcome["link"] for outcome in shown["templates"]],
            ["http://crm.test:1234/?ncobject=$ID", "http://eca.test:8/c/$ID"],
        )
        self.assertEqual(shown["templates"][0]["template"], "get_property('crm','HTTP','url')/?ncobject=$ID")
        self.assertEqual(
            self.gitlab.requests[0][1:3],
            ("/api/v4/projects/g%2Ft/repository/files/environment-configuration%2Fx.json/raw?ref=main", TOKEN),
        )
        self.orchestrator.reset(log=[(200, "customerId: 7&a=b\n")])
        out, text = self.result("--yes", "--interval", "0.1")
        expected = ["http://crm.test:1234/?ncobject=7%26a%3Db", "http://eca.test:8/c/7%26a%3Db"]
        self.assertEqual(out["links"], {"customerId": {"7&a=b": expected}})
        for link in expected:
            self.assertEqual(text.count(f"LINK customerId=7&a=b {link}\n"), 1, text)
        self.assertNotIn("hunter2", text)

    def test_the_default_template_and_a_password_in_the_url(self):
        """Without the key, the default template applies; the user and password of a URL are dropped."""
        self.links()
        self.serve(environment_configuration("https://bob:hunter2@crm.test/a b"))
        plan, text = self.result()
        self.assertEqual(plan["discovery"]["links"]["templates"][0]["link"], "https://crm.test/a%20b/?ncobject=$ID")
        self.assertNotIn("hunter2", text)

    def test_a_link_that_cannot_be_built_starts_nothing(self):
        """A bad setting, a missing property, or a missing file is an error before the pipeline."""
        good = environment_configuration()
        cases = [
            ("invalid_link_template", {"templates": []}, good),
            ("invalid_link_template", {"templates": ["http://x/"]}, good),
            ("invalid_link_template", {"templates": ["get_property('crm')/$ID"]}, good),
            ("invalid_link_template", {"templates": ["http://x/get_property('crm','HTTP','password')$ID"]}, good),
            ("invalid_value", {"BUSINESS_IDS_AS_LINKS": "yes"}, good),
            ("env_config_unresolved", {"extra": "A=1"}, good),
            ("env_config_unresolved", {"extra": "ENV_CONFIGURATION_TEMPLATE_FILENAME=../x.json"}, good),
            ("env_config_unresolved", {"templates": ["get_property('billing','HTTP','url')/$ID"]}, good),
            ("env_config_unresolved", {}, "not JSON hunter2"),
            ("env_config_unresolved", {}, "[]"),
            ("env_config_unresolved", {}, environment_configuration("javascript:alert(1)")),
        ]
        for code, keys, text in cases:
            self.links(**keys)
            self.serve(text)
            error = self.error_of("--yes")
            self.assertEqual(error["error"], code, (keys, text, error))
            self.assertNotIn("hunter2", error["message"])
            self.assertEqual([method for method, *_ in self.gitlab.requests if method == "POST"], [])
        self.links()
        self.gitlab.reset()
        self.assertIn("HTTP 404", self.error_of()["message"])

    def test_a_missing_value_is_reported_by_template(self):
        """The error shows every template, with its link or with what has no value."""
        good = "get_property('crm','HTTP','url')/$ID"
        bad = "get_property('billing','HTTP','url')/$ID"
        self.links([good, bad])
        self.serve(environment_configuration())
        error = self.error_of()
        self.assertEqual(
            error["templates"],
            [
                {"template": good, "link": "http://crm.test:1234/$ID"},
                {"template": bad, "missing": ["billing.HTTP.url"]},
            ],
        )
        self.assertIn("template 2: no value for billing.HTTP.url", error["message"])

    def test_an_escaped_comma_stays_in_its_value(self):
        """A pair is not split at an escaped comma, and the filename gets the comma."""
        extra = r"A=1\,ENV_CONFIGURATION_TEMPLATE_FILENAME=no.json,ENV_CONFIGURATION_TEMPLATE_FILENAME=a\,b.json"
        self.links(extra=extra)
        self.serve(environment_configuration())
        plan, _ = self.result()
        self.assertEqual(plan["discovery"]["links"]["file"], "environment-configuration/a,b.json")
        self.assertEqual(plan["variables"]["EXTRA_VARS"], extra)

    def test_different_names_give_a_warning(self):
        """A prefix that ends in '-' or '_' is allowed; another name is warned about."""
        for runtime, differ in (("environments/dyn-X.yaml", False), ("environments/max.yaml", True), ("", False)):
            self.links()
            self.serve(environment_configuration())
            plan, _ = self.result("--set", f"PIPELINE_RUNTIME_CONFIG={runtime}")
            self.assertEqual("warning" in plan["discovery"]["links"], differ, runtime)

    def test_without_the_search_the_links_are_not_checked(self):
        """With ORCHESTRATOR_URL empty, nothing is read, whatever the keys of the links hold."""
        self.links([], extra="", ORCHESTRATOR_URL="")
        self.result()
        self.assertEqual(self.gitlab.requests, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
