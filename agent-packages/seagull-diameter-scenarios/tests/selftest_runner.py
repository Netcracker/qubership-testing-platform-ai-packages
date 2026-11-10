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
from pathlib import Path, PureWindowsPath
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

    def test_the_message_names_the_settings_that_are_known(self) -> None:
        """The path of seagull.exe that the settings hold is in the message, so the agent does not ask for it."""
        with mock.patch.dict(os.environ, {"SEAGULL_WINDOWS_PATH": "C:/Seagull/seagull.exe"}):
            status, error = self.run_script("dry-run", str(self.session))
        self.assertEqual(status, 4)
        self.assertIn("docker (image seagull:local) or windows (seagull.exe at C:/Seagull/seagull.exe)", error)
        status, error = self.run_script("dry-run", str(self.session))
        self.assertIn("windows (and where its seagull.exe is)", error)

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

    def test_a_scenario_file_runs_that_scenario_in_docker(self) -> None:
        """A client scenario file gives the Docker script its output folder and, last, the name of the scenario."""
        scenario = self.session / "out" / "scenario" / "01-voice.client.xml"
        scenario.parent.mkdir(parents=True)
        scenario.write_text("<scenario/>", encoding="utf-8")
        env = {"SEAGULL_RUNNER": "docker", "SEAGULL_DOCKER_IMAGE": "seagull:test"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            status, _ = self.run_script("dry-run", str(scenario))
        command = run.call_args.args[0]
        self.assertEqual(status, 0)
        self.assertEqual(command[-2:], ["seagull:test", "01-voice"])
        self.assertTrue(command[-3].endswith("out"), command)

    def test_a_folder_runs_every_scenario_in_docker(self) -> None:
        """A folder gives the Docker script no scenario name."""
        env = {"SEAGULL_RUNNER": "docker", "SEAGULL_DOCKER_IMAGE": "seagull:test"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            self.run_script("dry-run", str(self.session))
        self.assertEqual(run.call_args.args[0][-1], "seagull:test")

    def test_a_file_that_is_no_client_scenario_is_refused(self) -> None:
        """Another file, or a path that does not exist, stops the run with status 2 and starts nothing."""
        other = self.session / "notes.txt"
        other.write_text("x", encoding="utf-8")
        env = {"SEAGULL_RUNNER": "docker"}
        for target in (other, self.session / "missing"):
            with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
                status, error = self.run_script("dry-run", str(target))
            self.assertEqual(status, 2)
            self.assertIn("error:", error)
            run.assert_not_called()

    def make_scenario(self) -> Path:
        """Write a client scenario file in an output folder of the session; return its path."""
        scenario = self.session / "out" / "scenario" / "01-voice.client.xml"
        scenario.parent.mkdir(parents=True)
        scenario.write_text("<scenario/>", encoding="utf-8")
        return scenario

    def test_run_needs_a_host_and_port_and_only_run_takes_one(self) -> None:
        """run without a valid --dest, and another command with one, stop with status 2 and start nothing."""
        scenario = self.make_scenario()
        env = {"SEAGULL_RUNNER": "docker"}
        cases = [
            ("run", str(scenario)),
            ("run", str(scenario), "--dest", "10.0.0.5"),
            ("run", str(scenario), "--dest", "10.0.0.5:3868; rm -rf /"),
            ("dry-run", str(scenario), "--dest", "10.0.0.5:3868"),
        ]
        for argv in cases:
            with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
                status, error = self.run_script(*argv)
            self.assertEqual(status, 2, argv)
            self.assertIn("--dest", error)
            run.assert_not_called()

    def test_run_gives_the_windows_runner_the_address(self) -> None:
        """The address and the logs folder reach seagull_windows_run.py, with the path of seagull.exe."""
        env = {"SEAGULL_RUNNER": "windows", "SEAGULL_WINDOWS_PATH": "C:/Seagull/seagull.exe"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.seagull_windows_run, "main") as run:
            run.return_value = 0
            status, _ = self.run_script("run", "x.client.xml", "--dest", "10.0.0.5:3868", "--logs", "logs")
        self.assertEqual(status, 0)
        forwarded = run.call_args.args[0]
        self.assertEqual(forwarded[:4], ["run", "x.client.xml", "--seagull-exe", "C:/Seagull/seagull.exe"])
        self.assertEqual(forwarded[-4:], ["--logs", "logs", "--dest", "10.0.0.5:3868"])

    def test_run_gives_the_docker_script_the_scenario_the_address_and_the_logs(self) -> None:
        """The Docker script gets the output folder, the image, the scenario name, the address, and the logs folder."""
        scenario = self.make_scenario()
        env = {"SEAGULL_RUNNER": "docker", "SEAGULL_DOCKER_IMAGE": "seagull:test"}
        argv = ["run", str(scenario), "--dest", "10.0.0.5:3868"]
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1)
            status, _ = self.run_script(*argv)
            command = run.call_args.args[0]
            self.run_script(*argv, "--logs", str(self.session / "logs"))
            with_logs = run.call_args.args[0]
        self.assertEqual(status, 1)
        self.assertIn("run-ocs.sh", " ".join(command))
        self.assertEqual(command[-3:], ["seagull:test", "01-voice", "10.0.0.5:3868"])
        self.assertEqual(with_logs[-4:-1], ["seagull:test", "01-voice", "10.0.0.5:3868"])
        self.assertTrue(with_logs[-1].endswith("logs"), with_logs)

    def test_logs_of_a_docker_dry_run_are_ignored_with_a_note(self) -> None:
        """A Docker dry run keeps no logs, so --logs gets a note on stderr; run keeps them and says nothing."""
        scenario = self.make_scenario()
        env = {"SEAGULL_RUNNER": "docker"}
        logs = ["--logs", str(self.session / "logs")]
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0)
            _, dry_run_error = self.run_script("dry-run", str(scenario), *logs)
            _, run_error = self.run_script("run", str(scenario), "--dest", "10.0.0.5:3868", *logs)
            _, no_logs_error = self.run_script("dry-run", str(scenario))
        self.assertIn("note: --logs is ignored", dry_run_error)
        self.assertEqual(run_error, "")
        self.assertEqual(no_logs_error, "")

    def test_run_takes_a_scenario_file_and_not_a_folder_in_docker(self) -> None:
        """A folder gives run nothing to run: status 2, and the Docker script does not start."""
        env = {"SEAGULL_RUNNER": "docker"}
        with mock.patch.dict(os.environ, env), mock.patch.object(seagull_run.subprocess, "run") as run:
            status, error = self.run_script("run", str(self.session), "--dest", "10.0.0.5:3868")
        self.assertEqual(status, 2)
        self.assertIn("one client scenario file", error)
        run.assert_not_called()

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

    def test_with_dest_sets_the_address_of_the_channel_only(self) -> None:
        """The host and the port of dest= are replaced, and no other attribute is."""
        text = 'transport="trans-1" open-args="mode=client;dest=127.0.0.1:3868" value="127.0.0.1:3868"'
        self.assertEqual(
            runner.with_dest(text, "ocs.example:30151"),
            'transport="trans-1" open-args="mode=client;dest=ocs.example:30151" value="127.0.0.1:3868"',
        )

    def test_run_refuses_a_folder_a_bad_address_and_a_missing_scenario(self) -> None:
        """run exits with 2 before it starts Seagull; the file named as seagull.exe is never executed."""
        folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        scenario = folder / "scenario" / "01-voice.client.xml"
        scenario.parent.mkdir()
        scenario.write_text("<scenario/>", encoding="utf-8")
        cases = [
            (str(folder), "10.0.0.5:3868"),
            (str(folder / "missing.client.xml"), "10.0.0.5:3868"),
            (str(scenario), "10.0.0.5"),
            (str(scenario), ""),
        ]
        for target, dest in cases:
            stderr = io.StringIO()
            with mock.patch.object(runner, "start") as start, redirect_stderr(stderr):
                argv = ["run", target, "--dest", dest, "--seagull-exe", sys.executable]
                self.assertEqual(runner.main(argv), 2, (target, dest))
            self.assertIn("error:", stderr.getvalue())
            start.assert_not_called()

    def test_with_calls_replaces_or_adds(self) -> None:
        """number-calls is replaced where it is defined and added where it is not."""
        defined = '<define name="number-calls" value="5"></define></configuration>'
        self.assertIn('value="1"', runner.with_calls(defined, 1))
        self.assertNotIn('value="5"', runner.with_calls(defined, 1))
        added = runner.with_calls("<configuration></configuration>", 3)
        self.assertIn('name="number-calls" value="3"', added)

    def test_split_target_tells_a_folder_from_a_scenario_file(self) -> None:
        """A folder runs every scenario; a client scenario file runs itself, in the output folder two levels up."""
        folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        scenario = folder / "scenario" / "01-voice.client.xml"
        scenario.parent.mkdir()
        scenario.write_text("<scenario/>", encoding="utf-8")
        template = folder / "scenario" / "01-voice.client.xml.tpl"
        template.write_text("<scenario/>", encoding="utf-8")
        self.assertEqual(runner.split_target(folder), (folder, None))
        self.assertEqual(runner.split_target(scenario), (folder, "01-voice"))
        for target in (template, folder / "missing"):
            with self.assertRaises(ValueError):
                runner.split_target(target)

    def test_select_jobs_picks_one_scenario_by_name(self) -> None:
        """The name of a scenario picks its job, and a name that matches none lists the known ones."""
        jobs = [
            runner.Job(n, Path("d"), (Path("s"), Path("c")), (Path("s"), Path("c"))) for n in ("01-voice", "02-sms")
        ]
        self.assertEqual(runner.select_jobs(jobs, None), jobs)
        self.assertEqual([j.name for j in runner.select_jobs(jobs, "02-sms")], ["02-sms"])
        with self.assertRaises(ValueError) as caught:
            runner.select_jobs(jobs, "03-data")
        self.assertIn("no scenario 03-data in the output folder; it has 01-voice, 02-sms", str(caught.exception))

    def test_with_data_file_sets_the_path(self) -> None:
        """The external-data-file of a configuration gets the path on this machine."""
        text = '<define name="external-data-file" value="/work/external-data.csv"></define>'
        result = runner.with_data_file(text, PureWindowsPath("C:/out/external-data.csv"))
        self.assertIn('value="C:/out/external-data.csv"', result)
        self.assertNotIn("/work/", result)

    def test_with_data_file_writes_no_backslash(self) -> None:
        """Seagull reads \\t of C:\\temp as a tab, so the path of the data file has forward slashes only."""
        text = '<define name="external-data-file" value="/work/external-data.csv"></define>'
        result = runner.with_data_file(text, PureWindowsPath(r"C:\temp\out\external-data.csv"))
        self.assertIn('value="C:/temp/out/external-data.csv"', result)
        self.assertNotIn("\\", result)

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

    def test_run_against_an_ocs_that_listens(self) -> None:
        """A scenario runs against the address it is given, and a closed port ends with a failure and the error."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder) / "out"
            argv = ["--steps", str(FIXTURES / "steps")]
            dictionaries = importlib.import_module("selftest_dictionaries")
            argv += ["--dictionary", str(dictionaries.converted_gy()), "--out", str(out)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(generate.main(argv), 0)
            job = runner.dry_run_jobs(out)[0]
            port = runner.free_port()
            work = Path(folder) / "stub"
            (work / "run").mkdir(parents=True)
            (work / "logs").mkdir()
            stub_conf = work / "server.xml"
            stub_text = runner.with_port(job.server[1].read_text(encoding=runner.ENCODING), port)
            stub_conf.write_text(stub_text, encoding=runner.ENCODING, newline="\n")
            stub = runner.start(SEAGULL_EXE, work / "run", runner.arguments(job, stub_conf, job.server[0], "stub"))
            self.addCleanup(runner.stop, stub)
            runner.time.sleep(runner.SETTLE_SECONDS)
            scenario = out / "scenario" / f"{job.name}.client.xml"
            status, output = self.run_runner("run", str(scenario), "--dest", f"127.0.0.1:{port}")
            self.assertEqual(status, 0, output)
            self.assertIn(f"{job.name}: successful calls: 1, failed calls: 0", output)
            runner.stop(stub)
            status, output = self.run_runner("run", str(scenario), "--dest", f"127.0.0.1:{port}", "--timeout", "30")
        self.assertEqual(status, 1, output)
        self.assertIn("successful calls: 0, failed calls: 0", output)
        self.assertIn("|E|", output)

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
