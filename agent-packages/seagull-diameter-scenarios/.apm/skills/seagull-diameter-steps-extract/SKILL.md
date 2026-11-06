---
name: seagull-diameter-steps-extract
description: Use only when the user types /seagull-diameter-steps-extract. Turns a file of recorded test steps (for example an xlsx export from a database) into the folder of Diameter request and response files that /seagull-diameter-scenario-generate reads, following the user's description of the file.
disable-model-invocation: true
argument-hint: "<source file or folder> -- <how to find the requests and the responses in it>"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-steps-extract

A command frontend for [seagull-diameter-extract-steps](../seagull-diameter-extract-steps/SKILL.md). It reads the
line below and runs the steps of that skill; the questions the description must answer, the steps, and the rules stay
there. For an ordinary request in plain language ("extract the steps from C:\work\Steps.xlsx, sheet Main, ..."), follow
that skill directly instead.

## Arguments

```text
/seagull-diameter-steps-extract <source> -- <how to read it>
```

| Part               | Meaning                                                                                                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `<source>`         | An `xlsx`, `csv`, JSON, or log file, or a folder that already has the `Step-NNN-...` files                                                                                   |
| `<how to read it>` | Free text. It must say what is needed to answer the questions in the skill                                                                                                   |
| output folder      | Optional, in the text: where to write; it must be new or empty. Default: a new folder next to the source, `Diameter-Steps`, or `Diameter-Steps-2` and so on when that exists |

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the usage from the "Arguments"
  section above, the syntax line and the table of parts, and nothing else.
- Never infer a missing `<source>`. Ask for it.
- A file source without a description after `--` is not enough. Ask the questions of the skill, all in one message.
- Run the steps of the skill with the given source and description. Every rule of the skill holds: never guess the
  structure of a file, never change the source, never write into a folder that has files.
