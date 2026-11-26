---
name: ddrs-run-local
description: Run a DDRS bulk workbook locally with tools/ddrs/ddrs.pyz (or tests-ddrs/run-bulk-usage.bat) against the Seagull binary on the QA machine. Covers finding the Seagull path (ddrs-local.json, SEAGULL_BINARY, ../Seagull/seagull.exe), validate and dry-run before sending, the real run, reading TC STATUS and ERROR DESC, and the console requirement of Seagull on Windows. Triggers on "run ddrs", "run workbook", "local bulk run", "run-bulk-usage", "ddrs.pyz run", "Fatal: Keyboard".
---

# Run a DDRS bulk workbook locally

Work from the test repository root (the folder above `tools/ddrs/ddrs.pyz`). The runner is the
`ddrs.pyz` archive. Do not check whether the archive is current: that is the user's responsibility.

This skill sends real usages to the OCS when the run is not a dry run. Before the real run, get a yes from the user
for the workbook, the environment, and the Seagull path.

## Step 1. Find the Seagull binary

Take the first one that exists, in this order:

1. A path the user gives in the request.
2. The environment variable `SEAGULL_BINARY`.
3. `tests-ddrs/ddrs-local.json`, field `seagull`:

   ```json
   { "seagull": "C:\\path\\to\\Seagull\\seagull.exe" }
   ```

   This file is listed in `.gitignore` (`**/ddrs-local.json`). Keep it per developer. It holds no secrets.
4. `../Seagull/seagull.exe` (the default the `.bat` uses, next to the test repository).

If none exists, ask the user for the path and offer to save it to `tests-ddrs/ddrs-local.json`. Write only after
the user agrees. `ddrs.pyz` does not read `ddrs-local.json` itself: pass the path with `--seagull`.

Dry runs do not need Seagull. Pass `--dry-run` and skip this step.

## Step 2. Environment file

Use `environment-configuration/environment-configuration-template-hardcode.json`. It holds the local endpoint
values and a password. Never print its contents in the chat or in a report. When you show a command, mask the
password as `***`.

Pass the file explicitly, relative to the repository root:

```
--env environment-configuration/environment-configuration-template-hardcode.json
```

Without `--env`, `ddrs.pyz` uses `environment-configuration-template.json` and needs the `${DDRS_...}`
variables in the shell. Use that form only if the user asks for it.

## Step 3. Validate and dry-run (always first)

```bash
python tools/ddrs/ddrs.pyz validate tests-ddrs/input/<book>.xlsx
python tools/ddrs/ddrs.pyz run tests-ddrs/input/<book>.xlsx --env environment-configuration/environment-configuration-template-hardcode.json --dry-run
```

- `validate` exits 0 only when every row is valid. On any `ERROR` line, stop, show the lines and
  point to the fix (`unknown USAGE TYPE` means the USAGE TYPE is not in any family; `Bulk profile not found`
  means `ddrs-profile.json` is missing from the `shared-ddrs` chain; `family <name>: ...` means that family's
  templates are broken).
- `--dry-run` renders every row and sends nothing. No result workbook is written.

## Step 4. The real run

Only after the user confirms:

```bash
python tools/ddrs/ddrs.pyz run tests-ddrs/input/<book>.xlsx --env environment-configuration/environment-configuration-template-hardcode.json --seagull "<seagull path>"
```

- Time budget: 1800 s for a local run. Set `ATP_RUN_TIMEOUT_SECONDS` only when the user asks for more.
- Seagull timeout per session: `SEAGULL_TIMEOUT_SECONDS` (default 120, max 600).
- The run prints one line per row (`> row N`, `+ row N: Usage Created`, `- row N: Failed ...`), then the ECA
  check, then `=== bulk <book>: rows N, Usage Created ..., Failed ..., Broken ...`. Show this summary.
- Exit code: 0 all passed, 1 some failed, 2 broken or setup error.

### Seagull needs a console on Windows

On Windows, Seagull takes its keyboard setup from the console. Started without one, it stops with
`Fatal: Keyboard saved configuration failure`, and the affected rows become `Broken`. If the output or the
result shows that message:

- Tell the user the run must be started from a normal `cmd` window, not from the agent's terminal.
- Give the command for that window: `tests-ddrs\run-bulk-usage.bat <book>` (from the `tests-ddrs`
  folder or with the full path). The `.bat` passes the same settings, and `SEAGULL_ARG` finds `..\Seagull\seagull.exe`.
- Do not start Seagull with redirected output to get around this.

If the agent runs under WSL, Seagull may be a Windows binary that cannot open the console from there. Then
the same advice applies.

## Step 5. Read the result

Outputs:

- `tests-ddrs/input/<book>.result.xlsx`: the input workbook with `STATUS`, `ERROR DESC`, `SESSION ID`,
  `BUCKET`, `EVENT COST AR`, `EVENT COST AR (ND)`, `TC STATUS` filled. `TC STATUS` is PASSED, FAILED or BROKEN.
- `tests-ddrs/input/ddrs-results/<time>/allure-results/`: one Allure result per row, with the steps and the
  attachments (`scenario.xml`, `seagull.log`, decoded Diameter messages) for rows that are not passed.

Summarise the outcome in a short table: `TC ID`, `TC STATUS`, `ERROR DESC`. For each non-passed row, explain
the message. Broken means the usage was not judged: invalid row, Seagull did not start, no `Result-Code`, time
budget used up, ECA SOAP fault. Failed means it was judged and rejected: `Result-Code` other than 2001 such as
5030, unexpected CCR sequence, event not found in ECA, AR not equal to ER.

Map the common cases:

| `ERROR DESC` contains | Meaning | Next step |
|---|---|---|
| `OCS rejected (Result-Code 5030)` | the OCS does not know the subscriber | check IMSI and MSISDN of the row |
| `unexpected CCR sequence` | template and Seagull disagree | adapt the template (`ddrs-adapt-template`) |
| `no costed event in ECA` | ECA has no event for the Session-Id | check the account, the day in `eca.timezone`, and the rating wait |
| `AR differs from ER` | the charged cost is not the expected cost | the expected cost in the matrix is wrong, or the rate plan differs |
| `OCS still holds the previous peer (5012)` | the runner retries by itself | nothing; if it stays, wait and run again |
| `Fatal: Keyboard` | no console | Step 4 |

## Notes

- The run changes OCS state (usages) and writes the result next to the workbook. Re-running a workbook sends the
  same usages again: say so before a second real run.
