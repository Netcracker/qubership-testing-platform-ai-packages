# atp-tests-assistant

Skills that work with the project's tests in GitLab: they read its repositories and run the tests in its pipeline.
One lists the Playwright test files of the test repository, sorted
by name, as a nested list; you can limit the list to one folder or to the files whose name contains a given text. The
second lists the environments of the GitLab pipeline, the YAML files in the `environments` folder of the pipeline
repository, and can keep only the names that contain a given text. A third shows the YAML file of one environment, the
current one or one that you specify by name or by a part of it. A fourth sets the environment of the pipeline: it
finds the file by name or by a part of it and writes `PIPELINE_RUNTIME_CONFIG`, also before you run a test case on an
environment. A fifth runs a test case or a scope in the pipeline, which is also how you generate test data. A sixth
shows and changes the settings of the package.

To install the package and run the skills, follow the [user guide](docs/user-guide.md).

## Skills

A task has a plain-language skill, which the agent picks from an ordinary request, and a command, which the agent runs
only when you type its name. The command is a frontend for the skill with formal arguments.

| Plain-language skill                                                | The command it serves    | Purpose                                                                         |
| ------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------- |
| [atp-tests-list](.apm/skills/atp-tests-list/SKILL.md)               | `/atp-list-tests`        | Lists the test files under `TestGeneration/tests/TestScenario`                  |
| [atp-environments-list](.apm/skills/atp-environments-list/SKILL.md) | `/atp-list-environments` | Lists the environments of the GitLab pipeline, optionally by a part of the name |
| [atp-environment-show](.apm/skills/atp-environment-show/SKILL.md)   | `/atp-show-environment`  | Shows the YAML file of one environment of the pipeline                          |
| [atp-environment-set](.apm/skills/atp-environment-set/SKILL.md)     | `/atp-set-environment`   | Sets `PIPELINE_RUNTIME_CONFIG` to one environment of the pipeline               |
| [atp-tests-run](.apm/skills/atp-tests-run/SKILL.md)                 | `/atp-run-tests`         | Runs a test case or a scope in the pipeline, which also generates test data     |
| [atp-config-manage](.apm/skills/atp-config-manage/SKILL.md)         | `/atp-config`            | Shows and changes the config of the package, and creates it                     |
| [atp-common](.apm/skills/atp-common/SKILL.md)                       |                          | Shared script code. Not a task; the agent never invokes it                      |

The package instruction
[atp-tests-assistant](.apm/instructions/atp-tests-assistant.instructions.md) applies to a plain request: the agent
takes the answer from the script, shows it as printed, and never reads or asks for the token.

## Settings

The package keeps its settings in one file, `.atp-assistant/config.json`. A script looks for it from the working
directory up. The scripts that list tests and environments also work without it, from the options of the command.
Running tests needs the file.

```json
{
  "GITLAB_URL": "https://gitlab.example.com",
  "GITLAB_PROJECT_ID": "7",
  "GITLAB_REF": "main",
  "variables": {
    "ATP_TESTS_GIT_REPO_URL": "https://gitlab.example.com/group/tests.git",
    "ATP_TESTS_GIT_REPO_BRANCH": "main",
    "PIPELINE_RUNTIME_CONFIG": "environments/dev.yaml",
    "EXECUTION_TYPE": "test",
    "EXECUTION_NAME": "Generate domestic customers",
    "ENABLE_JIRA_INTEGRATION": "false",
    "SEND_WEBEX_NOTIFICATION": "true"
  }
}
```

| Key                 | Holds                                                                                   |
| ------------------- | --------------------------------------------------------------------------------------- |
| `GITLAB_URL`        | Base URL of the GitLab service.                                                         |
| `GITLAB_PROJECT_ID` | The numeric ID or the path of the GitLab project that holds the pipeline.               |
| `GITLAB_REF`        | The branch of the pipeline repository, such as `main`.                                  |
| `GITLAB_TOKEN_ENV`  | Optional. The environment variable that holds the token. The default is `GITLAB_TOKEN`. |
| `variables`         | The variables of the pipeline. Keep there only what the pipeline receives.              |

Keep the token out of the config file. A script takes it from the environment variable, or else from the first line of
`.atp-assistant/gitlab-token`. Do not commit that file.

The package writes the config only when you ask: the environment that you set, and the values that you change with
`/atp-config` or in plain language. `/atp-config` also creates the file when there is none, with the project's own values empty and a sample or a
default in the others. The
patterns of the search for identifiers, and values whose name looks like a secret, are changed by hand.

## Running tests

atp-tests-run sends the `variables` to the pipeline, with the ones that your request names replaced. Before it starts
the pipeline, it checks that `ATP_TESTS_GIT_REPO_URL`, `EXECUTION_TYPE`, and `EXECUTION_NAME` are not empty, and that
`ENABLE_JIRA_INTEGRATION` and `SEND_WEBEX_NOTIFICATION` are `true` or `false`. The token needs the right to read the
project and to run pipelines. The pipeline normally ends within minutes, and the script stops waiting after 30 minutes;
it cannot cancel a pipeline.

### Search for business identifiers

The test cases create the business identifiers of new data, such as a customer ID, early in the pipeline. With the keys
below, at the top level of the config, the script reads the logs while the pipeline runs, and the agent reports each
identifier as soon as the logs show it. The search is on when `ORCHESTRATOR_URL` is set, and it then needs the next
three keys; a missing one is an error (`config_incomplete`). Without `ORCHESTRATOR_URL` the search is off, and the other
keys can stay in the config. It needs the downstream pipeline to be in the project of
`GITLAB_PROJECT_ID` or in another project that the token can read.

| Key                       | Holds                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| `ORCHESTRATOR_URL`        | Base URL of the test orchestrator, `http://` or `https://`. The script sends it no credentials. |
| `DOWNSTREAM_STAGE`        | The stage of the downstream pipeline whose first job logs the run ID.                           |
| `RUN_ID_PATTERN`          | A regular expression that finds the run ID in the log of that job.                              |
| `BUSINESS_ID_PATTERNS`    | An object: the name of an identifier, and a regular expression for it in the runner log.        |
| `DISCOVERY_TIMEOUT`       | Optional. Seconds from the start of the pipeline during which the script searches; `420`.       |
| `DISCOVERY_INTERVAL`      | Optional. Seconds between two rounds of the search until the run ID is known; `5`.              |
| `DISCOVERY_SLOW_INTERVAL` | Optional. Seconds between two rounds once the run ID is known; `15`.                            |

```json
{
  "ORCHESTRATOR_URL": "https://orchestrator.example.com",
  "DOWNSTREAM_STAGE": "1. Run ATP3 tests",
  "RUN_ID_PATTERN": "Run submitted: id=(?P<value>[0-9a-f-]{36})",
  "BUSINESS_ID_PATTERNS": {
    "customerId": "^customerId:[ \\t]*(?P<value>\\d+)[ \\t]*$"
  }
}
```

A pattern uses the Python regular expression syntax and is matched line by line, so `^` and `$` stand for the start and
the end of a line. The identifier is the group named `value`, or the first group when no group has that name. Each
distinct value is reported once. A value that is empty, longer than 200 characters, or not printable is ignored,
because a log is not trusted. A pattern that does not compile, or has no group, is refused as `invalid_pattern` before
the pipeline starts.

The script finds the downstream pipeline through the bridge job of the pipeline, takes the first job of
`DOWNSTREAM_STAGE`, and reads the run ID from the log of that job. It then reads the last 5000 lines of
`<ORCHESTRATOR_URL>/atp3/api/v1/runs/<run ID>/logs` on every round, because the identifiers appear one by one. Each
found value is printed as `FOUND <name>=<value>` in the progress output, and the result lists all of them in `found`.

Without the search, the result of a run says that none was made (`discovery.enabled` is false), and the agent tells
you that, not that nothing was found.

The search never stops the wait for the pipeline. It ends by itself after `DISCOVERY_TIMEOUT` seconds, or after five
failed requests in a row, and the result then says why in `discovery.stopped` and `discovery.message`. It needs the
agent to read the output of the script while it runs. A tool that shows the output only at the end gets the
identifiers at the end.

## Check the package

```bash
python agent-packages/atp-tests-assistant/tests/selftest.py
```

The self-test starts a fake GitLab on localhost and checks the output of the scripts, the filters, the pagination, the
search for an environment, the change of the config file, the choice of the repository and the branch, the token, and
the errors. With a fake orchestrator, it also checks the run of a pipeline and the search for business identifiers. It
does not test how the agent reads a request.
