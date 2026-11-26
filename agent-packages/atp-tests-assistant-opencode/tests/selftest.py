"""Self-test of atp-tests-assistant-opencode: its command files match the command skills.

Run: python tests/selftest.py

It compares .apm/prompts/ with the skills of the package atp-tests-assistant that only the
user starts, and checks the dependency on that package. It does not install anything.

Requires Python 3.9 or later.
"""

import re
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the package
PACKAGE = Path(__file__).resolve().parents[1]
MAIN = PACKAGE.parent / "atp-tests-assistant"
PROMPTS = PACKAGE / ".apm" / "prompts"


def front_matter(path, key):
    """Return the line of the front matter that starts with key, or "" when there is none."""
    block = path.read_text(encoding="utf-8").split("---", 2)[1]
    match = re.search(rf"^{key}: .*$", block, re.MULTILINE)
    return match.group(0) if match else ""


def command_skills():
    """Return {name: SKILL.md} of the skills that only the user starts."""
    return {
        path.parent.name: path
        for path in sorted((MAIN / ".apm" / "skills").glob("*/SKILL.md"))
        if front_matter(path, "disable-model-invocation") == "disable-model-invocation: true"
    }


class CommandCase(unittest.TestCase):
    """The command files and the dependency."""

    def test_there_is_one_command_file_for_each_command_skill(self):
        """A command skill without a file, or a file without a skill, fails."""
        names = sorted(path.name.removesuffix(".prompt.md") for path in PROMPTS.glob("*.prompt.md"))
        self.assertTrue(names)
        self.assertEqual(names, list(command_skills()))

    def test_each_command_file_passes_the_arguments_to_its_skill(self):
        """The file has the argument hint of the skill, loads that skill, and passes $ARGUMENTS."""
        for name, skill in command_skills().items():
            prompt = PROMPTS / f"{name}.prompt.md"
            text = prompt.read_text(encoding="utf-8")
            self.assertEqual(front_matter(prompt, "argument-hint"), front_matter(skill, "argument-hint"), name)
            self.assertTrue(front_matter(prompt, "description"), name)
            self.assertIn(f"Load the `{name}` skill", text, name)
            self.assertIn("\n$ARGUMENTS\n", text, name)

    def test_the_main_package_comes_from_the_same_ref(self):
        """The dependency is git: parent with the path of the main package, so it names no ref."""
        manifest = (PACKAGE / "apm.yml").read_text(encoding="utf-8")
        self.assertRegex(manifest, r"- git: parent\r?\n\s+path: agent-packages/atp-tests-assistant\r?\n")
        self.assertNotRegex(manifest, r"\bref:|atp-tests-assistant#")


if __name__ == "__main__":
    unittest.main(verbosity=2)
