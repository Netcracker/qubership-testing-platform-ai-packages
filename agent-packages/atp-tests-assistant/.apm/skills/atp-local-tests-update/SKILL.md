---
name: atp-local-tests-update
description: Use when the user asks to download, clone, update, or refresh the local copy of the project's tests, for example "clone the tests into D:\work\tests", "update the local tests", or "refresh my copy of the tests from the branch develop", or the same in another language. Clones the test repository into the folder of the local tests or fast-forwards that clone, without ever discarding local work, and writes LOCAL_ROOT_FOLDER in the config file of the package. It runs no test.
user-invocable: false
---

# Clone or update the local tests

The folder of the local tests, `LOCAL_ROOT_FOLDER` of `.atp-assistant/config.json`, holds a copy of the test
repository. A script clones the repository into it or updates the clone with Git. The agent runs no Git command for
this itself, and never reads the token.

## Run

```bash
python <skill folder>/scripts/update_local_tests.py [--path FOLDER] [--repo URL] [--branch BRANCH]
```

Run the script from the project folder, so that it finds `.atp-assistant/config.json`. If `python` isn't found, try
`python3` or `py -3`. Quote each value for the shell.

The request to clone or to update is the confirmation: run the script without asking. Print its output as it is. An
error comes as one JSON object on stderr with exit status 1; report its `message` and the remedy it names.

## Map the request to options

| User says                       | Option            |
| ------------------------------- | ----------------- |
| "update the local tests"        | none              |
| "clone the tests into `folder`" | `--path folder`   |
| a branch in the request         | `--branch <name>` |
| a repository in the request     | `--repo <url>`    |

- Pass `--branch` only when the request has a branch. It lets the script check out that branch.
- Without `--path`, the folder is the one of the config. Don't search the disk for one.
- The repository and the branch default to `ATP_TESTS_GIT_REPO_URL` and `ATP_TESTS_GIT_REPO_BRANCH` of the config.

## What the script does

| The folder                     | Result                                  |
| ------------------------------ | --------------------------------------- |
| missing or empty               | A clone                                 |
| a clone of the same repository | A fast-forward of the branch            |
| anything else                  | An error, and the folder stays as it is |

It never merges, rebases, stashes, resets, or deletes. After it, the folder is checked as
[atp-local-folder-set](../atp-local-folder-set/SKILL.md) does, and a folder given by `--path` is saved.

## Result and errors

When the script stops on local work, say what it found and leave it to the user. Don't commit, stash, reset, discard,
or delete anything to make the update pass unless the user asks for that step.

| Result                      | Say                                                                                           |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| What was cloned or updated  | Show it as printed.                                                                           |
| `local_changes`             | Show `files`: they have changes that are not committed.                                       |
| `local_diverged`            | The branch has local commits and new commits in the repository. The user decides how to join. |
| `branch_differs`            | Another branch is checked out. Ask which branch to update, and pass it as `--branch`.         |
| `branch_missing`            | The repository has no such branch.                                                            |
| `local_root_not_a_clone`    | Ask for an empty or a new folder.                                                             |
| `local_root_other_repo`     | The folder is a clone of another repository, which the message names.                         |
| `local_root_missing`        | No folder is set. Ask where to clone, and pass it as `--path`.                                |
| `local_root_invalid`        | Show `problems`: the clone or the update was made, but the folder lacks the files.            |
| `git_missing`               | Git is not installed.                                                                         |
| `git_failed`, `git_timeout` | Show the message. A refused sign-in usually means that the token is missing or wrong.         |
| `repo_missing`              | No test repository. Ask for it, or set `ATP_TESTS_GIT_REPO_URL` in the config.                |
| `repo_url_invalid`          | The repository URL has no host, group, and project.                                           |
| `config_missing`            | There is no `.atp-assistant/config.json`. Offer to create it with atp-config-manage.          |
| `config_unreadable`         | The message names the file and the problem. Don't repair the file unless the user asks.       |
| `config_unwritable`         | The file could not be written. Report the message.                                            |
| `invalid_value`             | `TESTS_FOLDER` or `ENV_CONFIGURATION_FOLDER` is not a folder path. Show the message.          |

The token is the environment variable `GITLAB_TOKEN`, or the first line of `.atp-assistant/gitlab-token`. Never ask
the user for the token in the chat, and never open the token file.
