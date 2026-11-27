---
name: atp-update-local-tests
description: Use only when the user types /atp-update-local-tests. Clones the project's test repository into the folder of the local tests, or fast-forwards that clone.
disable-model-invocation: true
argument-hint: "[path=<folder>] [branch=<branch>] [repo=<url>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-update-local-tests

A command frontend for [atp-local-tests-update](../atp-local-tests-update/SKILL.md). It reads the user's arguments
literally and runs the script that skill describes; the Git steps, the output, and the errors stay there. For an
ordinary request in plain language ("update the local tests"), follow atp-local-tests-update directly instead.

## Arguments

```text
/atp-update-local-tests [path=<folder>] [branch=<branch>] [repo=<url>]
```

| Argument          | Meaning                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------- |
| none              | Update the folder of the config.                                                          |
| `path=<folder>`   | The folder to clone into or to update. It is written to the config.                       |
| `branch=<branch>` | The branch to check out and update. Default: `ATP_TESTS_GIT_REPO_BRANCH`, if checked out. |
| `repo=<url>`      | The test repository. Default: `ATP_TESTS_GIT_REPO_URL` of the config.                     |

Put a path with spaces in double quotes: `path="D:\my tests"`.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `path=`, `branch=`, and `repo=` to `--path`, `--branch`, and `--repo`.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command and
  let the user send it or change it.
- Run the script, and show its output as atp-local-tests-update describes. Report the errors as it describes.
