---
name: atp-tests-list
description: Use when the user asks to show, list, or find the tests of the project's test repository, for example "show all tests", "list the tests in the folder Billing", or "tests with login in the name". Lists the Playwright test files (*.ts) of the tests folder of the repository, TestGeneration/tests/TestScenario by default, sorted by name, as a nested list.
user-invocable: false
---

# List the tests of the test repository

The project's tests are Playwright files (`*.ts`) in a GitLab repository, all of them in one tests folder, in folders
that can nest to any depth. The tests folder is `TESTS_FOLDER` of the config, by default
`TestGeneration/tests/TestScenario`. A script reads it from the GitLab API, applies the filters, sorts the files by
name, and prints the answer. The agent builds no request, reads no token, and does not clone the repository.

Below, `TestScenario` stands for the last part of the tests folder, which the answer shows as its root.

## Run

```bash
python <skill folder>/scripts/list_tests.py [--folder NAME | --under PATH] [--name TEXT] [--format tree|table]
                                            [--repo URL] [--branch BRANCH]
```

Run the script from the project folder, so that it finds `.atp-assistant/config.json`. If `python` isn't found, try
`python3` or `py -3`. Quote each value for the shell.

The script prints the answer in Markdown, ready to show. Print it to the user exactly as it is: don't reorder,
shorten, or rewrite it, and don't add the files you think are missing. You may add one sentence after it. An error
comes as one JSON object on stderr with exit status 1; report its `message` and the remedy it names.

## Map the request to options

| User says                                                 | Option                            |
| --------------------------------------------------------- | --------------------------------- |
| "all tests", "show the tests"                             | none                              |
| "in the folder Name", "in Name" (no leading slash)        | `--folder Name`                   |
| "in the folder /Name", "directly under TestScenario/Name" | `--under Name`                    |
| "in /A/B"                                                 | `--under A/B`                     |
| "with `text` in the name", "named like `text`"            | `--name text`                     |
| "named `*login*.ts`", a mask with `*` or `?`              | `--name "<mask>"`                 |
| "as a table"                                              | `--format table`                  |
| a repository or a branch in the request                   | `--repo <url>`, `--branch <name>` |

- `--folder Name` finds every folder called `Name` at any depth under `TestScenario`, ignoring case, and lists the
  tests in it and in its subfolders. When several folders have that name, the answer shows each one with its path.
- `--under PATH` counts the path from `TestScenario`. Pass it without a leading slash: a Windows shell turns `/Name`
  into a drive path.
- `--name TEXT` keeps the files whose name contains `TEXT`, ignoring case. A value with `*` or `?` is a mask for the
  whole filename.
- The filters combine: the folder narrows the search, and the name filters the files in it.
- The default output is a nested list, folders in bold and files in code font. Use the table only when the user
  asks for it.

Don't guess a folder or a name that the user didn't give. When the request is ambiguous, for example "tests for
customers" with no word that names a folder or a file, ask which one is meant.

## Where the repository comes from

Without `--repo`, the script takes `ATP_TESTS_GIT_REPO_URL` and `ATP_TESTS_GIT_REPO_BRANCH` from `variables` of
`.atp-assistant/config.json`. With `--repo` and no `--branch`, the script reads the default branch of that repository.
When the script reports `repo_missing`, tell the user to give the repository in the request or to add it to the
config.

The token is the environment variable `GITLAB_TOKEN`, or the first line of `.atp-assistant/gitlab-token`. Without a
token the script asks GitLab anonymously, which works for a public repository. Never ask the user for the token in the
chat, and never open the token file.

## Result and errors

| Result                          | Say                                                                                                |
| ------------------------------- | -------------------------------------------------------------------------------------------------- |
| A list or a table               | Show it as printed.                                                                                |
| `No test files (*.ts) found...` | Say that nothing matched, and repeat the filters the line names. Offer to loosen one.              |
| `folder_not_found`              | Say that the folder doesn't exist under `TestScenario`. Offer to list the folders at the top.      |
| `tests_folder_missing`          | The repository or the branch lacks the tests folder. Say which, as the message does.               |
| `invalid_value`                 | `TESTS_FOLDER` of the config is not a folder path. Show the message.                               |
| `repo_inaccessible`             | The repository doesn't exist, or the token is missing or can't read it. Give the message's remedy. |
| `server_unreachable`            | GitLab can't be reached. Say so; don't retry in a loop.                                            |
