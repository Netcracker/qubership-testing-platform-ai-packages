"""Self-test of the log-to-XML script of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It converts tests/fixtures/logs/sample.client, which holds a received DWR that the client
answers with a sent DWA, and a sent CCR with its answer. The log names its dictionary with the
placeholder @DICTIONARY@, which each test replaces by a path in a copy of the log. The
dictionary is tests/fixtures/seagull/log_dictionary.xml. The tests check the file names under
both numberings, the XML of both formats, and the choice of the dictionary.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import importlib
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from xml.etree import ElementTree

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LOG = FIXTURES / "logs" / "sample.client"
DICTIONARY = FIXTURES / "seagull" / "log_dictionary.xml"
MISSING = "/no/such/dictionary.xml"
log_to_xml = importlib.import_module("log_to_xml")


def convert(*extra: str, logged: str | None = None) -> tuple[int, Path, str]:
    """Convert a copy of the sample log; return the status, the output folder, the errors.

    The copy names logged as its dictionary, which is the fixture dictionary by default.
    """
    work = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
    log = work / "sample.client"
    text = LOG.read_text(encoding="utf-8").replace("@DICTIONARY@", logged or str(DICTIONARY))
    log.write_text(text, encoding="utf-8")
    out = work / "xml"
    errors = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(errors):
        status = log_to_xml.main([str(log), "--out", str(out), *extra])
    return status, out, errors.getvalue()


class LogToXmlTest(unittest.TestCase):
    """The script names the files by step or by sequence and keeps the AVP tree."""

    def names(self, *extra: str) -> list[str]:
        """Return the sorted file names that a conversion writes."""
        status, out, errors = convert(*extra)
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        self.assertEqual((status, errors), (0, ""))
        return sorted(path.name for path in out.iterdir())

    def test_a_request_and_its_answer_share_a_number_by_default(self) -> None:
        """The received DWR and the sent DWA are step 1, the sent CCR and received CCA step 2."""
        self.assertEqual(
            self.names(),
            [
                "001_received_DWR.xml",
                "001_sent_DWA.xml",
                "002_received_CCA.xml",
                "002_sent_CCR.xml",
            ],
        )

    def test_sequence_numbering_follows_the_log_order(self) -> None:
        """The messages are numbered 1 to 4 in the order of the log."""
        self.assertEqual(
            self.names("--numbering", "sequence"),
            [
                "001_received_DWR.xml",
                "002_sent_DWA.xml",
                "003_sent_CCR.xml",
                "004_received_CCA.xml",
            ],
        )

    def test_avp_tree_is_kept(self) -> None:
        """A group holds its children, and a hex value, a vendor, and the text are attributes."""
        _, out, _ = convert()
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(root.get("name"), "CCR")
        self.assertEqual(root.find("header").get("HbH-id"), "1")  # type: ignore[union-attr]
        group, vendor = root.findall("avp")[:2]
        data = group.findall("avp")[1]
        self.assertEqual(data.get("name"), "Subscription-Id-Data")
        self.assertEqual((data.get("hex"), data.get("text")), ("39 36 36", "966"))
        self.assertEqual(group.findall("avp")[0].get("value"), "0")
        self.assertEqual(vendor.get("vendor-id"), "10415")
        self.assertIsNone(vendor.get("text"))

    def test_pretty_printing_can_be_switched_off(self) -> None:
        """By default a file has many lines; with --no-pretty the steps format has one."""
        _, pretty, _ = convert("--format", "steps")
        _, plain, _ = convert("--format", "steps", "--no-pretty")
        self.addCleanup(shutil.rmtree, pretty.parent, ignore_errors=True)
        self.addCleanup(shutil.rmtree, plain.parent, ignore_errors=True)
        many = (pretty / "002_sent_CCR.xml").read_text(encoding="utf-8").splitlines()
        one = (plain / "002_sent_CCR.xml").read_text(encoding="utf-8").splitlines()
        self.assertGreater(len(many), 1)
        self.assertEqual(len(one), 1)

    def test_non_empty_output_folder_is_refused(self) -> None:
        """A folder that holds a file is not written into; the exit status is 2."""
        out = Path(tempfile.mkdtemp(prefix="seagull-selftest-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        (out / "old.txt").write_text("old", encoding="utf-8")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            status = log_to_xml.main([str(LOG), "--out", str(out)])
        self.assertEqual(status, 2)
        self.assertEqual([path.name for path in out.iterdir()], ["old.txt"])

    def test_seconds_since_1900_become_a_date(self) -> None:
        """The date format is the one of the recorded steps."""
        self.assertEqual(log_to_xml.ntp_date(4002098452), "2026-10-27 14:00:52 +0000 UTC")


class StepsFormatTest(unittest.TestCase):
    """The steps format writes each value by the type that the dictionary gives."""

    def steps(self, *extra: str, logged: str | None = None) -> tuple[int, Path, str]:
        """Convert to the steps format; return the status, the output folder, the errors."""
        status, out, errors = convert("--format", "steps", *extra, logged=logged)
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        return status, out, errors

    def test_the_dictionary_of_the_log_is_used_without_a_word(self) -> None:
        """The command is the root, a group holds its members, and each type has its form."""
        status, out, errors = self.steps()
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(status, 0)
        self.assertEqual(root.tag, "CCR")
        self.assertEqual(root.attrib, {})
        self.assertEqual(root.findtext("Subscription-Id/Subscription-Id-Data"), "966")
        self.assertEqual(root.findtext("Event-Timestamp"), "2026-10-27 14:00:52 +0000 UTC")
        self.assertEqual(root.findtext("Origin-Host"), "host")
        self.assertEqual(root.findtext("Host-IP-Address"), "192.0.2.10")
        self.assertEqual(ElementTree.parse(out / "002_received_CCA.xml").getroot().tag, "CCA")
        self.assertEqual(errors, "not in the dictionary, written by their bytes: Unlisted-Avp\n")

    def test_an_enumerated_value_is_its_name_when_the_dictionary_lists_names(self) -> None:
        """CC-Request-Type has names in the dictionary, Subscription-Id-Type has none."""
        _, out, _ = self.steps()
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(root.findtext("CC-Request-Type"), "INITIAL_REQUEST")
        self.assertEqual(root.findtext("Subscription-Id/Subscription-Id-Type"), "0")

    def test_the_definition_is_found_by_vendor_and_code(self) -> None:
        """Two MSC-Address AVPs of different vendors are a text and an OctetString."""
        _, out, _ = self.steps()
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual([e.text for e in root.findall("MSC-Address")], ["96", "0xff00"])
        self.assertEqual(root.findtext("TGPP-MS-TimeZone"), "0x2100")

    def test_an_avp_that_the_dictionary_lacks_is_written_by_its_bytes_and_listed(self) -> None:
        """Unlisted-Avp is text, because its bytes are printable, and stderr names it."""
        _, out, errors = self.steps()
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(root.findtext("Unlisted-Avp"), "ab")
        self.assertIn("Unlisted-Avp", errors)

    def test_dictionary_option_is_ignored_when_the_dictionary_of_the_log_exists(self) -> None:
        """The log names an existing file, so --dictionary changes nothing and stderr says so."""
        other = Path(tempfile.mkdtemp(prefix="seagull-selftest-")) / "other.xml"
        self.addCleanup(shutil.rmtree, other.parent, ignore_errors=True)
        status, out, errors = self.steps("--dictionary", str(other))
        self.assertEqual(status, 0)
        self.assertIn("--dictionary is ignored", errors)
        self.assertTrue((out / "002_sent_CCR.xml").is_file())

    def test_dictionary_option_replaces_a_missing_dictionary_of_the_log(self) -> None:
        """A path of another machine is missing here; --dictionary is used and stderr says so."""
        status, out, errors = self.steps("--dictionary", str(DICTIONARY), logged=MISSING)
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(status, 0)
        self.assertEqual(root.findtext("CC-Request-Type"), "INITIAL_REQUEST")
        self.assertIn(f"{MISSING}, does not exist", errors)
        self.assertIn("using the dictionary of --dictionary", errors)

    def test_no_dictionary_stops_the_run_and_writes_nothing(self) -> None:
        """Without a usable file the status is 3, and the output folder is not created."""
        status, out, errors = self.steps(logged=MISSING)
        self.assertEqual(status, 3)
        self.assertFalse(out.exists())
        self.assertIn("no dictionary for --format steps", errors)

    def test_missing_dictionary_option_file_is_reported(self) -> None:
        """A --dictionary that is not a file does not rescue the run; stderr names it."""
        status, _, errors = self.steps("--dictionary", "/no/such/other.xml", logged=MISSING)
        self.assertEqual(status, 3)
        self.assertIn(f"--dictionary {Path('/no/such/other.xml')} is not a file", errors)

    def test_avp_format_ignores_the_dictionary_option(self) -> None:
        """The avp format shows what Seagull printed, so it needs no dictionary."""
        status, out, errors = convert("--dictionary", str(DICTIONARY), logged=MISSING)
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        self.assertEqual(status, 0)
        self.assertIn("the avp format does not use a dictionary", errors)


if __name__ == "__main__":
    unittest.main()
