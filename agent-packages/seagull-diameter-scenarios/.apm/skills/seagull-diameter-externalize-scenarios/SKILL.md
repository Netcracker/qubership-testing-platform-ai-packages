---
name: seagull-diameter-externalize-scenarios
description: Use when the user asks to make chosen AVP values of generated Seagull scenarios come from an external CSV data file at run time, one row for each call, for example to send many different subscribers or Session-Ids from one scenario. Changes the scenarios in a new folder, writes the data file and the configuration for it, and runs the dry run only when the user asks for it.
user-invocable: false
---

# Read chosen AVP values of Seagull scenarios from a data file

Makes the values of chosen AVPs come from a CSV file that Seagull reads while it runs. Use it when one scenario should
send many different subscribers, Session-Ids, or amounts, and the values should live outside the scenario. It works on
scenarios that [seagull-diameter-generate-scenarios](../seagull-diameter-generate-scenarios/SKILL.md) already wrote. It
is a third way to parameterize, next to the `@@NAME@@` templates of
[seagull-diameter-templatize-scenarios](../seagull-diameter-templatize-scenarios/SKILL.md) and the `native` variables of
the generator; the user's request says which one is wanted.

The command [/seagull-diameter-scenario-externalize](../seagull-diameter-scenario-externalize/SKILL.md) runs the same
steps from formal arguments. What this page says holds for both.

## Required inputs

What the task needs before it starts, and what it takes from each place.

- **From the user:** the scenarios (the `scenario` folder of a generation, or `*.client.xml` files) and the AVPs that
  come from the data file, unless an options file already has them.
- **From the settings:** nothing is required to change the scenarios.
- **Only when Seagull is started** (the dry run): the runner and its path or image. `seagull_run.py` reads them; see
  [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs). Don't ask for them in advance.

## What to take from the request

| Parameter      | How the user says it                                      | Rule                                                                                               |
| -------------- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| scenarios      | "take the scenarios in C:\work\Seagull-Scenario\scenario" | Required: the `scenario` folder of a generation, or `*.client.xml` files. Ask when missing         |
| `placeholder=` | "read the subscriber number from the file, column MSISDN" | `<AVP>=<COLUMN>` pairs. The AVPs only from the user. See below                                     |
| `select=`      | "pick the rows at random", "in order"                     | `sequential` (default) or `random`                                                                 |
| `calls=`       | "make 50 calls"                                           | The number of calls Seagull makes, so how many rows it uses. Default: the configuration, 1         |
| `out=`         | "write the result to C:\work\external"                    | Optional: a new or empty folder. Default: `<generation folder>-external`                           |
| `data-path=`   | "Seagull will find the file at /data/external-data.csv"   | Only when the user says where Seagull will find the file. Default: `../scenario/external-data.csv` |
| `options=`     | "start from the options of the earlier generation"        | An older options file whose pairs to use                                                           |

The pairs work as in the other skills: `<AVP>` is the AVP name as the scenario file spells it, with an optional path
(`Multiple-Services-Credit-Control/Rating-Group`); the most specific pair wins. When there is no options file and the
user specifies no AVP, ask which AVPs should come from the data file; never pick them. The column is only a label of
the data file. When the user specifies the AVPs and no columns, propose a column for each (the AVP name in capitals,
with underscores) and say so.

When you had to interpret the wording to fill a pair or a number, say how you understood it before you run anything,
for example `placeholder=Subscription-Id-Data=MSISDN` and `calls=50`, and let the user correct it.

## Run

Write every path in a command in quotes. Single quotes keep a Windows path whole: Bash reads an unquoted
backslash as an escape and turns `C:\work\steps` into `C:worksteps`, and it splits a path with a space into two
arguments. Forward slashes (`'C:/work/steps'`) work on Windows too.

1. **Convert.**

   ```bash
   python <skill folder>/scripts/scenario_to_external.py <scenario folder or files> --out-auto \
       --placeholder <AVP>=<COLUMN> ... [--select random] [--calls <N>] [--data-path <path>] [--options <file>]
   ```

   Pass `--out <folder>` instead of `--out-auto` when the user gave a folder. A folder with files is refused with a
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
4. **The dry run** on the new folder starts Seagull. Run it only when the user asked for it, in the request or in the
   answer to your offer. Otherwise offer it in one sentence and say that the scenarios are not verified in Seagull yet.
   Name the runner in the offer: the last line the script printed, `Seagull for the check: ...`, has it; the run reads
   the setting itself, see [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs).

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/seagull_run.py dry-run <out folder>
   ```

   Exit status 4 means that a setting has no value; ask the one question of "Where Seagull runs", save the answer, and run
   the script again. In the image, the dry-run configuration reads the data file from `/work/scenario/`; the Windows
   runner points it to the file in the output folder. The stub OCS answers whatever the scenario sends, so the run proves
   that Seagull reads the file and sends the values, not that an OCS accepts them.

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
