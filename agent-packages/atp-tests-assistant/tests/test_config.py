"""Test manage_config.py. selftest.py runs these tests.

The tests cover the created template, the output and its masking, the changes with their
checks, the kept file after a wrong change, and the errors.
"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from test_run import run_isolated

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SCRIPT = Path(__file__).resolve().parents[1] / ".apm" / "skills" / "atp-config-manage" / "scripts" / "manage_config.py"
TOKEN = "secret-config-token"


class ConfigCase(unittest.TestCase):
    """Run the script in a temporary project."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.path = self.project / ".atp-assistant" / "config.json"

    def save(self, config):
        """Write the config of the project."""
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def config(self):
        """Return the config of the project."""
        return json.loads(self.path.read_text(encoding="utf-8"))

    def run_script(self, *args, token=None):
        """Return the exit code, stdout, and stderr of the script."""
        done = run_isolated(SCRIPT, args, self.project, token)
        return done.returncode, done.stdout, done.stderr

    def output(self, *args, **kwargs):
        """Return the output of a run that exits with 0."""
        code, out, err = self.run_script(*args, **kwargs)
        self.assertEqual(code, 0, err)
        return out

    def error_of(self, *args):
        """Return the error object of a run that exits with 1."""
        code, _, err = self.run_script(*args)
        self.assertEqual(code, 1, err)
        return json.loads(err)

    def test_a_missing_config_is_created_with_samples(self):
        """The project's own values are empty, the patterns hold samples that compile, and the output says so."""
        out = self.output()
        self.assertTrue(out.startswith("Created `"), out)
        self.assertEqual((self.config()["GITLAB_URL"], self.config()["ORCHESTRATOR_URL"]), ("", ""))
        patterns = [self.config()["RUN_ID_PATTERN"], *self.config()["BUSINESS_ID_PATTERNS"].values()]
        for pattern in patterns:
            self.assertIn("value", re.compile(pattern).groupindex, pattern)
        self.assertRegex("customerId: 42", patterns[1])
        self.assertEqual(self.config()["variables"]["EXECUTION_TYPE"], "test")
        self.assertIn("| `GITLAB_URL` | not set |", out)
        self.assertNotIn("Created", self.output())

    def test_the_config_is_shown_without_secrets(self):
        """Secret-looking values and a password of a URL are masked; the token is only reported as found."""
        variables = {"API_TOKEN": "abc123", "ATP_TESTS_GIT_REPO_URL": "https://bob:hunter2@g.example.com/g/t.git"}
        self.save({"GITLAB_TOKEN_ENV": "MY_VARIABLE", "variables": variables})
        out = self.output(token=TOKEN)
        self.assertIn("| `API_TOKEN` | hidden |", out)
        self.assertIn("https://bob:***@g.example.com/g/t.git", out)
        self.assertIn("| `GITLAB_TOKEN_ENV` | `MY_VARIABLE` |", out)
        for secret in ("abc123", "hunter2", TOKEN):
            self.assertNotIn(secret, out)
        (self.path.parent / "gitlab-token").write_text(TOKEN + "\n", encoding="utf-8")
        out = self.output()
        self.assertIn("Token: found in the file", out)
        self.assertNotIn(TOKEN, out)

    def test_settings_and_variables_are_changed(self):
        """A setting goes to the top level and a variable into variables; types are kept or normalized."""
        self.save({"GITLAB_REF": "main", "variables": {"OWN": "1", "ENABLE_JIRA_INTEGRATION": False}})
        out = self.output(
            "--set",
            "GITLAB_REF=develop",
            "--set",
            "OWN=a=b",
            "--set",
            "ENABLE_JIRA_INTEGRATION=TRUE",
            "--set",
            "DISCOVERY_TIMEOUT=60",
            "--set",
            "EXECUTION_NAME=Gen domestic",
        )
        self.assertIn("- `GITLAB_REF`: `main` → `develop`.", out)
        self.assertEqual((self.config()["GITLAB_REF"], self.config()["DISCOVERY_TIMEOUT"]), ("develop", 60))
        expected = {"OWN": "a=b", "ENABLE_JIRA_INTEGRATION": True, "EXECUTION_NAME": "Gen domestic"}
        self.assertEqual(self.config()["variables"], expected)

    def test_an_empty_value_removes_an_optional_setting(self):
        """An optional key is removed, so it does not read as a wrong value."""
        self.save({"GITLAB_REF": "main", "DISCOVERY_TIMEOUT": 60})
        self.output("--set", "DISCOVERY_TIMEOUT=")
        self.assertEqual(self.config(), {"GITLAB_REF": "main"})

    def test_the_same_value_leaves_the_file_alone(self):
        """A change to the current value does not write the file."""
        self.path.parent.mkdir()
        text = '{"GITLAB_REF":"main"}'
        self.path.write_text(text, encoding="utf-8")
        self.assertIn("is already `main`", self.output("--set", "GITLAB_REF=main"))
        self.assertEqual(self.path.read_text(encoding="utf-8"), text)

    def test_a_wrong_change_changes_nothing(self):
        """One wrong key or value among the changes leaves the file as it is."""
        self.save({"GITLAB_REF": "main"})
        before = self.path.read_bytes()
        cases = {
            "unknown_key": ("GITLAB_REFF=x", "BUSINESS_ID_PATTERNS=x", "RUN_ID_PATTERN=x", "API_TOKEN=x"),
            "invalid_value": ("GITLAB_URL=g.example.com", "DISCOVERY_TIMEOUT=0", "SEND_WEBEX_NOTIFICATION=yes"),
            "bad_argument": ("GITLAB_REF",),
        }
        for code, arguments in cases.items():
            for argument in arguments:
                error = self.error_of("--set", "GITLAB_REF=develop", "--set", argument)
                self.assertEqual(error["error"], code, argument)
                self.assertEqual(self.path.read_bytes(), before, argument)

    def test_a_broken_config_is_reported(self):
        """A file that is not a JSON object is not rewritten."""
        self.path.parent.mkdir()
        self.path.write_text("[", encoding="utf-8")
        self.assertEqual(self.error_of("--set", "GITLAB_REF=x")["error"], "config_unreadable")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "[")


if __name__ == "__main__":
    unittest.main(verbosity=2)
