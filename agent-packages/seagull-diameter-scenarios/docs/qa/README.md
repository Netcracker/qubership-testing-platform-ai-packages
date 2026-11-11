# Checking the seagull-diameter-scenarios package

This guide shows how to check that the package does what its pages say. It has two parts. Part 1 is for a tester who
types the prompts and reads the results. Part 2 is for a tester who also uses an agent session to read the
transcripts, find the cause of a failure, and verify a fix.

The cases are in the [test plan](test-plan.md). The [results](results.md) page records a full pass over them, and the
[history](history.md) lists the findings of that pass and the pull requests that fixed them. The inputs for the cases
are small and synthetic, so a check needs no data of a real project.

## Part 1: check by hand

### The commands and the plain requests

Each task of the package has two entries: a command that you type, and a skill that the agent picks from an ordinary
request. They do the same work. The command is a frontend with formal arguments, and the plain skill carries the steps
and the rules, so a command and a plain request with the same parameters produce the same files.

| Task                                                | Command                                  | What it writes                                                            | The same task in plain words                                  |
| --------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Convert project dictionaries for Seagull            | `/seagull-diameter-dictionary-convert`   | A new folder with `diameter-dictionary.xml` and a report                  | "Convert the Diameter dictionaries in this folder"            |
| Turn a recorded run into request and response files | `/seagull-diameter-steps-extract`        | A new folder with one request file and one response file for each step    | "Extract the Diameter steps from this file"                   |
| Generate scenarios or templates from the steps      | `/seagull-diameter-scenario-generate`    | A new folder with scenarios, configuration, a stub OCS, and a report      | "Generate Seagull scenarios from the steps in this folder"    |
| Make chosen AVP values placeholders                 | `/seagull-diameter-scenario-templatize`  | Templates (`.tpl`) and the values that reproduce the original scenarios   | "Make the subscriber number of these scenarios a placeholder" |
| Read chosen AVP values from a CSV data file         | `/seagull-diameter-scenario-externalize` | A new folder with the changed scenarios, the data file, and configuration | "Read the subscriber number from a data file"                 |
| Show or save the settings                           | `/seagull-diameter-settings`             | Nothing, or one saved setting                                             | "Show the settings of the Seagull skills"                     |

How the two ways differ:

- **A command runs only when you type it.** The agent cannot start it for you. It takes its arguments literally and
  asks only for what the arguments leave out.
- **A plain request starts a skill that the agent picks.** The package instruction then applies: the agent does not
  start Seagull, replace files, or choose dictionaries, placeholders, or flags on its own, and it says how it
  understood your wording (for example `placeholder=Subscription-Id-Data=NUMBER`) before it runs a script.
- **The result is the same.** For the same parameters, the output folders of the two ways are identical. The plan
  checks this in its parity cases.

Every command prints its usage when the only argument is `help` (`--help`, `-h`, and `?` work too). The command does
nothing else then. Type it first when you do not remember an argument:

```text
/seagull-diameter-scenario-generate help
```

### Before you start

1. Install the package into a project folder, as the [user guide](../user-guide.md#install-the-package) says, and start
   the agent in that folder.
2. Have one Seagull 1.8.3 to run the scenarios: Seagull for Windows or the Docker image. Check what the package uses
   with `/seagull-diameter-settings`.
3. Copy the [sample data](#sample-data) into a work folder. The plan refers to the copies by the names in its
   [inputs](test-plan.md#inputs) table.
4. Keep a copy of `.seagull-diameter/config.json` before the first case. Cases that change the settings say when to
   restore it.

### Run a case

1. Start a new agent session in the project folder. A session that has already seen a skill name proves nothing about
   how the agent picks a skill.
2. Type the prompt of the case as written. In a plain case, do not name a skill or a script.
3. Note which skill the agent loaded, the questions it asked and how you answered, the commands it ran, and the files it
   wrote.
4. Compare with the expected result and give a verdict:
   - **pass**: the package behaves as its pages say;
   - **fail**: it behaves against its own text;
   - **gap**: the text is silent and the agent did something, good or bad;
   - **blocked**: an earlier case did not give the input.
5. Where the agent asks a question that the skill says to ask, the case still passes. A question that the skill
   should have made unnecessary is a gap.

The prompts may be in your own language. The expected results do not depend on it.

### Phases

| Phase | What it covers                                                                        |
| ----- | ------------------------------------------------------------------------------------- |
| A     | Converting dictionaries, with the plain skill and with the command                    |
| B     | Extracting steps from a recorded run                                                  |
| C     | Generating scenarios and templates, running them against the stub OCS                 |
| D     | Turning scenarios into templates, filling templates in                                |
| E     | Reading values from a data file                                                       |
| F     | The runner, runs against an OCS, requests the package does not serve, and wrong input |

The phases depend on each other: A gives the dictionary for C to E, and B gives the steps. The plan marks the cases
that need an earlier result.

## Part 2: check with an agent

This part adds a second agent session, the coordinator. The tester still types each prompt in a fresh session. The
coordinator does the reading and the repair work that a tester does slowly by hand.

### The roles

- **Session under test.** A fresh session in the project folder, with the package installed. It gets the prompt of one
  case and nothing else.
- **Coordinator.** A session in the repository of the package. It exports the transcript of the session under test,
  reads it, writes the verdict in a log for the case, and, when the package is at fault, changes it.

### The loop

1. The tester types the prompt in a fresh session and tells the coordinator the case ID and the session name.
2. The coordinator exports the transcript and reads the whole of it: the skill the agent loaded, each tool call, each
   message the user saw, and the files written. What the user saw decides whether the agent said something before it
   ran a script; the type of a block in the transcript does not.
3. The coordinator writes a log of the case with the prompt, the skill, the questions, the commands, the files, and the
   verdict, and checks the files against the expected result.
4. When the package is at fault, the coordinator makes the change in the repository, runs the linters and the self-test
   (`python tests/selftest.py`), and installs the package again into the project folder.
5. The tester runs the same prompt again in a new session. Only a rerun shows that the change reaches the agent.
6. After the tester agrees, the coordinator commits the change and opens a pull request. The tester merges it.

### Rules that kept the check honest

- **A prompt carries only what a user knows.** It does not name a step, a parent column, a script, or a file format that
  the user would not know. The agent has to find or ask for these.
- **The coordinator runs no prompt in its own session.** It knows the skill names, so its run proves nothing about how
  the agent picks a skill.
- **A fix is verified by a rerun in a fresh session**, after the package is installed again. A text that the agent
  never loads does not change its behavior. The package instruction, for example, reaches the agent only after it
  reads a file of the project.
- **Restore the settings** after a case that changes them, and rename back any Docker image tag that a case hid.
- **Nothing is committed without the tester's yes**, and each change goes in its own pull request.
- **Do not search the disk for inputs.** A case that needs a dictionary or a Seagull path gives it in the prompt or in
  the settings, as a real user would.

### What to put in the log of a case

The prompt as typed, the skill the agent loaded, the questions and the answers, the commands, the files written (not
the temporary ones), the verdict, and, for a failure, the exact sentence of the skill or of the instruction that the
agent violated or that is silent.

## Sample data

The cases use these inputs. They are synthetic, so a tester can share logs and files freely.

| Input                                  | Where                                                              | Used for                               |
| -------------------------------------- | ------------------------------------------------------------------ | -------------------------------------- |
| Project dictionaries with the base one | [`tests/fixtures/dictionaries`](../../tests/fixtures/dictionaries) | Phase A, and the dictionary for C to E |
| A recorded run as a file               | [`data/steps-export.csv`](data/steps-export.csv)                   | Phase B                                |
| Ready request and response files       | [`tests/fixtures/steps`](../../tests/fixtures/steps)               | Phases C to F, and the parity of B     |

The recorded run has five steps in a tree: a test case holds steps, and a step holds the messages it sends and receives.
Three of the steps are Diameter requests with their answers, and the other two are not Diameter. The addresses in the
files are local or example values, and the run against an OCS uses a local address with a port that is out of range, so
that no OCS can answer it.
