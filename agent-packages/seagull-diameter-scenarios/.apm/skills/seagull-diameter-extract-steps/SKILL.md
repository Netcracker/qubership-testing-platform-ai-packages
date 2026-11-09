---
name: seagull-diameter-extract-steps
description: Use when the user asks to extract the Diameter requests and responses of a recorded test run (an xlsx export, a csv or JSON file, or a log) into a folder of step files, to prepare the input for Seagull scenarios. Follows the user's description of how the source is built and writes a new folder of Step-NNN request and response files.
user-invocable: false
---

# Extract the Diameter steps of a recorded run

Reads a recorded run, keeps its Diameter steps, and writes each request and each response to its own file, in the format
described in [seagull-diameter-common](../seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps). The
structure of the source differs from file to file, so this skill has none built-in: the user says how to read the
source, and the skill does what was said.

The command [/seagull-diameter-steps-extract](../seagull-diameter-steps-extract/SKILL.md) runs the same steps from a
formal line, `<source> -- <how to read it>`. What this page says holds for both.

## Required inputs

What the task needs before it starts, and what it takes from each place.

- **From the user:** the source (an `xlsx`, `csv`, JSON, or log file, or a folder in the step format) and, for a file,
  the description of how it is built.
- **From the settings:** nothing. Seagull is not started.

## What to take from the request

| Parameter     | How the user says it                                               | Rule                                                                                                 |
| ------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| source        | "take the steps from C:\work\Steps.xlsx"                           | Required: an `xlsx`, `csv`, JSON, or log file, or a folder in the step format                        |
| description   | "sheet Main, a row per step, column F is the request, column G..." | Required for a file. See the next section. Never guess the structure of a file                       |
| filenames     | "write request_NN.xml and response_NN.xml", "as req_NN.xml..."     | Only when the user gives them: use them. Default: `Step-NNN-request.txt` and `Step-NNN-response.txt` |
| output folder | "write them to C:\work\steps"                                      | Optional. It must be new or empty. Default: a new folder next to the source                          |

If the source is a folder that already follows the format, skip the extraction: run the check in the last step and
report.

## What the description must cover

A file source has to be described. When the request does not answer one of these, ask the user once, all questions in
one message, and wait. Never guess the structure of a file. One point may be filled from the data and not from the user:
how a request is tied to its response (point 3), when the user did not say. Take the rule only if the data confirms it
completely, for example every selected message has a neighbor of the other kind in the same place, so that all of them
fall into pairs with none left over, and in more than one reading the pairs would be the same. Then use it and state it,
before the script (step 2 of the run) and in the report ("the response is in the row above its request; all 20 rows form 10 pairs"). When the
data does not confirm one rule, or some message is left over, ask.

The questions may come with a proposal. After the look at the source (step 1 of the run), write what the data shows
(sheets, columns, kinds of rows, counts) and, for each open point, the reading that the data suggests, for example
"Diameter step: the request text starts with `<CCR`, the response with `<CCA`". Ask the user to confirm or correct it,
and wait. A proposal is a question, not an answer: write no file, and run no extraction script, until the user has
agreed to it in this conversation. Present what is not in the data (the order of the rows, a skip for another reason) as
a question without a proposal.

1. Which sheet, table, or section holds the steps.
2. Whether the order of the rows is the order in which the steps ran, or what to sort by.
3. How one step's request and its response are recognized: a column and the values that mark a request and a response,
   and how rows are tied to a step (a parent column, a shared key, or neighbors).
4. Where the text of a message is (a column or a field).
5. How to tell a Diameter step from any other step. A common rule: the message text starts with a Diameter command in
   angle brackets, such as `<CCR` or `<CCA`.
6. Whether the file has steps that must be skipped for another reason.

## Run

1. **Look before extracting.** Open the source read-only, by the path the user gave: test it directly (`test -f`, or open
   it with the library). Don't list folders to find it, don't cut a listing with `head` to look for it, and never search
   the disk; when the path does not exist, say so and ask for the right one. Print the sheet names, the header row, the
   number of rows, and a few rows, and compare them with the description. If they disagree (a column is not there, a
   value is not used), say what differs and ask; do not adapt the description silently. Never change the source file.
2. **Say what you took from the data or read into the words.** Write a short message, as plain text, before the
   extraction script, when you filled a point of the description from the data (the tie between a request and its
   response, as above) or had to interpret the user's wording. Name each such point and the rule you use, for example
   "the response is in the row above its request; all 20 rows form 10 pairs", and let the user correct it. Go on without
   waiting unless a point is open. When the request already said everything, skip this step; the report says how the
   file was read.
3. **Write a throwaway extraction script** outside the repository the user works in, in a temporary folder. It reads the
   rows in the order the user gave, and groups each request with its response by the rule from the description. Read
   `xlsx` files with a library that gives cell values (for example `openpyxl` with `data_only=True`), not with
   formatting applied.
4. **Select the Diameter steps** by the rule from the description. A step is kept only if both its request and its
   response are found; any other case is listed in the report.
5. **Choose the output folder, then write the files.** The folder must be new or empty; a folder with files is never
   written into. When the user gave none, take the first free `Diameter-Steps[-N]` next to the source:

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/output_folder.py next-free <folder of the source> Diameter-Steps
   ```

   When the user gave a folder, check it with `output_folder.py describe <folder>`. If it prints that the folder holds
   files (exit status 1), stop and tell the user what it printed, then ask for another folder or for permission to use
   a new one; never clear a folder or write beside its files, because the step files of two runs mix. A folder that
   does not exist yet is fine (`describe` says so, and `next-free` returns a path that is not created): the script makes
   it before it writes the first file. Number the kept
   steps one by one from `001` in the order they ran, as `Step-001-request.txt` and `Step-001-response.txt`. When the user
   gave a template for the names, such as `request_NN.xml` and `response_NN.xml`, use it for both files of each step,
   with the number in the width the user showed (`NN` is two digits, `NNN` three; a longer number is not cut). The
   next skills read the default names without further arguments, so say which names you used and, when they are not the
   default, that `check_steps.py` and the generator need `--request-name` and `--response-name` for them. Write the
   message text exactly as it is in the source, in UTF-8, with no trimming and no change of line breaks. Do not repair
   or reformat it here: the generator reports what it repairs.
6. **Write `Steps-index.csv`** (UTF-8 with a BOM, separator `;`) with the columns `Step file number`,
   `Step number in the scenario` (the position of the step in the source, counting every step, not only the kept ones),
   `Step ID` (any identifier the source has), `Status`, `Request` and `Response` (the command of each message), and
   `Step description`. Read the file back and compare a few rows with the source before you go on.
7. **Check the folder.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/check_steps.py <output folder> \
       [--request-name <template> --response-name <template>]
   ```

   Any `PROBLEM` line means the folder is not ready. Fix what the script names when the cause is in the extraction, such
   as a request paired with the wrong response. When the cause is in the source text, such as a message that is not XML,
   report it and let the user fix the source.
8. **Report**: how many steps the source has, how many are Diameter steps, the folder, and the repairs the check lists.
   Say that the files hold the recorded messages with their subscriber data, so they are not for a repository.
   Report the final state. A first version of a script or of the index that you rewrote on the way is not part of it: do
   not mention it.

## Don't

- Don't infer a rule the user did not give, such as "a message that starts with `<` is Diameter".
- Don't skip a step silently. Every step that is dropped, and why, is in the report.
- Don't edit the message text. A wrong value in the source is a finding for the user, not a thing to fix here.
