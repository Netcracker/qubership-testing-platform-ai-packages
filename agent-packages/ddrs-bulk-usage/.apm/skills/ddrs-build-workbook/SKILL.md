---
name: ddrs-build-workbook
description: Build a DDRS bulk input workbook (schema v2, like tests-ddrs/input/data-usage.result.xlsx) from subscriber data the user provides (CALLING NUMBER, IMSI, ACCOUNT NUMBER) and a QA test matrix (USAGE TYPE, DURATION, B, RG, EVENT COST ER, TC ID). Triggers on "build xlsx", "ddrs input workbook", "generate usages.xlsx", "ddrs build workbook".
---

# Build a DDRS input workbook

Output: one `.xlsx` in `tests-ddrs/input/` (or a folder the user names), schema v2, with the input columns
filled and the output columns empty. The runner writes the output columns later.

Work from the test repository root (the folder that holds `tools/ddrs/ddrs.pyz` and `tests-ddrs/`).

## Hard rules

- `EVENT COST ER` is never invented. It comes from the QA matrix. If a row has no value, ask. Never write 0.
- Subscriber data (`CALLING NUMBER`, `IMSI`, `ACCOUNT NUMBER`) comes only from the user's request or from a file the
  user names. Do not invent numbers, and do not take them from earlier runs or other workbooks. If data is missing, ask.
- No password, token, or URL secret goes into any file this skill writes.

## Step 1. Subscriber data

Ask the user for the rows, or for a file (CSV or xlsx) that holds them: one row per usage with `CALLING NUMBER`,
`IMSI`, `ACCOUNT NUMBER`. Show the rows back as a short table and wait for confirmation of the values and the count.

## Step 2. QA test matrix

Take the matrix from the request or from a CSV the user names. Columns:

| Column | Source | Rule |
|---|---|---|
| `TC ID` | matrix | required, shown in Allure as the case name |
| `USAGE TYPE` | matrix | must match a `usage_types` entry of some family in `tests-ddrs/shared-ddrs/bulk/*/family.json` (case, spaces, `-` and `_` ignored) |
| `DURATION` | matrix | whole number above 0: seconds for voice, octets for data. Not checked for sms |
| `B` | matrix | digits. For data it may be empty when the template does not use it |
| `RG` | matrix | digits. May be empty only if the variant has `values.RATING_GROUP` |
| `EVENT COST ER` | matrix | number, expected cost in the currency units of the sheet (for example `0.5`). Required |
| `CALLING NUMBER`, `IMSI`, `ACCOUNT NUMBER` | Step 1 | digits only |
| `ID`, `EVENT TYPE`, `DIRECTION`, `A` | optional | leave blank unless the user has a value |

If the matrix leaves `EVENT COST ER` or `TC ID` empty for any row, list those rows and ask. Do not fill them.

## Step 3. Plan, then write

Show the plan before writing: one line per row, `TC ID | USAGE TYPE | CALLING NUMBER | IMSI | ACCOUNT NUMBER |
DURATION | B | RG | EVENT COST ER`. Wait for a yes.

Create the empty file with the runner (it gives the schema v2 header, 20 columns):

```bash
python tools/ddrs/ddrs.pyz xlsx-template tests-ddrs/input/<name>.xlsx
```

Then fill the input columns with openpyxl. Keep the header row as written, leave the output columns
(`STATUS`, `ERROR DESC`, `SESSION ID`, `BUCKET`, `EVENT COST AR`, `EVENT COST AR (ND)`, `TC STATUS`) empty.
Write numbers that must stay text (`CALLING NUMBER`, `IMSI`, `ACCOUNT NUMBER`, `B`, `RG`) as strings, so
Excel does not drop leading zeros or switch to scientific notation.

Only one workbook per run. A workbook is one Allure suite.

## Step 4. Validate

```bash
python tools/ddrs/ddrs.pyz validate tests-ddrs/input/<name>.xlsx
```

`validate` checks the schema, the families of the whole repository, and every row. It prints one line per
problem: `ERROR row N: ...`. Fix the rows (go back to the matrix or to the user's data), rewrite the file, and run
again until it prints `OK`. Do not replace a failing value with a value you made up.

## Notes

- The workbook is the only source of the run. Do not look for other data sources on the disk.
