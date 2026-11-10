---
name: seagull-diameter-generate-scenarios
description: Use when the user asks to generate Seagull scenarios, or templates (scenarios whose chosen values are placeholders), from a folder of recorded Diameter requests and responses, for example to replay a recorded run. Reads one ready Seagull dictionary and writes client scenarios, configuration, and a stub OCS into a new folder, and runs the dry run against the stub only when the user asks for it.
user-invocable: false
---

# Generate Seagull scenarios from recorded Diameter steps

Turns the recorded Diameter requests of a run into [Seagull](https://gull.sourceforge.net/) scenarios that send them
again, check the answers, and give up when an answer is late. The input is the folder that
[seagull-diameter-extract-steps](../seagull-diameter-extract-steps/SKILL.md) writes, in the format of
[seagull-diameter-common](../seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps). A script does the work;
the agent runs it, reads its report, and tells the user what to review.

The command [/seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) runs the same steps
from formal arguments, and the dry run is part of it. What this page says holds for both.

## Required inputs

What the task needs before it starts, and what it takes from each place.

- **From the user:** the folder of recorded steps.
- **From the settings:** one ready Seagull dictionary, from `dictionary=` in the request or from
  `SEAGULL_DICTIONARY_PATH`. Without either, nothing is written; stop as [The dictionary](#the-dictionary) says.
  Never convert, search for, or take a dictionary yourself.
- **Only when Seagull is started** (the dry run): the runner and its path or image. `seagull_run.py` reads them; see
  [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs). Don't ask for them in advance.

## What to take from the request

| Parameter       | How the user says it                                                 | Rule                                                                                            |
| --------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| steps folder    | "generate scenarios from C:\work\Diameter-Steps"                     | Required. Ask when missing                                                                      |
| filenames       | "the files are request_NN.xml and response_NN.xml"                   | The templates of the names; default `Step-NNN-request.txt` and `Step-NNN-response.txt`. See Run |
| dictionary      | "the dictionary is C:\work\diameter-dictionary.xml"                  | One Seagull dictionary file. From the request, else the setting. Without it, stop. See below    |
| `out=`          | "write them to C:\work\Seagull-Scenario"                             | Optional. The folder must be new or empty                                                       |
| `replace=yes`   | "generate again into the same folder", "replace the old output"      | Only when the user asked, or answered your question. Never to get past the refusal              |
| `timeout=`      | "wait 10 seconds for an answer"                                      | Milliseconds. Default 5000                                                                      |
| `dest=`         | "the OCS is at 10.0.0.5:3868"                                        | Default `127.0.0.1:3868`. Never invent an address                                               |
| `host-ip=`      | "the client IP in the CER is 10.0.0.9"                               | Default `192.0.2.10`                                                                            |
| `mode=template` | "make templates", "I need placeholders"                              | `template` for templates or placeholders. Else `scenario`, or what the options file holds       |
| `placeholder=`  | "make the subscriber number a placeholder SUBSCRIBER_ID"             | Only pairs that the user gives. When placeholders are wanted but none given, ask which AVPs     |
| `option=`       | "log every step", "add check-presence", "pause 500 ms between steps" | `log=true`, `check-presence=true`, `wait-ms=500`; see the options file. Only what the user asks |
| `options=`      | "start from the options of the earlier generation"                   | An older `scenario-options.ini`                                                                 |
| dry run         | "and run it against the stub", "check that it works in Seagull"      | Starts Seagull. Run it only when the user asked; otherwise offer it at the end                  |

A parameter that the user gave in words, and not as `name=value`, is one you interpreted, however plain the words are:
"log every step" is `option=log=true`. Before you run anything, write as plain text how you read the request, as the
parameters (`option=log=true`, `option=wait-ms=500`, `dest=10.0.0.5:3868`), and let the user correct it. Go on without
waiting unless a point is open. The report comes after the files are written, too late to correct anything. A request
for templates is `mode=template`, even when the user did not write the parameter.

**The output folder is never reused silently.** Without `out=` the script takes the first free
`Seagull-Scenario[-N]` next to the steps folder (`--out-auto <parent>`), so an earlier output stays as it was. With
`out=` it refuses a folder that holds files and prints what the folder holds. When that happens, tell the user what the
message says (the number of files and their dates) and ask which they want: another folder, or `replace=yes`. Pass
`--replace` only when the user said so in the request or answered that question; never to get past the error. Then the
old contents move to a sibling folder named `<out>.previous-<time>`, nothing is deleted, and the report names that
folder. The reason: new files written into an old folder mix with scenarios of another sequence of messages, and the
dry run would run them all.

Generating into the same folder again, to change an option or a placeholder, is the case for `replace=yes`: the options
file is read before the old contents move, so the new run starts from it.

`mode=`, `placeholder=`, and `option=` change the options file, and the generator writes the result back. Pass them only
when the user states them in the request. A later run without them uses what the file holds, so the user states a
placeholder once and changes it only by naming it again. When the user asks for placeholders or templates but gives
none, ask which AVP values should become placeholders; never pick them. Ask in plain text, never in a dialog: a dialog
holds four options, and a list of AVPs is longer. List the candidates from the request files one AVP to a row, with its
name and its recorded value, and never merge AVPs under one label such as "subscriber number" or "Origin-Host /
Destination-Host". Mark the AVPs that carry the same recorded value (`Called-Party-Number` next to
`Subscription-Id-Data`) and the ones whose value differs between steps, because one placeholder keeps one value.

When the user specifies a value in words ("the subscriber number") and not an AVP, find the AVPs of the request files that
carry that recorded value. A placeholder replaces the AVPs it names and no others, so an AVP with the same value that
is left out, such as `Called-Party-Number` next to `Subscription-Id-Data`, keeps the recorded value in the template.
Say which AVPs you found, as `placeholder=` pairs, before the script. When one AVP carries the value, go on; when
several do, ask which become placeholders and wait.

## The dictionary

The generator reads **one** dictionary file in the Seagull format. Converting the project's dictionaries is a separate,
one-time job, done by [seagull-diameter-convert-dictionaries](../seagull-diameter-convert-dictionaries/SKILL.md); this
skill never converts, merges, or looks for dictionaries.

Take the path in this order:

1. The path in the request, as `--dictionary <file>`.
2. The setting: `python <skill folder>/../seagull-diameter-common/scripts/seagull_config.py get SEAGULL_DICTIONARY_PATH`.
   Exit status 4 and no output mean that it is not set. The script reads the same setting itself when `--dictionary`
   is absent.

When there is neither, **stop and tell the user**: there is no Seagull dictionary, and they either give the path of a
ready file, or convert the project's dictionaries with `/seagull-diameter-dictionary-convert` and give the result. Do
not search the disk for a dictionary, do not convert one yourself, and do not take one of Seagull's own. A path to a
folder is an error: the generator takes one file. When the user gives a path that the setting does not hold, offer to
save it with `seagull_config.py set SEAGULL_DICTIONARY_PATH <file>`, and save it only after they agree.

The file gives the vendor, the code, and the type of each AVP, so a time, an IP address, and a number are written
right. A name of an enumeration value, such as `INITIAL_REQUEST`, becomes its number only when the dictionary lists the
values in a comment above the AVP, which the converter writes. A dictionary without them, such as one from the project
or one converted with `no-comments=yes`, makes the generator stop on a value name with
`the dictionary lists no values`. Tell the user, and let them write the numbers in the steps or use a converted
dictionary.

## Prerequisites

- Python 3.9 or later, started as `python`, `python3`, or `py -3`.
- For the dry run: a Seagull 1.8.3, either in an image in Docker (by default tagged `seagull:local`) or as a Seagull for
  Windows. Which one is a setting; see
  [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs). On Windows without Docker in
  PowerShell, run the shell scripts through `wsl`.

## Run

1. **Check the steps folder.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/check_steps.py <steps folder> \
       [--request-name <template> --response-name <template>]
   ```

   The files of the folder are named `Step-NNN-request.txt` and `Step-NNN-response.txt` unless the user says otherwise or
   the folder shows otherwise. When the user gives templates (`request_NN.xml`, `response_NN.xml`), or the folder holds
   files whose names show the number of a step and whether the file is a request or a response (`req_01.xml` and
   `resp_01.xml`), derive the two templates, say how you understood them, and pass them to this script and to the
   generator as `--request-name` and `--response-name`. Ask only when the number or the kind of a file cannot be told from
   its name. Don't rename the user's files.

   Stop at a `PROBLEM` line. A line without it is a repair: a comment or a broken closing tag in a recorded message. The
   generator makes the same repairs, so say which steps had them and carry on.
2. **Generate.**

   ```bash
   python <skill folder>/scripts/generate_scenarios.py --steps <steps folder> [--dictionary <file>] \
       [--request-name <template> --response-name <template>] \
       (--out <out folder> | --out-auto <parent of the steps folder>) [--replace] \
       [--timeout-ms <ms>] [--dest <host:port>] [--host-ip <ip>]
   ```

   The first line of the report names the folder when the script chose it (`output folder: ... (new)`). Use that folder
   in the later steps and tell the user where it is.

   When the script says `there is no Seagull dictionary`, nothing was written. Stop and tell the user as "The dictionary"
   describes.

   The parameters `mode=`, `placeholder=`, `option=`, and `options=` become `--option mode=<value>`,
   `--placeholder <AVP>=<NAME>`, `--option <key>=<value>`, and `--options <file>`; repeat a flag for each pair.
   Options that the table does not list: `--check-avps <A,B,...>` sets the AVPs that the scenario compares in each
   answer (default `Result-Code,Session-Id,Auth-Application-Id,CC-Request-Type,CC-Request-Number`; an AVP that the
   recorded answer lacks is skipped and named in the report).
3. **Read the report** that the script prints and saves as `generation-report.txt`, and tell the user:
   - The numbers first: how many steps were read, and how many scenarios were written, one for each Diameter session
     ("3 steps read, 2 scenarios"). Then name each scenario and its steps.
   - Every AVP name with several definitions in the dictionaries (`<name>: definitions (vendor, code) ...; used ...`).
     The generator picks the one with the vendor of the enclosing group, else the first. The user knows the real AVP;
     ask for a confirmation.
   - Every line `<name>: the message needs vendor V code C, but Seagull sends vendor ... code ...`. Seagull finds an AVP
     by name and sends the first definition of the name wherever a scenario uses it, so the scenario sends a different
     AVP than the recorded one, and Seagull reports no error. Tell the user which AVP it is; only a change of the
     dictionary, which the owners of the dictionary decide, can fix it.

   Both kinds of line end with `Found in the request of step N (file)` or `the answer of step N (file)`: they are about
   AVPs that the steps contain, so they are about the scenarios just written, and not about the dictionary in general.
   Say so, and name the step, the file, and the scenario that holds the step (the scenario name lists its steps). A
   name that the dictionary defines twice and that no step uses is not in this report. It is a warning of the conversion
   of the dictionary; if you mention it, call it a possible problem for other steps.
   - The repairs of the recorded messages, and the checks that were skipped.
   - The lines about the options: `default-dwr is off` (the dictionary has no DWR and DWA), `<NAME>: values 'a' and
     'b'; used the first` (one placeholder stands for one value, so two AVPs with different values lose the
     difference), and `placeholder <AVP>: matched no AVP` (a misspelled name or an AVP that is not in the steps).
4. **Dry run.** Run it only when the user asked for it, in the request or in the answer to your offer. When the
   request did not mention it, end your reply by offering the run in one sentence, say that the scenarios are not
   verified yet, and do not start Seagull. Name the runner in the offer: the last line the script printed,
   `Seagull for the check: ...`, has it (see
   [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs)).

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/seagull_run.py dry-run <out folder>
   ```

   The script reads the settings and starts the Seagull they name. Exit status 4 means that a setting has no value; ask
   the one question of "Where Seagull runs", save the answer, and run the script again.

   It starts a stub OCS that answers with the recorded answers, runs each scenario against it, and prints one line for
   each: `successful calls: 1, failed calls: 0`. A scenario that does not end so is a defect of the generation or of the
   dictionary; read the `|E|` line that the script prints. Never report the scenarios as working without this run.

   Report the result in this order. First the verdict, in one sentence: how many scenarios of how many ended with
   `successful calls: 1, failed calls: 0`, and which did not. Then, if the script printed `|E|` lines next to a passed
   scenario, say at the start of the sentence whether they are errors. For the `Current Size` lines, write: "Not an
   error: the receiver of the stub logs it for a vendor AVP whose code is also a base AVP code; the bytes the client
   sends are correct", and name the scenarios where it appears. Last, say what the dry run does not show: the AVPs for
   which the report says that Seagull sends another vendor and code.
5. **Say how to run against the OCS**: put the address in `dest` of `config/conf.client.xml`, replace the placeholder
   address of the CER with `host-ip=`, and run one scenario. Never run it against a real OCS yourself.

   ```bash
   seagull -conf <out>/config/conf.client.xml -dico <out>/dictionary/diameter-dictionary.xml \
       -scen <out>/scenario/<name>.client.xml -log <logs>/<name> -llevel A -bg
   ```

   Without a terminal `-bg` is needed; wait until the log ends with `STOP  log`.

## What the output holds

| Path                                        | Content                                                                                                           |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `scenario/NN-<kind>-steps-<...>.client.xml` | The client scenario of one Diameter session: CER/CEA, then each request and its checks                            |
| `scenario/*.client.xml.tpl`                 | With `mode=template` and text placeholders: the template, with `@@NAME@@` in place of values                      |
| `scenario/*.client.xml.values`              | The values of the placeholders of that template. The `.client.xml` next to it is the template filled in with them |
| `scenario-options.ini`                      | The options of this generation: mode, tags, and placeholder pairs. The next run reads it                          |
| `scenario/*.stub-server.xml`                | A stub OCS for the dry run: answers with the AVPs of the recorded answers                                         |
| `config/conf.client.xml`                    | The client configuration with `dest` and the response timeout                                                     |
| `config/conf.dry-run.client.xml`            | The same, pointing at the stub OCS                                                                                |
| `config/conf.stub-server.xml`               | The stub OCS configuration                                                                                        |
| `dictionary/diameter-dictionary.xml`        | A copy of the Seagull dictionary that the scenarios and the stub use                                              |
| `generation-report.txt`                     | What the generator did and what to review                                                                         |

## What the scenarios do

- One scenario for each Diameter session. Seagull ties an answer to its call by the `Session-Id`, and it refuses an
  answer with a `Session-Id` that the call has not used. So steps with the same `Session-Id` are one scenario, and a new
  `Session-Id` starts a new one. Do not join sessions into one scenario.
- Each request carries the recorded AVPs in the recorded order with fixed values. Only the Hop-by-Hop and End-to-End
  identifiers come from counters. The attributes of the recorded root element are not sent, and commented-out AVPs are
  left out.
- A time such as `2026-10-27 14:00:52 +0000 UTC` becomes 4 bytes of NTP time in hex, and an IP address in an AVP of type
  Address becomes the address family followed by the address bytes. The time is a fixed value unless the
  `generated-timestamp` option is on.
- The `<default>` section answers a Device-Watchdog request from the OCS with a DWA, so a long run is not dropped. It is
  on unless `default-dwr=false`.
- The other tags are off until the options file turns them on: a Session-Id and an Event-Timestamp made at runtime, a
  `<log>` line for each step, `<check-presence>` before each `<check-value>`, and a `<wait-ms>` pause between steps.
  [The options file](../seagull-diameter-common/SKILL.md#the-options-file) lists the keys.
- In `mode=template`, the AVPs that a `[placeholders]` pair names carry `@@NAME@@` (`text` substitution) or a Seagull
  variable (`native` substitution). With `text`, the generator also fills the template in from the values it wrote, so
  the dry run runs the template. Fill a template in for real with
  `seagull-diameter-common/scripts/apply_placeholders.py`; it takes values from `--set`, from the environment with
  `--env`, and from a values file. With `native`, the scenario sets each variable once, in its first step, and restores
  it in the later steps; only top-level, non-repeated AVPs can be native.
- `TGPP-` at the start of an AVP name is written `3GPP-`, as the converted dictionary names it; the bytes are the same.
- After each answer the scenario checks the AVPs of `--check-avps` against the recorded answer, and any difference
  fails the call with `check failed in [CCA] command, value of avp [Result-Code]. Expected [2001] but got [5012]`.
- The response timeout is `call-timeout-ms` in the configuration. It applies to the wait for each answer, not to the
  whole call. The `timeout` attribute of `<receive>` is not read by Seagull 1.8.3.

## Limits

- The check compares top-level AVPs only. An AVP inside a group that has the name of a top-level one, such as the
  `Result-Code` of a Multiple-Services-Credit-Control, cannot be told apart by name.
- The CER carries a placeholder `Host-IP-Address`.
- `generated-timestamp`, and the time part of a generated Session-Id, need `time-method=<name>`: the name of a Seagull
  method that returns the time. The Seagull 1.8.3 image does not know the `sys_date_time_secs`
  that another project's scenario uses, and it does not know `sys_time_secs` either (`No method extern found for ...`).
  Without `time-method`, a generated Session-Id is `<Origin-Host>;<counter>` and `generated-timestamp=true` is an error.
  Set `time-method` only when the Seagull that runs the scenario defines the method, and say that the dry run in this
  image cannot check it.
- The generated Session-Id replaces the recorded one, so the scenario no longer compares the Session-Id of the answer.
- The check of an answer uses the recorded value, or the placeholder when the checked AVP has one in `text`
  substitution. In `native` substitution it keeps the recorded value.
- A stub OCS that runs the Seagull decoder may log `Current Size: ... is greater than expecting one: ...` for a vendor
  AVP whose code is also a base AVP code. It is a log line of the receiver; the bytes that the client sends are correct.

## Don't

- Don't edit a generated scenario by hand; change the input or the options and generate again.
- Don't convert the generated files to Windows line endings. Seagull's configuration parser stops with
  `lexical error : unknown token` on a carriage return, so a configuration file with CRLF does not load.
- Don't commit the output or the recorded messages to a repository unless the user asks: they hold subscriber data.
- Don't pick between several definitions of an AVP on your own; show the user the line from the report.
