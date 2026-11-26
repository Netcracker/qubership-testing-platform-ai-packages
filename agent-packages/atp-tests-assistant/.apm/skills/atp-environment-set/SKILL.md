---
name: atp-environment-set
description: Use when the user asks to set or change the environment of the GitLab pipeline, for example "set the pipeline environment to CI-Ivory", "change the pipeline config to dev", or the same in another language, and also before any request that runs a test case or a scope on a named environment, for example "run the test case Create customer on CI-Ivory". Finds the environment file in the pipeline repository by name or by a part of it and sets PIPELINE_RUNTIME_CONFIG in the config file of the package. It does not select an environment of the TDM3 service.
user-invocable: false
---

# Set the environment of the pipeline

The pipeline runs on the environment that `PIPELINE_RUNTIME_CONFIG` names in `variables` of
`.atp-assistant/config.json`, as `environments/<filename>`. A script finds the environment file in the pipeline's
GitLab repository and writes that value. The agent builds no request, reads no token, does not clone the repository, and does not edit the file itself.

The "environment" and the "config" of the pipeline mean the same thing here. When the request mentions TDM3 or the
TDM context, this skill does not apply.

## Run

```bash
python <skill folder>/scripts/set_environment.py --name TEXT [--url URL] [--project ID] [--ref BRANCH]
```

Run the script from the project folder, so that it finds `.atp-assistant/config.json`. If `python` isn't found, try
`python3` or `py -3`. Quote each value for the shell.

The request to set the environment is the confirmation: run the script without asking. Print its output as it is. An
error comes as one JSON object on stderr with exit status 1; report its `message` and the remedy it names.

## Map the request to options

| User says                                           | Option                        |
| --------------------------------------------------- | ----------------------------- |
| "the environment `name`", also a part of a name     | `--name name`                 |
| a GitLab URL, a project, or a branch in the request | `--url`, `--project`, `--ref` |

Pass the name as the user wrote it. Don't add a prefix and don't complete a partial name: the script does the search.
If the user wrote `environments/<name>.yaml`, pass `<name>`. If the user named no environment, ask for it.

## How the script finds the file

It searches as [atp-environment-show](../atp-environment-show/SKILL.md) does:

- It reads `environments/TEXT.yaml`. When there is no such file, it takes the name equal to `TEXT` ignoring case, or
  else the names that contain `TEXT`. A value with `*` or `?` is a mask for the whole name.
- When one environment is found, it sets `PIPELINE_RUNTIME_CONFIG` to `environments/<filename>`. It adds the variable
  when the config has none.
- When none or several are found, it changes nothing.

## Run a test case on an environment

When the request runs a test case or a scope on an environment, for example "run the test case Create customer on
CI-Ivory", set the environment first and run second:

1. Run the script with `--name` set to the environment of the request.
2. Continue only when the output says that `PIPELINE_RUNTIME_CONFIG` was set or already holds the value. When it lists
   several names, ask which one is meant, and run the script again with that name. When nothing matches, say so and run
   no test.
3. Follow [atp-tests-run](../atp-tests-run/SKILL.md), which says when to ask before the run. Don't pass the
   environment to it:
   the config already holds the file, and the name from the request is not a file.

## Result and errors

| Result                                 | Say                                                                                             |
| -------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `Set PIPELINE_RUNTIME_CONFIG to ...`   | Show it as printed.                                                                             |
| `... is already ... Nothing changed.`  | Show it as printed.                                                                             |
| `N environments match ... Specify one` | Show the list as printed and ask which one is meant. Don't choose for the user.                 |
| `No environment matches ...`           | Say that nothing matched and nothing changed. Offer atp-environments-list.                      |
| `config_missing`                       | There is no `.atp-assistant/config.json`. Say what it needs and where it goes.                  |
| `config_unreadable`                    | The message names the file and the problem. Don't repair the file unless the user asks.         |
| `config_unwritable`                    | The file could not be written. Report the message.                                              |
| `gitlab_settings_missing`              | The message names the missing keys. Tell the user where they go.                                |
| `environments_folder_missing`          | The repository or the branch has no `environments` folder, as the message says.                 |
| `repo_inaccessible`                    | The project doesn't exist, or the token is missing or can't read it. Give the message's remedy. |
| `server_unreachable`                   | GitLab can't be reached. Say so; don't retry in a loop.                                         |

The token is the environment variable `GITLAB_TOKEN`, or the first line of `.atp-assistant/gitlab-token`. Never ask
the user for the token in the chat, and never open the token file.
