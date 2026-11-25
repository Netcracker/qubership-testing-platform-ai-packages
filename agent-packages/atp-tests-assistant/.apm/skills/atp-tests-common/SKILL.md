---
name: atp-tests-common
description: Shared script code of the atp-tests-assistant skills: the config, the token, and the GitLab requests. Not a task; the agent never invokes it.
user-invocable: false
---

# Shared code of the atp-tests-assistant skills

The scripts of the other skills of this package import `scripts/atp_tests_common.py`. It has no task of its own, so
the agent doesn't run it.

## What it reads

Every file is optional, and a script works with command-line options alone.

| Source                                                | Holds                                                                                                                                           |
| ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `.tdm-assistant/config.json`                          | Found from the working directory up. Keys used: `GENERATE_VARIABLES_FILE`, `GITLAB_URL`, `GITLAB_PROJECT_ID`, `GITLAB_REF`, `GITLAB_TOKEN_ENV`. |
| The variables file named by `GENERATE_VARIABLES_FILE` | The `variables` object, with `ATP_TESTS_GIT_REPO_URL` and `ATP_TESTS_GIT_REPO_BRANCH`.                                                          |
| Environment variable `GITLAB_TOKEN`                   | The GitLab token. `GITLAB_TOKEN_ENV` names another variable.                                                                                    |
| `.tdm-assistant/gitlab-token`                         | The token on the first line, when the variable is empty.                                                                                        |

These files belong to the tdm-test-data-assistant package, which writes them. This package only reads them, so a
change of a key there needs the same change here.

## Output

A script prints its result on stdout. An error is one JSON object on stderr,
`{"ok": false, "error": "<code>", "message": "<text>"}`, with exit status 1. The token is never printed.
