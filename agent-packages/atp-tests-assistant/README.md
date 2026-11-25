# atp-tests-assistant

Skills that read the project's GitLab repositories. One lists the Playwright test files of the test repository, sorted
by name, as a nested list; you can limit the list to one folder or to the files whose name contains a given text. The
second lists the environments of the GitLab pipeline, the YAML files in the `environments` folder of the pipeline
repository, and can keep only the names that contain a given text. A third shows the YAML file of one environment, the
current one or one that you specify by name or by a part of it.

To install the package and run the skills, follow the [user guide](docs/user-guide.md).

## Skills

A task has a plain-language skill, which the agent picks from an ordinary request, and a command, which the agent runs
only when you type its name. The command is a frontend for the skill with formal arguments.

| Plain-language skill                                                            | The command it serves          | Purpose                                                                         |
| ------------------------------------------------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------- |
| [atp-tests-tests-list](.apm/skills/atp-tests-tests-list/SKILL.md)               | `/atp-tests-list-tests`        | Lists the test files under `TestGeneration/tests/TestScenario`                  |
| [atp-tests-environments-list](.apm/skills/atp-tests-environments-list/SKILL.md) | `/atp-tests-list-environments` | Lists the environments of the GitLab pipeline, optionally by a part of the name |
| [atp-tests-environment-show](.apm/skills/atp-tests-environment-show/SKILL.md)   | `/atp-tests-show-environment`  | Shows the YAML file of one environment of the pipeline                          |
| [atp-tests-common](.apm/skills/atp-tests-common/SKILL.md)                       |                                | Shared script code. Not a task; the agent never invokes it                      |

The package instruction
[atp-tests-assistant](.apm/instructions/atp-tests-assistant.instructions.md) applies to a plain request: the agent
takes the answer from the script, shows it as printed, and never reads or asks for the token.

## What the package reads

The scripts work from the command line alone. Where the project already uses the
[tdm-test-data-assistant](https://github.com/Netcracker/qubership-testing-platform-tdm3/tree/main/agent-packages/tdm-test-data-assistant)
package, they read the same files, so the project's values are set once:

| Source                                                  | Used for                                                                                           |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `.tdm-assistant/config.json`                            | `GENERATE_VARIABLES_FILE`, `GITLAB_URL`, `GITLAB_PROJECT_ID`, `GITLAB_REF`, and `GITLAB_TOKEN_ENV` |
| The variables file that `GENERATE_VARIABLES_FILE` names | `ATP_TESTS_GIT_REPO_URL`, `ATP_TESTS_GIT_REPO_BRANCH`, and `PIPELINE_RUNTIME_CONFIG`               |
| Environment variable `GITLAB_TOKEN`                     | The GitLab token; `GITLAB_TOKEN_ENV` names another variable                                        |
| `.tdm-assistant/gitlab-token`                           | The token on the first line, when the variable is empty                                            |

This package never writes these files. A change of one of the keys in the tdm-test-data-assistant package needs the same
change here.

## Check the package

```bash
python agent-packages/atp-tests-assistant/tests/selftest.py
```

The self-test starts a fake GitLab on localhost and checks the output of the scripts, the filters, the pagination, the
search for an environment, the choice of the repository and the branch, the token, and the errors. It does not test how
the agent reads a request.
