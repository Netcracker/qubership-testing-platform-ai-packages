# atp-tests-assistant user guide

## Install

Run `apm install` in the folder in which you start your agent:

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/atp-tests-assistant#main
```

You need Python 3.9 or later on the machine. The scripts use only its standard library.

## Set up the repository and the token

The skills need the settings of the pipeline repository, the URL and the branch of the test repository, and, for a
private repository, a GitLab token that can read them.

1. Create `.atp-assistant/config.json` in the folder in which you start your agent. The example and the keys are under
   [Settings](../README.md#settings) in the `README`.
2. Without the file, give the values in the request or the command, for example
   `/atp-list-tests repo=<url> branch=<branch>`. With `repo=` and no `branch=`, the script reads the default
   branch of that repository.
3. Set the token in the environment variable `GITLAB_TOKEN`, or put it on the first line of
   `.atp-assistant/gitlab-token`. The token needs the right to read the repositories. Never paste it into the chat: the
   script reads it, and the agent never does. If the folder is in a Git repository, add
   `.atp-assistant/gitlab-token` to `.gitignore`.

Without a token the script asks GitLab anonymously, which works for a public repository only.

### Move the settings from `.tdm-assistant`

Versions before 0.7.0 read the files of the tdm-test-data-assistant package. The scripts do not read them anymore, so
move the settings by hand:

1. Copy `GITLAB_URL`, `GITLAB_PROJECT_ID`, `GITLAB_REF`, and `GITLAB_TOKEN_ENV` from `.tdm-assistant/config.json` to
   `.atp-assistant/config.json`.
2. Copy the object `variables` from the file that `GENERATE_VARIABLES_FILE` names into the same file.
3. Move `.tdm-assistant/gitlab-token`, if you have it, to `.atp-assistant/gitlab-token`.

If you also generate test data with tdm-test-data-assistant, copy instead of moving: that package still reads its own
files.

## List the tests

Ask in plain language, or type the command:

| You write                                        | Command                                       |
| ------------------------------------------------ | --------------------------------------------- |
| Show all tests                                   | `/atp-list-tests`                             |
| Show the tests in the folder Billing             | `/atp-list-tests folder=Billing`              |
| Show the tests in the folder /Billing            | `/atp-list-tests folder=/Billing`             |
| Show the tests with `create` in the name         | `/atp-list-tests name=create`                 |
| Show the tests in the folder Billing, as a table | `/atp-list-tests folder=Billing format=table` |

All tests are `*.ts` files under `TestGeneration/tests/TestScenario`, and the answer shows them sorted by name, ignoring
case, at every level. A folder lists its own files first and its subfolders after them. A folder with no matching
files is left out.

```text
Found 4 test files in 3 folders of https://gitlab.example.com/group/tests, branch main, under TestGeneration/tests/TestScenario.

- **TestScenario/**
  - `smoke.spec.ts`
  - **Billing/**
    - `invoice.spec.ts`
    - **Corporate/**
      - `create.spec.ts`
      - `delete.spec.ts`
```

### Filters

- `folder=Name` finds every folder called `Name`, at any depth under `TestScenario`, ignoring case. It lists the tests
  in that folder and its subfolders. When several folders have the name, each one appears with its path.
- `folder=/Name` takes the path from `TestScenario`, so `folder=/Billing/Corporate` lists only that folder. The agent
  passes the path to the script without the leading slash.
- `name=text` keeps the files whose name contains `text`, ignoring case. A value with `*` or `?`, such as
  `name="*login*.spec.ts"`, is a mask for the whole filename.
- The filters combine: the folder narrows the search, and the name filters the files in it.
- `format=table` prints one row for each file, with its folder and its name.

## List the environments of the pipeline

The environments of the GitLab pipeline are the YAML files in the `environments` folder of the pipeline repository. The
name of an environment is the filename without `.yaml`. They are not the environments of the TDM3 service. A project
can have hundreds of them, so you can keep only the names that contain a text.

| You write                                          | Command                            |
| -------------------------------------------------- | ---------------------------------- |
| Show the list of environments for the pipeline     | `/atp-list-environments`           |
| Show the pipeline environments that contain `prod` | `/atp-list-environments name=prod` |

The command reads `GITLAB_URL`, `GITLAB_PROJECT_ID`, and `GITLAB_REF` from `.atp-assistant/config.json`. Without the
file, give them in the command:
`/atp-list-environments url=<gitlab url> project=<id> ref=<branch>`. The token is set as described in
[Set up the repository and the token](#set-up-the-repository-and-the-token).

The answer lists the names, sorted ignoring case, without `environments/` and without `.yaml`:

```text
Found 2 of 250 environments in https://gitlab.example.com, project 7, branch main, folder environments. Filter: name contains "ivory".

- `atp3prod_dyn-CI-Ivory`
- `dev-CI-Ivory`
```

To run the pipeline on an environment, [set it](#set-the-environment-of-the-pipeline), or pass
`environments/<name>.yaml` as `PIPELINE_RUNTIME_CONFIG`. For the first name
above, that is `environments/atp3prod_dyn-CI-Ivory.yaml`.

## Show the description of an environment

The description of an environment is its YAML file in the `environments` folder of the pipeline repository. The current
environment is the file that `PIPELINE_RUNTIME_CONFIG` names, such as `environments/atp3prod_dyn-CI-Ivory.yaml`, in
`variables` of `.atp-assistant/config.json`.

| You write                                          | Command                               |
| -------------------------------------------------- | ------------------------------------- |
| Show the description of the current environment    | `/atp-show-environment`               |
| Show the config of the current environment         | `/atp-show-environment`               |
| Show the description of the environment `CI-Ivory` | `/atp-show-environment name=CI-Ivory` |

Give the name without `environments/` and without `.yaml`. A part of the name is enough:

1. The command reads `environments/<name>.yaml`.
2. When there is no such file, it takes the name equal to `<name>` ignoring case, or else the names that contain it. A
   value with `*` or `?` is a mask for the whole name.
3. When one name matches, it shows that file. When several match, it lists them, and you specify one of them.

The repository, the branch, and the token are the same as for the list of environments, and the command accepts
`ref=`, `url=`, and `project=` too. The answer is a heading that names the file, and the file as it is:

````text
Current environment (PIPELINE_RUNTIME_CONFIG) `atp3prod_dyn-CI-Ivory`: file `environments/atp3prod_dyn-CI-Ivory.yaml` in https://gitlab.example.com, project 7, branch main.

```yaml
name: CI-Ivory
```
````

The file is not masked: a password or a key that it holds appears in the chat and goes to the model.

## Set the environment of the pipeline

The environment of the pipeline is the value of `PIPELINE_RUNTIME_CONFIG` in `variables` of
`.atp-assistant/config.json`: `environments/<filename>`.

| You write                                  | Command                                |
| ------------------------------------------ | -------------------------------------- |
| Set the pipeline environment to `CI-Ivory` | `/atp-set-environment name=CI-Ivory`   |
| Change the pipeline config to `CI-Ivory`   | `/atp-set-environment name=CI-Ivory`   |
| Run the test case `X` on `CI-Ivory`        | no command; write it in plain language |

The name is searched as for the description of an environment:

- When one environment is found, `PIPELINE_RUNTIME_CONFIG` is set to its file. The variable is added when the config has
  none. The agent does not ask for a confirmation.
- When several match, the agent lists them and changes nothing until you choose one.
- When none matches, nothing changes.

The script writes only this one value. The file is rewritten as JSON with its indentation and line ends. The other
values stay, but a layout of your own, such as a list written on one line, is not kept.

When you ask to run a test case on an environment, the agent sets the environment first and then starts the run with
the tdm-test-data-assistant package, which asks for its own confirmation. That package does not read the config of this
one, so the agent passes it the file of the environment. The value stays in the config after the run.

The repository, the branch, and the token are the same as for the list of environments, and the command accepts
`ref=`, `url=`, and `project=` too.

## Errors

| Error                         | Meaning and remedy                                                                                                                              |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `repo_missing`                | No repository. Give `repo=<url>`, or set `ATP_TESTS_GIT_REPO_URL` in `variables` of the config.                                                 |
| `repo_inaccessible`           | GitLab answered 401, 403, or 404: the repository doesn't exist, or the token is missing or can't read it.                                       |
| `tests_folder_missing`        | The repository or the branch has no `TestGeneration/tests/TestScenario`, or the branch doesn't exist.                                           |
| `folder_not_found`            | No folder with the given name or path under `TestScenario`.                                                                                     |
| `server_unreachable`          | The script can't reach GitLab. Check the URL and the network.                                                                                   |
| `gitlab_settings_missing`     | Environments only: `GITLAB_URL`, `GITLAB_PROJECT_ID`, or `GITLAB_REF` is missing. Set it in the config, or give `url=`, `project=`, and `ref=`. |
| `environments_folder_missing` | Environments only: the pipeline repository or the branch has no `environments` folder.                                                          |
| `runtime_config_missing`      | No current environment. Set `PIPELINE_RUNTIME_CONFIG` in `variables`, or give `name=`.                                                          |
| `config_missing`              | Setting the environment only: there is no `.atp-assistant/config.json`. Create it.                                                              |
| `config_unreadable`           | The config can't be read, or it or its `variables` is not a JSON object. Fix the file.                                                          |
| `config_unwritable`           | The config can't be written. Check that it is not read-only or locked.                                                                          |
| `environment_file_missing`    | The branch, or the file that `PIPELINE_RUNTIME_CONFIG` names, does not exist. Check the value and `GITLAB_REF`.                                 |

A request that matches no test file or no environment is not an error: the answer says that nothing was found.
