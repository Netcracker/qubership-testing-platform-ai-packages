---
name: atp-tests-show-environment
description: Use only when the user types /atp-tests-show-environment. Shows the YAML file of one environment of the project's GitLab pipeline, the current one that PIPELINE_RUNTIME_CONFIG names or one given by name.
disable-model-invocation: true
argument-hint: "[name=<text>] [ref=<branch>] [url=<gitlab url>] [project=<id>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-tests-show-environment

A command frontend for [atp-tests-environment-show](../atp-tests-environment-show/SKILL.md). It reads the user's
arguments literally and runs the script that skill describes; the options, the output, and the errors stay there. For an
ordinary request in plain language ("show the description of the current environment"), follow
atp-tests-environment-show directly instead.

## Arguments

```text
/atp-tests-show-environment [name=<text>] [ref=<branch>] [url=<gitlab url>] [project=<id>]
```

| Argument           | Meaning                                                                                      |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `name=<text>`      | The name of the environment or a part of it. Default: the one of `PIPELINE_RUNTIME_CONFIG`.  |
| `ref=<branch>`     | The branch of the pipeline repository. Default: `GITLAB_REF` of the config.                  |
| `url=<gitlab url>` | The GitLab service. Default: `GITLAB_URL` of the config.                                     |
| `project=<id>`     | The numeric ID or the path of the pipeline project. Default: `GITLAB_PROJECT_ID`.            |

Put a value with spaces in double quotes. With no argument, the command shows the current environment.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `name=`, `ref=`, `url=`, and `project=` to `--name`, `--ref`, `--url`, and `--project`.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command and
  let the user send it or change it.
- Run the script, and show its output as atp-tests-environment-show describes. Report the errors as it describes.
