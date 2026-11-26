# atp-tests-assistant

Skills that read the project's GitLab repositories. One lists the Playwright test files of the test repository, sorted
by name, as a nested list; you can limit the list to one folder or to the files whose name contains a given text. The
second lists the environments of the GitLab pipeline, the YAML files in the `environments` folder of the pipeline
repository, and can keep only the names that contain a given text. A third shows the YAML file of one environment, the
current one or one that you specify by name or by a part of it. A fourth sets the environment of the pipeline: it
finds the file by name or by a part of it and writes `PIPELINE_RUNTIME_CONFIG`, also before you run a test case on an
environment.

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
| [atp-common](.apm/skills/atp-common/SKILL.md)                       |                          | Shared script code. Not a task; the agent never invokes it                      |

The package instruction
[atp-tests-assistant](.apm/instructions/atp-tests-assistant.instructions.md) applies to a plain request: the agent
takes the answer from the script, shows it as printed, and never reads or asks for the token.

## Settings

The package keeps its settings in one file, `.atp-assistant/config.json`. A script looks for it from the working
directory up. The scripts that list tests and environments also work without it, from the options of the command.

```json
{
  "GITLAB_URL": "https://gitlab.example.com",
  "GITLAB_PROJECT_ID": "7",
  "GITLAB_REF": "main",
  "variables": {
    "ATP_TESTS_GIT_REPO_URL": "https://gitlab.example.com/group/tests.git",
    "ATP_TESTS_GIT_REPO_BRANCH": "main",
    "PIPELINE_RUNTIME_CONFIG": "environments/dev.yaml"
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

The package writes one value: `PIPELINE_RUNTIME_CONFIG` in `variables`, when you set the environment.

## Check the package

```bash
python agent-packages/atp-tests-assistant/tests/selftest.py
```

The self-test starts a fake GitLab on localhost and checks the output of the scripts, the filters, the pagination, the
search for an environment, the change of the config file, the choice of the repository and the branch, the token, and
the errors. It does not test how the agent reads a request.
