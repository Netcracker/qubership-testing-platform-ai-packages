---
name: atp-environments-list
description: Use when the user asks which environments the GitLab pipeline can run on, for example "show the list of environments for the pipeline", "which pipeline environments contain prod", or "list the environments of the generation pipeline". Lists the YAML files in the environments folder of the pipeline repository, by name without .yaml, optionally only the names that contain a text. It does not list the environments of the TDM3 service.
user-invocable: false
---

# List the environments of the pipeline

The pipeline that generates test data runs on an environment. Each environment is a YAML file in the `environments`
folder of the pipeline's GitLab repository, on the branch the pipeline starts from, and its name is the filename
without `.yaml`. A project can have hundreds of them. A script reads the folder from the GitLab API, applies the
filter, sorts the names, and prints the answer. The agent builds no request, reads no token, and does not clone the
repository.

These are not the environments of the TDM3 service. When the request says nothing about the pipeline, the generation, or
GitLab and could mean either, ask which one is meant.

## Run

```bash
python <skill folder>/scripts/list_environments.py [--name TEXT] [--url URL] [--project ID] [--ref BRANCH]
```

Run the script from the project folder, so that it finds `.tdm-assistant/config.json`. If `python` isn't found, try
`python3` or `py -3`. Quote each value for the shell.

The script prints the answer in Markdown, ready to show. Print it to the user exactly as it is: don't reorder, shorten,
or rewrite it, and don't add names you think are missing. You may add one sentence after it. An error comes as one
JSON object on stderr with exit status 1; report its `message` and the remedy it names.

## Map the request to options

| User says                                                     | Option                        |
| ------------------------------------------------------------- | ----------------------------- |
| "the environments for the pipeline", "all environments"       | none                          |
| "with `text` in the name", "containing `text`", "like `text`" | `--name text`                 |
| a GitLab URL, a project, or a branch in the request           | `--url`, `--project`, `--ref` |

- `--name TEXT` keeps the names that contain `TEXT`, ignoring case. A value with `*` or `?` is a mask for the whole name.
- The names are printed without `environments/` and without `.yaml`.
- When the list is long, for example more than 50 names, show it as printed and add one sentence that offers to narrow it
  by a part of the name.

Don't guess a part of the name that the user didn't give.

## After the user picks an environment

The value that selects the environment in the pipeline is `environments/<name>.yaml`, the `PIPELINE_RUNTIME_CONFIG`
variable of tdm-generate-test-data. Say that value when the user asks for it or chooses a name. Choosing a name starts
nothing. To set it, follow [atp-environment-set](../atp-environment-set/SKILL.md). To show what an
environment contains, follow
[atp-environment-show](../atp-environment-show/SKILL.md).

## Where the repository comes from

Without options, the script takes `GITLAB_URL`, `GITLAB_PROJECT_ID`, and `GITLAB_REF` from `.tdm-assistant/config.json`,
the settings that tdm-generate-test-data uses to start the pipeline. This repository is the pipeline's, not the
repository of the tests that atp-tests-list reads. When the script reports `gitlab_settings_missing`, tell the
user to add the named keys to the config file or to give them in the request.

The token is the environment variable `GITLAB_TOKEN`, or the first line of `.tdm-assistant/gitlab-token`. Without a
token the script asks GitLab anonymously, which works for a public repository. Never ask the user for the token in the
chat, and never open the token file.

## Result and errors

| Result                                   | Say                                                                                                  |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| A list                                   | Show it as printed.                                                                                  |
| `No environments (*.yaml) found ...`     | Say that nothing matched, and repeat the filter the line names. Offer to loosen it.                  |
| `gitlab_settings_missing`                | The message names the missing keys. Tell the user where they go.                                     |
| `environments_folder_missing`            | The repository or the branch has no `environments` folder, as the message says.                      |
| `repo_inaccessible`                      | The project doesn't exist, or the token is missing or can't read it. Give the message's remedy.      |
| `server_unreachable`                     | GitLab can't be reached. Say so; don't retry in a loop.                                              |
