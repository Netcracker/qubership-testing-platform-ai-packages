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
`codex`, `copilot`, `cursor`, `gemini`, or `opencode`, several joined with commas. APM downloads the package with git,
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

| Argument        | Meaning                                                                                                         |
|-----------------|-----------------------------------------------------------------------------------------------------------------|
| first argument  | The folder of recorded steps                                                                                    |
| `dictionaries=` | The folder of the project's dictionaries                                                                        |
| `merge=`        | The dictionaries to merge, in order. For an AVP name that two of them define, the first keeps the name           |
| `out=`          | Where to write the scenarios                                                                                    |
| `timeout=`      | How long Seagull waits for each answer, in milliseconds. Default 5000                                           |
| `dest=`         | The address and port of the OCS. Default `127.0.0.1:3868`, which is the stub OCS                                |
| `host-ip=`      | The IP address that the capabilities exchange announces as the client's. Default is a placeholder               |

When the dictionaries are missing from the command, the agent lists the files and asks which to merge. If the generator
says that an AVP is in none of the dictionaries, add the dictionary that has it to `merge=`.

The agent then reports:

- the scenarios, one for each Diameter session: the steps with the same `Session-Id` are one scenario;
- every AVP name that the dictionaries define more than once, and which definition the scenario uses. Check each line,
  because the generator chooses by the vendor of the enclosing group and cannot know what the recorded run really sent;
- the repairs that the recorded messages needed, and the answer fields that were not checked.

The output folder holds:

| Folder or file                   | Content                                                                        |
|----------------------------------|--------------------------------------------------------------------------------|
| `scenario/`                      | A client scenario and a stub OCS scenario for each session                     |
| `config/conf.client.xml`         | The configuration for the OCS under test: `dest` and the response timeout      |
| `config/conf.dry-run.client.xml` | The same, pointing at the stub OCS                                             |
| `dictionary/`                    | The merged Seagull dictionary and the conversion report                        |
| `generation-report.txt`          | What the generator did                                                         |

The generated files hold subscriber data from the recording and are not for a repository. They use line feed as the line
ending, which Seagull needs: its configuration parser fails on a carriage return, so do not let an editor or Git convert
them.

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

| Symptom                                               | Cause and fix                                                                                  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------------|
| The agent does not know the command                   | The skills are not loaded. Check that `apm install` finished, then restart the session         |
| `AVP <name> is in none of the project dictionaries`   | Add the dictionary that defines the AVP to `merge=`                                            |
| `the command <X> is not in ...`                       | The merged dictionary has no definition of that command; add the dictionary of its application |
| `PROBLEM ... not well-formed XML`                     | A recorded message is not XML even after the repairs. Fix the source and extract again         |
| `no statistics file` in the dry run                   | Seagull did not start. Look for a carriage return in a generated file, and for a missing image |
| A scenario fails with `Refused (new) call`            | A CCA arrived with a Session-Id that the call had not used. Check the recorded answers         |
| A scenario fails by timeout                           | The OCS did not answer in `timeout=` milliseconds. Raise it, or check the OCS                  |
