# Seagull Diameter scenarios user guide

The `seagull-diameter-scenarios` package gives your coding agent three commands. They turn a recorded test run into
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
- For the dry run: Docker, and the Seagull image of this repository, built with `docker build -t seagull:local .`. On
  Windows, Docker works in WSL; run the shell scripts as `wsl sh <script> ...`.
- The project's Diameter dictionaries in the project format, in one folder, with `DiameterBaseProtocol.xml` among them.
  Seagull reads its own format, so the generator converts them; see
  [the dictionary folder](../../../dictionary/README.md) of this repository for what the conversion does.
- The recorded run: either a file you can describe (an `xlsx` export of a test database, for example) or a folder that
  already has the `Step-NNN-request.txt` and `Step-NNN-response.txt` files.

## Install the package

Run `apm install` in the folder in which you start your agent, with the agent that you use:

```bash
apm install --target claude kagw95/seagull-docker/agent-packages/seagull-diameter-scenarios#main
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
| ---------------------------------------- | ------- |--------------------------------------------------------------------------------------------------|
| `/seagull-diameter-steps-extract`        | command | Turn a file of recorded steps into the folder of request and response files                      |
| `/seagull-diameter-scenario-generate`    | command | Turn that folder into scenarios or templates, configuration, and a dictionary, and run a dry run |
| `/seagull-diameter-scenario-templatize`  | command | Turn generated scenarios into templates, without reading the steps again                         |
| `seagull-diameter-common`                | support | Hold the shared scripts and the formats. You never invoke it                                     |

The commands run only when you type their name; the agent never starts them on its own.

### /seagull-diameter-steps-extract

**Purpose.** Reads a recorded run and writes each Diameter request and each response to its own file. The structure of
your file differs from every other, so the skill has none built in. You describe it in the prompt and the skill does
what you said.

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
7. optionally, the output folder. Default: a folder named `Diameter-Steps` next to the source.

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

**Arguments.**

```text
/seagull-diameter-scenario-generate <steps folder> dictionaries=<folder> merge=<A,B,C> [out=<folder>] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>] [mode=scenario|template] [placeholder=<AVP>=<NAME> ...] [option=<key>=<value> ...] [options=<file>]
```

| Argument         | Meaning                                                                                                   | Default                                      |
| ---------------- | --------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| first argument   | The folder of recorded steps                                                                              | required                                     |
| `dictionaries=`  | The folder of the project's dictionaries                                                                  | required                                     |
| `merge=`         | The dictionaries to merge, without `.xml`, in order. For an AVP that two of them define, the first wins   | required                                     |
| `out=`           | Where to write                                                                                            | `Seagull-Scenario` next to the steps folder  |
| `timeout=`       | How long Seagull waits for each answer, in milliseconds                                                   | 5000                                         |
| `dest=`          | Address and port of the OCS                                                                               | `127.0.0.1:3868`, the stub OCS               |
| `host-ip=`       | The IP address that the capabilities exchange announces as the client's                                   | a placeholder address                        |
| `mode=`          | `scenario` for fixed values, `template` for placeholders                                                  | the options file, else `scenario`            |
| `placeholder=`   | One `<AVP>=<NAME>` pair; repeat it. An empty `<NAME>` removes the pair                                    | the pairs in the options file                |
| `option=`        | One `<key>=<value>` option, see [Options and tags](#options-and-tags)                                     | the options file                             |
| `options=`       | The options file                                                                                          | `scenario-options.ini` in the output folder  |

When you leave out `dictionaries=` or `merge=`, the agent lists the files of the dictionary folder and asks which to
merge. If the generator says an AVP is in none of the dictionaries, add the one that has it to `merge=`.

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
sh .apm/skills/seagull-diameter-scenario-generate/scripts/dry-run.sh <out folder> [<image>]
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

- The Seagull in this repository's image has no time method. It rejects both `sys_date_time_secs` and `sys_time_secs`
  with `No method extern found`. Use `generated-timestamp` and a timed Session-Id only with a Seagull that defines the
  method, and name it in `time-method`. Without it, a generated Session-Id is the Origin-Host and a counter, and the dry
  run in the image checks everything except the time.
- `substitution=native` works for top-level AVPs that do not repeat. The scenario sets the variable in its first step
  and restores it in the later ones.

## Recommended sequence

The sequence below is the one to follow the first time. Each step names its prompt and what a good result looks like.

### 1. Install and check the package

```bash
apm install --target claude kagw95/seagull-docker/agent-packages/seagull-diameter-scenarios#main
docker build -t seagull:local .
```

Expected: `apm install` ends without an error, and the agent answers `/seagull-diameter-scenario-generate` by asking for
the arguments. The second command runs in the root of this repository and takes about four minutes.

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
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario mode=template placeholder=Subscription-Id/Subscription-Id-Data=SUBSCRIBER_ID option=log=true option=check-presence=true option=wait-ms=500
```

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
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario option=wait-ms=1000
```

The generator reads `scenario-options.ini`, changes `wait-ms`, and keeps the mode and the pairs. The generated files are
overwritten, so keep your own edits out of them: the files say `Do not edit; generate again`.

## When something goes wrong

| Symptom                                                 | Cause and fix                                                                                  |
|---------------------------------------------------------|------------------------------------------------------------------------------------------------|
| The agent does not know the command                     | The skills are not loaded. Check that `apm install` finished, then restart the session         |
| `AVP <name> is in none of the project dictionaries`     | Add the dictionary that defines the AVP to `merge=`                                            |
| `the command <X> is not in ...`                         | The merged dictionary has no definition of that command; add the dictionary of its application |
| `PROBLEM ... not well-formed XML`                       | A recorded message is not XML even after the repairs. Fix the source and extract again         |
| `default-dwr is off: the dictionary has no DWR and DWA` | The merged dictionary lacks the Device-Watchdog commands; add the dictionary that defines them |
| `placeholder <AVP>: matched no AVP`                     | The AVP name is misspelled, or the scenarios do not carry it. Check the spelling in a scenario |
| `generated-timestamp needs time-method`                 | Name a Seagull time method with `option=time-method=<name>`, or leave the option off           |
| `native substitution cannot address ...`                | Native variables take only top-level AVPs that do not repeat; use `substitution=text`          |
| `no value for placeholder(s) NAME`                      | Give the value in the values file, with `--set`, or with `--env`                               |
| `no statistics file` in the dry run                     | Seagull did not start. Look for a carriage return in a generated file, and for a missing image |
| A scenario fails with `Refused (new) call`              | A CCA arrived with a Session-Id that the call had not used. Check the recorded answers         |
| A scenario fails by timeout                             | The OCS did not answer in `timeout=` milliseconds. Raise it, or check the OCS                  |

## Limits

- The check of an answer compares top-level AVPs only. An AVP inside a group that has the name of a top-level one, such
  as the `Result-Code` of a Multiple-Services-Credit-Control, cannot be told apart by name.
- The scenarios send the recorded messages. They do not create new ones: a session whose messages were not recorded
  needs its steps recorded or written by hand first.
- The generated files and the recorded messages hold subscriber data. Do not commit them unless you have checked what
  they hold.
