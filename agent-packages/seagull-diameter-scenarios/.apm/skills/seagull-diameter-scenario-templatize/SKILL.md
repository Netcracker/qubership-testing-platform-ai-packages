---
name: seagull-diameter-scenario-templatize
description: Use only when the user types /seagull-diameter-scenario-templatize. Replaces the values of chosen AVPs in generated Seagull scenarios with @@NAME@@ placeholders, and writes a values file that reproduces the original scenario.
disable-model-invocation: true
argument-hint: "<scenario files or folder> [placeholder=<AVP>=<NAME> ...] [options=<file>] [out=<folder>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-templatize

A command frontend for [seagull-diameter-templatize-scenarios](../seagull-diameter-templatize-scenarios/SKILL.md). It
reads the user's arguments literally and runs the steps of that skill; the steps, the script, the rules for the pairs,
and the limits stay there. For an ordinary request in plain language ("make the subscriber number of the scenarios in
C:\work\Seagull-Scenario\scenario a placeholder"), follow that skill directly instead.

## Arguments

```text
/seagull-diameter-scenario-templatize <scenario files or folder> [placeholder=<AVP>=<NAME> ...] [options=<file>] [out=<folder>]
```

| Argument       | Meaning                                                                                                 | Default                                      |
| -------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| first argument | One or more `*.client.xml` files, or the `scenario` folder of a generation (every `*.client.xml` in it) | required                                     |
| `placeholder=` | One pair, `<AVP>=<NAME>`; repeat it for more pairs. An empty `<NAME>` removes the pair                  | the pairs in the options file                |
| `options=`     | The options file                                                                                        | `scenario-options.ini` next to the scenarios |
| `out=`         | The folder for the templates and values files                                                           | next to each scenario                        |

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Never infer a missing first argument. Ask for it. With no `placeholder=` and no options file, ask which AVP values
  become placeholders; never pick them.
- When an argument can't be parsed unambiguously, run nothing. This covers a word with no `=`, a value with spaces and
  no quotes, and any extra token. Reply with the corrected command and let the user send it or change it.
- Run the steps of the skill with the given values. `placeholder=<AVP>=<NAME>` becomes `--placeholder <AVP>=<NAME>`,
  `options=` becomes `--options`, and `out=` becomes `--out`.
- The command is the user's instruction to write the files, so don't ask again before replacing the templates of an
  earlier run in the same place; say which were replaced. The dry run is not part of the command: offer it.
