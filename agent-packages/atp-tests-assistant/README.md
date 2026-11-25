# atp-tests-assistant

Skills that read the project's test repository in GitLab. The first one lists its Playwright test files, sorted by
name, as a nested list. You can limit the list to one folder or to the files whose name contains a given text.

To install the package and run the skills, follow the [user guide](docs/user-guide.md).

## Skills

A task has a plain-language skill, which the agent picks from an ordinary request, and a command, which the agent runs
only when you type its name. The command is a frontend for the skill with formal arguments.

| Plain-language skill                                               | The command it serves | Purpose                                                           |
| ------------------------------------------------------------------ | --------------------- | ----------------------------------------------------------------- |
| [atp-tests-list-tests](.apm/skills/atp-tests-list-tests/SKILL.md)  | `/atp-tests-list`     | Lists the test files under `TestGeneration/tests/TestScenario`    |
| [atp-tests-common](.apm/skills/atp-tests-common/SKILL.md)          |                       | Shared script code. Not a task; the agent never invokes it        |

The package instruction
[atp-tests-assistant](.apm/instructions/atp-tests-assistant.instructions.md) applies to a plain request: the agent
takes the list from the script, shows it as printed, and never reads or asks for the token.

## What the package reads

The scripts work from the command line alone. Where the project already uses the
[tdm-test-data-assistant](https://github.com/Netcracker/qubership-testing-platform-tdm3/tree/main/agent-packages/tdm-test-data-assistant)
package, they read the same files, so the project's values are set once:

| Source                                                  | Used for                                                               |
| ------------------------------------------------------- | ---------------------------------------------------------------------- |
| `.tdm-assistant/config.json`                            | `GENERATE_VARIABLES_FILE`, `GITLAB_URL`, and `GITLAB_TOKEN_ENV`        |
| The variables file that `GENERATE_VARIABLES_FILE` names | `ATP_TESTS_GIT_REPO_URL` and `ATP_TESTS_GIT_REPO_BRANCH`               |
| Environment variable `GITLAB_TOKEN`                     | The GitLab token; `GITLAB_TOKEN_ENV` names another variable            |
| `.tdm-assistant/gitlab-token`                           | The token on the first line, when the variable is empty                |

This package never writes these files. A change of one of the keys in the tdm-test-data-assistant package needs the same
change here.

## Check the package

```bash
python agent-packages/atp-tests-assistant/tests/selftest.py
```

The self-test starts a fake GitLab on localhost and checks the output of the script, the filters, the pagination, the
choice of the repository and the branch, the token, and the errors. It does not test how the agent reads a request.
