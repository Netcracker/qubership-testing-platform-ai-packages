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
  sentence. When the user asks and the setting `SEAGULL_RUNNER` is not set, ask which Seagull to use, and save the
  answer only after the user confirms it, as `seagull-diameter-common` describes.
- **Existing files.** Don't move, replace, or delete an existing output folder or file unless the user asked for it.
  Write to a new folder.
- **A real OCS.** Never run a scenario against a real OCS on your own.
- **The base protocol.** When the project's dictionaries lack the Diameter base protocol, stop and tell the user. Don't
  take the dictionary of the Seagull distribution, and don't look for another one on the disk, unless the user allowed
  it after you warned that it may be wrong in places.

## What not to choose

Don't pick the dictionaries to merge or combine, the AVPs that become placeholders or read from a data file, the flags
of commands or AVPs, or an option such as a time method. When the request doesn't give them, ask.

## What to say first

When you filled a parameter by interpreting the user's wording, say how you understood it before you run anything,
using the name of the parameter (`combine=Gy,Sy`), and let the user correct it.
