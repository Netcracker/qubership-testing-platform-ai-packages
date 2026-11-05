---
name: seagull-diameter-scenario-externalize
description: Use only when the user types /seagull-diameter-scenario-externalize. Changes generated Seagull scenarios so that chosen AVP values come from an external CSV data file at run time, one row for each call, and writes the data file and the configuration for it into a new folder.
disable-model-invocation: true
argument-hint: "<scenario folder or files> placeholder=<AVP>=<COLUMN> ... [select=sequential|random] [calls=<N>] [out=<folder>] [data-path=<path>] [options=<file>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-externalize

Makes the values of chosen AVPs come from a CSV file that Seagull reads while it runs. Use it when one scenario should
send many different subscribers, Session-Ids, or amounts, and the values should live outside the scenario. It works on
scenarios that [seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) already wrote. It is
a third way to parameterize, next to the `@@NAME@@` templates of
[seagull-diameter-scenario-templatize](../seagull-diameter-scenario-templatize/SKILL.md) and the `native` variables of
the generator; the user's prompt says which one is wanted.

## Arguments

```text
/seagull-diameter-scenario-externalize <scenario folder or files> placeholder=<AVP>=<COLUMN> ... [select=sequential|random] [calls=<N>] [out=<folder>] [data-path=<path>] [options=<file>]
```

| Argument       | Meaning                                                                                              | Default                                                  |
| -------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| first argument | The `scenario` folder of a generation, or one or more `*.client.xml` files                           | required                                                 |
| `placeholder=` | One `<AVP>=<COLUMN>` pair; repeat it. `<COLUMN>` names a column of the data file                       | the pairs in the options file                            |
| `select=`      | `sequential` takes the rows in order and starts again at the end; `random` picks a row at random       | `sequential`                                             |
| `calls=`       | How many calls Seagull makes (`number-calls`), so how many rows it uses                                | the value in the configuration, 1                        |
| `out=`         | The folder to write to. It must be new or empty                                                        | a new folder, `<generation folder>-external`, `-external-2`, ... |
| `data-path=`   | Where Seagull will find the data file when it runs                                                     | `../scenario/external-data.csv`                          |
| `options=`     | An older options file whose pairs to use                                                               | `scenario-options.ini` in the generation folder          |

The pairs work as in the other skills: `<AVP>` is the AVP name as the scenario file spells it, with an optional path
(`Multiple-Services-Credit-Control/Rating-Group`); the most specific pair wins. When there is no options file and the
user names no pair, ask which AVPs should come from the data file; never pick them.

## Run

1. **Convert.**

   ```bash
   python <skill folder>/scripts/scenario_to_external.py <scenario folder or files> --out-auto \
       --placeholder <AVP>=<COLUMN> ... [--select random] [--calls <N>] [--data-path <path>] [--options <file>]
   ```

   Pass `--out <folder>` instead of `--out-auto` when the user named a folder. A folder with files is refused with a
   message that says what it holds: tell the user, and ask for another folder. Never empty a folder to make room.
2. **Read the report** and tell the user:
   - The output folder, the columns of the data file, and the configurations that now name it.
   - Every `removed the check of <AVP> in an answer` line. A scenario compares some answer fields with the recorded
     value. An AVP that now varies would fail that comparison, so the script removes the check of that AVP. Say which
     checks went.
   - `<COLUMN>: values 'a' and 'b'; used the first`: one column stands for one value in the first row.
   - `placeholder <AVP>: matched no AVP`: a misspelled name, or an AVP that the scenarios do not carry.
3. **Tell the user what is left to do.** The data file has one row, the recorded values. Seagull makes `number-calls`
   calls and uses one row for each, so the user puts as many rows into `scenario/external-data.csv` as calls are
   wanted, and sets `calls=`. All the steps of one call use the same row. With `sequential` the rows repeat from the
   top after the last one. With `random` the file ends with a spare row, because Seagull 1.8.3 never picks the last
   row of a random file; do not remove it.
4. **Run the dry run** on the new folder, as the generate skill describes:

   ```bash
   sh <skill folder>/../seagull-diameter-scenario-generate/scripts/dry-run.sh <out folder> [<image>]
   ```

   The dry-run configuration reads the data file from `/work/scenario/` inside the Seagull image. The stub OCS answers
   whatever the scenario sends, so the run proves that Seagull reads the file and sends the values, not that an OCS
   accepts them.

## The data file

```text
# SID; MSISDN; CHARGING
"string";"string";"string";
"TEST-A-1";"491700000001";"0x000000a1";
```

- A line that starts with `#` is a comment. The first other line defines the fields, one `"string";` for each column.
  Seagull stops with `No field definition (first line) found` without it.
- Each data row has the same number of fields, every value in quotes and followed by `;`. Seagull stops with
  `Illegal number of field for line` otherwise. A value must not hold a quote or a semicolon.
- A value is written as it stands in a scenario: a number as digits, text as text, bytes as `0x...`. A hexadecimal
  value is read as bytes.
- The column number in `restore-from-external field="N"` counts from 0, in the order of the header comment.

## What the script changes

For each request in `<traffic>` that holds a matched AVP, the script adds
`<restore-from-external field="N" entity="<AVP>"></restore-from-external>` to the action before the command. The
recorded value stays in the command as a default that the action overrides. It also removes a
`<set-value name="<AVP>" ...>` of the same AVP from that action. The capabilities exchange in `<init>` is not changed.

## Limits

- Seagull addresses the AVP by its name. A name that occurs twice in one request, such as a repeated `GGSN-Address` or
  `Rating-Group` in two groups, is refused; the script names it. Choose another AVP.
- An AVP that another tag already sets, such as the Session-Id of `generated-session-id`, is refused. Generate again
  without that option.
- A varied AVP loses its check in the answer. The scenario then no longer proves that the OCS echoed it.
- One call is one session. The data file does not make one scenario send several sessions.

## Don't

- Don't write into an old folder, and don't delete one.
- Don't edit the scenarios by hand to add a column; run the script again with the pair.
- Don't commit the data file: it holds subscriber data.
