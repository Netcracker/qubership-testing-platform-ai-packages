---
name: atp-local-folder-set
description: Use when the user asks to set, show, or check the folder on their computer that holds the tests for a local run, for example "the local tests are in D:\work\tests", "set the local tests folder to D:\work\tests", or "check my local tests folder", or the same in another language. Checks that the folder has the test files and the environment configurations, and writes LOCAL_ROOT_FOLDER in the config file of the package. It does not clone or update a repository, and it runs no test.
user-invocable: false
---

# Set the folder of the local tests

A local run takes the tests and the environment configurations from a folder on the user's computer, a copy of the
test repository with the same layout. `LOCAL_ROOT_FOLDER` of `.atp-assistant/config.json` names it. A script checks
the folder and writes the value. The agent does not edit the config itself.

## Run

```bash
python <skill folder>/scripts/set_local_folder.py [--path FOLDER]
```

Run the script from the project folder, so that it finds `.atp-assistant/config.json`. If `python` isn't found, try
`python3` or `py -3`. Quote each value for the shell.

- With a folder in the request, pass it as `--path`, as the user wrote it. The request is the confirmation: don't ask
  again.
- To show or check the current folder, run the script without `--path`.
- When the user asks to set the folder and names none, ask for it. Don't search the disk for one, and don't take one
  from a file or a log.

Print the output of the script as it is. An error comes as one JSON object on stderr with exit status 1; report its
`message` and the remedy it names.

## What the folder needs

| In the folder                                                      | Setting that moves it      |
| ------------------------------------------------------------------ | -------------------------- |
| `*.ts` files, at any depth, in `TestGeneration/tests/TestScenario` | `TESTS_FOLDER`             |
| `*.json` files in `TestGeneration/environment-configuration`       | `ENV_CONFIGURATION_FOLDER` |

The script reads the names of the files only. Don't open an environment configuration: it holds passwords.

## Result and errors

| Result                      | Say                                                                                                |
| --------------------------- | -------------------------------------------------------------------------------------------------- |
| The folder and its contents | Show it as printed.                                                                                |
| `local_root_invalid`        | Show `problems` and say that the config was not changed. Don't create folders or files to pass.    |
| `local_root_missing`        | No folder is set. Ask for it.                                                                      |
| `config_missing`            | There is no `.atp-assistant/config.json`. Offer to create it with atp-config-manage.               |
| `config_unreadable`         | The message names the file and the problem. Don't repair the file unless the user asks.            |
| `config_unwritable`         | The file could not be written. Report the message.                                                 |
| `invalid_value`             | `TESTS_FOLDER` or `ENV_CONFIGURATION_FOLDER` of the config is not a folder path. Show the message. |
