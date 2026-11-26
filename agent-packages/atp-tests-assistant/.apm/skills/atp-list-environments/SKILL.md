---
name: atp-list-environments
description: Use only when the user types /atp-list-environments. Lists the environments of the project's GitLab pipeline, the YAML files in the environments folder of the pipeline repository, optionally only the names that contain a text.
disable-model-invocation: true
argument-hint: "[name=<text>] [ref=<branch>] [url=<gitlab url>] [project=<id>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-list-environments

A command frontend for [atp-environments-list](../atp-environments-list/SKILL.md). It reads the user's
arguments literally and runs the script that skill describes; the options, the output, and the errors stay there. For an
ordinary request in plain language ("show the environments for the pipeline"), follow atp-environments-list
directly instead.

## Arguments

```text
/atp-list-environments [name=<text>] [ref=<branch>] [url=<gitlab url>] [project=<id>]
```

| Argument           | Meaning                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `name=<text>`      | Only the names that contain `<text>`, ignoring case. With `*` or `?`, a mask for the name. |
| `ref=<branch>`     | The branch of the pipeline repository. Default: `GITLAB_REF` of the config.                |
| `url=<gitlab url>` | The GitLab service. Default: `GITLAB_URL` of the config.                                   |
| `project=<id>`     | The numeric ID or the path of the pipeline project. Default: `GITLAB_PROJECT_ID`.          |

Put a value with spaces in double quotes. With no argument, the command lists all environments.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `name=`, `ref=`, `url=`, and `project=` to `--name`, `--ref`, `--url`, and `--project`.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command and
  let the user send it or change it.
- Run the script, and show its output as atp-environments-list describes. Report the errors as it describes.
