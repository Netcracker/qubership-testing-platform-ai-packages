# How the skills work together

This page shows the states that your work passes through and the skill or script that moves it from one state to the
next. Use it to find where you are when something fails. The steps in detail, with prompts, are in the
[user guide](user-guide.md).

## States and transitions

```mermaid
stateDiagram-v2
    direction TB

    [*] --> Source: you have a recorded run
    state "Source<br/>xlsx, csv, JSON, or log" as Source
    state "Steps folder<br/>Step-NNN-request.txt<br/>Step-NNN-response.txt" as Steps
    state "Generated output<br/>scenario/, config/, dictionary/<br/>scenario-options.ini" as Output
    state "Ready scenarios<br/>fixed values" as Ready
    state "Templates<br/>@@NAME@@ + values files" as Templates
    state "Scenarios proven against the stub OCS" as Proven
    state "Run against the OCS under test" as Run

    Source --> Steps: /seagull-diameter-steps-extract
    [*] --> Steps: you already have the folder
    Steps --> Steps: check_steps.py reports a PROBLEM,<br/>fix the source or the extraction
    Steps --> Output: /seagull-diameter-scenario-generate<br/>+ project dictionaries

    Output --> Ready: mode=scenario
    Output --> Templates: mode=template, substitution=text
    Output --> Ready: mode=template, substitution=native<br/>(variables inside the scenario)

    Ready --> Templates: /seagull-diameter-scenario-templatize<br/>+ placeholder pairs
    Templates --> Ready: apply_placeholders.py<br/>--set, --env, values file

    Ready --> Output: change an option or a placeholder,<br/>generate again
    Templates --> Output: change an option or a placeholder,<br/>generate again

    Ready --> Proven: dry-run.sh
    Proven --> Ready: a scenario fails the dry run,<br/>fix the input and generate again
    Proven --> Run: seagull -conf conf.client.xml -scen ...
    Run --> [*]
```

A template is not run as it is. `apply_placeholders.py` fills it in first, and the generator does this itself for the
dry run, so the dry run always sees a filled-in scenario.

## What each transition needs and produces

| Transition                       | Moved by                                | Needs                                                                  | Produces                                                                                                                        |
|----------------------------------|-----------------------------------------|------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Source to Steps folder           | `/seagull-diameter-steps-extract`       | The source file and your description of its structure                  | `Step-NNN-request.txt`, `Step-NNN-response.txt`, `Steps-index.csv`                                                              |
| Steps folder to Generated output | `/seagull-diameter-scenario-generate`   | The folder, the project dictionaries, and the names to merge           | Client and stub scenarios, three configurations, the merged Seagull dictionary, `generation-report.txt`, `scenario-options.ini` |
| Ready scenarios to Templates     | `/seagull-diameter-scenario-templatize` | Generated `*.client.xml`, and placeholder pairs                        | `*.client.xml.tpl`, `*.client.xml.values`                                                                                       |
| Templates to Ready scenarios     | `apply_placeholders.py`                 | A template, and values from `--set`, the environment, or a values file | A filled-in `*.client.xml`                                                                                                      |
| Ready scenarios to Proven        | `dry-run.sh`                            | Docker and the image `seagull:local`                                   | One line for each scenario: `successful calls: 1, failed calls: 0`                                                              |
| Proven to Run                    | `seagull` command                       | The address of the OCS in `config/conf.client.xml`                     | Seagull logs and statistics CSV files                                                                                           |

## Where the options file fits

`scenario-options.ini` is the memory of the generator. Each run reads it, applies the options and placeholder pairs that
you gave in the prompt, and writes it back. A decision therefore holds for every later run until you state another.

```mermaid
flowchart LR
    Prompt["Your prompt:<br/>mode, option, placeholder"] --> Merge{"Generator"}
    File[("scenario-options.ini<br/>in the output folder")] --> Merge
    Merge --> Files["Scenarios, templates,<br/>values files"]
    Merge --> File
```

A prompt wins over the file for the keys it names. A key that the prompt does not name keeps the value from the file.

## Where a run stops

| State where it stops            | Signal                                              | What to do                                                                                             |
|---------------------------------|-----------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| Steps folder, before generation | A `PROBLEM` line from `check_steps.py`              | Fix the extraction, or the source text, and extract again                                              |
| Generation, before any file     | `the output folder is not empty: ...`               | Use another folder, or `replace=yes` to move the old contents to a `.previous-<time>` folder           |
| Generation                      | `AVP <name> is in none of the project dictionaries` | Add the dictionary that defines the AVP to `merge=`                                                    |
| Generation                      | `the command <X> is not in ...`                     | Add the dictionary of the application that defines the command                                         |
| Generation                      | `generated-timestamp needs time-method`             | Name a time method, or leave the option off                                                            |
| Generation, template            | `no value for placeholder(s) NAME`                  | Give the value in the values file, with `--set`, or with `--env`                                       |
| Dry run                         | `no statistics file`                                | Seagull did not start: check the image and the line endings                                            |
| Dry run                         | `successful calls: 0, failed calls: 1`              | Read the `E` error line that the script prints next to it; the cause is in the input or the dictionary |
