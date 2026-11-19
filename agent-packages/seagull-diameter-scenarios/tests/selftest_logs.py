"""Self-test of the log-to-XML script of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It converts tests/fixtures/logs/sample.client, which holds a received DWR that the client
answers with a sent DWA, and a sent CCR with its answer, and checks the file names under
both numberings and the XML of a grouped AVP, a hex value, and a vendor AVP.

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

SKILLS = Path(__file__).resolve().parents[1] / ".apm" / "skills"
LOG = Path(__file__).resolve().parent / "fixtures" / "logs" / "sample.client"
log_to_xml = importlib.import_module("log_to_xml")


def convert(*extra: str) -> tuple[int, Path, str]:
    """Convert the sample log into a new folder; return the status, the folder, the errors."""
    out = Path(tempfile.mkdtemp(prefix="seagull-selftest-")) / "xml"
    errors = io.StringIO()
    with redirect_stdout(io.StringIO()), redirect_stderr(errors):
        status = log_to_xml.main([str(LOG), "--out", str(out), *extra])
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
        group, vendor = root.findall("avp")
        data = group.findall("avp")[1]
        self.assertEqual(data.get("name"), "Subscription-Id-Data")
        self.assertEqual((data.get("hex"), data.get("text")), ("39 36 36", "966"))
        self.assertEqual(group.findall("avp")[0].get("value"), "0")
        self.assertEqual(vendor.get("vendor-id"), "10415")
        self.assertIsNone(vendor.get("text"))

    def test_steps_format_is_the_form_of_the_recorded_steps(self) -> None:
        """The command is the root, a group holds its members, and non-text bytes are 0x hex."""
        _, out, _ = convert("--format", "steps")
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        root = ElementTree.parse(out / "002_sent_CCR.xml").getroot()
        self.assertEqual(root.tag, "CCR")
        self.assertEqual(root.attrib, {})
        self.assertEqual(root.findtext("Subscription-Id/Subscription-Id-Data"), "966")
        self.assertEqual(root.findtext("TGPP-MS-TimeZone"), "0x2100")
        self.assertEqual(ElementTree.parse(out / "002_received_CCA.xml").getroot().tag, "CCA")

    def test_event_timestamp_is_a_date_in_the_steps_format(self) -> None:
        """Seconds since 1900 become the date format of the recorded steps."""
        avp = log_to_xml.Avp("Event-Timestamp", "55", "64", "", value="4002098452")
        self.assertEqual(log_to_xml.steps_text(avp), "2026-10-27 14:00:52 +0000 UTC")

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


if __name__ == "__main__":
    unittest.main()
