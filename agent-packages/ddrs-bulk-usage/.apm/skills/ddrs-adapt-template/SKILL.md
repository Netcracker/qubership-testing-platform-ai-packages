---
name: ddrs-adapt-template
description: Adapt the DDRS bulk family templates (tests-ddrs/shared-ddrs/bulk/<family>/scenario.xml.tpl and family.json) to a new project's OCS, using a captured successful usage (Seagull log or Wireshark CCR/CCA) as the reference. Use when a QA engineer received the bulk template and asks to adapt AVPs, Origin/Service-Context values, constants, or to compare a real OCS trace with the scenario. Triggers on "adapt template", "ddrs adaptation", "AVP for our OCS", "compare traffic with template", "bulk template adapt", "init template".
---

# Adapt the DDRS bulk template to a project OCS

The bulk flow is the same for every project. Only the AVP values and a few constants differ. This skill
compares one reference usage from the project's OCS with the template and proposes edits. It never edits
files before the user confirms the table of proposed changes.

Work from the test repository root (the folder that holds `tools/ddrs/ddrs.pyz`).

## Inputs

1. The family to adapt: a folder `tests-ddrs/shared-ddrs/bulk/<family>/` with `family.json`,
   `scenario.xml.tpl`, `conf.client.xml.tpl`, and optionally `dictionary.xml`. Read `family.json` first:
   `kind` (voice, data, sms), `mt`, and the variants with their `usage_types` and `values`.
2. The reference: a Seagull log or a Wireshark export of one successful usage in the project's system
   (CCR-I, CCR-U, CCR-T for voice and data; CCR-E for sms). Ask for it if the user did not attach it.
   Ask the user which usage it is (variant name), because the reference must match one family.

If the reference is a raw Wireshark export and not a Seagull log, ask the user for the Seagull-style log or
for a decoded text of each CCR/CCA. Do not guess AVP names from raw bytes.

## Step 1. Decode the reference into AVPs

The decoder ships inside `tools/ddrs/ddrs.pyz`. Import it from the archive without extracting:

```bash
python -c "import sys; sys.path.insert(0, 'tools/ddrs/ddrs.pyz'); import ddrs_decode as d; \
t=open('<log>', encoding='utf-8', errors='replace').read(); \
dic=open('tests-ddrs/shared-ddrs/bulk/<family>/dictionary.xml','rb').read(); \
[print(title); print(xml) for title, xml in d.decode_log(t, dic)]"
```

If `dictionary.xml` is absent in the family folder, use `tests-ddrs/shared-ddrs/bulk/dictionary.xml`
(the shared one), as the runner does. For sms, use `tests-ddrs/shared-ddrs/bulk/sms/dictionary.xml`
if the family has none of its own.

Each message comes out as an XML element tree (`steps` form): the command name is the root, AVPs are
elements named as in the log, grouped AVPs hold their members.

## Step 2. Compare with the template, command by command

Match messages by command and order: the Nth `CCR` in the template is the Nth `CCR` in the reference.
Compare the AVP trees of each pair. The sequence of `CC-Request-Type` values must be the same in both
(voice and data: 1, 2, 3; sms: 4). If it is not, stop and report the difference. The runner's verdict
compares the Seagull log with the CCR sequence of the template, so a changed sequence makes every usage
Failed.

Sort every difference into one of three groups:

- **Add**: an AVP is in the reference and not in the template. Propose inserting it in the same position
  of the same command. If its value depends on the row (MSISDN, IMSI, called number, timestamps,
  octets, rating group, MCC/MNC of the row), use a runner token (the list is in the next section). If the value is a
  project constant, put it in `variants.<name>.values` of `family.json` and reference it as `@@NAME@@`.
- **Change**: an AVP is in both but the value differs. Typical project-specific AVPs:
  `Origin-Host`, `Origin-Realm`, `Destination-Realm`, `Service-Context-Id`, `Product-Name`,
  `Called-Station-Id`, `TGPP-Charging-Characteristics`, `GGSN-Address`, `SGSN-Address`, `User-Equipment-Info-Value`.
  Show old and new value. Keep row-dependent AVPs as tokens: never replace `@@...@@` with a value from
  the reference.
- **Remove candidates**: an AVP is in the template and not in the reference. Report them only. Removal
  is optional: an AVP the OCS ignores does no harm. Do not remove anything without the user's choice.

Never write a real MSISDN, IMSI, session id, or secret from the reference into a template. Replace them
with the token that carries that value.

### Runner tokens

The runner fills these tokens for each row. A `@@TOKEN@@` that is neither here nor in `values` of the variant is a
template error.

| Token | Source | Kinds |
|---|---|---|
| `SESSION_ID` | `session_id_format` of `ddrs-profile.json` | all |
| `DESTINATION_HOST`, `DESTINATION_PORT` | `ddrs.DIAMETER` of the environment configuration | all |
| `EVENT_TS_I`, `CALL_TIMEOUT_MS` | computed | all |
| `EVENT_TS_U`, `EVENT_TS_T` | computed | voice, data |
| `CC_TIME` | `DURATION` (required in a voice template) | voice |
| `OCTETS_U_TOTAL`, `OCTETS_U_INPUT`, `OCTETS_U_OUTPUT`, `OCTETS_T_TOTAL`, `OCTETS_T_INPUT`, `OCTETS_T_OUTPUT` | `DURATION` (`OCTETS_T_TOTAL` required) | data |
| `MSISDN` | `CALLING NUMBER` | all |
| `CALLING_PARTY`, `CALLED_PARTY` | `CALLING NUMBER` and `B`; swapped when `mt` is true | all |
| `IMSI` | `IMSI` | all |
| `RATING_GROUP` | `RG`, otherwise `values.RATING_GROUP` | all |
| any other `UPPER_CASE` name | `values` of the variant | all |

## Step 3. Show the proposal and wait

Show one table with columns: command, AVP path, group (add / change / remove candidate), template value,
reference value, proposed edit. Then ask the user to confirm which rows to apply. Do not write files
before confirmation.

## Step 4. Rules the edits must keep

- Do not change the CCR order or the number of CCR commands in `<traffic>`.
- A voice template must keep `@@CC_TIME@@`. A data template must keep `@@OCTETS_T_TOTAL@@`.
- Every `@@TOKEN@@` must be either a runner token for the family kind or a key of `values` in that variant.
  A key of `values` must not repeat a runner token (except `RATING_GROUP`).
- `family.json` allows only the fields `kind`, `mt`, `variants`; a variant allows only `usage_types`,
  `values`. Unknown fields make the whole workbook broken.
- The `scenario.xml.tpl` must stay valid XML once tokens are replaced by 0.
- A new variant needs a unique name `[a-z0-9][a-z0-9-]*` and usage types that appear in no other family.

## Step 5. Check the result

Run from the test repository root:

```bash
python tools/ddrs/ddrs.pyz validate <workbook.xlsx>
python tools/ddrs/ddrs.pyz run <workbook.xlsx> --dry-run
```

`validate` checks every family of the repository, not only the one changed. `--dry-run` renders every row
and sends nothing. Show the output. If the user has a workbook with a real row for this variant, the next
step is one real usage through the `ddrs-run-local` skill.

If the test run gives `Result-Code` 5xxx or an `Error-Message`, use it as the next input: the reference
trace of the rejected usage is a better reference than the first one. Repeat from step 1.

## Notes

- `tools/ddrs/ddrs.pyz` may be an older build. The `ddrs_decode` module in it may lack a fix present in
  the runner sources. Use it as is and report any decoder error; do not patch the archive.
- The runner reads templates as UTF-8 (`ddrs_families.py`), although the XML header of
  `scenario.xml.tpl` says ISO-8859-1. Keep the new values ASCII so both readings agree.
