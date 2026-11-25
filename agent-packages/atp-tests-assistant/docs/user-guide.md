# atp-tests-assistant user guide

## Install

Run `apm install` in the folder in which you start your agent:

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/atp-tests-assistant#main
```

You need Python 3.9 or later on the machine. The scripts use only its standard library.

## Set up the repository and the token

The skills need the URL and the branch of the test repository, and, for a private repository, a GitLab token that can
read it.

1. If the project already uses the tdm-test-data-assistant package, nothing else is needed for the repository: the
   script reads `ATP_TESTS_GIT_REPO_URL` and `ATP_TESTS_GIT_REPO_BRANCH` from the variables file that
   `GENERATE_VARIABLES_FILE` names in `.tdm-assistant/config.json`.
2. Without that package, give the repository in the request or the command: `/atp-tests-list repo=<url> branch=<branch>`.
   With `repo=` and no `branch=`, the script reads the default branch of that repository.
3. Set the token in the environment variable `GITLAB_TOKEN`, or put it on the first line of
   `.tdm-assistant/gitlab-token`. The token needs the right to read the repository. Never paste it into the chat: the
   script reads it, and the agent never does.

Without a token the script asks GitLab anonymously, which works for a public repository only.

## List the tests

Ask in plain language, or type the command:

| You write                                         | Command                                       |
| ------------------------------------------------- | --------------------------------------------- |
| Show all tests                                    | `/atp-tests-list`                             |
| Show the tests in the folder Billing              | `/atp-tests-list folder=Billing`              |
| Show the tests in the folder /Billing             | `/atp-tests-list folder=/Billing`             |
| Show the tests with `create` in the name          | `/atp-tests-list name=create`                 |
| Show the tests in the folder Billing, as a table  | `/atp-tests-list folder=Billing format=table` |

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

| You write                                          | Command                                 |
| -------------------------------------------------- | --------------------------------------- |
| Show the list of environments for the pipeline     | `/atp-tests-environments`               |
| Show the pipeline environments that contain `prod` | `/atp-tests-environments name=prod`     |

The command reads `GITLAB_URL`, `GITLAB_PROJECT_ID`, and `GITLAB_REF` from `.tdm-assistant/config.json`, the settings
that tdm-generate-test-data uses to start the pipeline. Without that package, give them in the command:
`/atp-tests-environments url=<gitlab url> project=<id> ref=<branch>`. The token is set as described in
[Set up the repository and the token](#set-up-the-repository-and-the-token).

The answer lists the names, sorted ignoring case, without `environments/` and without `.yaml`:

```text
Found 2 of 250 environments in https://gitlab.example.com, project 7, branch main, folder environments. Filter: name contains "ivory".

- `atp3prod_dyn-CI-Ivory`
- `dev-CI-Ivory`
```

To run the pipeline on an environment, pass `environments/<name>.yaml` as `PIPELINE_RUNTIME_CONFIG`. For the first name
above, that is `environments/atp3prod_dyn-CI-Ivory.yaml`.

## Errors

| Error                         | Meaning and remedy                                                                                                                              |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `repo_missing`                | No repository. Give `repo=<url>`, or set `ATP_TESTS_GIT_REPO_URL` in the variables file.                                                        |
| `repo_inaccessible`           | GitLab answered 401, 403, or 404: the repository doesn't exist, or the token is missing or can't read it.                                       |
| `tests_folder_missing`        | The repository or the branch has no `TestGeneration/tests/TestScenario`, or the branch doesn't exist.                                           |
| `folder_not_found`            | No folder with the given name or path under `TestScenario`.                                                                                     |
| `server_unreachable`          | The script can't reach GitLab. Check the URL and the network.                                                                                   |
| `gitlab_settings_missing`     | Environments only: `GITLAB_URL`, `GITLAB_PROJECT_ID`, or `GITLAB_REF` is missing. Set it in the config, or give `url=`, `project=`, and `ref=`. |
| `environments_folder_missing` | Environments only: the pipeline repository or the branch has no `environments` folder.                                                          |

A request that matches no test file is not an error: the answer says that nothing was found and names the filters.
