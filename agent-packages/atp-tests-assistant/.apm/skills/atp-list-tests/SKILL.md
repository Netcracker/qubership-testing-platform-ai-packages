---
name: atp-list-tests
description: Use only when the user types /atp-list-tests. Lists the Playwright test files (*.ts) of the project's test repository as a nested list, optionally for one folder, with a part of the filename, or as a table.
disable-model-invocation: true
argument-hint: "[folder=<name> | folder=/<path>] [name=<text>] [format=tree|table] [repo=<url>] [branch=<branch>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-list-tests

A command frontend for [atp-tests-list](../atp-tests-list/SKILL.md). It reads the user's arguments
literally and runs the script that skill describes; the options, the output, and the errors stay there. For an ordinary
request in plain language ("show all tests"), follow atp-tests-list directly instead.

## Arguments

```text
/atp-list-tests [folder=<name> | folder=/<path>] [name=<text>] [format=tree|table] [repo=<url>] [branch=<branch>]
```

| Argument              | Meaning                                                                                                       |
| --------------------- | ------------------------------------------------------------------------------------------------------------- |
| `folder=<name>`       | The tests in every folder called `<name>`, at any depth under `TestScenario`, ignoring case.                  |
| `folder=/<path>`      | The tests in `<path>`, counted from `TestScenario`, such as `folder=/Billing` or `folder=/A/B`.               |
| `name=<text>`         | Only the files whose name contains `<text>`, ignoring case. With `*` or `?`, a mask for the name.             |
| `format=table`        | A table with one row for each file. The default, `format=tree`, is a nested list.                             |
| `repo=<url>`          | The test repository. Default: `ATP_TESTS_GIT_REPO_URL` of the config.                                         |
| `branch=<branch>`     | The branch. Default: `ATP_TESTS_GIT_REPO_BRANCH`; with `repo=` and no branch, the default branch.             |

Put a value with spaces in double quotes: `name="create customer"`. With no argument, the command lists all tests.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `folder=<name>` to `--folder <name>`, and `folder=/<path>` to `--under <path>` without the leading slash. Map
  `name=`, `format=`, `repo=`, and `branch=` to the options of the same name.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command
  and let the user send it or change it.
- Run the script, and show its output as atp-tests-list describes. Report the errors as it describes.
