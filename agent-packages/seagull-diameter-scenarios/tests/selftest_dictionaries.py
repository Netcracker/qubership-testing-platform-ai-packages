"""Self-test of the dictionary conversion of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It converts the invented dictionaries in tests/fixtures: the output folder, the options
that reach the converter, the flags of commands and AVPs, and the options file. The check
of a converted dictionary in the Seagull image runs only when the environment variable
SEAGULL_IMAGE names an image and `sh` and `docker` work.

Requires Python 3.9 or later.
"""

from __future__ import annotations

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
convert = importlib.import_module("convert_dictionaries")
FIXTURES = Path(__file__).resolve().parent / "fixtures"
IMAGE = os.environ.get("SEAGULL_IMAGE", "")


def run_convert(argv: list[str]) -> tuple[int, str, str]:
    """Run convert_dictionaries.py; return the exit status, its output, and its error output."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = convert.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


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
        expected = [
            "DiameterBaseProtocol.xml",
            "Gy.xml",
            "conversion-report.txt",
            "dictionary-options.ini",
        ]
        self.assertEqual(files, expected)

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
                texts[name] = (out / "Gy.xml").read_text(encoding="utf-8")
        self.assertIn('name="3GPP-Charging-Id"', texts["plain"])
        self.assertIn('name="TGPP-Charging-Id"', texts["kept"])

    def test_missing_base_protocol_writes_nothing(self) -> None:
        """Without DiameterBaseProtocol.xml the status is 2 and no folder is created."""
        with tempfile.TemporaryDirectory(prefix="seagull-selftest-") as folder:
            source = Path(folder) / "dictionaries"
            source.mkdir()
            shutil.copy(FIXTURES / "dictionaries" / "Gy.xml", source)
            out = Path(folder) / "out"
            status, _, error = run_convert([str(source), "--out", str(out)])
            created = out.exists()
        self.assertEqual(status, 2)
        self.assertIn("DiameterBaseProtocol.xml is required", error)
        self.assertFalse(created)


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
        gy = out / "Gy.xml"
        self.assertEqual((defined_flags(gy, "CCR"), defined_flags(gy, "CCA")), (128, 0))
        self.assertEqual(defined_flags(gy, "3GPP-Charging-Id"), 192)
        self.assertNotIn("NOTE", text)

    def test_command_flags_by_name_and_by_direction(self) -> None:
        """CCR=192 changes one request; answer=64 changes every answer that is not named."""
        pairs = ("--command-flags", "CCR=192", "--command-flags", "answer=64")
        _, out, text, _ = self.convert_with(*pairs)
        gy = out / "Gy.xml"
        self.assertEqual((defined_flags(gy, "CCR"), defined_flags(gy, "CER")), (192, 128))
        self.assertEqual((defined_flags(gy, "CCA"), defined_flags(gy, "CEA")), (64, 64))
        self.assertIn("NOTE CCR: flags 192 (the converter's default is 128)", text)

    def test_avp_flags_by_name(self) -> None:
        """An AVP named in --avp-flags gets those flags; the report says what the source gave."""
        _, out, text, _ = self.convert_with("--avp-flags", "3GPP-Charging-Id=128")
        self.assertEqual(defined_flags(out / "Gy.xml", "3GPP-Charging-Id"), 128)
        self.assertEqual(defined_flags(out / "Gy.xml", "Subscription-Id"), 64)
        self.assertIn("NOTE 3GPP-Charging-Id: flags 128 (the source gives 192)", text)

    def test_vendor_mandatory_no_clears_m_on_vendor_avps_only(self) -> None:
        """The policy changes the M bit of vendor AVPs and leaves the others as they are."""
        _, out, text, _ = self.convert_with("--vendor-mandatory", "no")
        gy = out / "Gy.xml"
        self.assertEqual(defined_flags(gy, "3GPP-Charging-Id"), 128)
        self.assertEqual(defined_flags(gy, "Subscription-Id"), 64)
        self.assertIn("NOTE vendor-mandatory=no: changed the M bit of 7 of 7 vendor AVPs", text)

    def test_avp_flags_win_over_the_policy(self) -> None:
        """A named AVP keeps its own flags whatever the policy says."""
        pairs = ("--vendor-mandatory", "no", "--avp-flags", "3GPP-Charging-Id=192")
        _, out, _, _ = self.convert_with(*pairs)
        gy = out / "Gy.xml"
        flags = [defined_flags(gy, name) for name in ("3GPP-Charging-Id", "SGSN-Address")]
        self.assertEqual(flags, [192, 128])

    def test_options_file_repeats_the_run(self) -> None:
        """The file that a run writes gives the same dictionaries when the next run reads it."""
        _, first, _, _ = self.convert_with("--command-flags", "CCR=192", "--vendor-mandatory", "no")
        saved = (first / "dictionary-options.ini").read_text(encoding="utf-8")
        _, second, _, _ = self.convert_with("--options", str(first / "dictionary-options.ini"))
        self.assertIn("CCR = 192", saved)
        self.assertEqual(
            (first / "Gy.xml").read_text(encoding="iso-8859-1"),
            (second / "Gy.xml").read_text(encoding="iso-8859-1"),
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
            (first / "Gy.xml").read_text(encoding="iso-8859-1"),
            (plain / "Gy.xml").read_text(encoding="iso-8859-1"),
        )

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
