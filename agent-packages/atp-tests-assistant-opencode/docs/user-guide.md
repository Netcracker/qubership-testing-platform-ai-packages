# atp-tests-assistant-opencode user guide

Use this package for OpenCode only. For Claude Code, Codex, and Cursor, install `atp-tests-assistant` itself: the
commands of this package would appear next to the skills with the same names.

## Install

Run `apm install` in the folder in which you start OpenCode:

```bash
apm install --target opencode Netcracker/qubership-testing-platform-ai-packages/agent-packages/atp-tests-assistant-opencode
```

The command installs from the default branch. To install a release, add `#<tag>` to the end of the command. The main
package then comes from the same tag.

APM writes the commands to `.opencode/commands/` and the skills to `.agents/skills/`. Run `apm compile` once, so that
the instruction of the main package reaches `AGENTS.md`. Then restart OpenCode.

To check the installation without GitLab, type `/atp-run-tests help`. The command prints its syntax and sends no
request.

## Use

The settings, the token, the commands, and the errors are those of the main package. Follow its
[user guide](../../atp-tests-assistant/docs/user-guide.md).
