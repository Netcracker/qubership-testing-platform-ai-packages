---
name: atp-run-tests
description: Use only when the user types /atp-run-tests. Starts the project's GitLab pipeline with an explicit test case or scope and environment, and waits until it ends.
disable-model-invocation: true
argument-hint: "test=<name> | scope=<name> [env=<environment>] [branch=<branch>] [VARIABLE=value ...] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-run-tests

A command frontend for [atp-tests-run](../atp-tests-run/SKILL.md). It reads the user's arguments literally and runs the
script that skill describes; the confirmation, the way of waiting, and the handling of the result stay there. For an
ordinary request in plain language ("run the test case Create customer"), follow atp-tests-run directly instead.

## Arguments

```text
/atp-run-tests test=<name> | scope=<name> | type=<type> name=<name>  [env=<environment>] [branch=<branch>]
               [repo=<url>] [jira=true|false] [webex=true|false] [<VARIABLE>=<value> ...]
```

| Argument             | Meaning                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| `test=<name>`        | Run the test case with this name: `EXECUTION_TYPE=test`, `EXECUTION_NAME=<name>`.                |
| `scope=<name>`       | Run the scope with this name: `EXECUTION_TYPE=scope`, `EXECUTION_NAME=<name>`.                   |
| `type=` and `name=`  | Another execution type and its name. Use both together.                                          |
| `env=<environment>`  | The environment of the pipeline: its name or a part of it. It is saved as the current one.       |
| `branch=<branch>`    | The branch of the test repository: `ATP_TESTS_GIT_REPO_BRANCH`.                                  |
| `repo=<url>`         | The test repository: `ATP_TESTS_GIT_REPO_URL`.                                                   |
| `jira=`, `webex=`    | `ENABLE_JIRA_INTEGRATION` and `SEND_WEBEX_NOTIFICATION`; `true` or `false`.                      |
| `<VARIABLE>=<value>` | Any other variable of the config, by its name.                                                   |

Put a name or a value with spaces in double quotes: `test="Generate domestic customers"`. Everything not given keeps
the value from the config.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, send no request. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Give exactly one of `test=`, `scope=`, or `type=` with `name=`. With none of them, ask for the test case or the scope.
  Never infer the name.
- When an argument can't be parsed unambiguously, send nothing. Reply with the corrected command and let the user send
  it or change it.
- With `env=`, set the environment first, as atp-tests-run describes. Pass `env=environments/<name>.yaml` to
  atp-environment-set as `<name>`. Run nothing when the environment is not found or several match.
- Map the other arguments to `--set` options as the table says, run the script without `--yes`, and show the
  variables. Show the config before the first run of the conversation, and ask or don't ask for a confirmation, as
  atp-tests-run describes. When a question is due, start the pipeline only after a yes.
- While the script runs, read its output and report each business identifier (`FOUND <name>=<value>`) as soon as it
  appears, as atp-tests-run describes.
- Report the result, the failures, and the errors as atp-tests-run describes.
