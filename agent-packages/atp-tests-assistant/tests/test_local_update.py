"""Tests of update_local_tests.py with real git and a repository served on localhost.

selftest.py imports this module, so one run checks the whole package. Python 3.9+.
"""

import base64
import functools
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from test_run import run_isolated

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SKILL = Path(__file__).resolve().parents[1] / ".apm" / "skills" / "atp-local-tests-update"
SCRIPT = SKILL / "scripts" / "update_local_tests.py"
TOKEN = "secret-clone-token"
TEST_FILE = "TestGeneration/tests/TestScenario/a.spec.ts"
CONFIGURATION = "TestGeneration/environment-configuration/dev.json"


class Files(SimpleHTTPRequestHandler):
    """Serve a bare repository as files, git's dumb HTTP protocol, and record the headers."""

    headers_seen: ClassVar[list] = []

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass

    def do_GET(self):  # pylint: disable=invalid-name
        """Record the Authorization header and send the file."""
        Files.headers_seen.append(self.headers.get("Authorization"))
        super().do_GET()


def git(folder, *args):
    """Run git in folder with an author, and return its output."""
    author = ["-c", "user.name=Tester", "-c", "user.email=tester@example.com", "-c", "core.autocrlf=false"]
    command = ["git", *author, "-C", str(folder), *args]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()


def remove(folder):
    """Delete a folder with a repository, whose object files are read-only."""
    for path in Path(folder).rglob("*"):
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    shutil.rmtree(folder, ignore_errors=True)


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class LocalUpdateCase(unittest.TestCase):
    """The clone and the fast-forward of the folder of the local tests."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(remove, self.base)
        self.project = self.base / "project"
        self.root = self.base / "local tests"
        self.source = self.base / "source"
        self.bare = self.base / "served" / "group" / "tests.git"
        self.source.mkdir()
        git(self.source, "init", "--quiet", "-b", "main")
        self.publish(TEST_FILE, "first", CONFIGURATION)
        handler = functools.partial(Files, directory=str(self.base / "served"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.repo = f"http://127.0.0.1:{server.server_port}/group/tests.git"
        self.path = self.project / ".atp-assistant" / "config.json"
        self.path.parent.mkdir(parents=True)
        variables = {"ATP_TESTS_GIT_REPO_URL": self.repo, "ATP_TESTS_GIT_REPO_BRANCH": "main"}
        self.path.write_text(json.dumps({"variables": variables}), encoding="utf-8")
        Files.headers_seen = []

    def publish(self, name, text, *more):
        """Commit a file to the source repository and serve the new state."""
        for each in (name, *more):
            file = self.source / each
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
        git(self.source, "add", "-A")
        git(self.source, "commit", "--quiet", "-m", text)
        if self.bare.exists():
            git(self.source, "push", "--quiet", str(self.bare), "main")
        else:
            self.bare.parent.mkdir(parents=True)
            git(self.base, "clone", "--quiet", "--bare", str(self.source), str(self.bare))
        git(self.bare, "update-server-info")

    def config(self):
        """Return the config of the project."""
        return json.loads(self.path.read_text(encoding="utf-8"))

    def output(self, *args, token=None):
        """Return the output of a run that exits with 0."""
        done = run_isolated(SCRIPT, args, self.project, token)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def error_of(self, *args):
        """Return the error object of a run that exits with 1."""
        done = run_isolated(SCRIPT, args, self.project, None)
        self.assertEqual(done.returncode, 1, done.stderr)
        return json.loads(done.stderr)

    def cloned(self):
        """Clone into the folder of the local tests."""
        self.output("--path", str(self.root))

    def read(self, name=TEST_FILE):
        """Return the text of a file of the clone."""
        return (self.root / name).read_text(encoding="utf-8")

    def test_a_new_folder_gets_a_clone_and_the_token_stays_out_of_it(self):
        """The setting is written, and the token is a header that is in no file and no output."""
        out = self.output("--path", str(self.root), token=TOKEN)
        self.assertIn("Cloned ", out)
        self.assertIn("- Tests: 1 `*.ts` file", out)
        self.assertEqual(Path(self.config()["LOCAL_ROOT_FOLDER"]).resolve(), self.root.resolve())
        secret = base64.b64encode(f"oauth2:{TOKEN}".encode()).decode("ascii")
        self.assertEqual(set(Files.headers_seen), {f"Basic {secret}"})
        kept = (self.root / ".git" / "config").read_text(encoding="utf-8") + out
        self.assertNotIn(TOKEN, kept)
        self.assertNotIn(secret, kept)

    def test_an_update_is_a_fast_forward(self):
        """Without --path the folder of the config is updated; untracked files stay."""
        self.cloned()
        self.assertIn("has every commit of the repository", self.output())
        (self.root / "notes.txt").write_text("mine", encoding="utf-8")
        self.publish(TEST_FILE, "second")
        self.assertIn("1 new commit,", self.output())
        self.assertEqual((self.read(), self.read("notes.txt")), ("second", "mine"))

    def test_local_work_is_never_overwritten(self):
        """A changed file or a local commit stops the update, and the file keeps its text."""
        self.cloned()
        self.publish(TEST_FILE, "second")
        (self.root / TEST_FILE).write_text("mine", encoding="utf-8")
        error = self.error_of()
        self.assertEqual((error["error"], error["files"]), ("local_changes", [TEST_FILE]))
        self.assertEqual(self.read(), "mine")
        git(self.root, "commit", "--quiet", "-am", "mine")
        self.assertEqual(self.error_of()["error"], "local_diverged")
        self.assertEqual(self.read(), "mine")

    def test_another_branch_is_left_alone_unless_it_is_named(self):
        """The branch of the config does not replace a checked out one; --branch does."""
        self.cloned()
        git(self.root, "switch", "--quiet", "-c", "feature")
        self.assertEqual(self.error_of()["error"], "branch_differs")
        self.assertEqual(git(self.root, "branch", "--show-current"), "feature")
        self.assertEqual(self.error_of("--branch", "nowhere")["error"], "branch_missing")
        self.assertIn("Checked out branch main instead of feature.", self.output("--branch", "main"))

    def test_a_folder_that_is_not_this_clone_is_left_alone(self):
        """A folder with other files, a clone of another repository, and a repository without tests."""
        self.root.mkdir()
        (self.root / "mine.txt").write_text("mine", encoding="utf-8")
        self.assertEqual(self.error_of("--path", str(self.root))["error"], "local_root_not_a_clone")
        git(self.root, "init", "--quiet")
        git(self.root, "remote", "add", "origin", "https://other.example.com/g/t.git")
        self.assertEqual(self.error_of("--path", str(self.root))["error"], "local_root_other_repo")
        self.publish("readme.md", "no configurations")
        git(self.source, "rm", "--quiet", CONFIGURATION)
        self.publish("readme.md", "removed")
        error = self.error_of("--path", str(self.base / "second"))
        self.assertEqual(error["error"], "local_root_invalid")
        self.assertNotIn("LOCAL_ROOT_FOLDER", self.config())


if __name__ == "__main__":
    unittest.main(verbosity=2)
