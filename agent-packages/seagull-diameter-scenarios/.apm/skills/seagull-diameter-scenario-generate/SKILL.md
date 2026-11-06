---
name: seagull-diameter-scenario-generate
description: Use only when the user types /seagull-diameter-scenario-generate. Generates Seagull client scenarios or templates with placeholders, configuration, and a stub OCS from a folder of recorded Diameter requests and responses and one ready Seagull dictionary, and runs them in a dry run.
disable-model-invocation: true
argument-hint: "<steps folder> [dictionary=<file>] [out=<folder>] [replace=yes] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>] [mode=scenario|template] [placeholder=<AVP>=<NAME> ...] [option=<key>=<value> ...] [options=<file>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-generate

A command frontend for [seagull-diameter-generate-scenarios](../seagull-diameter-generate-scenarios/SKILL.md). It reads
the user's arguments literally and runs the steps of that skill, the dry run included; the steps, the scripts, the
rules for the output folder, the description of the output, and the limits stay there. For an ordinary request in plain
language ("generate scenarios from C:\work\Diameter-Steps with the dictionary ..."), follow that skill directly
instead.

## Arguments

```text
/seagull-diameter-scenario-generate <steps folder> [dictionary=<file>] [out=<folder>] [replace=yes] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>] [mode=scenario|template] [placeholder=<AVP>=<NAME> ...] [option=<key>=<value> ...] [options=<file>]
```

| Argument         | Meaning                                                                                                                                       | Default                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `<steps folder>` | The folder of recorded steps                                                                                                                  | required                                                                               |
| `dictionary=`    | The one Seagull dictionary file for the scenarios; a folder is refused. /seagull-diameter-dictionary-convert makes it                         | the setting SEAGULL_DICTIONARY_PATH; without both, the command stops                   |
| `out=`           | The folder to write to. It must be new or empty, unless `replace=yes`                                                                         | a new folder, `Seagull-Scenario` or `Seagull-Scenario-2`, ... next to the steps folder |
| `replace=`       | `yes` moves the old contents of a non-empty `out=` aside, then generates. The options file is kept                                            | no                                                                                     |
| `timeout=`       | How long Seagull waits for each answer, in milliseconds                                                                                       | 5000                                                                                   |
| `dest=`          | Address and port of the OCS, written into `config/conf.client.xml`                                                                            | `127.0.0.1:3868`                                                                       |
| `host-ip=`       | The IP address that the CER announces as the client's own                                                                                     | `192.0.2.10`                                                                           |
| `mode=`          | `scenario` writes ready scenarios with fixed values; `template` puts placeholders where values were                                           | the options file, else `scenario`                                                      |
| `placeholder=`   | One `<AVP>=<NAME>` pair; repeat it for more. An empty `<NAME>` removes the pair                                                               | the pairs in the options file                                                          |
| `option=`        | One `<key>=<value>` option of [the options file](../seagull-diameter-common/SKILL.md#the-options-file)                                        | the options file                                                                       |
| `options=`       | An older options file to start from. The result is always written to `scenario-options.ini` in the output folder; the older file is only read | `scenario-options.ini` in the output folder                                            |

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Never infer a missing `<steps folder>`. Ask for it.
- Without `dictionary=` and without the setting, stop and tell the user that there is no Seagull dictionary, as
  [The dictionary](../seagull-diameter-generate-scenarios/SKILL.md#the-dictionary) describes. Never search for one,
  convert one, or take one of Seagull's own.
- When an argument can't be parsed unambiguously, run nothing. This covers a word with no `=`, a value with spaces and
  no quotes, and any extra token. Reply with the corrected command and let the user send it or change it.
- Run the steps of the skill with the given values. `dictionary=`, `mode=`, `placeholder=`, `option=`, and `options=`
  become the script options that the skill names. The command is the user's instruction for the dry run, so run it
  without asking.
- `replace=yes` is the user's explicit word. Without it, a folder that has files is refused, as the skill says.
- Never pick a placeholder or an option yourself.
