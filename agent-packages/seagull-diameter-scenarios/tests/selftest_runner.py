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
sys.path.insert(0, str(SKILLS / "seagull-diameter-manage-settings" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
config = importlib.import_module("seagull_config")
seagull_run = importlib.import_module("seagull_run")
show_settings = importlib.import_module("show_settings")
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

    def test_session_folder_is_the_folder_above_the_skills_folder(self) -> None:
        """A current folder inside .claude/skills/<name> still reads the settings of the session."""
        inside = self.session / ".claude" / "skills" / "seagull-diameter-common" / "scripts"
        self.assertEqual(config.session_folder(inside), self.session)
        self.assertEqual(config.session_folder(self.session), self.session)

    def test_runner_summary_names_the_runner_and_the_path(self) -> None:
        """The line that a conversion prints says where Seagull runs, or that the user is asked."""
        environ: dict[str, str] = {}
        unset = config.runner_summary(self.session, self.home, environ)
        self.assertEqual(unset, "Seagull for the check: not set; ask the user which Seagull to use")
        exe = self.session / "seagull.exe"
        exe.write_text("", encoding="utf-8")
        self.command("set", "SEAGULL_RUNNER", "windows")
        self.command("set", "SEAGULL_WINDOWS_PATH", str(exe))
        line = config.runner_summary(self.session, self.home, environ)
        self.assertEqual(line, f"Seagull for the check: windows, {exe}")
        self.command("set", "SEAGULL_RUNNER", "docker")
        docker = config.runner_summary(self.session, self.home, environ)
        self.assertEqual(docker, "Seagull for the check: docker, image seagull:local")

    def test_get_without_a_key_lists_every_setting(self) -> None:
        """An agent that forgets the key gets the list that show prints, not an error."""
        self.command("set", "SEAGULL_RUNNER", "docker")
        status, output, error = self.command("get")
        self.assertEqual((status, error), (0, ""))
        self.assertIn("SEAGULL_RUNNER=docker", output)
        self.assertIn("SEAGULL_WINDOWS_PATH=  (not set)", output)

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

    def test_settings_folder_is_the_nearest_folder_upward_that_has_the_file(self) -> None:
        """A script run from any subfolder finds the file of the session above it."""
        self.command("set", "SEAGULL_DOCKER_IMAGE", "seagull:test")
        deep = self.session / "work" / "output"
        deep.mkdir(parents=True)
        self.assertEqual(config.settings_folder(deep), self.session)
        self.assertEqual(config.settings_folder(self.home), self.home)

    def test_settings_folder_falls_back_to_the_session_that_holds_the_script(self) -> None:
        """A script run from a folder outside the session still reads the settings of its own session."""
        self.command("set", "SEAGULL_DOCKER_IMAGE", "seagull:test")
        script = self.session / ".claude" / "skills" / "seagull-diameter-common" / "scripts" / "seagull_config.py"
        outside = self.home / "elsewhere"
        outside.mkdir()
        with mock.patch.object(config, "__file__", str(script)):
            found = config.settings_folder(outside)
        self.assertEqual(found.resolve(), self.session.resolve())
        self.assertEqual(config.settings_folder(outside), outside)


class SeagullRunTest(unittest.TestCase):
    """seagull_run.py picks the runner from the settings and asks only when a setting has no value."""

    def setUp(self) -> None:
        """Make a session folder with no settings, and run from it."""
        folder = tempfile.mkdtemp(prefix="seagull-selftest-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.session = Path(folder) / "session"
        self.session.mkdir()
        for target in (
            mock.patch.dict(os.environ, clear=True),
            mock.patch.object(Path, "home", return_value=Path(folder) / "home"),
            mock.patch.object(Path, "cwd", return_value=self.session),
        ):
            target.start()
            self.addCleanup(target.stop)

    def run_script(self, *argv: str) -> tuple[int, str]:
        """Run seagull_run.py; return the exit status and the error output."""
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            status = seagull_run.main(list(argv))
        return status, stderr.getvalue()

    def test_an_unset_runner_exits_with_4_and_says_to_ask(self) -> None:
        """Without SEAGULL_RUNNER the script starts nothing and exits with 4."""
        status, error = self.run_script("dry-run", str(self.session))
        self.assertEqual(status, 4)
        self.assertIn("SEAGULL_RUNNER is not set; ask the user", error)

    def test_windows_without_a_path_exits_with_4(self) -> None:
        """The runner is windows and the path of seagull.exe is missing: exit 4, not a guess."""
        with mock.patch.dict(os.environ, {"SEAGULL_RUNNER": "windows"}):
            status, error = self.run_script("check-converted", str(self.session))
        self.assertEqual(status, 4)
        self.assertIn("SEAGULL_WINDOWS_PATH is not set", error)

    def test_windows_runs_the_windows_runner_with_the_path_of_the_settings(self) -> None:
        """The path comes from the settings; the folder and the options of the call are forwarded."""
        env = {"SEAGULL_RUNNER": "windows", "SEAGULL_WINDOWS_PATH": "C:/Seagull/seagull.exe"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.seagull_windows_run, "main") as run:
            run.return_value = 0
            status, _ = self.run_script("dry-run", "out", "--logs", "logs")
        self.assertEqual(status, 0)
        forwarded = run.call_args.args[0]
        self.assertEqual(forwarded[:4], ["dry-run", "out", "--seagull-exe", "C:/Seagull/seagull.exe"])
        self.assertEqual(forwarded[-2:], ["--logs", "logs"])

    def test_an_option_wins_over_the_settings(self) -> None:
        """--runner and --seagull-exe override the settings for one run."""
        env = {"SEAGULL_RUNNER": "docker"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.seagull_windows_run, "main") as run:
            run.return_value = 3
            status, _ = self.run_script("dry-run", "out", "--runner", "windows", "--seagull-exe", "x.exe")
        self.assertEqual(status, 3)
        self.assertIn("x.exe", run.call_args.args[0])

    def test_docker_runs_the_script_of_the_image_with_the_image_of_the_settings(self) -> None:
        """The Docker script gets the folder and the image; the exit status is the script's."""
        env = {"SEAGULL_RUNNER": "docker", "SEAGULL_DOCKER_IMAGE": "seagull:test"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1)
            status, _ = self.run_script("check-converted", str(self.session))
        command = run.call_args.args[0]
        self.assertEqual(status, 1)
        self.assertEqual(command[-1], "seagull:test")
        self.assertIn("check-converted.sh", " ".join(command))

    @unittest.skipUnless(os.name == "nt", "drive letters exist on Windows")
    def test_a_windows_path_is_given_to_wsl_as_a_mnt_path(self) -> None:
        """to_wsl turns C:\\work\\out into /mnt/c/work/out."""
        self.assertEqual(seagull_run.to_wsl(Path("C:/work/out")), "/mnt/c/work/out")


class ShowSettingsTest(unittest.TestCase):
    """show_settings.py prints the settings, the dictionary options, and the note on scenario options."""

    def setUp(self) -> None:
        """Make a session folder, a home folder, and a converted dictionary with its options file."""
        folder = tempfile.mkdtemp(prefix="seagull-selftest-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.session, self.home = Path(folder) / "session", Path(folder) / "home"
        self.session.mkdir()
        self.home.mkdir()
        self.dictionary = Path(folder) / "converted" / "diameter-dictionary.xml"
        self.dictionary.parent.mkdir()
        self.dictionary.write_text("<dictionary/>", encoding="utf-8")
        patcher = mock.patch.dict(os.environ, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def report(self) -> str:
        """Return the report for the session folder."""
        return show_settings.build_report(self.session, self.home, dict(os.environ))

    def test_unset_settings_and_no_dictionary(self) -> None:
        """Every key says not set, the dictionary part says why it is empty, and the note ends the report."""
        text = self.report()
        self.assertIn("## Settings\n- SEAGULL_RUNNER: not set", text)
        self.assertIn("SEAGULL_DICTIONARY_PATH is not set, so there is no dictionary", text)
        self.assertTrue(text.rstrip().endswith("in the folder of that set."))

    def test_the_options_next_to_the_dictionary_are_shown_under_their_heading(self) -> None:
        """dictionary-options.ini is read from the folder of the dictionary of the settings, and only there."""
        (self.dictionary.parent / "dictionary-options.ini").write_text("[command-flags]\nCCR = 192\n", encoding="utf-8")
        config.save("SEAGULL_DICTIONARY_PATH", str(self.dictionary), self.session, self.home)
        text = self.report()
        self.assertIn("## Dictionary options\nDictionary: " + str(self.dictionary), text)
        self.assertIn("CCR = 192", text)
        self.assertIn(f"- SEAGULL_DICTIONARY_PATH: {self.dictionary}", text)

    def test_a_missing_options_file_is_named(self) -> None:
        """A dictionary without dictionary-options.ini next to it gets one line, not a search."""
        config.save("SEAGULL_DICTIONARY_PATH", str(self.dictionary), self.session, self.home)
        self.assertIn("dictionary-options.ini was not found next to it.", self.report())


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
            dictionaries = importlib.import_module("selftest_dictionaries")
            argv += ["--dictionary", str(dictionaries.converted_gy()), "--out", folder + "/out"]
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
            argv += ["--combine", "DiameterBaseProtocol"]
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
