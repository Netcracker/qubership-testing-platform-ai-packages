# Seagull Diameter scenarios user guide

The `seagull-diameter-scenarios` package gives your coding agent five commands. They turn a recorded test run into
[Seagull](https://gull.sourceforge.net/) scenarios that send the recorded Diameter requests again, check the answers,
and give up when an answer is late. You can write the scenarios with fixed values or as templates with placeholders, and
you can try them against a stand-in OCS before they meet the real one.

Follow the sections in order the first time. For the picture of how the steps connect and where a run can stop, see
[how the skills work together](workflow.md). For the list of skills, see the [package `README`](../README.md).

## Before you start

You need:

- A coding agent that APM can deploy to, such as Claude Code, Codex, Cursor, or OpenCode.
- The APM command-line tool, `apm`, on your `PATH`. Run `apm --version` to check. The layout of this package follows the
  one of `tdm-test-data-assistant`, which was checked with APM 0.29.1.
- Python 3.9 or later, available as `python`, `python3`, or `py -3`. The scripts use nothing outside the standard
  library.
- For the dry run and for checking converted dictionaries, one of two ways to start Seagull 1.8.3: Docker with an image
  tagged `seagull:local` (this repository does not build the image; build it with `docker build -t seagull:local .` in
  the repository that holds the Seagull `Dockerfile`; on Windows, Docker works in WSL, and you run the shell scripts as
  `wsl sh <script> ...`), or a Seagull for Windows, with its `seagull.exe`. See
  [Where Seagull runs](#where-seagull-runs).
- The project's Diameter dictionaries in the project format, in one folder. They must define the
  Diameter base protocol (`CER`, `DWR`, and the AVPs of the handshake), in any file; see
  [The base protocol](dictionary-conversion.md#the-base-protocol). Seagull reads its own format, so the generator
  converts them.
- The recorded run: either a file you can describe (an `xlsx` export of a test database, for example) or a folder that
  already has the `Step-NNN-request.txt` and `Step-NNN-response.txt` files.

## Install the package

Run `apm install` in the folder in which you start your agent, with the agent that you use:

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/seagull-diameter-scenarios#main
```

The part after `#` is the branch or tag to follow; use a tag to stay on one version. `--target` names the agent:
`claude`, `codex`, `copilot`, `cursor`, `gemini`, or `opencode`, several joined with commas. APM downloads the package
with Git, so the repository must be readable with your credentials.

APM records the dependency in the `apm.yml` of that folder. Start your agent in the folder, or restart a session that
was already running, and type `/seagull-diameter-scenario-generate`. The agent should answer by asking for the
arguments. If it does not know the command, the skills are not loaded: check that `apm install` finished without an
error, and restart the session. Codex starts a skill only when you name it, and the package says so in
`agents/openai.yaml`; nothing else needs setting.

## Upgrade the package

Run the installation again in the folder that holds `apm.yml`:

```bash
apm install
```

To move to another branch or tag, change the part after `#` in the dependency line of `apm.yml` first, then run the
command. If `apm install` leaves the old version in place, run `apm --help` and look for the command that refreshes
locked dependencies in your APM version. Restart the agent session afterwards, so it reads the new skills.

Your own work is not touched by an upgrade: the output folders and the `scenario-options.ini` files live outside the
package. After an upgrade, generate once with the same arguments and compare the report with the previous one.

## The skills

| Skill                                    | Type    | Use it to                                                                                        |
| ---------------------------------------- | ------- | ------------------------------------------------------------------------------------------------ |
| `/seagull-diameter-steps-extract`        | command | Turn a file of recorded steps into the folder of request and response files                      |
| `/seagull-diameter-scenario-generate`    | command | Turn that folder into scenarios or templates, configuration, and a dictionary, and run a dry run |
| `/seagull-diameter-scenario-templatize`  | command | Turn generated scenarios into templates, without reading the steps again                         |
| `/seagull-diameter-scenario-externalize` | command | Make chosen AVPs read their values from a CSV data file, one row for each call                   |
| `/seagull-diameter-dictionary-convert`   | command | Convert the project's dictionaries into Seagull dictionaries, and check them                     |
| `seagull-diameter-extract-steps`         | plain   | Do the same as the steps command, from a request in your own words                               |
| `seagull-diameter-generate-scenarios`    | plain   | Do the same as the generate command, from a request in your own words                            |
| `seagull-diameter-templatize-scenarios`  | plain   | Do the same as the templatize command, from a request in your own words                          |
| `seagull-diameter-externalize-scenarios` | plain   | Do the same as the externalize command, from a request in your own words                         |
| `seagull-diameter-convert-dictionaries`  | plain   | Do the same as the dictionary command, from a request in your own words                          |
| `seagull-diameter-common`                | support | Hold the shared scripts and the formats. You never invoke it                                     |

The commands run only when you type their name, and they take their arguments literally. A plain skill is picked by the
agent from an ordinary request, such as "convert the dictionaries in C:\work\dictionaries". Every task has a plain
skill, and the command is the place for many exact parameters.

### Plain requests

A plain request starts the same steps as the command, with these rules from the package instruction:

- The agent does not start Seagull (Docker, WSL, or Seagull for Windows), so there is no dry run and no check of a
  converted dictionary, unless your request asks for it.
  Otherwise it finishes the task and offers the run in one sentence.
- It does not move, replace, or delete an existing file or folder, and it writes to a new folder.
- It does not choose the dictionaries to merge, the placeholders, the flags, or an option such as a time method. When
  your request does not give them, it asks.
- When it had to interpret your wording to fill a parameter, it says how it understood it, for example
  `combine=Gy,Sy`, before it runs anything, and you can correct it.

The command is the place for many exact parameters. Both ways give the same result for the same parameters.

### /seagull-diameter-steps-extract

**Purpose.** Reads a recorded run and writes each Diameter request and each response to its own file. The structure of
your file differs from every other, so the skill has none built-in. You describe it in the prompt and the skill does
what you said.

You can also ask in plain words, for example "extract the Diameter steps from C:\work\Steps.xlsx: the sheet is Main,
column F holds the request, column G the response". The agent follows the skill `seagull-diameter-extract-steps` and
the rules in "Plain requests" above. If your description leaves one of the questions of the skill open, it asks them all
in one message, and when you described the file in running text it restates the rules as it understood them before it
writes anything.

**Arguments.**

```text
/seagull-diameter-steps-extract <source> -- <how to read it>
```

`<source>` is an `xlsx`, `csv`, JSON, or log file, or a folder that already has the step files. The text after `--` is
free. It must say:

1. which sheet, table, or section holds the steps;
2. whether the rows are in the order the steps ran, or what to sort by;
3. how a request and its response are told apart, and how they are tied to a step;
4. where the text of a message is;
5. how to tell a Diameter step from any other step, for example that the text starts with `<CCR` or `<CCA`;
6. which other steps to skip, if any;
7. optionally, the output folder, which must be new or empty. Default: a new folder named `Diameter-Steps` next to the
   source, or `Diameter-Steps-2` and so on when that name is taken. The agent never writes into a folder that holds
   files; it tells you what the folder holds and asks.

If the text leaves a point open, the agent asks one message with all its questions and waits. It never guesses the
structure.

**Example prompt.**

```text
/seagull-diameter-steps-extract "C:\work\Steps and messages.xlsx" -- The first sheet has one row for each node of a tree
of test steps, in the order of execution. The columns are ID, PARENT, TYPE, DESCRIPTION. A step is a row with TYPE
StepInstance. The messages of a step are in rows below it: TYPE "outgoing message" is the request and TYPE "incoming
message" is the response; their text is in DESCRIPTION. Every step has one of each. Keep only the steps whose request
starts with a Diameter command in angle brackets, such as <CCR. Write the files to C:\work\Diameter-Steps.
```

**What you get.**

```text
C:\work\Diameter-Steps\
  Step-001-request.txt   Step-001-response.txt
  Step-002-request.txt   Step-002-response.txt
  ...
  Steps-index.csv
```

Each file holds one Diameter command as XML, exactly as it was in the source. The format is in
[the common skill](../.apm/skills/seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps).

**What the agent tells you.** It looks at the source first and reports any difference from your description before it
writes anything. After the extraction it reports the number of steps in the source, how many are Diameter steps, the
output folder, every step it dropped with the reason, and the repairs that the check lists. For example:

```text
The sheet has 12 steps. 10 are Diameter steps (CCR/CCA), written to C:\work\Diameter-Steps. 2 were dropped: no Diameter command.
The check found no problem. The files hold subscriber data; keep them out of a repository.
```

A source folder that already has the files skips the extraction; the agent only runs the check.

### /seagull-diameter-scenario-generate

**Purpose.** Reads the steps folder and writes the client scenarios, a stub OCS for the dry run, the configuration, and
a Seagull dictionary merged from your project dictionaries. Then it runs the dry run.

You can also ask in plain words, for example "generate scenarios from C:\work\Diameter-Steps, the dictionaries are in
C:\work\dictionaries, merge RoSCP and Gy, and log every step". The agent follows the skill
`seagull-diameter-generate-scenarios` and the rules in "Plain requests" above. It generates, but it runs the dry run
only when you ask for it, with "and run it against the stub" in the request or with a yes to its offer; until then it
says that the scenarios are not verified. It asks which dictionaries to merge and which AVPs become placeholders when
you do not say, and a generation into a folder that has files stops until you choose another folder or `replace=yes`.

**Arguments.**

```text
/seagull-diameter-scenario-generate <steps folder> dictionaries=<folder> merge=<A,B,C> [out=<folder>] [replace=yes] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>] [mode=scenario|template] [placeholder=<AVP>=<NAME> ...] [option=<key>=<value> ...] [options=<file>]
```

| Argument         | Meaning                                                                                                   | Default                                                      |
| ---------------- | --------------------------------------------------------------------------------------------------------- |--------------------------------------------------------------|
| first argument   | The folder of recorded steps                                                                              | required                                                     |
| `dictionaries=`  | The folder of the project's dictionaries                                                                  | required                                                     |
| `merge=`         | The dictionaries to merge, without `.xml`, in order. For an AVP that two of them define, the first wins   | required                                                     |
| `out=`           | Where to write. A folder with files is refused, see [the output folder](#the-output-folder)               | a new `Seagull-Scenario`, `-2`, ... next to the steps folder |
| `replace=`       | `yes` moves the old contents of a non-empty `out=` aside and generates anew                               | no                                                           |
| `timeout=`       | How long Seagull waits for each answer, in milliseconds                                                   | 5000                                                         |
| `dest=`          | Address and port of the OCS                                                                               | `127.0.0.1:3868`, the stub OCS                               |
| `host-ip=`       | The IP address that the capabilities exchange announces as the client's                                   | a placeholder address                                        |
| `mode=`          | `scenario` for fixed values, `template` for placeholders                                                  | the options file, else `scenario`                            |
| `placeholder=`   | One `<AVP>=<NAME>` pair; repeat it. An empty `<NAME>` removes the pair                                    | the pairs in the options file                                |
| `option=`        | One `<key>=<value>` option, see [Options and tags](#options-and-tags)                                     | the options file                                             |
| `seagull-base=`  | A `base_draft08.xml` of Seagull for a folder without the base protocol. Your definitions win              | none: such a folder is refused                               |
| `options=`       | An older options file to start from; it is only read. The result goes to the output folder                | `scenario-options.ini` in the output folder                  |

When you leave out `dictionaries=` or `merge=`, the agent lists the files of the dictionary folder and asks which to
merge. If the generator says an AVP is in none of the dictionaries, add the one that has it to `merge=`.

#### The output folder

A run never writes into a folder that already holds files, because new scenarios would mix with the old ones. If the old
ones came from another sequence of messages, the folder would hold scenarios of both, and the dry run would run them
all.

- Without `out=`, the agent uses a new folder next to the steps folder: `Seagull-Scenario`, or `Seagull-Scenario-2` and
  so on when that name is taken. The report names the folder. Earlier outputs stay as they were.
- With `out=` that names an empty or missing folder, the agent writes there.
- With `out=` that names a folder with files, the agent stops, tells you what the folder holds (the number of files and
  their dates), and asks: another folder, or `replace=yes`.
- With `replace=yes`, the old contents move to a sibling folder named `<out>.previous-<date>-<time>`. Nothing is
  deleted. The options file is read before the move, so the new run starts from it.

A new folder starts without an options file. To keep your mode, tags, and placeholders, name the older file with
`options=<old folder>\scenario-options.ini`; the generator only reads it and writes the result to the new folder.

**Example prompt, ready scenarios.**

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario dest=10.0.0.5:3868
```

**What you get.** One client scenario and one stub scenario for each Diameter session. Steps that share a `Session-Id`
are one scenario, because Seagull refuses an answer whose `Session-Id` the call has not used.

```text
C:\work\Seagull-Scenario\
  scenario\
    01-voice-steps-001-002.client.xml        01-voice-steps-001-002.stub-server.xml
    02-voice-steps-003-004.client.xml        02-voice-steps-003-004.stub-server.xml
    03-sms-steps-005.client.xml              03-sms-steps-005.stub-server.xml
    04-data-steps-006-007-008-009-010.client.xml   04-data-steps-006-007-008-009-010.stub-server.xml
  config\
    conf.client.xml        (dest = the OCS, call-timeout-ms)
    conf.dry-run.client.xml (the same, pointing at the stub OCS)
    conf.stub-server.xml
  dictionary\
    diameter-dictionary.xml  conversion-report.txt
  scenario-options.ini
  generation-report.txt
```

The generated files use line feed as the line ending, which Seagull needs. Do not let an editor or Git convert them: the
configuration parser stops on a carriage return.

**What the agent tells you.** It prints the report and asks you to review these points:

- the scenarios, one for each session;
- every AVP name that your dictionaries define more than once, and which definition was used. The generator picks the
  definition with the vendor of the enclosing group, else the first one. You know what the recorded run really sent, so
  confirm each line, and change the `merge=` order if a choice is wrong;
- the repairs that the recorded messages needed, and the answer fields that were not checked;
- the lines about the options (see [Options and tags](#options-and-tags)).

An excerpt of a report:

```text
scenario 01-voice-steps-001-002: 2 step(s)
scenario 02-voice-steps-003-004: 2 step(s)
options: C:\work\Seagull-Scenario\scenario-options.ini
Node-Id: definitions (vendor, code) [(10415, 2064), (99999, 5)]; used vendor 10415 code 2064, chosen by the vendor of the enclosing group
time converted to NTP hex: 8 time(s)
```

**The dry run.** After the report the agent runs a stub OCS that answers each request with the AVPs of the recorded
answer, and runs each client scenario against it. It never calls the scenarios working without this run. You can start
it yourself:

```bash
sh .apm/skills/seagull-diameter-generate-scenarios/scripts/dry-run.sh <out folder> [<image>]
```

Expected, one line for each scenario:

```text
01-voice-steps-001-002: successful calls: 1, failed calls: 0
02-voice-steps-003-004: successful calls: 1, failed calls: 0
```

A scenario that does not end so is a defect of the generation or of the dictionary. The line carries the error that
Seagull logged. Do not take the scenarios to the OCS before every line is clean.

**Example prompt, a template.**

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario mode=template placeholder=Subscription-Id/Subscription-Id-Data=SUBSCRIBER_ID placeholder=3GPP-Charging-Id=CHARGING_ID_HEX
```

Besides the client scenario, each session then has two more files:

| File                       | Content                                                                             |
| -------------------------- |-------------------------------------------------------------------------------------|
| `<name>.client.xml.tpl`    | The template, for example `value="0x@@CHARGING_ID_HEX@@"`                           |
| `<name>.client.xml.values` | `NAME=value` lines with the recorded values; a hexadecimal value does not hold `0x` |
| `<name>.client.xml`        | The template filled in with the values file; the dry run uses this one              |

### /seagull-diameter-scenario-templatize

**Purpose.** Turns scenarios that you already generated into templates, without reading the steps again. Use it when you
decide later that some values should be parameters.

You can also ask in plain words, for example "make the subscriber number of the scenarios in
C:\work\Seagull-Scenario\scenario a placeholder SUBSCRIBER_ID". The agent follows the skill
`seagull-diameter-templatize-scenarios` and the rules in "Plain requests" above. It asks which AVP values become
placeholders when you do not say. If a template or a values file of the same name already exists next to a scenario, it
stops and asks for another folder or for your permission to replace it, because the script would overwrite it. It does
not run the dry run unless you ask.

**Arguments.**

```text
/seagull-diameter-scenario-templatize <scenario files or folder> [placeholder=<AVP>=<NAME> ...] [options=<file>] [out=<folder>]
```

The first argument is one or more `*.client.xml` files, or the `scenario` folder of a generation. Pairs and options work
as in the generate command. When there is no options file and you name no placeholder, the agent asks which values
should become placeholders. It never picks them.

**Example prompt.**

```text
/seagull-diameter-scenario-templatize C:\work\Seagull-Scenario\scenario placeholder=Subscription-Id-Data=SUBSCRIBER_ID placeholder=Rating-Group=RATING_GROUP
```

**What you get.** For each `X.client.xml`, the files `X.client.xml.tpl` and `X.client.xml.values`. Filling the template
in with the unchanged values file gives back the original scenario.

**What the agent tells you.** The number of placeholders for each file, the lines `NAME: values 'a' and 'b'; used the
first` (one placeholder stands for one value, so two AVPs with different values lose the difference), and the lines
`placeholder <AVP>: matched no AVP` (a misspelled name, or an AVP that the scenarios do not have). Example:

```text
04-data-steps-006-007-008-009-010.client.xml: 2 placeholder(s) written to 04-data-steps-006-007-008-009-010.client.xml.tpl
placeholder Rating-Group: matched no AVP
options: C:\work\Seagull-Scenario\scenario\scenario-options.ini
```

The script reads scenarios whose `<avp>` elements stand on one line each, as the generator writes them. It changes only
the `<command>` elements.

### Fill a template in

A template is not run as it is. `apply_placeholders.py` fills it in. Run it yourself, or let a pipeline run it:

```bash
python .apm/skills/seagull-diameter-common/scripts/apply_placeholders.py 04-data.client.xml.tpl --out 04-data.client.xml \
    --values 04-data.client.xml.values --env --set SUBSCRIBER_ID=966581105391
```

A value comes from `--set`, then from the environment (only with `--env`), then from the values file. The script stops
and names every placeholder that has no value:

```text
error: no value for placeholder(s) RATING_GROUP
```

### /seagull-diameter-scenario-externalize

**Purpose.** Makes chosen AVPs read their values from a CSV file while Seagull runs. Seagull picks one row for each
call, so one scenario can send many subscribers or Session-Ids without a new scenario for each. Use it after generation,
when you want the values outside the scenario and outside the command line.

You can also ask in plain words, for example "read the subscriber number of the scenarios in
C:\work\Seagull-Scenario\scenario from a data file, column MSISDN, and make 50 calls at random". The agent follows the
skill `seagull-diameter-externalize-scenarios` and the rules in "Plain requests" above. It asks which AVPs come from
the file when you do not say, proposes names for the columns if you give none, and says how it understood the numbers
before it runs. The result always goes to a new folder. It does not run the dry run unless you ask.

**Arguments.**

```text
/seagull-diameter-scenario-externalize <scenario folder or files> placeholder=<AVP>=<COLUMN> ... [select=sequential|random] [calls=<N>] [out=<folder>] [data-path=<path>] [options=<file>]
```

| Argument       | Meaning                                                                                         | Default                                                  |
| -------------- | ----------------------------------------------------------------------------------------------- |----------------------------------------------------------|
| first argument | The `scenario` folder of a generation, or `*.client.xml` files                                  | required                                                 |
| `placeholder=` | One `<AVP>=<COLUMN>` pair; repeat it. The column is a name that heads a column of the data file | the pairs in the options file                            |
| `select=`      | `sequential` takes the rows in order and starts over; `random` picks a row at random            | `sequential`                                             |
| `calls=`       | How many calls Seagull makes, which is how many rows it uses                                    | the configuration, 1                                     |
| `out=`         | The folder to write to; it must be new or empty                                                 | a new `<generation folder>-external`, `-external-2`, ... |
| `data-path=`   | Where Seagull finds the data file when you run it                                               | `../scenario/external-data.csv`                          |

The pairs use the same names as the placeholders of the other skills: a bare AVP name, or a path such as
`Subscription-Id/Subscription-Id-Data`.

**Example prompt.**

```text
/seagull-diameter-scenario-externalize C:\work\Seagull-Scenario\scenario placeholder=Session-Id=SID placeholder=Subscription-Id-Data=MSISDN select=random calls=50
```

**What you get.** A new folder next to the old one, which stays as it was:

```text
C:\work\Seagull-Scenario-external\
  scenario\
    01-voice-steps-001-002.client.xml          (requests read SID and MSISDN from the data file)
    01-voice-steps-001-002.stub-server.xml     (a copy, unchanged)
    external-data.csv
  config\    conf.client.xml, conf.dry-run.client.xml (now name the data file), conf.stub-server.xml
  dictionary\
  scenario-options.ini
```

The data file starts with the recorded values as its only row:

```text
# SID; MSISDN
"string";"string";
"VOICE18597302321";"966581105391";
# spare row: Seagull 1.8.3 never picks the last row of a random file
"VOICE18597302321";"966581105391";
```

Put as many rows into it as you want calls, each with the same number of fields, every value in quotes and followed by
`;`. The first line that is not a comment defines the fields (`"string";` for each column); Seagull refuses the file
without it.

**What the agent tells you.** The new folder, the columns, the configurations that now name the file, and the answer
checks that it removed. Example:

```text
output folder: C:\work\Seagull-Scenario-external
01-voice-steps-001-002.client.xml: changed
01-voice-steps-001-002.client.xml: removed the check of Session-Id in an answer
data file: C:\work\Seagull-Scenario-external\scenario\external-data.csv with the columns SID, MSISDN
config conf.client.xml: ../scenario/external-data.csv
config conf.dry-run.client.xml: /work/scenario/external-data.csv
```

Four things to know:

- A scenario compares some answer fields with the recorded value. An AVP that now varies would fail that comparison, so
  the skill removes the check of that AVP and says so.
- All the steps of one call use the same row, so the CCR-I and the CCR-T of a session carry the same Session-Id.
- With `random`, Seagull 1.8.3 never picks the last row, so the skill ends the file with a spare copy. Keep it.
- Seagull addresses an AVP by name. A name that occurs twice in one request, such as a repeated `GGSN-Address`, is
  refused.

The dry run runs the new folder as it is. It makes `calls=` calls and reads one row for each, so it proves that Seagull
reads the file and sends the values. The line shows the number of calls (`successful calls: 50, failed calls: 0`):

```bash
sh .apm/skills/seagull-diameter-generate-scenarios/scripts/dry-run.sh C:\work\Seagull-Scenario-external
```

### /seagull-diameter-dictionary-convert

Converts the project's Diameter dictionaries into dictionaries that Seagull reads. The generate skill already does this
for the dictionaries it merges. Use this command when you want the dictionaries themselves: to run a hand-written
scenario with `-dico`, to read the conversion report before you generate, or to check that Seagull loads a result.
What the conversion does is in [the dictionary conversion page](dictionary-conversion.md).

You can also ask in plain words, for example "convert the dictionaries in C:\work\dictionaries" (one file), "... one
file for each dictionary", or "... and merge only Gy and Sy". The agent then follows the skill `seagull-diameter-convert-dictionaries` and the rules in
"Plain requests" above; it validates the sources only when you ask for it.

```text
/seagull-diameter-dictionary-convert <dictionaries folder> [out=<folder>] [combine=yes|no|<A,B> ...] [rename=<OLD>=<NEW> ...] [command-flags=<KEY>=<N> ...] [avp-flags=<AVP>=<N> ...] [vendor-mandatory=source|yes|no] [options=<file>] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [xsd=<folder>] [seagull-base=<file>] [check=yes]
```

| Argument            | Meaning                                                                                                                                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| first argument      | The folder with the project's AVP dictionaries. It must define the base protocol, in any file                                                                                                                     |
| `out=`              | The folder to write to. It must be new or empty. Default: `Seagull-Dictionary`, `Seagull-Dictionary-2`, ... next to the input folder                                                                              |
| `combine=`          | `yes` (the default) writes one file, `diameter-dictionary.xml`, of all the dictionaries and the base protocol; `no` writes one file for each; `A,B` writes only one file of the named ones, in that order         |
| `rename=`           | `OLD=NEW`: renames an AVP in every result, to match the name a scenario uses; repeat for more pairs                                                                                                               |
| `command-flags=`    | `<KEY>=<N>`: the flags byte, 0 to 255, of every request (`request=`), every answer (`answer=`), or one request or answer by its Seagull name (`CCR=192`); repeat for more pairs. Default: requests 128, answers 0 |
| `avp-flags=`        | `<AVP>=<N>`: the flags byte of one AVP, by its name in the result; repeat for more pairs. Default: what the source gives                                                                                          |
| `vendor-mandatory=` | The M bit of every vendor AVP: `source` keeps what the source says (the default), `yes` sets it, `no` clears it. A named `avp-flags=` pair wins                                                                   |
| `options=`          | A `dictionary-options.ini` that an earlier run wrote, to start from. The pairs of the prompt win over it                                                                                                          |
| `keep-tgpp=`        | `yes` keeps the `TGPP-` prefix of AVP names instead of writing `3GPP-`                                                                                                                                            |
| `no-comments=`      | `yes` leaves the enumeration values and the group members out of the results                                                                                                                                      |
| `validate=`         | `yes` first checks the sources against their XSD files (needs Java 11). Default `no`: then no schema is looked for                                                                                                |
| `xsd=`              | The folder of the XSD files, for `validate=yes`. Without it only the schema references inside the files are used                                                                                                  |
| `seagull-base=`     | A `base_draft08.xml` of Seagull that supplies the base protocol the folder lacks. Your definitions win; the agent asks first                                                                                      |
| `check=`            | `yes` then loads each result in Seagull and runs one Credit-Control exchange (Docker or Seagull for Windows)                                                                                                      |

Example:

```text
/seagull-diameter-dictionary-convert C:\work\dictionaries combine=Gy,Sy check=yes
```

Expected: a new folder next to `C:\work\dictionaries` with the file `Gy+Sy.xml`, `conversion-report.txt`, and
`dictionary-options.ini`. Without `combine=`, the file is `diameter-dictionary.xml` and holds every dictionary of the
folder. The agent tells you the number of AVPs and commands in each file and every warning:

```text
Gy+Sy.xml: 25 AVPs, 3 command pairs, 1 warnings
    WARNING AVP name Node-Id is defined twice with different identity: vendor 10415 code 2064 (Gy.xml) and vendor 99999 code 5 (Gy.xml); Seagull sends the first one wherever a scenario uses the name
```

The numbers and the name above come from the invented dictionaries of the self-test; yours differ.

A warning is a finding about the sources, not an error of the conversion. The script reports what looks inconsistent
and corrects nothing; the owners of the dictionary decide which definition is intended.

With `check=yes`, the agent adds one line for each result that defines `CCR`:

```text
Gy+Sy: successful calls: 1, failed calls: 0
```

A result without `CCR`, such as the base protocol alone, is skipped. The check proves that Seagull loads the dictionary
and finds the AVP names of the check scenario in it. It does not prove that an OCS accepts the messages.

Pass one result to Seagull with `-dico`. Seagull loads one dictionary for each run, so the default is one file with all
the dictionaries. Use `combine=no` for one file for each dictionary, and `combine=Gy,Sy` to merge only some, or to set
the order in which the first definition of an AVP name wins.

#### Validate the sources

Most projects do not need this, so `validate=` is `no` and the agent never looks for XSD files then. With
`validate=yes` the agent checks each dictionary against its schema before converting. It takes the schema from the
reference inside the file, and for a file without a reference (AVP dictionaries usually have none) from the folder in
`xsd=`, by the root element and not by the filename. The exact order is in
[the dictionary conversion page](dictionary-conversion.md#validate-the-sources).

```text
/seagull-diameter-dictionary-convert C:\work\dictionaries validate=yes xsd=C:\work\schemas
```

If a schema cannot be found, nothing is validated, and the agent asks in one message where the XSD files are and whether
to keep the answer in `dictionary-options.ini`. A file that fails its schema is reported and still converted.

#### Flags of commands and AVPs

The project dictionaries give no flags for a command, so the converter writes 128 (R) for every request and 0 for
every answer. It takes the M and P bits of an AVP from its source. Another dictionary, such as one from the project's
own tooling, may differ: RFC 4006 describes `CCR` and `CCA` with the P bit (192 and 64), and a vendor AVP may carry the
M bit where the source does not set it. Neither choice is known to be right for your OCS, so the defaults stay as they
are and you change them when you know the value you need:

```text
/seagull-diameter-dictionary-convert C:\work\dictionaries command-flags=CCR=192 command-flags=CCA=64 vendor-mandatory=yes avp-flags=PDP-Address=128
```

Each change is a `NOTE` line in the report, for example `CCR: flags 192 (the converter's default is 128)` and
`vendor-mandatory=yes: changed the M bit of 45 of 509 vendor AVPs`. The options in effect are written to
`dictionary-options.ini` in the new folder. Pass that file as `options=` to repeat the run on other dictionaries.
A flags byte that contradicts the V bit of the AVP (a vendor AVP without 128, or a base AVP with it) is refused.

## Where Seagull runs

The dry run of a generation and the check of converted dictionaries start Seagull. They can use the Seagull image in
Docker, or the `seagull.exe` of a Seagull for Windows, so a machine without Docker still works. Which one is a setting
in `.seagull-diameter/config.json`:

```json
{
  "SEAGULL_RUNNER": "windows",
  "SEAGULL_WINDOWS_PATH": "C:\\Program Files (x86)\\Seagull\\seagull.exe"
}
```

| Key                    | Meaning                                                 |
| ---------------------- | ------------------------------------------------------- |
| `SEAGULL_RUNNER`       | `docker` or `windows`                                   |
| `SEAGULL_DOCKER_IMAGE` | The Seagull image for `docker`. Default `seagull:local` |
| `SEAGULL_WINDOWS_PATH` | The `seagull.exe` for `windows`                         |

The agent reads exactly two files, in this order: `.seagull-diameter/config.json` in the folder where the session works,
then the same path in your home folder. It searches nothing else. A value in your request wins over the environment
variable of the same name, which wins over the file, which wins over the default. The first time the agent needs
Seagull and the runner is not set, it asks you one question, Docker or Seagull for Windows and where `seagull.exe` is,
and saves the answer after you confirm it. It saves to the session folder, or to your home folder when you ask for
that. The file never holds a password or a token.

With `windows` the runner starts a stub OCS and the client as two `seagull.exe` processes in a hidden console, with
copies of the configurations. The stub gets a free port, because the machine may already use 3868, and a scenario that
reads a data file gets the path of that file on your machine. The runner stops only the processes it started. It prints
the same line for each scenario as the Docker script: `successful calls: 1, failed calls: 0`. Add `--logs <folder>` to
the runner to keep the Seagull logs, which are deleted otherwise.

## Options and tags

`scenario-options.ini` in the output folder keeps what you decided about the shape of the scenarios. Each run reads it,
applies the options and pairs that your prompt names, and writes it back. State a decision once; it holds until you
state another. Give an option in a prompt as `option=<key>=<value>`.

| Option                         | Effect                                                                                                |
| ------------------------------ |-------------------------------------------------------------------------------------------------------|
| `mode`                         | `scenario` writes fixed values; `template` applies the placeholder pairs                              |
| `substitution`                 | `text` writes `@@NAME@@`; `native` keeps the value in the scenario as a Seagull variable              |
| `default-dwr`                  | On by default. A `<default>` section that answers a Device-Watchdog request of the OCS with a DWA     |
| `generated-session-id`         | A Session-Id built from a counter in the first step and reused in the later steps of the session      |
| `generated-timestamp`          | An Event-Timestamp set when the request is sent. Needs `time-method`                                  |
| `log`                          | A `<log>` line in each send and receive block                                                         |
| `check-presence`               | A `<check-presence>` before each `<check-value>`                                                      |
| `wait-ms`                      | A pause in milliseconds between two steps. Map `wait-ms` in the placeholders to make it a placeholder |
| `time-method`                  | The name of the Seagull method that returns the time                                                  |

A placeholder pair is `<AVP name>=<placeholder name>`, with the AVP name as the scenario file spells it. A bare name
matches the AVP at any depth. A path, such as `Multiple-Services-Credit-Control/Rating-Group`, matches it inside that
group only, and `GGSN-Address[2]` matches the second AVP of that name among its siblings. The most specific pair wins.
The full format is in [the common skill](../.apm/skills/seagull-diameter-common/SKILL.md#the-options-file).

Two limits matter in practice:

- The Seagull 1.8.3 image has no time method. It rejects both `sys_date_time_secs` and `sys_time_secs`
  with `No method extern found`. Use `generated-timestamp` and a timed Session-Id only with a Seagull that defines the
  method, and name it in `time-method`. Without it, a generated Session-Id is the Origin-Host and a counter, and the dry
  run in the image checks everything except the time.
- `substitution=native` works for top-level AVPs that do not repeat. The scenario sets the variable in its first step
  and restores it in the later ones.

## Recommended sequence

The sequence below is the one to follow the first time. Each step names its prompt and what a good result looks like.

### 1. Install and check the package

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/seagull-diameter-scenarios#main
docker image inspect seagull:local
```

Expected: `apm install` ends without an error, and the agent answers `/seagull-diameter-scenario-generate` by asking for
the arguments. The second command prints the data of the Seagull image; if the image is missing, build it first, as the
prerequisites say.

### 2. Get the steps into a folder

Use `/seagull-diameter-steps-extract` with a description of your file, or skip the step if you already have the folder.
Expected: a report with the number of steps and no `PROBLEM` line. If the agent names a `PROBLEM`, fix the cause in the
source or in your description, and run it again.

### 3. Generate ready scenarios first

Start with the plain run, even if you want templates later:

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario
```

Expected: the scenario files, a report with the AVPs that have several definitions, and a dry run with
`successful calls: 1, failed calls: 0` for every scenario. Answer the agent's questions about the definitions before you
go on. A plain run shows whether the steps, the dictionaries, and the merge order are right, and it keeps the failures
apart from the parameters.

### 4. Turn on what you need

Decide which values should vary and which tags help. Either regenerate with the new options:

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario replace=yes mode=template placeholder=Subscription-Id/Subscription-Id-Data=SUBSCRIBER_ID option=log=true option=check-presence=true option=wait-ms=500
```

`replace=yes` is needed because the folder already holds the first run; the agent moves that run aside. Leave out `out=`
to get a new folder next to the old one instead, and add `options=C:\work\Seagull-Scenario\scenario-options.ini` if you
want its settings.

or template what you already have:

```text
/seagull-diameter-scenario-templatize C:\work\Seagull-Scenario\scenario placeholder=Subscription-Id-Data=SUBSCRIBER_ID
```

Expected: the `.tpl` and `.values` files, and a dry run that is clean again. To drop a pair later, name it with an empty
placeholder: `placeholder=Subscription-Id-Data=`. To change a tag, give the option again with the other value.

### 5. Point the scenario at the OCS

Set `dest` in `config/conf.client.xml` to the OCS, and replace the `Host-IP-Address` of the capabilities exchange with
the address of your machine (or generate with `host-ip=`). For a template, fill it in first with the values of this run:

```bash
python .apm/skills/seagull-diameter-common/scripts/apply_placeholders.py 01-voice-steps-001-002.client.xml.tpl \
    --out 01-voice-steps-001-002.client.xml --values 01-voice-steps-001-002.client.xml.values --set SUBSCRIBER_ID=491700000001
```

### 6. Run one scenario

In the Seagull image:

```bash
seagull -conf /work/config/conf.client.xml -dico /work/dictionary/diameter-dictionary.xml \
    -scen /work/scenario/01-voice-steps-001-002.client.xml -log ../logs/voice-1 -llevel A -bg
```

Without a terminal `-bg` is needed; wait until the log ends with `STOP  log`. The statistics file `client-stat.*.csv` in
the logs folder counts the successful and the failed calls. A failed check shows in the log as `check failed in [CCA]
command, value of avp [Result-Code]. Expected [2001] but got [5012]`.

## Change a decision later

You change a decision with the same command, and the rest stays. For example, to add a pause and keep every placeholder:

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario replace=yes option=wait-ms=1000
```

The generator reads `scenario-options.ini`, changes `wait-ms`, and keeps the mode and the pairs. With `replace=yes` the
agent moves the previous output to `C:\work\Seagull-Scenario.previous-<date>-<time>` first, so the new folder holds only
files of this run. Keep your own edits out of the generated files: they say `Do not edit; generate again`.

## When something goes wrong

| Symptom                                                 | Cause and fix                                                                                   |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `the output folder is not empty: ...`                   | The folder holds files. Use another folder, or `replace=yes` to move its contents aside         |
| The agent does not know the command                     | The skills are not loaded. Check that `apm install` finished, then restart the session          |
| `AVP <name> is in none of the project dictionaries`     | Add the dictionary that defines the AVP to `merge=`                                             |
| `the command <X> is not in ...`                         | The merged dictionary has no definition of that command; add the dictionary of its application  |
| `PROBLEM ... not well-formed XML`                       | A recorded message is not XML even after the repairs. Fix the source and extract again          |
| `default-dwr is off: the dictionary has no DWR and DWA` | The merged dictionary lacks the Device-Watchdog commands; add the dictionary that defines them  |
| `placeholder <AVP>: matched no AVP`                     | The AVP name is misspelled, or the scenarios do not carry it. Check the spelling in a scenario  |
| `generated-timestamp needs time-method`                 | Name a Seagull time method with `option=time-method=<name>`, or leave the option off            |
| `native substitution cannot address ...`                | Native variables take only top-level AVPs that do not repeat; use `substitution=text`           |
| `no value for placeholder(s) NAME`                      | Give the value in the values file, with `--set`, or with `--env`                                |
| `no statistics file` in the dry run                     | Seagull did not start. Look for a carriage return in a generated file, and for a missing image  |
| A scenario fails with `Refused (new) call`              | A CCA arrived with a Session-Id that the call had not used. Check the recorded answers          |
| A scenario fails by timeout                             | The OCS did not answer in `timeout=` milliseconds. Raise it, or check the OCS                   |
| `do not define the base protocol`                       | Add the files that define it, or allow the Seagull dictionary (`seagull-base=`)                 |
| `NO SCHEMA ...` with `validate=yes`                     | No XSD file was found for those dictionaries; tell the agent where they are, or use `xsd=`      |
| A dictionary fails `check=yes`                          | Seagull could not load it, or it lacks an AVP that the check scenario sends; read the `E` lines |

## Limits

- The check of an answer compares top-level AVPs only. An AVP inside a group that has the name of a top-level one, such
  as the `Result-Code` of a Multiple-Services-Credit-Control, cannot be told apart by name.
- The scenarios send the recorded messages. They do not create new ones: a session whose messages were not recorded
  needs its steps recorded or written by hand first.
- The generated files and the recorded messages hold subscriber data. Do not commit them unless you have checked what
  they hold.
