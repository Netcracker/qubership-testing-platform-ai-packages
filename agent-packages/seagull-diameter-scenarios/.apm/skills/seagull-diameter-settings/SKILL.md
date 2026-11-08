---
name: seagull-diameter-settings
description: Use only when the user types /seagull-diameter-settings. Shows the settings of the Seagull Diameter skills with their sources and the options of the converted dictionary, or saves the runner, the path of seagull.exe, the Docker image, or the dictionary file from explicit arguments.
disable-model-invocation: true
argument-hint: "[runner=docker|windows] [seagull-exe=<path>] [image=<image>] [dictionary=<file>] [home=yes] | help"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-settings

A command frontend for [seagull-diameter-manage-settings](../seagull-diameter-manage-settings/SKILL.md). It reads the
user's arguments literally and runs the steps of that skill; the settings, the script, and the limits stay there. For an
ordinary request in plain language ("show the settings"), follow that skill directly instead.

## Arguments

```text
/seagull-diameter-settings [runner=docker|windows] [seagull-exe=<path>] [image=<image>] [dictionary=<file>] [home=yes]
```

| Argument       | Meaning                                                                                           | Default         |
| -------------- | ------------------------------------------------------------------------------------------------- | --------------- |
| none           | Shows the settings, the dictionary options, and where the scenario options are                    | -               |
| `runner=`      | Saves `SEAGULL_RUNNER`: where the dry run and the dictionary check start Seagull                  | not saved       |
| `seagull-exe=` | Saves `SEAGULL_WINDOWS_PATH`: the `seagull.exe` of a Seagull for Windows; the file must exist     | not saved       |
| `image=`       | Saves `SEAGULL_DOCKER_IMAGE`: the Seagull image for `runner=docker`                               | `seagull:local` |
| `dictionary=`  | Saves `SEAGULL_DICTIONARY_PATH`: the one Seagull dictionary file that the generator reads         | not saved       |
| `home=`        | `yes` saves into the file in the user's home folder, for every folder, and not into the session's | no              |

## Behavior

- With no arguments, run the script of the skill and show its three parts under their headings. Change nothing.
- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the syntax line and the table from the
  "Arguments" section above, and nothing else.
- Each of `runner=`, `seagull-exe=`, `image=`, and `dictionary=` saves one key with `seagull_config.py set`, in the order
  given, and `home=yes` adds `--home` to each. The arguments are the user's instruction, so don't ask again. After the last
  one, show the settings as with no arguments.
- An argument that is not in the table is an error. Say which one isn't recognized, name the valid forms, and save nothing.
  This covers a word with no `=`, a value with spaces and no quotes, and any extra token.
- When a value is refused (`SEAGULL_RUNNER must be one of docker, windows`, `no file ...`), report the message and leave
  that key as it was.
- Don't edit `dictionary-options.ini` or `scenario-options.ini`; pass `options=` to the commands that use them.
