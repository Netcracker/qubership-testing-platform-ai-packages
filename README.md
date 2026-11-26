# qubership-testing-platform-ai-packages

APM packages with skills and instructions for AI agents that work on the Qubership Testing Platform. Each package lives
in its own folder under `agent-packages/` and installs on its own.

## Packages

| Package                                                                               | Purpose                                                               |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| [atp-tests-assistant](agent-packages/atp-tests-assistant/README.md)                   | Lists and runs the project's tests in its GitLab pipeline             |
| [atp-tests-assistant-opencode](agent-packages/atp-tests-assistant-opencode/README.md) | The commands of atp-tests-assistant for OpenCode                      |
| [seagull-diameter-scenarios](agent-packages/seagull-diameter-scenarios/README.md)     | Turns recorded Diameter requests and responses into Seagull scenarios |

## Install a package

Run `apm install` in the folder in which you start your agent:

```bash
apm install --target claude Netcracker/qubership-testing-platform-ai-packages/agent-packages/<package>#main
```

The steps for each package are in its `README` and user guide.
