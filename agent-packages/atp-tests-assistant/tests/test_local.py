"""Tests of the skills that work with the local copy of the test repository.

selftest.py imports this module, so one run checks the whole package. Python 3.9+.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from test_run import run_isolated

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SKILL = Path(__file__).resolve().parents[1] / ".apm" / "skills" / "atp-local-folder-set"
SCRIPT = SKILL / "scripts" / "set_local_folder.py"
TESTS = "TestGeneration/tests/TestScenario"
CONFIGURATIONS = "TestGeneration/environment-configuration"


class LocalFolderCase(unittest.TestCase):
    """set_local_folder.py: the check of the folder and the setting."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.path = self.project / ".atp-assistant" / "config.json"
        self.root = self.project / "my tests"
        self.save({"GITLAB_REF": "main"})

    def save(self, config):
        """Write the config of the project."""
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    def config(self):
        """Return the config of the project."""
        return json.loads(self.path.read_text(encoding="utf-8"))

    def add(self, *names, root=None):
        """Create files in the folder of the local tests."""
        for name in names:
            file = (root or self.root) / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("hunter2", encoding="utf-8")

    def output(self, *args):
        """Return the output of a run that exits with 0."""
        done = run_isolated(SCRIPT, args, self.project, None)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def error_of(self, *args):
        """Return the error object of a run that exits with 1."""
        done = run_isolated(SCRIPT, args, self.project, None)
        self.assertEqual(done.returncode, 1, done.stderr)
        return json.loads(done.stderr)

    def test_a_folder_with_tests_and_configurations_is_set(self):
        """A relative path is stored as an absolute one, and the check without --path reads it."""
        self.add(f"{TESTS}/a.spec.ts", f"{TESTS}/Billing/b.spec.ts", f"{TESTS}/node_modules/x/c.ts")
        self.add(f"{CONFIGURATIONS}/dev.json", f"{CONFIGURATIONS}/CI-Ivory.json", f"{CONFIGURATIONS}/readme.md")
        out = self.output("--path", "my tests")
        stored = self.config()["LOCAL_ROOT_FOLDER"]
        self.assertEqual(Path(stored).resolve(), self.root.resolve())
        self.assertTrue(Path(stored).is_absolute(), stored)
        self.assertIn("It was not set.", out)
        self.assertIn(f"- Tests: 2 `*.ts` files in `{TESTS}`.", out)
        self.assertIn(f"`{CONFIGURATIONS}`: `CI-Ivory.json`, `dev.json`.", out)
        self.assertNotIn("hunter2", out)
        self.assertIn("is already", self.output("--path", stored))
        self.assertIn(f"LOCAL_ROOT_FOLDER is `{stored}`.", self.output())

    def test_a_folder_that_does_not_pass_changes_nothing(self):
        """Every problem is reported, and the config keeps its text."""
        before = self.path.read_bytes()
        error = self.error_of("--path", "nowhere")
        self.assertEqual((error["error"], len(error["problems"])), ("local_root_invalid", 1))
        self.assertIn("does not exist", error["problems"][0])
        self.add(f"{TESTS}/readme.md")
        error = self.error_of("--path", str(self.root))
        self.assertEqual(error["problems"], [f"No *.ts files in {TESTS}.", f"No folder {CONFIGURATIONS}."])
        self.assertIn("The config was not changed.", error["message"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_the_folders_of_the_config_are_checked(self):
        """TESTS_FOLDER and ENV_CONFIGURATION_FOLDER say where the files are."""
        self.save({"TESTS_FOLDER": "e2e", "ENV_CONFIGURATION_FOLDER": "env"})
        self.add("e2e/a.spec.ts", "env/dev.json")
        self.assertIn("1 `*.ts` file in `e2e`.", self.output("--path", str(self.root)))

    def test_a_stored_folder_is_checked_again(self):
        """No folder, a folder that lost its files, and a path relative to the project."""
        self.assertEqual(self.error_of()["error"], "local_root_missing")
        self.save({"LOCAL_ROOT_FOLDER": "my tests"})
        self.assertEqual(self.error_of()["error"], "local_root_invalid")
        self.add(f"{TESTS}/a.spec.ts", f"{CONFIGURATIONS}/dev.json")
        self.assertIn("- Tests: 1", self.output())

    def test_without_a_config_nothing_is_created(self):
        """The script needs the config file and says how to create it."""
        self.path.unlink()
        error = self.error_of("--path", str(self.root))
        self.assertEqual(error["error"], "config_missing")
        self.assertIn("/atp-config", error["message"])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
