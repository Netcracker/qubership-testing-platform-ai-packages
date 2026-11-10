---
description: Rules for the Seagull Diameter skills when a request comes in plain language and not as a command.
applyTo: "**/*"
---

# Seagull Diameter scenarios rules

These rules hold when the user asks for a Seagull Diameter task in plain language ("convert the dictionaries",
"generate scenarios from these steps") and the matching `seagull-diameter-*` skill applies. A command such as
`/seagull-diameter-dictionary-convert` already carries the user's explicit arguments and follows its own page.

## What to ask before acting

- **Seagull.** Don't start Seagull (in Docker, in WSL, or as a Seagull for Windows), a dry run, or any container unless
  the user asked for it in the request. When the request didn't mention it, finish the task and offer the run in one
  sentence. Start a run with `seagull_run.py`, which reads where Seagull runs from the settings; name the runner and its
  path in the offer (`seagull_config.py show` prints them). Ask which Seagull to use only when the script exits with 4 or
  `SEAGULL_RUNNER` is not set, and save the answer only after the user confirms it, as `seagull-diameter-common`
  describes. Never ask where Seagull runs, or for the path of `seagull.exe`, while the settings have a value.
- **Existing files.** Don't move, replace, or delete an existing output folder or file unless the user asked for it.
  Write to a new folder.
- **A real OCS.** Never run a scenario against a real OCS on your own.
- **The base protocol.** When the project's dictionaries lack the Diameter base protocol, stop and tell the user. Don't
  take the dictionary of the Seagull distribution, and don't look for another one on the disk, unless the user allowed
  it after you warned that it may be wrong in places.
- **The Seagull dictionary for generation.** The scenario generator reads one ready Seagull dictionary file. When the
  request and the setting `SEAGULL_DICTIONARY_PATH` give none, stop and tell the user to give a file or to convert the
  project's dictionaries. Don't search the disk for one, and don't convert it as a step of the generation.

## What not to choose

Don't pick the dictionaries to merge or combine, the AVPs that become placeholders or read from a data file, the flags
of commands or AVPs, or an option such as a time method. When the request doesn't give them, ask.

## What to say first

When you filled a parameter by interpreting the user's wording, say how you understood it before you run anything,
using the name of the parameter (`combine=Gy,Sy`), and let the user correct it.

## How to ask

Ask in plain text, never in a dialog, when the answer is a pick from a list that can be long or is the user's own
description: the AVPs that become placeholders, the dictionaries to merge, how a recorded run is built. A dialog holds
four options, and a list squeezed into four labels merges items that must stay apart. List the candidates one to a
row, each by its own name.
