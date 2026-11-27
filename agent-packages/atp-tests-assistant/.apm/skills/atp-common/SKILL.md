---
name: atp-common
description: Shared script code of the atp-tests-assistant skills: the config, the token, and the GitLab requests. Not a task; the agent never invokes it.
user-invocable: false
---

# Shared code of the atp-tests-assistant skills

The scripts of the other skills of this package import `scripts/atp_common.py`. It has no task of its own, so
the agent doesn't run it.

## What it reads

Every file is optional, and a script works with command-line options alone. The exception is
atp-environment-set, which needs the config file to write, and atp-tests-run, which needs it to start a pipeline.

| Source                              | Holds                                                                                                                                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `.atp-assistant/config.json`        | Found from the working directory up. `GITLAB_URL`, `GITLAB_PROJECT_ID`, `GITLAB_REF`, `GITLAB_TOKEN_ENV`, and the object `variables` with the variables of the pipeline. |
| Environment variable `GITLAB_TOKEN` | The GitLab token. `GITLAB_TOKEN_ENV` names another variable.                                                                                                             |
| `.atp-assistant/gitlab-token`       | The token on the first line, when the variable is empty.                                                                                                                 |

The package writes the config only when the user asks: `PIPELINE_RUNTIME_CONFIG` through atp-environment-set, and
other values through atp-config-manage, which also creates a missing file. The keys are described in the `README` of
the package, under "Settings". atp-tests-run adds the keys of its search for business identifiers and of the links to them.
`TESTS_FOLDER` and `ENV_CONFIGURATION_FOLDER` name folders of the test repository; `read_folder` gives their
defaults. `LOCAL_ROOT_FOLDER` names the local copy of the test repository; `local_root` and `read_local_root`
find and check it.

## Output

A script prints its result on stdout. An error is one JSON object on stderr,
`{"ok": false, "error": "<code>", "message": "<text>"}`, with exit status 1. The script of atp-tests-run prints the
error on stdout, where its JSON result goes, because its stderr carries progress lines. The token is never printed.
