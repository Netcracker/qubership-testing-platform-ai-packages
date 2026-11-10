---
name: seagull-diameter-manage-settings
description: Use when the user asks to show, check, or change the settings of the Seagull Diameter skills, for example which Seagull runs the checks, the path of seagull.exe, the Docker image, or the dictionary that scenario generation uses, or to show the options of the dictionary conversion. Prints the settings with their sources and the dictionary options; saves a setting only when the user asks for it.
user-invocable: false
---

# Show and change the settings of the Seagull Diameter skills

The skills keep four settings in one JSON file, `.seagull-diameter/config.json`. This skill shows them, with the options
of the converted dictionary, and saves a new value when the user asks. The settings and their order of precedence are
described in [seagull-diameter-common](../seagull-diameter-common/SKILL.md#where-seagull-runs).

The command [/seagull-diameter-settings](../seagull-diameter-settings/SKILL.md) runs the same steps from explicit
arguments. For an ordinary request ("show the settings", "which Seagull do you use?", "use Docker from now on"), follow
this page.

## Show

Run the script from the folder the session works in, and don't change into the skill folder first:

```bash
python <skill folder>/scripts/show_settings.py
```

It prints three parts, each under its own heading. Show them in this order, with the headings:

1. **Settings.** Each key with its value and where the value came from (the environment, a file, or the default), and the
   two files that were read. A key with no value says `not set`.
2. **Dictionary options.** The `dictionary-options.ini` next to the dictionary that `SEAGULL_DICTIONARY_PATH` names, with
   its content. Without that setting, or without the file, the script says so.
3. **Scenario options.** One sentence: the options of each generated set of scenarios are in the file
   `scenario-options.ini`, in the folder of that set. Finish the answer with it.

Don't search the disk for any of the files, and don't look for `scenario-options.ini`: a generation writes it in its own
folder, and the settings do not name that folder. When the user asks for the options of one set of scenarios and gives
its folder, read the `scenario-options.ini` of that folder and show it under the same kind of heading.

## Change

Write every path in a command in quotes. Single quotes keep a Windows path whole: Bash reads an unquoted
backslash as an escape and turns `C:\work\steps` into `C:worksteps`, and it splits a path with a space into two
arguments. Forward slashes (`'C:/work/steps'`) work on Windows too.

Only when the user asks to change a setting, or answers yes to your offer. The keys:

| Key                       | The user says                                   | Value                                 |
| ------------------------- | ----------------------------------------------- | ------------------------------------- |
| `SEAGULL_RUNNER`          | "use Docker", "run the checks on Windows"       | `docker` or `windows`                 |
| `SEAGULL_WINDOWS_PATH`    | "seagull.exe is in C:\Seagull"                  | The path of `seagull.exe`; must exist |
| `SEAGULL_DOCKER_IMAGE`    | "the image is seagull:test"                     | The image name                        |
| `SEAGULL_DICTIONARY_PATH` | "generate from C:\work\diameter-dictionary.xml" | One dictionary file; must exist       |

```bash
python <skill folder>/../seagull-diameter-common/scripts/seagull_config.py set <KEY> <value>
```

The script refuses an unknown runner and a path that is not a file. It writes the file of the session, and the file in the
user's home folder with `--home`, which the user has to ask for ("for every folder"). It keeps the other keys. Say what you
saved and where, and show the settings again.

Never put a password or a token in the file. The `.ini` files are not changed here: the options of the dictionary
conversion and of the generation are passed as `options=` to the skills that use them.
