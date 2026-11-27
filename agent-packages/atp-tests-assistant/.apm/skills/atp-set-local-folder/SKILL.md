---
name: atp-set-local-folder
description: Use only when the user types /atp-set-local-folder. Sets LOCAL_ROOT_FOLDER in the config file of the package to the folder that holds the local tests, or checks the current one.
disable-model-invocation: true
argument-hint: "[path=<folder>] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-set-local-folder

A command frontend for [atp-local-folder-set](../atp-local-folder-set/SKILL.md). It reads the user's arguments
literally and runs the script that skill describes; the check, the output, and the errors stay there. For an ordinary
request in plain language ("the local tests are in D:\work\tests"), follow atp-local-folder-set directly instead.

## Arguments

```text
/atp-set-local-folder [path=<folder>]
```

| Argument        | Meaning                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------- |
| none            | Check the folder of the config.                                                           |
| `path=<folder>` | The folder with the copy of the test repository. It is checked and written to the config. |

Put a path with spaces in double quotes: `path="D:\my tests"`.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map `path=<folder>` to `--path <folder>`. Without arguments, run the script without options.
- When an argument can't be parsed unambiguously, or one is unknown, run nothing. Reply with the corrected command and
  let the user send it or change it.
- Run the script, and show its output as atp-local-folder-set describes. Report the errors as it describes.
