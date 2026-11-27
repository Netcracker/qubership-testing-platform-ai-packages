# atp-tests-assistant-opencode

The slash commands of [atp-tests-assistant](../atp-tests-assistant/README.md) for OpenCode. OpenCode lists commands in
its `/` menu but not skills, so the skills of that package alone give no `/atp-run-tests` there. This package adds one
command file for each command skill, and it depends on `atp-tests-assistant`, so one install brings both.

To install the package and check it, follow the [user guide](docs/user-guide.md).

## Commands

Each command file loads the skill of the same name and passes it the text after the command name as `$ARGUMENTS`. The
rules, the arguments, and the safety checks stay in the skill. The package has no logic of its own.

| Command                   | Does                                                                     |
| ------------------------- | ------------------------------------------------------------------------ |
| `/atp-config`             | Show or change the config of the tests assistant                         |
| `/atp-list-tests`         | List the tests of the project's test repository                          |
| `/atp-list-environments`  | List the environments of the GitLab pipeline                             |
| `/atp-show-environment`   | Show the YAML file of one environment of the pipeline                    |
| `/atp-set-environment`    | Set the environment of the GitLab pipeline                               |
| `/atp-set-local-folder`   | Set or check the folder of the local tests                               |
| `/atp-update-local-tests` | Clone or update the local tests                                          |
| `/atp-run-tests`          | Run a test case or a scope in the GitLab pipeline and wait until it ends |

The arguments and examples are in the
[user guide of the main package](../atp-tests-assistant/docs/user-guide.md), and the keys of the config under
[Settings](../atp-tests-assistant/README.md#settings) of that package.

## Keeping it in sync

A command file repeats the `argument-hint` of its skill in `atp-tests-assistant`. When a command skill is added,
renamed, removed, or gets another `argument-hint`, change the file in `.apm/prompts/` too. The self-test fails until
the two match:

```bash
python agent-packages/atp-tests-assistant-opencode/tests/selftest.py
```
