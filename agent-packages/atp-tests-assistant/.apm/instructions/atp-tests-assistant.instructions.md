---
description: Rules for the atp-tests-assistant skills when a request about the project's tests comes in plain language and not as a command.
applyTo: "**/*"
---

# ATP tests assistant rules

These rules hold when the user asks about the tests of the project's test repository, or about the environments of the
project's GitLab pipeline, in plain language ("show all tests", "which tests are in the folder Billing", "show the
environments for the pipeline") and an `atp-tests-*` skill applies. A command such as `/atp-tests-list` carries the
user's explicit arguments and follows its own page.

- **Use the script.** Take the list of tests or of environments from the skill's script. Don't clone the repository, don't search the
  disk for a copy of it, and don't answer from files you happen to have open.
- **Show the output as printed.** Don't reorder, shorten, or complete it.
- **The token is not yours.** Don't read `.tdm-assistant/gitlab-token`, don't print the value of `GITLAB_TOKEN`, and
  don't ask the user to paste a token into the chat. When the script reports a missing token, tell the user where it
  goes.
- **Say how you read the wording.** When "in Customers" could mean a folder at any depth or a folder directly under
  `TestScenario`, say which one you chose, as `--folder` or `--under`.
