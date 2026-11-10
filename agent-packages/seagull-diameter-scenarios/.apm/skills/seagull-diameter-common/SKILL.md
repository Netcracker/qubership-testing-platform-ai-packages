---
name: seagull-diameter-common
description: Support files for the other seagull-diameter skills, and the format of the folder of recorded Diameter steps. Not a task; never invoke it.
user-invocable: false
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# seagull-diameter-common

This folder holds the code and the format that
[seagull-diameter-steps-extract](../seagull-diameter-steps-extract/SKILL.md)
and [seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) share. It is a skill only
because APM deploys the files of a skill folder next to each other, so the scripts of the other skills can import
`../../seagull-diameter-common/scripts`.

| Script                           | Purpose                                                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `scripts/steps_format.py`        | Reads a folder of recorded steps; repairs and reports the faults of hand-edited text                             |
| `scripts/check_steps.py`         | Checks a folder of recorded steps; run it before generating                                                      |
| `scripts/dict2seagull.py`        | Converts the project's AVP dictionaries into Seagull dictionaries; the generate and convert skills use it        |
| `scripts/dictionary_options.py`  | Reads and writes the flag options of the dictionary conversion; dict2seagull.py applies them                     |
| `scripts/scenario_options.py`    | Reads and writes the options file; matches AVPs to placeholders; fills templates in                              |
| `scripts/apply_placeholders.py`  | Replaces the `@@NAME@@` placeholders of a template with values                                                   |
| `scripts/scenario_text.py`       | Reads the `<avp>` lines of a generated scenario, with their paths; the templatize and externalize scripts use it |
| `scripts/output_folder.py`       | Picks the first free output folder (`next-free`) and describes a folder (`describe`)                             |
| `scripts/seagull_config.py`      | Reads and writes the settings that say where Seagull runs; see "Where Seagull runs"                              |
| `scripts/seagull_run.py`         | Runs the dry run and the check of converted dictionaries with the Seagull that the settings name                 |
| `scripts/seagull_windows_run.py` | Runs the dry run and the check of converted dictionaries with a Seagull for Windows; seagull_run.py calls it     |

## Where Seagull runs

The dry run of a generation and the check of converted dictionaries start Seagull. It runs in the Seagull image in
Docker, or as `seagull.exe` of a Seagull for Windows. One script chooses, from the settings, and runs it:

```bash
python <skill folder>/scripts/seagull_run.py dry-run <output folder>
python <skill folder>/scripts/seagull_run.py check-converted <converted folder>
```

The script reads the settings itself, so the caller passes only the folder. It prints the lines that the two runners
print, `<name>: successful calls: 1, failed calls: 0`, and its exit status is that of the run. `--runner`,
`--seagull-exe`, and `--image` override the settings for one run, and `--logs <folder>` keeps the Seagull logs of a
Seagull for Windows. With `docker` on Windows it runs the script of the image through `wsl`. Seagull for Windows uses
the ports of the machine, so the script gives the stub a free one in copies of the configurations, and it stops only the
processes that it started.

**Ask only when the script asks.** Exit status 4 and a message `SEAGULL_RUNNER is not set` or `SEAGULL_WINDOWS_PATH is not
set` mean that a setting has no value. Then ask the user one question: Docker with a Seagull image, or Seagull for
Windows and where its `seagull.exe` is (don't guess a path; the usual place is
`C:\Program Files (x86)\Seagull\seagull.exe`). Save the answer after the user confirms, and run the script again:

```bash
python <skill folder>/scripts/seagull_config.py set SEAGULL_RUNNER windows
python <skill folder>/scripts/seagull_config.py set SEAGULL_WINDOWS_PATH "C:\Program Files (x86)\Seagull\seagull.exe"
```

`set` writes the file of the session; add `--home` when the user wants the answer for every folder. It refuses an
unknown runner and a path that is not a file. Never put a password or a token in the file.

The settings are in one JSON file, `.seagull-diameter/config.json`. Two files are read, in this order: the one in the
nearest folder, from the current folder upward, that holds it, then the one in the user's home folder. Don't search the
disk for the file or for Seagull. A value in the user's request wins, then the environment variable of the same name,
then the file, then the default.

| Key                       | Meaning                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| `SEAGULL_RUNNER`          | `docker` or `windows`                                                                     |
| `SEAGULL_DOCKER_IMAGE`    | The Seagull image for `docker`. Default `seagull:local`                                   |
| `SEAGULL_WINDOWS_PATH`    | The `seagull.exe` for `windows`, e.g. `C:\Program Files (x86)\Seagull\seagull.exe`        |
| `SEAGULL_DICTIONARY_PATH` | The one Seagull dictionary file for the generator, e.g. `C:\work\diameter-dictionary.xml` |

To tell the user where the next run would happen, name the runner and its path in the offer: the last line that the
conversion, the generation, the templates, and the data-file scripts print, `Seagull for the check: ...`, or
`python <skill folder>/scripts/seagull_config.py show`, has them. Don't ask
where Seagull runs, or for the path of `seagull.exe` or the image, when either printed a value. To show or change the
settings at the user's request, see
[seagull-diameter-manage-settings](../seagull-diameter-manage-settings/SKILL.md).

## The folder of recorded steps

One folder holds the Diameter steps of one recorded run, in the order they ran.

```text
<folder>/
  Step-001-request.txt
  Step-001-response.txt
  Step-002-request.txt
  Step-002-response.txt
  Steps-index.csv          optional
```

- `NNN` is a number of any width; the steps are read in numeric order. A step needs both of its files.
- **The names are a default, not a rule.** A folder may name its files in any way that shows the number of the step and
  whether the file is a request or a response, for example `request_01.xml` and `response_01.xml`, or `req_1.xml` and
  `resp_1.xml`. Two templates describe the names, with the number written as `NN` (two or more capital N, once in each
  template): `request_NN.xml` and `response_NN.xml`. `check_steps.py` and `generate_scenarios.py` take them as
  `--request-name` and `--response-name`; without them the templates are `Step-NNN-request.txt` and
  `Step-NNN-response.txt`. A number is compared as a number, so `request_1.xml` and `response_01.xml` are one step.
  When a user gives a folder of other names, derive the two templates from the names, say how you understood them
  (`request_NN.xml` and `response_NN.xml`), and pass them; ask only when the number or the kind of a file cannot be told
  from its name. A file that matches neither template is reported as a problem.
- The text of a file is one Diameter command as XML, written exactly as it was recorded, in UTF-8. The root element is
  the
  command (`CCR`, `CCA`, and so on). Each child element is an AVP, named as the project dictionary names it. A grouped
  AVP
  holds its members as child elements; any other AVP holds its value as text.

  ```xml
  <CCR Description="CCR-I" Service="peer-1">
    <Session-Id>VOICE94156515166</Session-Id>
    <Auth-Application-Id>4</Auth-Application-Id>
    <CC-Request-Type>1</CC-Request-Type>
    <Subscription-Id>
      <Subscription-Id-Type>0</Subscription-Id-Type>
      <Subscription-Id-Data>491700000001</Subscription-Id-Data>
    </Subscription-Id>
  </CCR>
  ```

- The attributes of the root element (`Description`, `Service`, and any others) are settings of the system that recorded
  the step. They are never sent. `Description` names the step in the generated scenario.
- Every request has a `Session-Id`. Steps with the same `Session-Id`, one after another, are one Diameter session.
- A value is written the way the recording system took it: numbers as digits, a time as `2026-10-27 14:00:52 +0000 UTC`,
  an IP address in dotted form, bytes as `0x...`, an enumeration in a request as its number (an answer may use its
  name).
- `Steps-index.csv` is optional: UTF-8 with a BOM, separator `;`, columns `Step file number` and
  `Step number in the scenario`, and any others. The generator uses the second column only in comments.

The reader repairs two faults that hand editing leaves, and reports every repair: a comment (`<!-- ... -->`, also one
that
ends in `--` without `>`) is removed together with the AVPs inside it, and a closing tag without `>` is completed.
Anything
else that is not XML is an error: send the folder back to the person who made it.

## The options file

`scenario-options.ini` holds what the user decided about the shape of the generated scenarios. The generator reads it,
applies the `--option` and `--placeholder` flags of the run, and writes the result to `scenario-options.ini` in the
output folder. A run in a new folder starts from an older file when `--options` names it, and only reads that file. Edit
the options by running the generator with a flag, not by hand, unless the user asks.

```ini
[output]
mode = template
substitution = text

[tags]
default-dwr = true
generated-session-id = false
generated-timestamp = false
log = false
check-presence = false
wait-ms = 0
time-method =

[placeholders]
Subscription-Id/Subscription-Id-Data = SUBSCRIBER_ID
3GPP-Charging-Id = CHARGING_ID_HEX
wait-ms = WAIT_MS
```

| Key                    | Values                      | Effect                                                                                   |
| ---------------------- | --------------------------- |------------------------------------------------------------------------------------------|
| `mode`                 | `scenario`, `template`      | `scenario` writes fixed values and ignores `[placeholders]`; `template` applies them     |
| `substitution`         | `text`, `native`            | `text` writes `@@NAME@@`; `native` keeps the value in the scenario as a Seagull variable |
| `default-dwr`          | `true`, `false`             | A `<default>` section that answers DWR with DWA. Default `true`                          |
| `generated-session-id` | `true`, `false`             | A Session-Id built from a counter in the first step and restored in the later ones       |
| `generated-timestamp`  | `true`, `false`             | An Event-Timestamp set at runtime; needs `time-method`                                   |
| `log`                  | `true`, `false`             | A `<log>` line in each send and receive block                                            |
| `check-presence`       | `true`, `false`             | A `<check-presence>` before each `<check-value>`                                         |
| `wait-ms`              | milliseconds, `0` for none  | A `<wait-ms>` pause between two steps                                                    |
| `time-method`          | a Seagull method name       | The method that returns the time, for `generated-timestamp` and a timed Session-Id       |

In `[placeholders]` the key is the AVP name as the scenario file spells it, and the value is the placeholder name
(letters, digits, and `_`, starting with a letter). A bare name matches that AVP at any depth, a path such as
`Subscription-Id/Subscription-Id-Data` matches only inside that group, and `GGSN-Address[2]` matches the second sibling
of that name. The most specific key wins. The key `wait-ms` names the placeholder for the pause. An empty value removes
the pair.

One placeholder stands for one value in a scenario file: the first AVP that uses it sets the value, and the generator
reports a different value of a later one. A hexadecimal value keeps its `0x` outside the marker
(`0x@@CHARGING_ID_HEX@@`), and the values file holds the digits only.

## Python

The scripts need Python 3.9 or later and no other package. Start them as `python`, `python3`, or `py -3`, whichever the
machine has.

## Paths in commands

Write every path in a command in quotes. Single quotes keep a Windows path whole: Bash reads an unquoted
backslash as an escape and turns `C:\work\steps` into `C:worksteps`, and it splits a path with a space into two
arguments. Forward slashes (`'C:/work/steps'`) work on Windows too.
