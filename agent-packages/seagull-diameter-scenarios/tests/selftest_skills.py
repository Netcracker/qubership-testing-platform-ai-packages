"""Self-test of the structure of the skills of the seagull-diameter-scenarios package.

It is part of tests/selftest.py, which imports these tests. Run: python tests/selftest.py

It reads the SKILL.md files and checks what an agent relies on: the name matches the folder, the
description is not empty, every relative link resolves, and each command that has a plain-language
skill points to it, is hidden from the model, and is pointed back to by that skill. PLAIN_SKILLS
lists the pairs; a pair is added when its plain skill is.

Requires Python 3.9 or later.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SKILLS = PACKAGE / ".apm" / "skills"
INSTRUCTIONS = PACKAGE / ".apm" / "instructions"
# command skill -> the plain-language skill whose steps it runs
PLAIN_SKILLS = {
    "seagull-diameter-dictionary-convert": "seagull-diameter-convert-dictionaries",
}
LINK = re.compile(r"\]\(([^)\s]+)\)")


def read_skill(name: str) -> tuple[dict[str, str], str]:
    """Return the top-level frontmatter keys of a SKILL.md and its body."""
    text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    head, _, body = text.removeprefix("---\n").partition("\n---\n")
    keys = {}
    for line in head.splitlines():
        key, separator, value = line.partition(":")
        if separator and not line.startswith(" "):
            keys[key.strip()] = value.strip()
    return keys, body


def skill_names() -> list[str]:
    """Return the folder names of all skills of the package."""
    return sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))


class SkillStructureTest(unittest.TestCase):
    """The SKILL.md files agree with their folders, with each other, and with their links."""

    def test_name_and_description(self) -> None:
        """The name is the folder name, and the description is present and on one line."""
        for name in skill_names():
            with self.subTest(skill=name):
                keys, _ = read_skill(name)
                self.assertEqual(keys.get("name"), name)
                self.assertTrue(keys.get("description"), "the description is empty")

    def test_relative_links_resolve(self) -> None:
        """Every relative link of a SKILL.md names a file or folder that exists."""
        for name in skill_names():
            _, body = read_skill(name)
            for target in LINK.findall(body):
                if target.startswith(("http://", "https://", "#")):
                    continue
                with self.subTest(skill=name, link=target):
                    path = target.partition("#")[0]
                    self.assertTrue((SKILLS / name / path).exists(), f"{target} does not exist")

    def test_commands_and_plain_skills_point_to_each_other(self) -> None:
        """A command is hidden from the model and links to its plain skill, which links back."""
        for command, plain in PLAIN_SKILLS.items():
            with self.subTest(command=command):
                command_keys, command_body = read_skill(command)
                plain_keys, plain_body = read_skill(plain)
                self.assertEqual(command_keys.get("disable-model-invocation"), "true")
                self.assertIn(f"](../{plain}/SKILL.md)", command_body)
                self.assertEqual(plain_keys.get("user-invocable"), "false")
                self.assertNotIn("disable-model-invocation", plain_keys)
                self.assertTrue(plain_keys["description"].startswith("Use when"))
                self.assertIn(f"](../{command}/SKILL.md)", plain_body)

    def test_instruction_file_applies_everywhere(self) -> None:
        """The package instruction exists and carries a description and applyTo."""
        path = INSTRUCTIONS / "seagull-diameter-scenarios.instructions.md"
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ndescription: "))
        self.assertIn('\napplyTo: "**/*"\n', text)


if __name__ == "__main__":
    unittest.main()
