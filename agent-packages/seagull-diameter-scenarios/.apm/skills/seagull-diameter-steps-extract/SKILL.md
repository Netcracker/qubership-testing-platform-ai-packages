---
name: seagull-diameter-steps-extract
description: Use only when the user types /seagull-diameter-steps-extract. Turns a file of recorded test steps (for example an xlsx export from a database) into the folder of Diameter request and response files that /seagull-diameter-scenario-generate reads, following the user's description of the file.
disable-model-invocation: true
argument-hint: "<source file or folder> -- <how to find the requests and the responses in it>"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-steps-extract

Reads a recorded run, keeps its Diameter steps, and writes each request and each response to its own file, in the format
described in [seagull-diameter-common](../seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps). The
structure of the source differs from file to file, so this skill has none built-in: the user says how to read the
source, and the skill does what was said.

## Arguments

```text
/seagull-diameter-steps-extract <source> -- <how to read it>
```

| Part              | Meaning                                                                                                     |
|-------------------|-------------------------------------------------------------------------------------------------------------|
| `<source>`        | An `xlsx`, `csv`, JSON, or log file, or a folder that already has the `Step-NNN-...` files                  |
| `<how to read it>`| Free text. It must say what is needed to answer the questions in the next section                           |
| output folder     | Optional, in the text: where to write. Default: a new folder next to the source, named `Diameter-Steps`     |

If the source is a folder that already follows the format, skip the extraction: run the check in the last section and
report.

## What the description must cover

A file source has to be described. When the text does not answer one of these, ask the user once, all questions in one
message, and wait. Never guess the structure of a file.

1. Which sheet, table, or section holds the steps.
2. Whether the order of the rows is the order in which the steps ran, or what to sort by.
3. How one step's request and its response are recognized: a column and the values that mark a request and a response,
   and how rows are tied to a step (a parent column, a shared key, or neighbors).
4. Where the text of a message is (a column or a field).
5. How to tell a Diameter step from any other step. A common rule: the message text starts with a Diameter command in
   angle brackets, such as `<CCR` or `<CCA`.
6. Whether the file has steps that must be skipped for another reason.

## Run

1. **Look before extracting.** Open the source read-only. Print the sheet names, the header row, the number of rows, and
   a few rows, and compare them with the description. If they disagree (a column is not there, a value is not used),
   say what differs and ask; do not adapt the description silently. Never change the source file.
2. **Write a throwaway extraction script** outside the repository the user works in, in a temporary folder. It reads the
   rows in the order the user gave, and groups each request with its response by the rule from the description. Read
   `xlsx` files with a library that gives cell values (for example `openpyxl` with `data_only=True`), not with
   formatting applied.
3. **Select the Diameter steps** by the rule from the description. A step is kept only if both its request and its
   response are found; any other case is listed in the report.
4. **Write the files** to the output folder, which must be new or empty. Number the kept steps one by one from `001` in
   the order they ran, as `Step-001-request.txt` and `Step-001-response.txt`. Write the message text exactly as it is in
   the
   source, in UTF-8, with no trimming and no change of line breaks. Do not repair or reformat it here: the generator
   reports what it repairs.
5. **Write `Steps-index.csv`** (UTF-8 with a BOM, separator `;`) with the columns `Step file number`,
   `Step number in the scenario` (the position of the step in the source, counting every step, not only the kept ones),
   `Step ID` (any identifier the source has), `Status`, `Request` and `Response` (the command of each message), and
   `Step description`.
6. **Check the folder.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/check_steps.py <output folder>
   ```

   Any `PROBLEM` line means the folder is not ready. Fix what the script names when the cause is in the extraction, such
   as a request paired with the wrong response. When the cause is in the source text, such as a message that is not XML,
   report it and let the user fix the source.
7. **Report**: how many steps the source has, how many are Diameter steps, the folder, and the repairs the check lists.
   Say that the files hold the recorded messages with their subscriber data, so they are not for a repository.

## Don't

- Don't infer a rule the user did not give, such as "a message that starts with `<` is Diameter".
- Don't skip a step silently. Every step that is dropped, and why, is in the report.
- Don't edit the message text. A wrong value in the source is a finding for the user, not a thing to fix here.
