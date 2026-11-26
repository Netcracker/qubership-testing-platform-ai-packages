---
description: Conventions for developing the atp-tests-assistant package.
applyTo: "agent-packages/atp-tests-assistant/{apm.yml,README.md}"
---

## Developing atp-tests-assistant

These rules apply to every change under `agent-packages/atp-tests-assistant/`, in addition to the rules for all
packages.

### Names

- A plain-language skill is `atp-<object>-<verb>`, such as `atp-environment-show`.
- A command is `/atp-<verb>-<object>`, such as `/atp-show-environment`. The exception is `/atp-config`, which shows
  and changes the config.
- A filter by name is `name=<text>`.

### Scripts

A task has a Python script in the `scripts/` folder of its plain-language skill. The script does the work, and both
skills run it. Shared code goes into the `atp-common` skill.

### OpenCode commands

The package `atp-tests-assistant-opencode` has one command file for each command skill. When a command skill is added,
renamed, removed, or gets another `argument-hint`, change the file in its `.apm/prompts/` too, and run its self-test.

### User documentation

The table of errors in `docs/user-guide.md` lists the errors of the scripts.
