"""Self-test of the dictionary conversion of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It converts the invented dictionaries in tests/fixtures: the output folder, the options
that reach the converter, the flags of commands and AVPs, and the options file. The check
of a converted dictionary in the Seagull image runs only when the environment variable
SEAGULL_IMAGE names an image and `sh` and `docker` work.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import atexit
import functools
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
CONVERT_DIR = SKILLS / "seagull-diameter-convert-dictionaries" / "scripts"
sys.path.insert(0, str(SKILLS / "seagull-diameter-common" / "scripts"))
sys.path.insert(0, str(CONVERT_DIR))
sys.path.insert(0, str(SKILLS / "seagull-diameter-generate-scenarios" / "scripts"))
convert = importlib.import_module("convert_dictionaries")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
IMAGE = os.environ.get("SEAGULL_IMAGE", "")


def run_convert(argv: list[str]) -> tuple[int, str, str]:
    """Run convert_dictionaries.py; return the exit status, its output, and its error output."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = convert.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


@functools.cache
def converted_gy(*extra: str) -> Path:
    """Convert the fixture dictionaries once; return the Seagull dictionary made of Gy."""
    folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-dictionary-"))
    atexit.register(shutil.rmtree, folder, ignore_errors=True)
    argv = [str(FIXTURES / "dictionaries"), "--out", str(folder / "out"), "--combine", "Gy", *extra]
    status, _, error = run_convert(argv)
    if status != 0:
        raise RuntimeError(error)
    return folder / "out" / "Gy.xml"


class ConvertDictionariesTest(unittest.TestCase):
    """convert_dictionaries.py writes Seagull dictionaries into a new folder."""

    def test_out_auto_never_reuses_a_folder(self) -> None:
        """Without a named folder, the results go next to the input, and the second run to -2."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            source = Path(folder) / "dictionaries"
            shutil.copytree(FIXTURES / "dictionaries", source)
            statuses = [run_convert([str(source), "--out-auto"])[0] for _ in range(2)]
            names = sorted(p.name for p in Path(folder).iterdir())
            files = sorted(p.name for p in (Path(folder) / "Seagull-Dictionary").iterdir())
        self.assertEqual(statuses, [0, 0])
        self.assertEqual(names, ["Seagull-Dictionary", "Seagull-Dictionary-2", "dictionaries"])
        expected = ["conversion-report.txt", "dictionary-options.ini", "diameter-dictionary.xml"]
        self.assertEqual(files, sorted(expected))

    def test_non_empty_folder_is_refused(self) -> None:
        """A named folder that holds files stops the run and keeps the files."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            out = Path(folder)
            (out / "old.txt").write_text("keep me", encoding="utf-8")
            argv = [str(FIXTURES / "dictionaries"), "--out", str(out)]
            status, _, error = run_convert(argv)
            names = sorted(p.name for p in out.iterdir())
        self.assertEqual(status, 1)
        self.assertIn("the output folder is not empty", error)
        self.assertEqual(names, ["old.txt"])

    def test_options_reach_the_converter(self) -> None:
        """--keep-tgpp keeps the TGPP- prefix that the conversion rewrites to 3GPP-."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            texts = {}
            for name, extra in (("plain", []), ("kept", ["--keep-tgpp"])):
                out = Path(folder) / name
                argv = [str(FIXTURES / "dictionaries"), "--out", str(out), *extra]
                self.assertEqual(run_convert(argv)[0], 0)
                texts[name] = (out / "diameter-dictionary.xml").read_text(encoding="utf-8")
        self.assertIn('name="3GPP-Charging-Id"', texts["plain"])
        self.assertIn('name="TGPP-Charging-Id"', texts["kept"])

    def converted(self) -> tuple[str, str]:
        """Convert the fixture dictionaries; return the dictionary and the report."""
        folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        argv = [str(FIXTURES / "dictionaries"), "--out", str(folder / "out")]
        status, text, error = run_convert(argv)
        self.assertEqual(status, 0, error)
        return (folder / "out" / "diameter-dictionary.xml").read_text(encoding="iso-8859-1"), text

    def test_the_type_of_an_avp_is_kept(self) -> None:
        """An AVP keeps its type name, and the output defines each type in use and no other."""
        text, _ = self.converted()
        self.assertIn('<define name="Event-Timestamp" type="Time">', text)
        self.assertIn('<typedef name="Time" type="number" size="4" unit="octet">', text)
        self.assertIn('<typedef name="Enumerated" type="signed" size="4" unit="octet">', text)
        self.assertIn('<typedef name="UTF8String" type="string" size="4" unit="octet">', text)
        self.assertNotIn('<typedef name="Integer64"', text)

    def test_a_name_with_two_identities_is_not_renamed(self) -> None:
        """Both definitions are written under the name; the report says which one Seagull uses."""
        text, report = self.converted()
        self.assertEqual(text.count('<define name="Node-Id" '), 2)
        self.assertNotIn("Node-Id-v", text)
        self.assertIn("Node-Id is defined twice with different identity", report)
        self.assertIn("Seagull sends the first one", report)


SEAGULL_BASE = FIXTURES / "seagull" / "base_invented.xml"
MINE = """<dictionary><vendor id="0" name="base">
  <avp name="Sess-Id" code="263" mandatory="must" protected="may" may-encrypt="yes" vendor-specific="no">
    <type type-name="UTF8String"/>
  </avp>
  <avp name="Invented-Extra" code="5555" mandatory="may" protected="may" may-encrypt="yes" vendor-specific="no">
    <type type-name="Unsigned32"/>
  </avp>
</vendor></dictionary>
"""


class BaseProtocolTest(unittest.TestCase):
    """The base protocol is found by its content, and missing items can come from Seagull."""

    def folder(self, *names: str) -> tuple[Path, Path]:
        """Return a new folder with the named fixture dictionaries, and the path of an output."""
        root = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        source = root / "dictionaries"
        source.mkdir()
        for name in names:
            shutil.copy(FIXTURES / "dictionaries" / name, source)
        return source, root / "out"

    def test_base_is_found_by_its_content_and_not_by_its_name(self) -> None:
        """A base protocol in a file with another name is used, and the report says so."""
        source, out = self.folder("DiameterBaseProtocol.xml", "Gy.xml")
        (source / "DiameterBaseProtocol.xml").rename(source / "Base.xml")
        status, text, error = run_convert([str(source), "--out", str(out)])
        self.assertEqual(status, 0, error)
        self.assertIn("NOTE the base protocol is taken from Base (found by its commands)", text)
        self.assertEqual(defined_flags(out / "diameter-dictionary.xml", "CER"), 128)

    def two_dictionaries(self) -> tuple[Path, Path]:
        """Return a folder with the base protocol, Gy, and Mine, and the path of an output."""
        source, out = self.folder("DiameterBaseProtocol.xml", "Gy.xml")
        (source / "Mine.xml").write_text(MINE, encoding="utf-8")
        return source, out

    def test_by_default_all_dictionaries_go_into_one_file(self) -> None:
        """Without --combine, and with yes, one file holds every dictionary and the base."""
        for extra in ([], ["--combine", "yes"]):
            source, out = self.two_dictionaries()
            status, _, error = run_convert([str(source), "--out", str(out), *extra])
            self.assertEqual(status, 0, error)
            self.assertEqual(
                sorted(p.name for p in out.glob("*.xml")),
                ["diameter-dictionary.xml"],
            )
            text = (out / "diameter-dictionary.xml").read_text(encoding="iso-8859-1")
            self.assertIn('name="Sess-Id"', text)
            self.assertIn('name="3GPP-Charging-Id"', text)
            self.assertEqual(defined_flags(out / "diameter-dictionary.xml", "CER"), 128)

    def test_combine_no_writes_one_file_for_each_dictionary(self) -> None:
        """With no, each AVP dictionary is its own file, and the base protocol alone is not."""
        source, out = self.two_dictionaries()
        status, _, error = run_convert([str(source), "--out", str(out), "--combine", "no"])
        self.assertEqual(status, 0, error)
        self.assertEqual(sorted(p.name for p in out.glob("*.xml")), ["Gy.xml", "Mine.xml"])
        self.assertEqual(defined_flags(out / "Gy.xml", "CER"), 128)

    def test_a_list_writes_only_the_merged_file_in_that_order(self) -> None:
        """A list of names makes one file from those dictionaries, and nothing else."""
        source, out = self.two_dictionaries()
        argv = [str(source), "--out", str(out), "--combine", "Mine,Gy"]
        status, _, error = run_convert(argv)
        self.assertEqual(status, 0, error)
        self.assertEqual(sorted(p.name for p in out.glob("*.xml")), ["Mine+Gy.xml"])

    def test_an_unknown_name_in_a_list_is_refused(self) -> None:
        """A name that is no dictionary of the folder stops the run before any file."""
        source, out = self.two_dictionaries()
        status, _, error = run_convert([str(source), "--out", str(out), "--combine", "Gy,Nope"])
        self.assertEqual(status, 2)
        self.assertIn("unknown dictionary in --combine: ['Nope']", error)

    def test_missing_base_lists_the_codes_and_offers_the_choice(self) -> None:
        """Without the base protocol nothing is written; the message names codes and options."""
        source, out = self.folder("Gy.xml")
        status, _, error = run_convert([str(source), "--out", str(out)])
        self.assertEqual(status, 2)
        self.assertIn("missing AVP 257 (Host-IP-Address)", error)
        self.assertIn("command 280 (DWR/DWA)", error)
        self.assertIn("--seagull-base", error)
        self.assertFalse(out.exists())

    def test_seagull_dictionary_supplies_the_base_protocol(self) -> None:
        """The base protocol of the Seagull dictionary is added, and the report says so."""
        source, out = self.folder("Gy.xml")
        argv = [str(source), "--out", str(out), "--seagull-base", str(SEAGULL_BASE)]
        status, text, error = run_convert(argv)
        self.assertEqual(status, 0, error)
        self.assertIn("added 13 AVPs and 2 command pairs from base_invented.xml", text)
        self.assertIn("may be wrong in places", text)
        gy = out / "diameter-dictionary.xml"
        self.assertEqual((defined_flags(gy, "CER"), defined_flags(gy, "Origin-Host")), (128, 64))
        self.assertEqual(defined_flags(gy, "Destination-Realm"), 64)

    def test_the_users_dictionary_wins_over_the_seagull_one(self) -> None:
        """A name or a code defined by the user keeps the user's definition; nothing is renamed."""
        source, out = self.folder("Gy.xml")
        (source / "Mine.xml").write_text(MINE, encoding="utf-8")
        argv = [str(source), "--out", str(out), "--combine", "Gy,Mine"]
        argv += ["--seagull-base", str(SEAGULL_BASE)]
        status, _, error = run_convert(argv)
        text = (out / "Gy+Mine.xml").read_text(encoding="iso-8859-1")
        self.assertEqual(status, 0, error)
        self.assertIn('name="Sess-Id"', text)
        self.assertNotIn('name="Session-Id"', text)
        self.assertIn('name="Invented-Extra" type="Unsigned32">', text)
        self.assertIn('value="5555"', text)
        self.assertNotIn('value="9001"', text)

    def test_a_name_taken_with_another_code_is_not_filled(self) -> None:
        """A user's AVP with the name of a required base AVP under another code leaves the gap."""
        source, out = self.folder("Gy.xml")
        taken = MINE.replace('name="Sess-Id" code="263"', 'name="Origin-Host" code="9999"')
        (source / "Mine.xml").write_text(taken, encoding="utf-8")
        argv = [str(source), "--out", str(out), "--seagull-base", str(SEAGULL_BASE)]
        status, _, error = run_convert(argv)
        self.assertEqual(status, 2)
        self.assertIn("does not supply them either", error)
        self.assertIn("AVP 264 (Origin-Host)", error)
        self.assertFalse(out.exists())

    def test_generation_works_from_a_dictionary_with_the_seagull_base(self) -> None:
        """The scenarios are generated from a dictionary that got its base from Seagull."""
        source, out = self.folder("Gy.xml")
        converted = out.parent / "converted"
        argv = [str(source), "--out", str(converted), "--seagull-base", str(SEAGULL_BASE)]
        self.assertEqual(run_convert(argv)[0], 0)
        generate = importlib.import_module("generate_scenarios")
        dictionary = converted / "diameter-dictionary.xml"
        argv = ["--steps", str(FIXTURES / "steps"), "--dictionary", str(dictionary)]
        argv += ["--out", str(out)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(generate.main(argv), 0)
        self.assertEqual(defined_flags(out / "dictionary" / "diameter-dictionary.xml", "CER"), 128)

    def test_exporter_copies_the_file_from_a_windows_installation(self) -> None:
        """export_seagull_base.py copies base_draft08.xml from next to seagull.exe."""
        exporter = importlib.import_module("export_seagull_base")
        root = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        config = root / "Seagull" / "diameter-env" / "config"
        config.mkdir(parents=True)
        (root / "Seagull" / "seagull.exe").write_bytes(b"")
        shutil.copy(SEAGULL_BASE, config / "base_draft08.xml")
        out = root / "base.xml"
        exe = root / "Seagull" / "seagull.exe"
        argv = ["--runner", "windows", "--seagull-exe", str(exe), "--out", str(out)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(exporter.main(argv), 0)
        self.assertEqual(out.read_bytes(), SEAGULL_BASE.read_bytes())
        (config / "base_draft08.xml").unlink()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(exporter.main(argv), 2)


def defined_flags(path: Path, name: str) -> int:
    """Return the flags value of the AVP or command definition with the name."""
    root = ElementTree.parse(path).getroot()
    for define in root.iter("define"):
        if define.get("name") == name:
            fields = {s.get("name"): s.get("value") for s in define.findall("setfield")}
            return int(fields["flags"] or 0)
    raise AssertionError(f"{path.name} defines no {name}")


class FlagOptionsTest(unittest.TestCase):
    """The flags of commands and AVPs follow the options, and default to the source."""

    def convert_with(self, *extra: str) -> tuple[int, Path, str, str]:
        """Convert the fixtures into a new folder; return the status, the folder, and the output."""
        folder = tempfile.mkdtemp(prefix="seagull-selftest-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        out = Path(folder) / "out"
        source = str(FIXTURES / "dictionaries")
        status, text, error = run_convert([source, "--out", str(out), *extra])
        return status, out, text, error

    def test_default_flags_are_the_converters_own(self) -> None:
        """Requests get 128, answers 0, and an AVP gets the V and M bits of its source."""
        status, out, text, _ = self.convert_with()
        self.assertEqual(status, 0)
        gy = out / "diameter-dictionary.xml"
        self.assertEqual((defined_flags(gy, "CCR"), defined_flags(gy, "CCA")), (128, 0))
        self.assertEqual(defined_flags(gy, "3GPP-Charging-Id"), 192)
        self.assertNotIn("NOTE", text)

    def test_command_flags_by_name_and_by_direction(self) -> None:
        """CCR=192 changes one request; answer=64 changes every answer that is not named."""
        pairs = ("--command-flags", "CCR=192", "--command-flags", "answer=64")
        _, out, text, _ = self.convert_with(*pairs)
        gy = out / "diameter-dictionary.xml"
        self.assertEqual((defined_flags(gy, "CCR"), defined_flags(gy, "CER")), (192, 128))
        self.assertEqual((defined_flags(gy, "CCA"), defined_flags(gy, "CEA")), (64, 64))
        self.assertIn("NOTE CCR: flags 192 (the converter's default is 128)", text)

    def test_avp_flags_by_name(self) -> None:
        """An AVP named in --avp-flags gets those flags; the report says what the source gave."""
        _, out, text, _ = self.convert_with("--avp-flags", "3GPP-Charging-Id=128")
        self.assertEqual(defined_flags(out / "diameter-dictionary.xml", "3GPP-Charging-Id"), 128)
        self.assertEqual(defined_flags(out / "diameter-dictionary.xml", "Subscription-Id"), 64)
        self.assertIn("NOTE 3GPP-Charging-Id: flags 128 (the source gives 192)", text)

    def test_vendor_mandatory_no_clears_m_on_vendor_avps_only(self) -> None:
        """The policy changes the M bit of vendor AVPs and leaves the others as they are."""
        _, out, text, _ = self.convert_with("--vendor-mandatory", "no")
        gy = out / "diameter-dictionary.xml"
        self.assertEqual(defined_flags(gy, "3GPP-Charging-Id"), 128)
        self.assertEqual(defined_flags(gy, "Subscription-Id"), 64)
        self.assertIn("NOTE vendor-mandatory=no: changed the M bit of 7 of 7 vendor AVPs", text)

    def test_avp_flags_win_over_the_policy(self) -> None:
        """A named AVP keeps its own flags whatever the policy says."""
        pairs = ("--vendor-mandatory", "no", "--avp-flags", "3GPP-Charging-Id=192")
        _, out, _, _ = self.convert_with(*pairs)
        gy = out / "diameter-dictionary.xml"
        flags = [defined_flags(gy, name) for name in ("3GPP-Charging-Id", "SGSN-Address")]
        self.assertEqual(flags, [192, 128])

    def test_options_file_repeats_the_run(self) -> None:
        """The file that a run writes gives the same dictionaries when the next run reads it."""
        _, first, _, _ = self.convert_with("--command-flags", "CCR=192", "--vendor-mandatory", "no")
        saved = (first / "dictionary-options.ini").read_text(encoding="utf-8")
        _, second, _, _ = self.convert_with("--options", str(first / "dictionary-options.ini"))
        self.assertIn("CCR = 192", saved)
        self.assertEqual(
            (first / "diameter-dictionary.xml").read_text(encoding="iso-8859-1"),
            (second / "diameter-dictionary.xml").read_text(encoding="iso-8859-1"),
        )

    def test_xsd_folder_is_kept_for_the_validation_step(self) -> None:
        """--xsd-dir is written to the options file and kept by the next run; output is the same."""
        _, first, _, _ = self.convert_with("--xsd-dir", "/data/xsd")
        ini = first / "dictionary-options.ini"
        _, second, _, _ = self.convert_with("--options", str(ini))
        _, plain, _, _ = self.convert_with()
        saved = ini.read_text(encoding="utf-8")
        kept = (second / "dictionary-options.ini").read_text(encoding="utf-8")
        default = (plain / "dictionary-options.ini").read_text(encoding="utf-8")
        self.assertIn("[validate]\nxsd = /data/xsd\n", saved)
        self.assertIn("xsd = /data/xsd", kept)
        self.assertNotIn("[validate]", default)
        self.assertEqual(
            (first / "diameter-dictionary.xml").read_text(encoding="iso-8859-1"),
            (plain / "diameter-dictionary.xml").read_text(encoding="iso-8859-1"),
        )

    def test_validate_commands_is_kept_for_the_validation_step(self) -> None:
        """--validate-commands yes is written to the options file and kept by the next run."""
        _, first, _, _ = self.convert_with("--validate-commands", "yes", "--xsd-dir", "/data/xsd")
        ini = first / "dictionary-options.ini"
        _, second, _, _ = self.convert_with("--options", str(ini))
        _, off, _, _ = self.convert_with("--options", str(ini), "--validate-commands", "no")
        saved = ini.read_text(encoding="utf-8")
        self.assertIn("[validate]\nxsd = /data/xsd\ncommands = yes\n", saved)
        self.assertIn("commands = yes", (second / "dictionary-options.ini").read_text("utf-8"))
        self.assertNotIn("commands", (off / "dictionary-options.ini").read_text("utf-8"))

    def test_validate_commands_must_be_yes_or_no(self) -> None:
        """An options file with another value stops the run before any file is written."""
        folder = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        ini = folder / "options.ini"
        ini.write_text("[validate]\ncommands = maybe\n", encoding="utf-8")
        status, out, _, error = self.convert_with("--options", str(ini))
        self.assertEqual(status, 2)
        self.assertIn("'maybe' is not yes or no", error)
        self.assertFalse(out.exists())

    def test_list_sources_names_the_files_and_writes_nothing(self) -> None:
        """The base protocol comes first, then the dictionaries of the result, once each."""
        source = str(FIXTURES / "dictionaries")
        for extra in ([], ["--combine", "Gy"], ["--combine", "Gy,DiameterBaseProtocol"]):
            status, text, _ = run_convert([source, "--list-sources", *extra])
            self.assertEqual(status, 0)
            self.assertEqual(text.split(), ["DiameterBaseProtocol.xml", "Gy.xml"])

    def test_list_sources_refuses_an_unknown_dictionary(self) -> None:
        """A name that is not in the folder is refused, as it is in a conversion."""
        source = str(FIXTURES / "dictionaries")
        status, _, error = run_convert([source, "--list-sources", "--combine", "Nope"])
        self.assertEqual(status, 2)
        self.assertIn("unknown dictionary in --combine: ['Nope']", error)

    def test_a_name_that_matches_nothing_is_a_warning(self) -> None:
        """A misspelled AVP or command is reported and does not stop the conversion."""
        pairs = ("--avp-flags", "No-Such-Avp=64", "--command-flags", "XYZ=1")
        status, _, text, _ = self.convert_with(*pairs)
        self.assertEqual(status, 0)
        self.assertIn("WARNING --avp-flags No-Such-Avp: no AVP has that name", text)
        self.assertIn("WARNING --command-flags XYZ: no command has that name", text)

    def test_flags_that_contradict_the_v_bit_are_refused(self) -> None:
        """A vendor AVP without the V bit stops the run before any file is written."""
        status, out, _, error = self.convert_with("--avp-flags", "3GPP-Charging-Id=64")
        self.assertEqual(status, 2)
        self.assertIn("contradict the V bit", error)
        self.assertFalse(out.exists())

    def test_a_flags_value_outside_a_byte_is_refused(self) -> None:
        """A flags value must be a number from 0 to 255."""
        status, _, _, error = self.convert_with("--command-flags", "CCR=300")
        self.assertEqual(status, 2)
        self.assertIn("is not a flags byte", error)


# The AVPs that the client of the check sends and the fixture dictionaries lack.
EXTRA_AVPS: dict[int, list[tuple[str, int, str | None]]] = {
    0: [
        ("Multiple-Services-Credit-Control", 456, None),
        ("Rating-Group", 432, "Unsigned32"),
        ("Called-Station-Id", 30, "UTF8String"),
    ],
    10415: [
        ("Dynamic-Address-Flag", 2051, "Enumerated"),
        ("Serving-Node-Type", 2047, "Enumerated"),
        ("TGPP-PDP-Type", 3, "Enumerated"),
        ("PDP-Address", 1227, "Address"),
        ("GGSN-Address", 847, "Address"),
        ("TGPP-IMSI-MCC-MNC", 8, "UTF8String"),
        ("TGPP-GGSN-MCC-MNC", 9, "UTF8String"),
        ("TGPP-SGSN-MCC-MNC", 18, "UTF8String"),
        ("TGPP-NSAPI", 10, "OctetString"),
        ("TGPP-Selection-Mode", 12, "UTF8String"),
        ("TGPP-RAT-Type", 21, "OctetString"),
    ],
}


def extra_dictionary() -> str:
    """Return a project-format dictionary of EXTRA_AVPS."""
    lines = ["<dictionary>"]
    for vendor, avps in EXTRA_AVPS.items():
        vendor_name = "TGPP" if vendor else "base"
        specific = "yes" if vendor else "no"
        flags = f'mandatory="must" protected="may" may-encrypt="yes" vendor-specific="{specific}"'
        lines.append(f'  <vendor id="{vendor}" name="{vendor_name}">')
        for name, code, kind in avps:
            body = "<grouped/>" if kind is None else f'<type type-name="{kind}"/>'
            lines.append(f'    <avp name="{name}" code="{code}" {flags}>')
            lines.append(f"      {body}")
            lines.append("    </avp>")
        lines.append("  </vendor>")
    return "\n".join([*lines, "</dictionary>", ""])


@unittest.skipUnless(IMAGE, "set SEAGULL_IMAGE for the check in the image")
class CheckConvertedTest(unittest.TestCase):
    """Seagull loads a converted dictionary and completes a Credit-Control exchange with it."""

    def test_check_converted(self) -> None:
        """check-converted.sh reports 1 successful call and 0 failed calls."""
        script = CONVERT_DIR / "check-converted.sh"
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            source = Path(folder) / "dictionaries"
            shutil.copytree(FIXTURES / "dictionaries", source)
            (source / "Extra.xml").write_text(extra_dictionary(), encoding="utf-8")
            out = Path(folder) / "converted"
            argv = [str(source), "--out", str(out), "--combine", "Gy,Extra"]
            status, _, error = run_convert(argv)
            self.assertEqual(status, 0, error)
            checked = Path(folder) / "checked"
            checked.mkdir()
            shutil.copy(out / "Gy+Extra.xml", checked)
            command = ["sh", str(script), str(checked), IMAGE]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Gy+Extra: successful calls: 1, failed calls: 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
