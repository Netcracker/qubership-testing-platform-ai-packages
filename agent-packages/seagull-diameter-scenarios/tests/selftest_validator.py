"""Self-test of the XSD validator of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It runs ValidateDictionaries.java on small invented dictionaries and schemas: how the schema of
a file is chosen (its own reference, the name of the reference in --xsd-dir, the root element),
what happens when none is found, and the exit statuses. The tests need `java` (Java 11 or later)
on PATH or JAVA_HOME and are skipped without it.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / ".apm" / "skills"
VALIDATOR = SKILLS / "seagull-diameter-dictionary-convert" / "scripts" / "ValidateDictionaries.java"
JAVA = shutil.which("java") or (
    str(Path(os.environ["JAVA_HOME"]) / "bin" / "java") if os.environ.get("JAVA_HOME") else ""
)

XS = "http://www.w3.org/2001/XMLSchema"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
NAME = '<xs:attribute name="name" type="xs:string" use="required"/>'
AVP_SCHEMA = f"""<xs:schema xmlns:xs="{XS}">
  <xs:element name="dictionary">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="avp" maxOccurs="unbounded">
          <xs:complexType>{NAME}</xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""
# The command schema nests an element that is also called "dictionary". Only the global
# elements of a schema name the root elements that it describes.
COMMAND_SCHEMA = f"""<xs:schema xmlns:xs="{XS}">
  <xs:element name="diameter-command-dictionary">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="dictionary">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="command" maxOccurs="unbounded">
                <xs:complexType>{NAME}</xs:complexType>
              </xs:element>
            </xs:sequence>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""
BAD_AVP = "<dictionary><avp/></dictionary>\n"


def reference(location: str) -> str:
    """Return the attributes of a root element that name a schema."""
    if not location:
        return ""
    return f' xmlns:xsi="{XSI}" xsi:noNamespaceSchemaLocation="{location}"'


def avp_file(location: str = "") -> str:
    """Return a valid AVP dictionary, with a schema reference when a location is given."""
    return f'<dictionary{reference(location)}><avp name="A"/></dictionary>\n'


def command_file(location: str = "") -> str:
    """Return a valid command dictionary, with a schema reference when a location is given."""
    body = '<dictionary><command name="C"/></dictionary>'
    root = f"diameter-command-dictionary{reference(location)}"
    return f"<{root}>{body}</diameter-command-dictionary>\n"


@unittest.skipUnless(JAVA, "set JAVA_HOME or put java on PATH for the validator tests")
class ValidatorTest(unittest.TestCase):
    """ValidateDictionaries.java chooses a schema for each file, or says that it cannot."""

    def setUp(self) -> None:
        """Make dict/ for the dictionaries and schemas/ with two schemas of other names."""
        folder = tempfile.mkdtemp(prefix="seagull-selftest-")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self.root = Path(folder)
        self.dictionaries = self.root / "dict"
        self.schemas = self.root / "schemas"
        self.dictionaries.mkdir()
        self.schemas.mkdir()
        (self.schemas / "schema-a.xsd").write_text(AVP_SCHEMA, encoding="utf-8")
        (self.schemas / "schema-b.xsd").write_text(COMMAND_SCHEMA, encoding="utf-8")

    def put(self, name: str, text: str) -> None:
        """Write a dictionary file."""
        (self.dictionaries / name).write_text(text, encoding="utf-8")

    def run_validator(self, *args: str) -> tuple[int, str]:
        """Run the validator on the dictionaries folder; return the exit status and the output."""
        command = [JAVA, str(VALIDATOR), *args, str(self.dictionaries)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout + result.stderr

    def test_file_without_a_reference_needs_an_xsd_dir(self) -> None:
        """A file with no schema reference stops the run when --xsd-dir is not given."""
        self.put("Good.xml", avp_file())
        status, output = self.run_validator()
        self.assertEqual(status, 3)
        self.assertIn("NO SCHEMA Good.xml (dictionary): the file has no schema reference", output)

    def test_reference_is_resolved_against_the_folder_of_the_file(self) -> None:
        """A reference that names an existing file is used, wherever that file is."""
        self.put("Good.xml", avp_file("../schemas/schema-a.xsd"))
        status, output = self.run_validator()
        self.assertEqual(status, 0, output)
        self.assertIn("Good.xml (dictionary): valid", output)
        self.assertIn("schema-a.xsd", output)

    def test_one_missing_reference_is_listed_once(self) -> None:
        """Files that share an unresolved reference give one problem, with the file count."""
        for name in ("OneCommands.xml", "TwoCommands.xml"):
            self.put(name, command_file("xsd/diameter-command.xsd"))
        status, output = self.run_validator()
        self.assertEqual(status, 3)
        self.assertIn("1 distinct problem(s) in 2 file(s)", output)
        self.assertIn("the reference xsd/diameter-command.xsd does not resolve", output)

    def test_xsd_dir_chooses_by_root_element_and_not_by_file_name(self) -> None:
        """The schemas have other names than the reference, so the root element decides."""
        self.put("Good.xml", avp_file())
        self.put("GoodCommands.xml", command_file("xsd/diameter-command.xsd"))
        status, output = self.run_validator("--plan", "--xsd-dir", str(self.schemas))
        self.assertEqual(status, 0, output)
        lines = {line.split(" (")[0]: line for line in output.splitlines()}
        self.assertIn("schema-a.xsd", lines["Good.xml"])
        self.assertIn("schema-b.xsd", lines["GoodCommands.xml"])

    def test_a_nested_element_does_not_make_a_schema_a_candidate(self) -> None:
        """schema-b.xsd has a nested <dictionary>, which must not capture a <dictionary> file."""
        self.put("Good.xml", avp_file())
        status, output = self.run_validator("--xsd-dir", str(self.schemas))
        self.assertEqual(status, 0, output)
        self.assertIn("schema-a.xsd", output)
        self.assertNotIn("schema-b.xsd", output)

    def test_an_invalid_file_gives_status_1(self) -> None:
        """A file that breaks its schema is reported with the error, and the status is 1."""
        self.put("Bad.xml", BAD_AVP)
        status, output = self.run_validator("--xsd-dir", str(self.schemas))
        self.assertEqual(status, 1)
        self.assertIn("Bad.xml (dictionary): 1 errors", output)
        self.assertIn("1 of 1 files are invalid", output)

    def test_two_schemas_for_one_root_are_reported(self) -> None:
        """When two schemas declare the root element, the validator names both."""
        shutil.copy(self.schemas / "schema-a.xsd", self.schemas / "schema-a2.xsd")
        self.put("Good.xml", avp_file())
        status, output = self.run_validator("--xsd-dir", str(self.schemas))
        self.assertEqual(status, 3)
        self.assertIn("schema-a.xsd, schema-a2.xsd", output)

    def test_a_url_is_not_downloaded(self) -> None:
        """A reference that is a URL is a problem, and nothing is fetched."""
        self.put("Good.xml", avp_file("http://example.test/a.xsd"))
        status, output = self.run_validator()
        self.assertEqual(status, 3)
        self.assertIn("is a URL, and this program downloads nothing", output)

    def test_plan_validates_nothing(self) -> None:
        """--plan prints the schema of each file and does not report errors of an invalid one."""
        self.put("Bad.xml", BAD_AVP)
        status, output = self.run_validator("--plan", "--xsd-dir", str(self.schemas))
        self.assertEqual(status, 0, output)
        self.assertIn("chosen by", output)
        self.assertNotIn("errors", output)


if __name__ == "__main__":
    unittest.main()
