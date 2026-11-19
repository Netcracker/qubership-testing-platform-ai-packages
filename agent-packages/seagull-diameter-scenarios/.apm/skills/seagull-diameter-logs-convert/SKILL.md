---
name: seagull-diameter-logs-convert
description: Use only when the user types /seagull-diameter-logs-convert. Writes each Diameter message of a Seagull log (*.client or *.stub) to its own XML file, from explicit arguments.
disable-model-invocation: true
argument-hint: "<log> [out=<folder>] [numbering=step|sequence] [format=avp|steps] [pretty=true|false] [dictionary=<file>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-logs-convert

A command frontend for [seagull-diameter-convert-logs](../seagull-diameter-convert-logs/SKILL.md). It reads the user's
arguments literally and runs the steps of that skill; the format of the files, the script, and the limits stay there.

## Arguments

```text
/seagull-diameter-logs-convert <log> [out=<folder>] [numbering=step|sequence] [format=avp|steps] [pretty=true|false] [dictionary=<file>]
```

| Argument     | Meaning                                                                              | Default                      |
| ------------ | ------------------------------------------------------------------------------------ | ---------------------------- |
| `<log>`      | The Seagull log file; required                                                       | -                            |
| `out=`       | The output folder; it must be new or empty                                           | A new folder next to the log |
| `numbering=` | `step`: a request and its answer share a number; `sequence`: the log order           | `step`                       |
| `format=`    | `avp`: a message with a header and AVP elements; `steps`: the form of recorded steps | `avp`                        |
| `pretty=`    | `true` indents the XML; `false` writes each file on one line                         | `true`                       |
| `dictionary=` | `format=steps` only: the Seagull dictionary to use when the file the log names is missing | The file the log names  |

A value with a space must be in quotes. A missing `<log>`, another key, or a `numbering`, `format`, or `pretty` value
that is not listed is refused: say which form is valid, and run nothing.
