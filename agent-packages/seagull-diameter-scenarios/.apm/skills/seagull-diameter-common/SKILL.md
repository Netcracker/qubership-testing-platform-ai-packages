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
| `scripts/seagull_windows_run.py` | Runs the dry run and the check of converted dictionaries with a Seagull for Windows                              |

## Where Seagull runs

The dry run of a generation and the check of converted dictionaries start Seagull. It runs in the Seagull image in
Docker (`dry-run.sh`, `check-converted.sh`), or as `seagull.exe` of a Seagull for Windows
(`seagull_windows_run.py`). The settings that choose are in one JSON file, `.seagull-diameter/config.json`.

**Read exactly two paths, in this order:** the file in the folder the session works in, then the file in the user's
home folder. Don't search the disk for the file or for Seagull.

| Key                       | Meaning                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| `SEAGULL_RUNNER`          | `docker` or `windows`                                                                     |
| `SEAGULL_DOCKER_IMAGE`    | The Seagull image for `docker`. Default `seagull:local`                                   |
| `SEAGULL_WINDOWS_PATH`    | The `seagull.exe` for `windows`, e.g. `C:\Program Files (x86)\Seagull\seagull.exe`        |
| `SEAGULL_DICTIONARY_PATH` | The one Seagull dictionary file for the generator, e.g. `C:\work\diameter-dictionary.xml` |

A value in the user's request wins, then the environment variable of the same name, then the file, then the default.
Never put a password or a token in the file. Do these steps before you run Seagull, and also before you offer a run or
say anything to the user about where Seagull runs:

1. Read every setting at once: `python <skill folder>/scripts/seagull_config.py show`. It prints each key with its
   value and where the value came from, or `not set`. (`get KEY` prints one value, and exits with 4 and prints nothing
   when the key has no value.) When `SEAGULL_RUNNER` has a value, the answer is known. Name the runner and its path in
   your offer, for example "with the Seagull for Windows, `C:\Program Files (x86)\Seagull\seagull.exe`". Don't ask the
   user where Seagull runs, and don't ask for the path of `seagull.exe` or for the image when `show` printed it.
2. Only when the runner is not set, ask the user one question: Docker with a Seagull image, or Seagull for Windows
   (and where its `seagull.exe` is, so don't guess a path; the usual place is
   `C:\Program Files (x86)\Seagull\seagull.exe`). Check the answer by what the user says, and save it after the user
   confirms:

   ```bash
   python <skill folder>/scripts/seagull_config.py set SEAGULL_RUNNER windows
   python <skill folder>/scripts/seagull_config.py set SEAGULL_WINDOWS_PATH "C:\Program Files (x86)\Seagull\seagull.exe"
   ```

   `set` writes the session folder; add `--home` when the user wants the answer for every folder. It refuses an unknown
   runner and a path that is not a file.
3. With `docker`, run the scripts as before, with the image from `SEAGULL_DOCKER_IMAGE`. With `windows`, run
   `python <skill folder>/scripts/seagull_windows_run.py dry-run <output folder> --seagull-exe <path>`, or
   `check-converted <converted folder>` for the dictionaries. They print the same lines as the scripts, and the exit
   status is the same. `--logs <folder>` keeps the Seagull logs.

Seagull for Windows uses the ports of the machine, so the runner gives the stub a free one in copies of the
configurations. It stops only the processes that it started. Docker is not needed, and nothing is run in WSL.

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
