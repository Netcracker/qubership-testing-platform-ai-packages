---
description: Conventions for developing the atp-tests-assistant package.
applyTo: "agent-packages/atp-tests-assistant/**"
---

## Developing atp-tests-assistant

These rules are for changing the package, not for using its skills. The paths below start in
`agent-packages/atp-tests-assistant/`.

Before you add or change a skill, read `README.md`, `docs/user-guide.md`, the skills under `.apm/skills/`, and
`tests/selftest.py`.

### What a task consists of

A task that a user can ask for has three parts:

- A plain-language skill with `user-invocable: false`. The agent picks it from an ordinary request.
- A command, which is a skill that runs only when the user types its name: `disable-model-invocation: true`,
  `metadata.opencode/autoinvoke: "false"`, and `agents/openai.yaml` with `allow_implicit_invocation: false`.
- A Python script in the `scripts/` folder of the plain-language skill. It does the work, and both skills run it.

Code that several scripts need goes into the `atp-tests-common` skill.

### Names

- A plain-language skill is `atp-tests-<object>-<verb>`, such as `atp-tests-environment-show`.
- A command is `/atp-tests-<verb>-<object>`, such as `/atp-tests-show-environment`.
- A parameter that means the same thing has the same name in every skill. A filter by name is `name=<text>`.

### Scripts

Scripts run on the user's machine: use only the standard library of Python 3.9.

### What changes with a new or changed task

- `README.md` and `docs/user-guide.md`, including the table of errors.
- `.apm/instructions/atp-tests-assistant.instructions.md`, which ships to users: the plain requests that it quotes.
- `apm.yml`: the version, and the description when the package does something new.
- `tests/selftest.py`.

### Checks

- Run `python agent-packages/atp-tests-assistant/tests/selftest.py` from the repository root.
- Run the linters with the configurations in `.github/linters/` of the repository root.
