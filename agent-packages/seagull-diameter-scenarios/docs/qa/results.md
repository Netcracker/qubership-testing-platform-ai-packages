# Results of the first full check

This page records the first pass over the [test plan](test-plan.md), made in November 2026 with an agent session as the
session under test and a second agent session as the coordinator (see [Part 2](README.md#part-2-check-with-an-agent)).
The runs used a recorded run and project dictionaries of a real project, with Seagull 1.8.3 for Windows and, for the Docker
cases, the Seagull image through WSL. The sample data of this guide are smaller, so counts of steps and scenarios in a
rerun differ from the counts seen then. The verdicts do not depend on them.

Each verdict is the last one, after the reruns that followed a fix. A case that needed a rerun says so in the notes.

## Verdicts

| Case | Verdict        | Notes                                                                                                                               |
| ---- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| A1   | pass           | New folder, one `diameter-dictionary.xml`, no Seagull and no XSD before the request                                                 |
| A2   | pass           | Stopped on the missing base protocol, named the codes, offered two ways                                                             |
| A2b  | pass           | Warned that Seagull's dictionary may be wrong, named the added items and `Event-Timestamp`                                          |
| A3   | pass           | Third run. The earlier runs asked for a runner that the settings held, and validated files the result does not use                  |
| A4   | pass           | Second run. The first did not name the runner and the path from the settings in its offer                                           |
| A5   | pass           | Second run. A folder with files was never emptied or overwritten                                                                    |
| A6   | pass           | `validate=yes` without `xsd=` stopped and asked one question, without searching the disk                                            |
| A7   | pass           | Arguments taken literally; same files as A4                                                                                         |
| B1   | pass           | Third run. Found the Diameter pairs by the text of the messages and said how it tied request to response                            |
| B2   | pass, a remark | Proposed a reading drawn from the data and asked to confirm it; the skill did not say this is allowed. Fixed in the skill           |
| B3   | pass           | Wrote nothing in a folder with files, and asked                                                                                     |
| B4   | pass, remarks  | Same files as B6. Remarks about the message before the script; fixed in the skill                                                   |
| B5   | pass           | The questions in one message; nothing written                                                                                       |
| B6   | pass           | Default names, `Steps-index.csv`, the step check                                                                                    |
| B7   | pass           | A folder with other filenames was processed                                                                                         |
| C1   | pass           | Stopped without a dictionary and wrote nothing                                                                                      |
| C2   | pass           | Counts first, the dry run offered with the runner and its path                                                                      |
| C3   | covered        | Seen in C2 and C8; not run on its own                                                                                               |
| C4   | pass           | Asked before touching the folder; the old files moved aside after the user said to replace                                          |
| C5   | pass           | Second run. The first did not say how it read "subscriber number" before the script. Fixed in the skill                             |
| C6   | pass           | Rerun after the fixes. The first run gave plain scenarios for "templates". Fixed in the skill                                       |
| C7   | pass           | Second run. The first kept the reading of "log every step" in its reasoning only. Fixed in the skill                                |
| C8   | pass           | Fourth run. One report with headings, the dry run made without asking                                                               |
| C9   | pass           | Refusal, then replace with templates and options                                                                                    |
| C10  | pass           | Stopped without a dictionary                                                                                                        |
| C11  | pass           | The setting was read                                                                                                                |
| C12  | pass           | Both stopped                                                                                                                        |
| C13  | pass           | Stopped with the AVP name. A failed generation had left a partial folder; fixed                                                     |
| D1   | pass           | Found the earlier templates first and wrote nothing                                                                                 |
| D2   | pass           | Asked which AVPs                                                                                                                    |
| D3   | pass           | The pair was told after the run in the first run; fixed in the skill                                                                |
| D4   | pass           | `.tpl` and `.values` files. Parity with D3 is not exact: D3 used one pair and D4 two                                                |
| D5   | pass           | A misspelled `--set` name was ignored; the script now stops                                                                         |
| E1   | pass           | Second run. The first dry run failed on a data-file path with backslashes; fixed                                                    |
| E2   | pass           | `select=random calls=50`, 50 successful calls for each scenario                                                                     |
| E3   | pass           | Asked which AVPs                                                                                                                    |
| E4   | covered        | Seen in E1 and E2                                                                                                                   |
| E5   | pass           | The pairs taken literally                                                                                                           |
| E6   | pass           | `successful calls: 5, failed calls: 0` for each scenario                                                                            |
| F1   | pass           | The agent had written a script of its own to run one scenario. `seagull_run.py` now takes a scenario file                           |
| F2   | pass           | No skill matched the first run, and the agent searched the disk for `seagull.exe`. Fixed; the exit message names the known settings |
| F3   | pass           | See the findings below                                                                                                              |
| F4   | pass           | Stopped at the missing image. A Docker dry run ignored `--logs` silently; it now says so                                            |
| F5   | pass           | One of the three prompts of the plan was run; the answer used no skill and no tool                                                  |
| F6   | pass           | Generation skill with `mode=template`; asked for the steps, the dictionary, and the AVPs                                            |
| F7   | pass           | Followed the plain extraction skill and asked to confirm its reading                                                                |
| F8   | pass           | A pair whose AVP no step has is a note in the report; the folder is still written (decision, see below)                             |
| S1   | pass           | Three parts under headings                                                                                                          |
| S2   | pass           | `runner=` saved one key; an unknown argument was refused                                                                            |

Not run: `runner=podman`, `seagull-exe=`, `image=`, and `home=yes` of the settings command, and the plan's other two
prompts of F5 (a JSON conversion and a hand-written scenario).

## Findings and the changes that fixed them

The defects and gaps found in this pass were fixed in pull requests 14 to 24, each after the tester agreed. The
[history](history.md) lists them and tells the two longer stories, the run against an OCS (F3) and the pair that
matches no AVP (F8).

## What this check does not show

- The scenarios were never run against a real OCS. A dry run against the stub shows that Seagull loads the dictionary,
  sends the recorded requests, and accepts the stub's answers. It does not show that an OCS accepts the messages.
- Each case ran on one model and one host. A different agent may choose differently where the pages leave room.
