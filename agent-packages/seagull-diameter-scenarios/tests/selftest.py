"""Self-test of the scripts of the seagull-diameter-scenarios package.

Run: python tests/selftest.py

It generates scenarios from the invented dictionaries and steps in tests/fixtures
and checks the result: the repairs, the grouping of steps into sessions, the
choice between several definitions of an AVP, the value conversions, the checks of
the answer, the dynamic tags, placeholders, templates, the conversion of a ready
scenario into a template, and the failure on an AVP that no dictionary has. The tests
of the dictionary conversion are in selftest_dictionaries.py, and those of the XSD
validator (which need Java) in selftest_validator.py, and those of the SKILL.md files
in selftest_skills.py; this file imports all three. The dry run and the check of the
converted dictionaries in the Seagull image run only when the environment variable
SEAGULL_IMAGE names an image and `sh` and `docker` work.

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
sys.path.insert(0, str(SKILLS / "seagull-diameter-scenario-externalize" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
check_steps = importlib.import_module("check_steps")
generate = importlib.import_module("generate_scenarios")
options_module = importlib.import_module("scenario_options")
apply_placeholders = importlib.import_module("apply_placeholders")
to_template = importlib.import_module("scenario_to_template")
output_folder = importlib.import_module("output_folder")
to_external = importlib.import_module("scenario_to_external")
dictionary_tests = importlib.import_module("selftest_dictionaries")
ConvertDictionariesTest = dictionary_tests.ConvertDictionariesTest
FlagOptionsTest = dictionary_tests.FlagOptionsTest
CheckConvertedTest = dictionary_tests.CheckConvertedTest
ValidatorTest = importlib.import_module("selftest_validator").ValidatorTest
SkillStructureTest = importlib.import_module("selftest_skills").SkillStructureTest
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
            status, _, error = run_generator(out, extra=("--replace",))
            text = (out / "scenario" / (CLIENT + ".tpl")).read_text("iso-8859-1")
        self.assertEqual(status, 0, error)
        self.assertIn("@@SUBSCRIBER_ID@@", text)

    def test_empty_placeholder_removes_the_pair(self) -> None:
        """--placeholder AVP= drops the pair from the file and from the template."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder)
            shutil.copy(self.folder / "scenario-options.ini", out)
            extra = ("--replace", "--placeholder", "Auth-Application-Id=")
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
            self.assertEqual(text.count('<store name="REALM" entity="Origin-Realm">'), 1)
            self.assertEqual(text.count('<restore name="REALM" entity="Origin-Realm">'), 1)
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
            expected_values = options_module.read_values(self.scenario(CLIENT + ".values"))
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


class OutputFolderTest(unittest.TestCase):
    """The generator never mixes new files with the contents of an old folder."""

    def test_next_free_skips_existing_folders(self) -> None:
        """next_free returns NAME, then NAME-2, then NAME-3."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            parent = Path(folder)
            self.assertEqual(output_folder.next_free(parent, "S").name, "S")
            (parent / "S").mkdir()
            self.assertEqual(output_folder.next_free(parent, "S").name, "S-2")
            (parent / "S-2").mkdir()
            self.assertEqual(output_folder.next_free(parent, "S").name, "S-3")

    def test_out_auto_never_reuses_a_folder(self) -> None:
        """Without a named folder, the second run goes to Seagull-Scenario-2."""
        base = ["--steps", str(FIXTURES / "steps")]
        base += ["--dictionaries-dir", str(FIXTURES / "dictionaries")]
        base += ["--dictionaries", "Gy"]
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            for _ in range(2):
                with redirect_stdout(io.StringIO()):
                    status = generate.main([*base, "--out-auto", folder])
                self.assertEqual(status, 0)
            names = sorted(p.name for p in Path(folder).iterdir())
        self.assertEqual(names, ["Seagull-Scenario", "Seagull-Scenario-2"])

    def test_non_empty_folder_is_refused(self) -> None:
        """A named folder that holds files stops the run and keeps the files."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder)
            (out / "old.txt").write_text("keep me", encoding="utf-8")
            status, _, error = run_generator(out)
            kept = (out / "old.txt").read_text(encoding="utf-8")
            names = sorted(p.name for p in out.iterdir())
        self.assertEqual(status, 1)
        self.assertIn("the output folder is not empty", error)
        self.assertIn("1 file(s)", error)
        self.assertEqual((kept, names), ("keep me", ["old.txt"]))

    def test_replace_moves_the_old_contents_aside(self) -> None:
        """--replace keeps the old files in a sibling folder and the placeholders."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder) / "out"
            run_generator(out, extra=TEMPLATE_ARGS)
            (out / "scenario" / "stale.client.xml").write_text("old", encoding="utf-8")
            status, report, error = run_generator(out, extra=("--replace",))
            aside = [p for p in Path(folder).iterdir() if ".previous-" in p.name]
            stale_kept = (aside[0] / "scenario" / "stale.client.xml").exists()
            stale_new = (out / "scenario" / "stale.client.xml").exists()
            options = (out / "scenario-options.ini").read_text(encoding="utf-8")
        self.assertEqual(status, 0, error)
        self.assertEqual((len(aside), stale_kept, stale_new), (1, True, False))
        self.assertIn("replaced the old output", report)
        self.assertIn("Subscription-Id/Subscription-Id-Data = SUBSCRIBER_ID", options)

    def test_options_carry_into_a_new_folder(self) -> None:
        """--options reads an older file; the old folder is not written to."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            first, second = Path(folder) / "first", Path(folder) / "second"
            run_generator(first, extra=TEMPLATE_ARGS)
            old = first / "scenario-options.ini"
            before = old.read_text(encoding="utf-8")
            status, _, error = run_generator(second, extra=("--options", str(old)))
            carried = (second / "scenario-options.ini").read_text(encoding="utf-8")
            after = old.read_text(encoding="utf-8")
        self.assertEqual(status, 0, error)
        self.assertIn("SUBSCRIBER_ID", carried)
        self.assertEqual(before, after)


EXTERNAL_ARGS = (
    "--placeholder",
    "Session-Id=SID",
    "--placeholder",
    "Subscription-Id-Data=MSISDN",
    "--placeholder",
    "3GPP-Charging-Id=CHARGING",
)


def run_external(source: Path, out: Path, *extra: str) -> tuple[int, str, str]:
    """Run the externalize script on a generation; return status, output, error."""
    argv = [str(source / "scenario"), "--out", str(out), *extra]
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = to_external.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class ExternalizeTest(unittest.TestCase):
    """Scenarios that read AVP values from an external data file."""

    root: Path
    source: Path

    @classmethod
    def setUpClass(cls) -> None:
        """Generate a ready run to convert."""
        cls.root = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        cls.source = cls.root / "gen"
        status, _, error = run_generator(cls.source)
        assert status == 0, error

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove the temporary folder."""
        shutil.rmtree(cls.root, ignore_errors=True)

    def convert(self, name: str, *extra: str) -> Path:
        """Convert into a new folder named name; fail the test on an error."""
        out = self.root / name
        status, _, error = run_external(self.source, out, *EXTERNAL_ARGS, *extra)
        self.assertEqual(status, 0, error)
        return out

    def test_requests_read_the_data_file(self) -> None:
        """Each matched AVP is read by field number in the action before the command."""
        out = self.convert("plain")
        text = (out / "scenario" / CLIENT).read_text("iso-8859-1")
        names = ("Session-Id", "Subscription-Id-Data", "3GPP-Charging-Id")
        for field, (name, steps) in enumerate(zip(names, (2, 2, 1))):
            line = f'<restore-from-external field="{field}" entity="{name}">'
            self.assertEqual(text.count(line), steps, line)  # the steps that carry it
        self.assertNotIn('<set-value name="Session-Id"', text)

    def test_check_of_a_varied_avp_is_removed(self) -> None:
        """The answer check of the Session-Id goes, because its value now varies."""
        out = self.convert("checks")
        text = (out / "scenario" / CLIENT).read_text("iso-8859-1")
        self.assertNotIn('<check-value name="Session-Id"', text)
        self.assertIn('<check-value name="Result-Code"', text)

    def test_data_file_holds_the_recorded_row(self) -> None:
        """The data file has the columns, the field definition, and the recorded values."""
        out = self.convert("data")
        lines = (out / "scenario" / "external-data.csv").read_text("ascii").splitlines()
        self.assertEqual(lines[0], "# SID; MSISDN; CHARGING")
        self.assertEqual(lines[1], '"string";"string";"string";')
        self.assertEqual(lines[2], '"TEST-A-1";"491700000001";"0x000000a1";')

    def test_configurations_name_the_data_file(self) -> None:
        """The client configurations get the file, the selection, and the call count."""
        out = self.convert("config", "--select", "random", "--calls", "7")
        client = (out / "config" / "conf.client.xml").read_text("iso-8859-1")
        dry_run = (out / "config" / "conf.dry-run.client.xml").read_text("iso-8859-1")
        stub = (out / "config" / "conf.stub-server.xml").read_text("iso-8859-1")
        self.assertIn('name="external-data-file" value="../scenario/external-data.csv"', client)
        self.assertIn(
            'name="external-data-file" value="/work/scenario/external-data.csv"',
            dry_run,
        )
        self.assertIn('name="external-data-select" value="random"', client)
        self.assertIn('name="number-calls" value="7"', client)
        self.assertNotIn("external-data", stub)

    def test_random_file_ends_with_a_spare_row(self) -> None:
        """Seagull never picks the last row of a random file, so a copy is appended."""
        out = self.convert("random", "--select", "random")
        lines = (out / "scenario" / "external-data.csv").read_text("ascii").splitlines()
        self.assertEqual((len(lines), lines[2]), (5, lines[4]))
        self.assertTrue(lines[3].startswith("# spare row"))

    def test_stub_scenarios_are_copied_unchanged(self) -> None:
        """The dry run needs the stub scenarios, and they hold no data-file reads."""
        out = self.convert("stubs")
        stub = out / "scenario" / "01-test-steps-001-002.stub-server.xml"
        original = self.source / "scenario" / stub.name
        self.assertEqual(stub.read_bytes(), original.read_bytes())

    def test_old_output_is_never_touched(self) -> None:
        """A folder with files is refused, and the source scenarios stay as they were."""
        before = (self.source / "scenario" / CLIENT).read_bytes()
        out = self.root / "busy"
        out.mkdir()
        (out / "old.txt").write_text("keep", encoding="utf-8")
        status, _, error = run_external(self.source, out, *EXTERNAL_ARGS)
        self.assertEqual(status, 1)
        self.assertIn("the output folder is not empty", error)
        self.assertEqual((self.source / "scenario" / CLIENT).read_bytes(), before)

    def test_repeated_avp_is_refused(self) -> None:
        """Seagull reads an AVP by name, so a name twice in one request is an error."""
        copy = self.root / "twice"
        shutil.copytree(self.source, copy)
        path = copy / "scenario" / CLIENT
        text = path.read_text("iso-8859-1")
        line = '        <avp name="Subscription-Id-Data" value="491700000001"></avp>\n'
        path.write_text(text.replace(line, line + line, 1), encoding="iso-8859-1")
        status, _, error = run_external(copy, self.root / "twice-out", *EXTERNAL_ARGS)
        self.assertEqual(status, 1)
        self.assertIn("occurs more than once in a request", error)

    def test_scenario_is_not_converted_twice(self) -> None:
        """A scenario that already reads the data file is refused."""
        out = self.convert("first")
        status, _, error = run_external(out, self.root / "second", *EXTERNAL_ARGS)
        self.assertEqual(status, 1)
        self.assertIn("already reads from an external data file", error)

    def test_no_avp_named_is_an_error(self) -> None:
        """Without pairs there is nothing to read from the file."""
        status, _, error = run_external(self.source, self.root / "none")
        self.assertEqual(status, 1)
        self.assertIn("no AVP is named", error)

    def test_unmatched_pair_is_reported(self) -> None:
        """A pair that matches no AVP is named in the report."""
        out = self.root / "unmatched"
        extra = (*EXTERNAL_ARGS, "--placeholder", "No-Such=NOPE")
        status, report, error = run_external(self.source, out, *extra)
        self.assertEqual(status, 0, error)
        self.assertIn("placeholder No-Such: matched no AVP", report)


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

    def test_dry_run_reading_from_the_data_file(self) -> None:
        """Three calls take three rows: Session-Id, MSISDN, and a hex value from the file."""
        script = GENERATE_DIR / "dry-run.sh"
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            source, out = Path(folder) / "gen", Path(folder) / "ext"
            self.assertEqual(run_generator(source)[0], 0)
            status, _, error = run_external(source, out, *EXTERNAL_ARGS, "--calls", "3")
            self.assertEqual(status, 0, error)
            data = out / "scenario" / "external-data.csv"
            rows = [
                '"TEST-A-2";"491700000002";"0x000000a2";',
                '"TEST-A-3";"491700000003";"0x000000a3";',
            ]
            data.write_text(data.read_text("ascii") + "\n".join(rows) + "\n", "ascii")
            command = ["sh", str(script), str(out), IMAGE]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        line = "successful calls: 3, failed calls: 0"
        self.assertEqual(result.stdout.count(line), 2, result.stdout)

    def test_dry_run_with_native_variables(self) -> None:
        """Native variables set once and restored in the next step run."""
        extra = ("--option", "mode=template", "--option", "substitution=native")
        self.dry_run((*extra, "--placeholder", "Origin-Realm=REALM"))


if __name__ == "__main__":
    unittest.main()
