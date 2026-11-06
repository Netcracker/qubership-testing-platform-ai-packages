---
name: seagull-diameter-scenario-externalize
description: Use only when the user types /seagull-diameter-scenario-externalize. Changes generated Seagull scenarios so that chosen AVP values come from an external CSV data file at run time, one row for each call, and writes the data file and the configuration for it into a new folder.
disable-model-invocation: true
argument-hint: "<scenario folder or files> placeholder=<AVP>=<COLUMN> ... [select=sequential|random] [calls=<N>] [out=<folder>] [data-path=<path>] [options=<file>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-externalize

A command frontend for [seagull-diameter-externalize-scenarios](../seagull-diameter-externalize-scenarios/SKILL.md). It
reads the user's arguments literally and runs the steps of that skill; the steps, the script, the format of the data
file, and the limits stay there. For an ordinary request in plain language ("read the subscriber number of the
scenarios in C:\work\Seagull-Scenario\scenario from a data file"), follow that skill directly instead.

## Arguments

```text
/seagull-diameter-scenario-externalize <scenario folder or files> placeholder=<AVP>=<COLUMN> ... [select=sequential|random] [calls=<N>] [out=<folder>] [data-path=<path>] [options=<file>]
```

| Argument       | Meaning                                                                                          | Default                                                          |
| -------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| first argument | The `scenario` folder of a generation, or one or more `*.client.xml` files                       | required                                                         |
| `placeholder=` | One `<AVP>=<COLUMN>` pair; repeat it. `<COLUMN>` names a column of the data file                 | the pairs in the options file                                    |
| `select=`      | `sequential` takes the rows in order and starts again at the end; `random` picks a row at random | `sequential`                                                     |
| `calls=`       | How many calls Seagull makes (`number-calls`), so how many rows it uses                          | the value in the configuration, 1                                |
| `out=`         | The folder to write to. It must be new or empty                                                  | a new folder, `<generation folder>-external`, `-external-2`, ... |
| `data-path=`   | Where Seagull will find the data file when it runs                                               | `../scenario/external-data.csv`                                  |
| `options=`     | An older options file whose pairs to use                                                         | `scenario-options.ini` in the generation folder                  |

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Never infer a missing first argument. Ask for it. With no `placeholder=` and no options file, ask which AVPs come
  from the data file; never pick them.
- When an argument can't be parsed unambiguously, run nothing. This covers a word with no `=`, a value with spaces and
  no quotes, and any extra token. Reply with the corrected command and let the user send it or change it.
- Run the steps of the skill with the given values. `placeholder=<AVP>=<COLUMN>` becomes
  `--placeholder <AVP>=<COLUMN>`, `select=random` becomes `--select random`, and `calls=`, `data-path=`, and `options=`
  become `--calls`, `--data-path`, and `--options`. Pass `--out <folder>` for `out=`, else `--out-auto`.
- The dry run is not part of the command. Offer it in one sentence, and run it only when the user says yes.
