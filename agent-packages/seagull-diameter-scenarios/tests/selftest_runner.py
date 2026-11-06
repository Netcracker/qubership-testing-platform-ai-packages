"""Self-test of the settings and of the Windows runner of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It checks the file that says where Seagull runs (the two places, the order of values, what is
refused), the pure helpers of the Windows runner, and, when the environment variable SEAGULL_EXE
names the seagull.exe of Seagull for Windows, a real dry run and a real check of a converted
dictionary with it. The real runs are skipped without SEAGULL_EXE, and on other systems.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import importlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parents[1] / ".apm" / "skills"
sys.path.insert(0, str(SKILLS / "seagull-diameter-common" / "scripts"))
sys.path.insert(0, str(SKILLS / "seagull-diameter-generate-scenarios" / "scripts"))
sys.path.insert(0, str(SKILLS / "seagull-diameter-convert-dictionaries" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
config = importlib.import_module("seagull_config")
runner = importlib.import_module("seagull_windows_run")
generate = importlib.import_module("generate_scenarios")
convert = importlib.import_module("convert_dictionaries")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SEAGULL_EXE = os.environ.get("SEAGULL_EXE", "")


class ConfigTest(unittest.TestCase):
    """seagull_config.py reads two files, in order, and writes one."""

    def setUp(self) -> None:
        """Make a session folder and a home folder, and an environment without the settings."""
        folder = tempfile.mkdtemp(prefix="seagull-selftest-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.session, self.home = Path(folder) / "session", Path(folder) / "home"
        self.session.mkdir()
        self.home.mkdir()
        patcher = mock.patch.dict(os.environ, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def command(self, *argv: str) -> tuple[int, str, str]:
        """Run the command line against the folders of the test."""
        args = config.parse_arguments([*argv, "--folder", str(self.session)])
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = config.run(args, home=self.home)
            except config.ConfigError as error:
                stderr.write(str(error))
                status = 2
        return status, stdout.getvalue(), stderr.getvalue()

    def test_unset_runner_exits_with_4(self) -> None:
        """A key without a value prints nothing and exits with 4, the signal to ask the user."""
        status, output, _ = self.command("get", "SEAGULL_RUNNER")
        self.assertEqual((status, output), (4, ""))

    def test_default_image(self) -> None:
        """The image has a default, so it is never asked."""
        _, output, _ = self.command("get", "SEAGULL_DOCKER_IMAGE")
        self.assertEqual(output.strip(), "seagull:local")

    def test_set_writes_the_session_file_and_keeps_other_keys(self) -> None:
        """set writes the session file, .seagull-diameter/config.json, and keeps the other keys."""
        self.command("set", "SEAGULL_DOCKER_IMAGE", "seagull:test")
        status, _, _ = self.command("set", "SEAGULL_RUNNER", "docker")
        text = (self.session / ".seagull-diameter" / "config.json").read_text(encoding="utf-8")
        self.assertEqual(status, 0)
        self.assertIn('"SEAGULL_RUNNER": "docker"', text)
        self.assertIn('"SEAGULL_DOCKER_IMAGE": "seagull:test"', text)

    def test_session_file_wins_over_home_and_environment_wins_over_both(self) -> None:
        """The order is the environment, the session file, the home file."""
        self.command("set", "SEAGULL_RUNNER", "docker", "--home")
        self.assertEqual(self.command("get", "SEAGULL_RUNNER")[1].strip(), "docker")
        session_file = self.session / ".seagull-diameter" / "config.json"
        session_file.parent.mkdir()
        session_file.write_text('{"SEAGULL_RUNNER": "windows"}', encoding="utf-8")
        self.assertEqual(self.command("get", "SEAGULL_RUNNER")[1].strip(), "windows")
        with mock.patch.dict(os.environ, {"SEAGULL_RUNNER": "docker"}):
            self.assertEqual(self.command("get", "SEAGULL_RUNNER")[1].strip(), "docker")

    def test_invalid_settings_are_refused(self) -> None:
        """An unknown key, an unknown runner, and a path that is not a file are refused."""
        self.assertEqual(self.command("set", "PASSWORD", "x")[0], 2)
        self.assertEqual(self.command("set", "SEAGULL_RUNNER", "podman")[0], 2)
        status, _, error = self.command("set", "SEAGULL_WINDOWS_PATH", str(self.home / "nope.exe"))
        self.assertEqual(status, 2)
        self.assertIn("no file", error)
        self.assertFalse((self.session / ".seagull-diameter").exists())


class RunnerHelpersTest(unittest.TestCase):
    """The helpers of the Windows runner change configurations and read statistics."""

    def test_with_port_changes_source_and_dest_only(self) -> None:
        """The port of source= and dest= is replaced, and no other number is."""
        text = 'open-args="mode=server;source=127.0.0.1:3868" value="3868"'
        self.assertEqual(
            runner.with_port(text, 5555),
            'open-args="mode=server;source=127.0.0.1:5555" value="3868"',
        )
        client = 'open-args="mode=client;dest=10.0.0.1:3868"'
        self.assertEqual(runner.with_port(client, 7), 'open-args="mode=client;dest=10.0.0.1:7"')

    def test_with_calls_replaces_or_adds(self) -> None:
        """number-calls is replaced where it is defined and added where it is not."""
        defined = '<define name="number-calls" value="5"></define></configuration>'
        self.assertIn('value="1"', runner.with_calls(defined, 1))
        self.assertNotIn('value="5"', runner.with_calls(defined, 1))
        added = runner.with_calls("<configuration></configuration>", 3)
        self.assertIn('name="number-calls" value="3"', added)

    def test_with_data_file_sets_the_path(self) -> None:
        """The external-data-file of a configuration gets the path on this machine."""
        text = '<define name="external-data-file" value="/work/external-data.csv"></define>'
        result = runner.with_data_file(text, Path("C:/out/external-data.csv"))
        self.assertIn(str(Path("C:/out/external-data.csv")), result)
        self.assertNotIn("/work/", result)

    def test_free_port_is_a_port_number(self) -> None:
        """free_port returns a usable port number."""
        self.assertGreater(runner.free_port(), 1023)

    def test_read_stats_takes_the_last_row_of_the_newest_file(self) -> None:
        """The successful and failed calls come from the last row of the newest statistics."""
        folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.assertIsNone(runner.read_stats(folder))
        header = "TrafficSuccessfulCall(C);FailedCall(C)\n"
        (folder / "client-stat.1.csv").write_text(header + "1;0\n5;2\n", encoding="utf-8")
        self.assertEqual(runner.read_stats(folder), (5, 2))

    def test_report_lines(self) -> None:
        """A job passes with at least one successful call and no failed call."""
        line = "a: successful calls: 5, failed calls: 0"
        self.assertEqual(runner.report("a", (5, 0, "")), (line, True))
        self.assertFalse(runner.report("a", (0, 0, ""))[1])
        self.assertFalse(runner.report("a", (3, 1, "|E|"))[1])
        self.assertEqual(runner.report("a", None), ("a: no statistics file", False))


@unittest.skipUnless(SEAGULL_EXE and os.name == "nt", "set SEAGULL_EXE to a seagull.exe")
class WindowsRunTest(unittest.TestCase):
    """The Windows runner completes a dry run and a check with the real seagull.exe."""

    def run_runner(self, *argv: str) -> tuple[int, str]:
        """Run the runner with SEAGULL_EXE; return the exit status and the output."""
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = runner.main([*argv, "--seagull-exe", SEAGULL_EXE])
        return status, stdout.getvalue()

    def test_dry_run_of_generated_scenarios(self) -> None:
        """Both generated scenarios end with 1 successful call and 0 failed calls."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            argv = ["--steps", str(FIXTURES / "steps")]
            argv += ["--dictionaries-dir", str(FIXTURES / "dictionaries")]
            argv += ["--dictionaries", "Gy", "--out", folder + "/out"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(generate.main(argv), 0)
            status, output = self.run_runner("dry-run", folder + "/out")
        self.assertEqual(status, 0, output)
        self.assertEqual(output.count("successful calls: 1, failed calls: 0"), 2, output)

    def test_check_of_a_converted_dictionary(self) -> None:
        """A combined dictionary completes the exchange, and a dictionary without CCR is skipped."""
        dictionaries = importlib.import_module("selftest_dictionaries")
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            source = Path(folder) / "dictionaries"
            shutil.copytree(FIXTURES / "dictionaries", source)
            (source / "Extra.xml").write_text(dictionaries.extra_dictionary(), encoding="utf-8")
            out = Path(folder) / "converted"
            argv = [str(source), "--out", str(out), "--combine", "Gy,Extra"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(convert.main(argv), 0)
            checked = Path(folder) / "checked"
            checked.mkdir()
            shutil.copy(out / "Gy+Extra.xml", checked)
            shutil.copy(out / "DiameterBaseProtocol.xml", checked)
            status, output = self.run_runner("check-converted", str(checked))
        self.assertEqual(status, 0, output)
        self.assertIn("Gy+Extra: successful calls: 1, failed calls: 0", output)
        self.assertIn("DiameterBaseProtocol: skipped, the dictionary defines no CCR", output)


if __name__ == "__main__":
    unittest.main()
