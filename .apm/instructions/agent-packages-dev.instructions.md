---
description: Conventions for developing any package under agent-packages.
applyTo: "agent-packages/**"
---

## Developing the packages

These rules apply when you change a package under `agent-packages/`, not when you use its skills. The paths below
start in the folder of the package. A package can add rules of its own in the `AGENTS.md` of its folder; read that file
before you change the package.

Before you add or change a skill, read `README.md`, `docs/user-guide.md`, the skills under `.apm/skills/`, and
`tests/selftest.py`.

### What a task consists of

A task that a user can ask for has two skills:

- A plain-language skill with `user-invocable: false`. The agent picks it from an ordinary request. It holds the steps
  and the rules of the task.
- A command, which is a skill that runs only when the user types its name: `disable-model-invocation: true`,
  `metadata.opencode/autoinvoke: "false"`, and `agents/openai.yaml` with `allow_implicit_invocation: false`. It reads
  its arguments literally, prints its usage for `help`, and links to the plain-language skill for the rest.

Both skills run the same scripts. Code that several scripts need goes into the `<prefix>-common` skill, where
`<prefix>` is the one that the skills of the package share.

A parameter that means the same thing has the same name in every skill of a package.

### Scripts

Scripts run on the user's machine: use only the standard library of Python 3.9.

### What changes with a new or changed task

- `README.md` and `docs/user-guide.md`, including the errors that a user can see.
- `.apm/instructions/<package>.instructions.md`, which ships to users, when the change affects what it says.
- `apm.yml`: the version, and the description when the package does something new.
- `tests/selftest.py` or the test modules that it imports.

### A new package

- Create `agent-packages/<package>/` with `apm.yml`, `.apm/instructions/<package>.instructions.md`, `.apm/skills/`,
  `README.md`, `docs/user-guide.md`, and `tests/selftest.py`.
- Name a plain-language skill `<prefix>-<object>-<verb>` and a command `/<prefix>-<verb>-<object>`.
- Add the package to the table in the `README.md` of the repository root.
- If the package needs rules of its own, add `.apm/instructions/<package>-dev.instructions.md` in the repository root
  with `applyTo: "agent-packages/<package>/{apm.yml,README.md}"`, and run `apm compile`.

### Checks

- Run `python agent-packages/<package>/tests/selftest.py` from the repository root.
- Run the linters with the configurations in `.github/linters/` of the repository root.
