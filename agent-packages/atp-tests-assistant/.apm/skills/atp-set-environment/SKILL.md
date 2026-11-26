---
name: atp-set-environment
description: Use only when the user types /atp-set-environment. Sets PIPELINE_RUNTIME_CONFIG in the config file of the package to the environment of the project's GitLab pipeline given by name.
disable-model-invocation: true
argument-hint: "name=<text> [ref=<branch>] [url=<gitlab url>] [project=<id>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-set-environment

A command frontend for [atp-environment-set](../atp-environment-set/SKILL.md). It reads the user's
arguments literally and runs the script that skill describes; the search, the output, and the errors stay there. For an
ordinary request in plain language ("set the pipeline environment to CI-Ivory"), follow atp-environment-set
directly instead.

## Arguments

```text
/atp-set-environment name=<text> [ref=<branch>] [url=<gitlab url>] [project=<id>]
```

| Argument           | Meaning                                                                           |
| ------------------ | --------------------------------------------------------------------------------- |
| `name=<text>`      | The name of the environment or a part of it. Required.                            |
| `ref=<branch>`     | The branch of the pipeline repository. Default: `GITLAB_REF` of the config.       |
| `url=<gitlab url>` | The GitLab service. Default: `GITLAB_URL` of the config.                          |
| `project=<id>`     | The numeric ID or the path of the pipeline project. Default: `GITLAB_PROJECT_ID`. |

Put a value with spaces in double quotes.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `name=`, `ref=`, `url=`, and `project=` to `--name`, `--ref`, `--url`, and `--project`.
- Without `name=`, run nothing and ask for it.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command and
  let the user send it or change it.
- Run the script, and show its output as atp-environment-set describes. Report the errors as it describes.
