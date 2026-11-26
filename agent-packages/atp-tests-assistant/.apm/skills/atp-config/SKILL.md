---
name: atp-config
description: Use only when the user types /atp-config. Shows the config of atp-tests-assistant, .atp-assistant/config.json, or changes its values, and creates it when there is none.
disable-model-invocation: true
argument-hint: "[KEY=value ...] | help"
metadata:
  opencode/autoinvoke: "false"
---

# /atp-config

A command frontend for [atp-config-manage](../atp-config-manage/SKILL.md). It reads the user's arguments literally and
runs the script that skill describes; the output and the errors stay there. For an ordinary request in plain language
("show the ATP config"), follow atp-config-manage directly instead.

## Arguments

```text
/atp-config [KEY=value ...]
```

| Argument    | Meaning                                                                         |
| ----------- | ------------------------------------------------------------------------------- |
| none        | Show the config.                                                                |
| `KEY=value` | Set a setting or a variable of the pipeline. Repeat for more.                   |
| `KEY=`      | Remove an optional setting, such as `ORCHESTRATOR_URL`, or empty another value. |

Put a value with spaces in double quotes: `EXECUTION_NAME="Generate domestic customers"`.

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, run no script. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Map each `KEY=value` to `--set KEY=value`, with the key as typed. Without arguments, run the script without options.
- When an argument is not `KEY=value`, run nothing. Reply with the corrected command and let the user send it or change
  it.
- Run the script, and show its output as atp-config-manage describes. Report the errors as it describes.
