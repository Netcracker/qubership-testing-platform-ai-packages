# ddrs-bulk-usage

Skills for QA engineers of a project that received the DDRS bulk usage template. The template is the folder
`tests-ddrs/shared-ddrs/bulk` of the test repository: Seagull scenario templates for voice, data, and SMS usages. The
test runner sends one usage for each row of an `xlsx` workbook through Seagull and compares the cost that ECA reports
with the expected cost.

The skills do not run the template scenarios of the `seagull-diameter-scenarios` package. They work on the bulk template
and its workbook.

## Skills

| Skill                                                                | Purpose                                                                                                                                              |
| -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| [ddrs-adapt-template](.apm/skills/ddrs-adapt-template/SKILL.md)       | Compares a captured successful usage of the project's OCS with the template, and proposes AVPs to add, change, or (optionally) remove                |
| [ddrs-build-workbook](.apm/skills/ddrs-build-workbook/SKILL.md)       | Reads free test data from ATP-TDM and a test matrix, and writes the input workbook (schema v2) with `CALLING NUMBER`, `IMSI`, and `ACCOUNT NUMBER`    |
| [ddrs-run-local](.apm/skills/ddrs-run-local/SKILL.md)                 | Validates the workbook, makes a dry run, then runs it with `tools/ddrs/ddrs.pyz` against the local Seagull, and explains the result                  |

Each skill is plain-language: the agent picks it from a request such as "adapt the template to our OCS", "build a
workbook from TDM", or "run the workbook".

## What the skills expect

The skills work from the root of the project's test repository and use these paths:

- `tests-ddrs/shared-ddrs/bulk/<family>/`: `family.json`, `scenario.xml.tpl`, `conf.client.xml.tpl`, and optionally
  `dictionary.xml`.
- `tests-ddrs/shared-ddrs/ddrs-profile.json`: the bulk profile.
- `tools/ddrs/ddrs.pyz`: the DDRS local tool. The skills do not check whether it is current. Update it yourself.
- `environment-configuration/environment-configuration-template-hardcode.json`: the local endpoint values for
  `ddrs-run-local`.
- `tests-ddrs/ddrs-local.json`: the path of Seagull on your machine, for example `{"seagull": "C:\\Seagull\\seagull.exe"}`.
  Add `**/ddrs-local.json` to `.gitignore`.
- `tests-ddrs/shared-ddrs/tdm-mapping.json`: which TDM column holds which workbook column. The `ddrs-build-workbook`
  skill writes it after you confirm the mapping.
- `.tdm-assistant/config.json`: the TDM address and the project, environment, and system. The TDM skills write it.

## Install

The package depends on `tdm-test-data-assistant` for the TDM calls. APM installs both. Run `apm install` in the folder
in which you start your agent:

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/ddrs-bulk-usage#main
```

Or add it to the `apm.yml` of the test repository:

```yaml
dependencies:
  apm:
    - Netcracker/qubership-testing-platform-ai-packages/agent-packages/ddrs-bulk-usage#main
```

## Safety

- `ddrs-adapt-template` edits nothing before you confirm the table of changes.
- `ddrs-build-workbook` never invents `EVENT COST ER`, and occupies TDM rows only after you confirm.
- `ddrs-run-local` sends real usages to the OCS. It validates and makes a dry run first, and asks before the real run.
- No skill writes a password or a token to a file, and none prints the content of the environment file.
