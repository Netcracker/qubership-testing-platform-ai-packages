"""Self-test of the scripts of the seagull-diameter-scenarios package.

Run: python tests/selftest.py

It generates scenarios from the invented dictionaries and steps in tests/fixtures
and checks the result: the repairs, the grouping of steps into sessions, the
choice between several definitions of an AVP, the value conversions, the checks of
the answer, the dynamic tags, placeholders, templates, the conversion of a ready
scenario into a template, and the failure on an AVP that no dictionary has. The dry run in the
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
TEMPLATIZE_DIR = SKILLS / "seagull-diameter-scenario-templatize" / "scripts"
sys.path.insert(0, str(SKILLS / "seagull-diameter-common" / "scripts"))
sys.path.insert(0, str(GENERATE_DIR))
sys.path.insert(0, str(TEMPLATIZE_DIR))
check_steps = importlib.import_module("check_steps")
generate = importlib.import_module("generate_scenarios")
options_module = importlib.import_module("scenario_options")
apply_placeholders = importlib.import_module("apply_placeholders")
to_template = importlib.import_module("scenario_to_template")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
IMAGE = os.environ.get("SEAGULL_IMAGE", "")
CHECKED = (
    "Result-Code",
    "Session-Id",
    "Auth-Application-Id",
    "CC-Request-Type",
    "CC-Request-Number",
)


def run_generator(
    out: Path,
    steps: Path = FIXTURES / "steps",
    extra: tuple = (),
) -> tuple[int, str, str]:
    """Run the generator; return the exit status, its output, and its error output."""
    argv = ["--steps", str(steps), "--dictionaries-dir", str(FIXTURES / "dictionaries")]
    argv += ["--dictionaries", "Gy", "--out", str(out), *extra]
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
        # The DWA of the default section, the CER, and two requests.
        self.assertEqual(first.count("<send channel"), 4)
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


TEMPLATE_ARGS = (
    "--option",
    "mode=template",
    "--placeholder",
    "Subscription-Id/Subscription-Id-Data=SUBSCRIBER_ID",
    "--placeholder",
    "3GPP-Charging-Id=CHARGING_ID_HEX",
    "--placeholder",
    "Auth-Application-Id=APP_ID",
)
CLIENT = "01-test-steps-001-002.client.xml"


def scenario_body(text: str) -> str:
    """Return a scenario without its header comment, which names the mode."""
    return text.partition("<scenario>")[2]


class TagsTest(unittest.TestCase):
    """The dynamic tags that the options file switches on and off."""

    def generate(self, *options: str) -> str:
        """Generate with options given as KEY=VALUE; return the first client scenario."""
        extra: tuple = ()
        for option in options:
            extra += ("--option", option)
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            status, _, error = run_generator(Path(folder), extra=extra)
            self.assertEqual(status, 0, error)
            return (Path(folder) / "scenario" / CLIENT).read_text("iso-8859-1")

    def test_default_section_answers_dwr(self) -> None:
        """The default section is on by default and answers DWR with DWA."""
        text = self.generate()
        self.assertIn('<default behaviour="ignore">', text)
        self.assertIn('<command name="DWR"></command>', text)
        self.assertIn('<restore name="DWR_HBH" entity="HbH-id"></restore>', text)
        self.assertIn('<command name="DWA">', text)

    def test_default_section_can_be_off(self) -> None:
        """default-dwr=false leaves the section out."""
        self.assertNotIn("<default", self.generate("default-dwr=false"))

    def test_other_tags_are_off_by_default(self) -> None:
        """A run without options writes no log, presence check, pause, or counter."""
        text = self.generate()
        for tag in ("<log ", "check-presence", "wait-ms", "session-counter"):
            self.assertNotIn(tag, text)
        self.assertNotIn('<set-value name="Event-Timestamp"', text)

    def test_generated_session_id(self) -> None:
        """The Session-Id comes from a counter in the first step and is restored after."""
        text = self.generate("generated-session-id=true")
        self.assertIn('<counterdef name="session-counter" init="0"></counterdef>', text)
        self.assertEqual(text.count('<inc-counter name="session-counter">'), 1)
        sid = 'format="client.example.test;$(session-counter)"'
        self.assertIn(sid, text)
        self.assertIn('<store name="VAR_SESSION_ID" entity="Session-Id">', text)
        self.assertEqual(text.count('<restore name="VAR_SESSION_ID"'), 1)
        self.assertNotIn('<check-value name="Session-Id"', text)
        self.assertNotIn('format="TEST-A-1"', text)

    def test_time_method_is_used_for_the_timestamp(self) -> None:
        """With a time method, the Event-Timestamp and the Session-Id use it."""
        text = self.generate(
            "generated-timestamp=true",
            "generated-session-id=true",
            "time-method=sys_date_time_secs",
        )
        method = 'method="sys_date_time_secs" format="startoffset=2208988800"'
        self.assertEqual(text.count(method), 2)  # one for each request
        self.assertIn('<store name="VAR_TS" entity="Event-Timestamp">', text)
        self.assertIn("client.example.test;$(VAR_TS);$(session-counter)", text)

    def test_timestamp_needs_a_time_method(self) -> None:
        """generated-timestamp without time-method is an error that says so."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            extra = ("--option", "generated-timestamp=true")
            status, _, error = run_generator(Path(folder), extra=extra)
        self.assertEqual(status, 1)
        self.assertIn("generated-timestamp needs time-method", error)

    def test_log_presence_and_pause(self) -> None:
        """log, check-presence, and wait-ms add their tags once in the right places."""
        text = self.generate("log=true", "check-presence=true", "wait-ms=250")
        self.assertIn('<log format="CCR-I step 001"></log>', text)
        self.assertIn('<log format="CCA step 002 checked"></log>', text)
        self.assertEqual(text.count('<wait-ms value="250"></wait-ms>'), 1)
        presence = '<check-presence name="Result-Code" behaviour="error">'
        value = '<check-value name="Result-Code" behaviour="error"></check-value>'
        self.assertIn(f"{presence}</check-presence>\n      {value}", text)

    def test_empty_tags_have_no_inner_space(self) -> None:
        """An empty element is written <x></x>, with nothing between the tags."""
        text = self.generate()
        self.assertNotIn("> </", text)

    def test_bad_option_is_an_error(self) -> None:
        """An unknown option key stops the generator and names the known ones."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            status, _, error = run_generator(Path(folder), extra=("--option", "x=1"))
        self.assertEqual(status, 1)
        self.assertIn("unknown option 'x'", error)


AVP_PATH = [("Multiple-Services-Credit-Control", "MSCC", 1), ("Rating-Group", "RG", 2)]


class LookupTest(unittest.TestCase):
    """The match of an AVP path against the placeholder keys."""

    def test_name_matches_at_any_depth(self) -> None:
        """A bare name matches the AVP inside a group, by Seagull or recorded name."""
        self.assertEqual(options_module.lookup({"Rating-Group": "A"}, AVP_PATH)[1], "A")
        self.assertEqual(options_module.lookup({"RG": "A"}, AVP_PATH)[1], "A")

    def test_path_and_index_narrow_the_match(self) -> None:
        """A path must match the end of the AVP path, and an index the position."""
        group = "Multiple-Services-Credit-Control/Rating-Group"
        self.assertIsNotNone(options_module.lookup({group: "A"}, AVP_PATH))
        self.assertIsNone(options_module.lookup({"Other/Rating-Group": "A"}, AVP_PATH))
        self.assertIsNotNone(options_module.lookup({"Rating-Group[2]": "A"}, AVP_PATH))
        self.assertIsNone(options_module.lookup({"Rating-Group[1]": "A"}, AVP_PATH))

    def test_the_most_specific_key_wins(self) -> None:
        """A key with more segments beats a bare name."""
        rules = {
            "Rating-Group": "SHORT",
            "Multiple-Services-Credit-Control/Rating-Group": "LONG",
        }
        self.assertEqual(options_module.lookup(rules, AVP_PATH)[1], "LONG")


class TemplateTest(unittest.TestCase):
    """Templates, their values, and the conversion of a ready scenario."""

    folder: Path
    ready: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Generate a ready run and a template run into temporary folders."""
        root = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        cls.ready = root / "ready"
        cls.folder = root / "template"
        run_generator(cls.ready)
        status, _, error = run_generator(cls.folder, extra=TEMPLATE_ARGS)
        assert status == 0, error

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the temporary folders."""
        shutil.rmtree(cls.folder.parent, ignore_errors=True)

    def scenario(self, name: str) -> Path:
        """Return the path of a file of the template run."""
        return self.folder / "scenario" / name

    def test_template_holds_placeholders(self) -> None:
        """The template has @@NAME@@ for the chosen AVPs and keeps the 0x prefix."""
        text = self.scenario(CLIENT + ".tpl").read_text("iso-8859-1")
        self.assertIn('value="@@SUBSCRIBER_ID@@"', text)
        self.assertIn('value="0x@@CHARGING_ID_HEX@@"', text)
        self.assertIn('<avp name="Auth-Application-Id" value="@@APP_ID@@">', text)
        self.assertNotIn("491700000001", text)

    def test_values_file_lists_the_recorded_values(self) -> None:
        """The values file maps each placeholder to the recorded value, without 0x."""
        values = options_module.read_values(self.scenario(CLIENT + ".values"))
        expected = {"SUBSCRIBER_ID": "491700000001", "CHARGING_ID_HEX": "000000a1"}
        self.assertEqual(values, {**expected, "APP_ID": "4"})

    def test_render_reproduces_the_ready_scenario(self) -> None:
        """The rendered client scenario equals the one written without placeholders."""
        rendered = self.scenario(CLIENT).read_text("iso-8859-1")
        ready = (self.ready / "scenario" / CLIENT).read_text("iso-8859-1")
        self.assertEqual(scenario_body(rendered), scenario_body(ready))

    def test_next_run_reads_the_options_file(self) -> None:
        """A run without placeholder arguments uses the pairs that the file holds."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder)
            shutil.copy(self.folder / "scenario-options.ini", out)
            status, _, error = run_generator(out)
            text = (out / "scenario" / (CLIENT + ".tpl")).read_text("iso-8859-1")
        self.assertEqual(status, 0, error)
        self.assertIn("@@SUBSCRIBER_ID@@", text)

    def test_empty_placeholder_removes_the_pair(self) -> None:
        """--placeholder AVP= drops the pair from the file and from the template."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder)
            shutil.copy(self.folder / "scenario-options.ini", out)
            extra = ("--placeholder", "Auth-Application-Id=")
            status, _, error = run_generator(out, extra=extra)
            text = (out / "scenario" / (CLIENT + ".tpl")).read_text("iso-8859-1")
            options = (out / "scenario-options.ini").read_text("utf-8")
        self.assertEqual(status, 0, error)
        self.assertNotIn("APP_ID", text + options)

    def test_unused_pair_is_reported(self) -> None:
        """A pair that matches no AVP is named in the report."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            extra = (*TEMPLATE_ARGS, "--placeholder", "No-Such=NOPE")
            status, report, _ = run_generator(Path(folder), extra=extra)
        self.assertEqual(status, 0)
        self.assertIn("placeholder No-Such: matched no AVP", report)

    def test_native_mode_keeps_values_in_the_scenario(self) -> None:
        """Native substitution sets a variable once, restores it, and refuses groups."""
        args = ("--option", "mode=template", "--option", "substitution=native")
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            extra = (*args, "--placeholder", "Origin-Realm=REALM")
            status, _, error = run_generator(Path(folder), extra=extra)
            text = (Path(folder) / "scenario" / CLIENT).read_text("iso-8859-1")
            self.assertEqual(status, 0, error)
            self.assertEqual(
                text.count('<store name="REALM" entity="Origin-Realm">'), 1
            )
            self.assertEqual(
                text.count('<restore name="REALM" entity="Origin-Realm">'), 1
            )
            self.assertFalse((Path(folder) / "scenario" / (CLIENT + ".tpl")).exists())
            nested = ("--placeholder", "Subscription-Id-Data=X")
            status, _, error = run_generator(Path(folder) / "n", extra=(*args, *nested))
        self.assertEqual(status, 1)
        self.assertIn("native substitution cannot address", error)

    def test_conversion_matches_the_generator(self) -> None:
        """Converting the ready scenario gives the template the generator writes."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            ready = Path(folder) / CLIENT
            shutil.copy(self.ready / "scenario" / CLIENT, ready)
            shutil.copy(self.folder / "scenario-options.ini", Path(folder))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(to_template.main([str(ready)]), 0)
            made = Path(folder) / (CLIENT + ".tpl")
            made_values = Path(folder) / (CLIENT + ".values")
            text = made.read_text("iso-8859-1")
            values = options_module.read_values(made_values)
            expected = self.scenario(CLIENT + ".tpl").read_text("iso-8859-1")
            expected_values = options_module.read_values(
                self.scenario(CLIENT + ".values")
            )
            out = Path(folder) / "again.xml"
            argv = [str(made), "--out", str(out), "--values", str(made_values)]
            with redirect_stdout(io.StringIO()):
                status = apply_placeholders.main(argv)
            again = out.read_text("iso-8859-1")
            original = ready.read_text("iso-8859-1")
        self.assertEqual(scenario_body(text), scenario_body(expected))
        self.assertEqual(values, expected_values)
        self.assertEqual(status, 0)
        self.assertEqual(again, original)


class ApplyPlaceholdersTest(unittest.TestCase):
    """apply_placeholders.py: sources of values and the failure on a missing one."""

    def render(self, *args: str) -> tuple[int, str, str]:
        """Render a one-line template with the arguments; return status, text, error."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            template = Path(folder) / "t.xml"
            template.write_text('<avp value="@@A@@"></avp>\n', encoding="iso-8859-1")
            out = Path(folder) / "o.xml"
            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                argv = [str(template), "--out", str(out), *args]
                status = apply_placeholders.main(argv)
            text = out.read_text("iso-8859-1") if out.exists() else ""
        return status, text, stderr.getvalue()

    def test_set_value(self) -> None:
        """--set gives a value, which is escaped for XML."""
        status, text, _ = self.render("--set", 'A=a"b&c')
        self.assertEqual(status, 0)
        self.assertEqual(text, '<avp value="a&quot;b&amp;c"></avp>\n')

    def test_environment_only_with_env(self) -> None:
        """The environment is read only with --env, and --set wins over it."""
        os.environ["A"] = "from-env"
        try:
            self.assertEqual(self.render()[0], 1)
            self.assertIn("from-env", self.render("--env")[1])
            self.assertIn("from-set", self.render("--env", "--set", "A=from-set")[1])
        finally:
            del os.environ["A"]

    def test_missing_value_names_the_placeholder(self) -> None:
        """A placeholder without a value stops the script and is named."""
        status, text, error = self.render()
        self.assertEqual(status, 1)
        self.assertEqual(text, "")
        self.assertIn("no value for placeholder(s) A", error)


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

    def dry_run(self, extra: tuple = ()) -> None:
        """Generate with the options, run dry-run.sh, and expect 1 call per scenario."""
        script = GENERATE_DIR / "dry-run.sh"
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            status, _, error = run_generator(Path(folder), extra=extra)
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

    def test_dry_run(self) -> None:
        """dry-run.sh exits with 0 and reports 1 successful call per scenario."""
        self.dry_run()

    def test_dry_run_with_tags(self) -> None:
        """Seagull accepts the default section, counters, log, presence, and pause."""
        options = (
            "log=true",
            "check-presence=true",
            "generated-session-id=true",
            "wait-ms=100",
        )
        extra: tuple = ()
        for option in options:
            extra += ("--option", option)
        self.dry_run(extra)

    def test_dry_run_of_a_rendered_template(self) -> None:
        """A template, rendered from its values file, runs like a ready scenario."""
        self.dry_run(TEMPLATE_ARGS)

    def test_dry_run_with_native_variables(self) -> None:
        """Native variables set once and restored in the next step run."""
        extra = ("--option", "mode=template", "--option", "substitution=native")
        self.dry_run((*extra, "--placeholder", "Origin-Realm=REALM"))


if __name__ == "__main__":
    unittest.main()
