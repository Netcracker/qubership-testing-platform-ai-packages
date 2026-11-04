# Seagull Diameter scenarios user guide

The `seagull-diameter-scenarios` package gives your coding agent two commands. One reads a recorded test run and writes
the
Diameter requests and responses of it to files. The other turns those files into Seagull scenarios that send the
requests
again and check the answers. Follow the sections in order the first time: install the package, prepare the steps,
generate
the scenarios, and try them. For the list of skills, see the [package `README`](../README.md).

## Before you start

You need:

- A coding agent that APM can deploy to, such as Claude Code, Codex, Cursor, or OpenCode.
- The APM command-line tool, `apm`, on your `PATH`. Run `apm --version` to check. The layout of this package follows the
  one of
  `tdm-test-data-assistant`, which was checked with APM 0.29.1.
- Python 3.9 or later, available as `python`, `python3`, or `py -3`. The scripts use nothing outside the standard
  library.
- For the dry run: Docker, and the Seagull image of this repository, built with `docker build -t seagull:local .`. On
  Windows,
  Docker works in WSL; run the dry-run script as `wsl sh <script> ...`.
- The project's Diameter dictionaries in the project format, in one folder, with `DiameterBaseProtocol.xml` among them.
  Seagull reads its own format, so the second skill converts them; see
  [the dictionary folder](../../../dictionary/README.md) of this repository for what the conversion does.
- The recorded run: either a file you can describe (an `xlsx` export of a test database, for example) or a folder that
  already has the `Step-NNN-request.txt` and `Step-NNN-response.txt` files.

## Install the package

Run `apm install` in the folder in which you start your agent, with the agent that you use:

```bash
apm install --target claude kagw95/seagull-docker/agent-packages/seagull-diameter-scenarios#main
```

The part after `#` is the branch or tag to follow; use a tag to stay on one version. `--target` names the agent:
`claude`,
`codex`, `copilot`, `cursor`, `gemini`, or `opencode`, several joined with commas. APM downloads the package with Git,
so
the repository must be readable with your credentials.

The skills are commands. Start your agent in the folder, or restart a session that was already running, and type
`/seagull-diameter-scenario-generate`: the agent should answer by asking for the arguments. Codex starts a skill only
when you name it, and the package says so in `agents/openai.yaml`; nothing else needs setting.

## Prepare the steps

The scenario generator reads a folder with one request file and one response file for each Diameter step. Each file
holds the
Diameter command as XML, exactly as it was recorded. The
[format](../.apm/skills/seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps) is short; read it once.

### The steps are in a file

Tell the agent how to read the file. The package builds in no structure, so the description is the only thing the
agent has. Say, in your own words:

- which sheet or table holds the steps, and whether the rows are in the order in which the steps ran;
- how a request and its response are marked, and how they are tied to a step (a parent column, a shared key);
- where the text of a message is;
- how to tell a Diameter step from any other one, for example that the text starts with `<CCR` or `<CCA`.

For an `xlsx` export of a tree of steps, a command can read like this:

```text
/seagull-diameter-steps-extract "C:\work\Steps and messages.xlsx" -- The first sheet has one row for each node of a tree
of test steps, in the order of execution. The columns are ID, PARENT, TYPE, DESCRIPTION. A step is a row with TYPE
StepInstance. The messages of a step are in rows below it: TYPE "outgoing message" is the request and TYPE "incoming
message" is the response; their text is in DESCRIPTION. Every step has one of each. Keep only the steps whose request
starts with a Diameter command in angle brackets, such as <CCR. Write the files to C:\work\Diameter-Steps.
```

The agent looks at the file first and tells you if it differs from your description. It then writes the folder, checks
it,
and reports how many steps the file has and how many are Diameter steps. A step that it cannot pair is named in the
report.

### The steps are already in a folder

Skip this section. The first run of the generator checks the folder.

## Generate the scenarios

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy,Integration out=C:\work\Seagull-Scenario dest=10.0.0.5:3868
```

| Argument        | Meaning                                                                                                |
| --------------- | ------------------------------------------------------------------------------------------------------ |
| first argument  | The folder of recorded steps                                                                           |
| `dictionaries=` | The folder of the project's dictionaries                                                               |
| `merge=`        | The dictionaries to merge, in order. For an AVP name that two of them define, the first keeps the name |
| `out=`          | Where to write the scenarios                                                                           |
| `timeout=`      | How long Seagull waits for each answer, in milliseconds. Default 5000                                  |
| `dest=`         | The address and port of the OCS. Default `127.0.0.1:3868`, which is the stub OCS                       |
| `host-ip=`      | The IP address that the capabilities exchange announces as the client's. Default is a placeholder      |

When the dictionaries are missing from the command, the agent lists the files and asks which to merge. If the generator
says that an AVP is in none of the dictionaries, add the dictionary that has it to `merge=`.

The agent then reports:

- the scenarios, one for each Diameter session: the steps with the same `Session-Id` are one scenario;
- every AVP name that the dictionaries define more than once, and which definition the scenario uses. Check each line,
  because the generator chooses by the vendor of the enclosing group and cannot know what the recorded run really sent;
- the repairs that the recorded messages needed, and the answer fields that were not checked.

The output folder holds:

| Folder or file                   | Content                                                                   |
| -------------------------------- | ------------------------------------------------------------------------- |
| `scenario/`                      | A client scenario and a stub OCS scenario for each session                |
| `config/conf.client.xml`         | The configuration for the OCS under test: `dest` and the response timeout |
| `config/conf.dry-run.client.xml` | The same, pointing at the stub OCS                                        |
| `dictionary/`                    | The merged Seagull dictionary and the conversion report                   |
| `generation-report.txt`          | What the generator did                                                    |

The generated files hold subscriber data from the recording and are not for a repository. They use line feed as the line
ending, which Seagull needs: its configuration parser fails on a carriage return, so do not let an editor or Git convert
them.

## Make templates, and add dynamic tags

By default the scenarios hold the recorded values. Three things change that. Each is a decision that you state in a
prompt once; the generator writes it to `scenario-options.ini` in the output folder and reads it on every later run
until you state another.

### Placeholders

To get a template, add `mode=template` and name the AVPs whose values should be placeholders:

```text
/seagull-diameter-scenario-generate C:\work\Diameter-Steps dictionaries=C:\work\dictionaries merge=RoSCP,Gy out=C:\work\Seagull-Scenario mode=template placeholder=Subscription-Id/Subscription-Id-Data=SUBSCRIBER_ID placeholder=3GPP-Charging-Id=CHARGING_ID_HEX
```

Each `placeholder=` is `<AVP name>=<placeholder name>`. The AVP name is the one that the scenario file spells. A bare name
matches the AVP at any depth, a path such as `Multiple-Services-Credit-Control/Rating-Group` matches only inside that
group, and `GGSN-Address[2]` matches the second AVP of that name among its siblings. To drop a pair, name the AVP with an
empty placeholder name (`placeholder=Rating-Group=`).

For each session the scenario folder then holds three files:

| File                       | Content                                                                          |
| -------------------------- | -------------------------------------------------------------------------------- |
| `<name>.client.xml.tpl`    | The template, for example `value="0x@@CHARGING_ID_HEX@@"`                        |
| `<name>.client.xml.values` | `NAME=value` lines with the recorded values; hexadecimal values do not hold `0x` |
| `<name>.client.xml`        | The template filled in with the values file, which the dry run uses              |

A placeholder stands for one value in a file. When two AVPs that share a name had different values, the generator uses
the first and says so in the report.

To fill the template in with your own values, run the script that the package ships:

```bash
python .apm/skills/seagull-diameter-common/scripts/apply_placeholders.py <name>.client.xml.tpl --out <name>.client.xml \
    --values <name>.client.xml.values --env --set SUBSCRIBER_ID=966581105391
```

A value comes from `--set`, then from the environment (only with `--env`), then from the values file. The script stops and
names every placeholder that has no value.

If you want Seagull to hold the values instead, add `option=substitution=native`: each placeholder becomes a variable
that the scenario sets in its first step and restores in the later ones. It works for top-level AVPs that do not repeat.

### Scenarios you already have

`/seagull-diameter-scenario-templatize C:\work\Seagull-Scenario\scenario placeholder=Subscription-Id-Data=SUBSCRIBER_ID`
turns every `*.client.xml` in the folder into a template with a values file, without reading the steps again. It uses
the pairs of the options file when you name none.

### Tags

| Option                         | Adds                                                                                               |
| ------------------------------ | -------------------------------------------------------------------------------------------------- |
| `default-dwr` (on by default)  | A `<default>` section that answers a Device-Watchdog request of the OCS with a DWA                  |
| `generated-session-id=true`    | A Session-Id built from a counter in the first step and reused in the later steps of the session   |
| `generated-timestamp=true`     | An Event-Timestamp set when the request is sent; needs `time-method`                               |
| `log=true`                     | A `<log>` line in each send and receive block                                                      |
| `check-presence=true`          | A `<check-presence>` before each `<check-value>`                                                   |
| `wait-ms=<ms>`                 | A pause between two steps. Map `wait-ms` in the placeholders to make the pause a placeholder       |
| `time-method=<name>`           | The Seagull method that returns the time                                                           |

Give each one as `option=<key>=<value>`. The Seagull in this repository's image has no time method: it rejects both
`sys_date_time_secs` and `sys_time_secs` with `No method extern found`. Use `generated-timestamp` and a timed Session-Id
only with a Seagull that defines the method, and name it in `time-method`. Without it, a generated Session-Id is the
Origin-Host and a counter, and the dry run in the image checks everything except the time.

## Try the scenarios without an OCS

The agent runs this for you after generating. To run it yourself, from the folder of the package:

```bash
sh .apm/skills/seagull-diameter-scenario-generate/scripts/dry-run.sh <out folder> [<image>]
```

A stub OCS answers each request with the AVPs of the recorded answer, and the script prints one line for each scenario:

```text
01-voice-steps-001-002: successful calls: 1, failed calls: 0
```

A scenario that does not end with `successful calls: 1, failed calls: 0` is a defect of the generation or of the
dictionary.
Do not take the scenarios to the OCS before every line is clean.

## Run against the OCS

Set `dest` in `config/conf.client.xml` to the OCS, and the Host-IP-Address of the CER to your machine's address. Then
run one
scenario. In the Seagull image:

```bash
seagull -conf /work/config/conf.client.xml -dico /work/dictionary/diameter-dictionary.xml \
    -scen /work/scenario/01-voice-steps-001-002.client.xml -log ../logs/voice-1 -llevel A -bg
```

Without a terminal `-bg` is needed; wait until the log ends with `STOP  log`. The statistics file `client-stat.*.csv` in
the
logs folder counts the successful and the failed calls. A failed check shows in the log as
`check failed in [CCA] command, value of avp [Result-Code]. Expected [2001] but got [5012]`.

## Update the package

```bash
apm install
```

Run it in the folder that holds `apm.yml`; to move to another branch or tag, change the part after `#` in the dependency
line first.

## When something goes wrong

| Symptom                                             | Cause and fix                                                                                  |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| The agent does not know the command                 | The skills are not loaded. Check that `apm install` finished, then restart the session         |
| `AVP <name> is in none of the project dictionaries` | Add the dictionary that defines the AVP to `merge=`                                            |
| `the command <X> is not in ...`                     | The merged dictionary has no definition of that command; add the dictionary of its application |
| `PROBLEM ... not well-formed XML`                   | A recorded message is not XML even after the repairs. Fix the source and extract again         |
| `no statistics file` in the dry run                 | Seagull did not start. Look for a carriage return in a generated file, and for a missing image |
| A scenario fails with `Refused (new) call`          | A CCA arrived with a Session-Id that the call had not used. Check the recorded answers         |
| A scenario fails by timeout                         | The OCS did not answer in `timeout=` milliseconds. Raise it, or check the OCS                  |
