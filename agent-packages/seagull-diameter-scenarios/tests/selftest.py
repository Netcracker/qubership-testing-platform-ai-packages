"""Self-test of the scripts of the seagull-diameter-scenarios package.

Run: python tests/selftest.py

It generates scenarios from the invented dictionaries and steps in tests/fixtures
and checks the result: the repairs, the grouping of steps into sessions, the
choice between several definitions of an AVP, the value conversions, the checks of
the answer, and the failure on an AVP that no dictionary has. The dry run in the
Seagull image runs only when the environment variable SEAGULL_IMAGE names an image
and `sh` and `docker` work.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import calendar
import importlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
SKILLS = Path(__file__).resolve().parents[1] / ".apm" / "skills"
GENERATE_DIR = SKILLS / "seagull-diameter-scenario-generate" / "scripts"
sys.path.insert(0, str(SKILLS / "seagull-diameter-common" / "scripts"))
sys.path.insert(0, str(GENERATE_DIR))
check_steps = importlib.import_module("check_steps")
generate = importlib.import_module("generate_scenarios")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
IMAGE = os.environ.get("SEAGULL_IMAGE", "")
CHECKED = (
    "Result-Code",
    "Session-Id",
    "Auth-Application-Id",
    "CC-Request-Type",
    "CC-Request-Number",
)


def run_generator(out: Path, steps: Path = FIXTURES / "steps") -> tuple[int, str, str]:
    """Run the generator; return the exit status, its output, and its error output."""
    argv = ["--steps", str(steps), "--dictionaries-dir", str(FIXTURES / "dictionaries")]
    argv += ["--dictionaries", "Gy", "--out", str(out)]
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = generate.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class GeneratorTest(unittest.TestCase):
    """Generate once, then look at the files."""

    folder: Path
    status: int
    report: str
    error: str
    scenarios: list[Path]

    @classmethod
    def setUpClass(cls) -> None:
        """Generate the scenarios into a temporary folder."""
        cls.folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        cls.status, cls.report, cls.error = run_generator(cls.folder)
        cls.scenarios = sorted((cls.folder / "scenario").glob("*.client.xml"))

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the temporary folder."""
        shutil.rmtree(cls.folder, ignore_errors=True)

    def text(self, index: int) -> str:
        """Return the text of the client scenario at this position."""
        return self.scenarios[index].read_text(encoding="iso-8859-1")

    def test_files(self) -> None:
        """The generator writes the scenarios, the stubs, the configuration."""
        self.assertEqual(self.status, 0, self.error)
        names = sorted(p.name for p in (self.folder / "scenario").iterdir())
        expected = [
            "01-test-steps-001-002.client.xml",
            "01-test-steps-001-002.stub-server.xml",
            "02-test-steps-003.client.xml",
            "02-test-steps-003.stub-server.xml",
        ]
        self.assertEqual(names, expected)
        for path in (self.folder / "config").iterdir():
            self.assertNotIn(b"\r", path.read_bytes(), f"{path.name} has a CR")
        self.assertTrue((self.folder / "dictionary/diameter-dictionary.xml").exists())

    def test_all_scenarios_are_xml(self) -> None:
        """Every scenario parses as XML."""
        for path in (self.folder / "scenario").iterdir():
            text = path.read_text(encoding="iso-8859-1")
            ElementTree.fromstring(text.split("?>", 1)[1])

    def test_sessions_are_split_at_session_id(self) -> None:
        """Steps 1 and 2 share a Session-Id and make one scenario; step 3 another."""
        first, second = self.text(0), self.text(1)
        self.assertEqual(first.count("<send channel"), 3)  # CER and two requests
        self.assertIn('format="TEST-A-1"', first)
        self.assertNotIn("TEST-B-1", first)
        self.assertIn('format="TEST-B-1"', second)

    def test_repairs_are_reported(self) -> None:
        """A comment and a closing tag without '>' are repaired and reported."""
        report = self.report
        self.assertIn("Step-001-request.txt: 1 commented-out AVP(s) left out", report)
        self.assertIn("Step-003-request.txt: 1 closing tag(s) without '>'", report)
        self.assertNotIn("left out", self.text(0).replace("left out", "", 0))
        self.assertNotIn('<avp name="User-Name" value="left out">', self.text(0))
        self.assertIn('<avp name="User-Name" value="broken-tag">', self.text(1))

    def test_value_conversions(self) -> None:
        """A time becomes NTP hex, an IP address Address hex, an enumeration a number."""
        ntp = calendar.timegm((2026, 10, 27, 14, 0, 52)) + 2208988800
        text = self.text(0)
        self.assertIn(f'<avp name="Event-Timestamp" value="0x{ntp:08X}">', text)
        self.assertIn('<avp name="SGSN-Address" value="0x00010a010203">', text)
        self.assertIn('<avp name="3GPP-Charging-Id" value="0x000000a1">', text)
        self.assertIn('<avp name="CC-Request-Type" value="1"></avp>', text)

    def test_choice_between_definitions(self) -> None:
        """Node-Id has two definitions: the enclosing group's vendor decides."""
        text = self.text(0)
        self.assertIn('<avp name="Node-Id" value="first-node">', text)
        self.assertIn('<avp name="Node-Id-v99999c5" value="example-node">', text)
        self.assertIn("Node-Id: definitions (vendor, code)", self.report)

    def test_answer_is_checked(self) -> None:
        """Each answer is checked against the recorded and the sent values."""
        text = self.text(0)
        self.assertIn('<avp name="Result-Code" value="2001"></avp>', text)
        for name in CHECKED:
            self.assertIn(f'<check-value name="{name}" behaviour="error">', text)
        termination = '<avp name="CC-Request-Type" value="3"></avp>'
        self.assertIn(termination, text)  # TERMINATION_REQUEST of step 2

    def test_stub_answers_with_recorded_avps(self) -> None:
        """The stub OCS sends the recorded answer with the request's Session-Id."""
        stub = self.folder / "scenario" / "01-test-steps-001-002.stub-server.xml"
        text = stub.read_text(encoding="iso-8859-1")
        self.assertIn('<avp name="Origin-Host" value="ocs.example.test"></avp>', text)
        self.assertIn('<restore name="sid" entity="Session-Id">', text)

    def test_timeout_is_in_the_configuration(self) -> None:
        """The response timeout is call-timeout-ms of the client configuration."""
        config = (self.folder / "config" / "conf.client.xml").read_text("iso-8859-1")
        self.assertIn('name="call-timeout-ms" value="5000"', config)


class FailureTest(unittest.TestCase):
    """The generator stops, with a message, when the input is wrong."""

    def test_avp_without_a_definition(self) -> None:
        """An AVP that no merged dictionary defines is an error that names it."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            steps = Path(folder) / "steps"
            shutil.copytree(FIXTURES / "steps", steps)
            request = steps / "Step-002-request.txt"
            text = request.read_text(encoding="utf-8")
            extra = "<No-Such-Avp>1</No-Such-Avp></CCR>"
            request.write_text(text.replace("</CCR>", extra), encoding="utf-8")
            status, _, error = run_generator(Path(folder) / "out", steps)
        self.assertEqual(status, 1)
        self.assertIn("AVP No-Such-Avp is in none of the project dictionaries", error)

    def test_check_steps_reports_an_unpaired_file(self) -> None:
        """check_steps names a request that has no response."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            steps = Path(folder) / "steps"
            shutil.copytree(FIXTURES / "steps", steps)
            (steps / "Step-003-response.txt").unlink()
            problems, _ = check_steps.check(steps)
        self.assertEqual(problems, ["step 003: the response file is missing"])

    def test_check_steps_accepts_the_fixture(self) -> None:
        """The fixture steps have no problem."""
        problems, notes = check_steps.check(FIXTURES / "steps")
        self.assertEqual(problems, [])
        self.assertIn("3 complete step(s)", notes[0])


@unittest.skipUnless(IMAGE, "set SEAGULL_IMAGE for the dry run")
class DryRunTest(unittest.TestCase):
    """The generated scenarios complete against the stub OCS in the Seagull image."""

    def test_dry_run(self) -> None:
        """dry-run.sh exits with 0 and reports 1 successful call per scenario."""
        script = GENERATE_DIR / "dry-run.sh"
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            status, _, error = run_generator(Path(folder))
            self.assertEqual(status, 0, error)
            command = ["sh", str(script), folder, IMAGE]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = "successful calls: 1, failed calls: 0"
        self.assertEqual(result.stdout.count(line), 2, result.stdout)


if __name__ == "__main__":
    unittest.main()
