---
name: seagull-diameter-scenario-generate
description: Use only when the user types /seagull-diameter-scenario-generate. Generates Seagull client scenarios, a merged Seagull dictionary, configuration, and a stub OCS from a folder of recorded Diameter requests and responses, and runs them in a dry run.
disable-model-invocation: true
argument-hint: "<steps folder> dictionaries=<folder> merge=<A,B,C> [out=<folder>] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-generate

Turns the recorded Diameter requests of a run into [Seagull](https://gull.sourceforge.net/) scenarios that send them
again,
check the answers, and give up when an answer is late. The input is the folder that
[seagull-diameter-steps-extract](../seagull-diameter-steps-extract/SKILL.md) writes, in the format of
[seagull-diameter-common](../seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps). A script does the work;
the agent runs it, reads its report, and tells the user what to review.

## Arguments

```text
/seagull-diameter-scenario-generate <steps folder> dictionaries=<folder> merge=<A,B,C> [out=<folder>] [timeout=<ms>] [dest=<host:port>] [host-ip=<ip>]
```

| Argument        | Meaning                                                                                                         | Default            |
|-----------------|-----------------------------------------------------------------------------------------------------------------|--------------------|
| `<steps folder>`| The folder of recorded steps                                                                                    | required           |
| `dictionaries=` | The folder of the project's AVP dictionaries. It must hold `DiameterBaseProtocol.xml`                            | required           |
| `merge=`        | The AVP dictionaries to merge into the Seagull dictionary, names without `.xml`, in order of precedence         | required           |
| `out=`          | The folder to write to                                                                                          | `Seagull-Scenario` next to the steps folder |
| `timeout=`      | How long Seagull waits for each answer, in milliseconds                                                         | 5000               |
| `dest=`         | Address and port of the OCS, written into `config/conf.client.xml`                                              | `127.0.0.1:3868`   |
| `host-ip=`      | The IP address that the CER announces as the client's own                                                       | `192.0.2.10`       |

When `dictionaries=` or `merge=` is missing, list the `.xml` files of the dictionary folder and ask the user which to
merge. Never guess. Start with the dictionary of the interface the messages use, and add another only when the
generator reports `AVP <name> is in none of the project dictionaries that were given`. For an AVP name defined in
several
of the merged dictionaries, the first one in `merge=` keeps the name.

## Prerequisites

- Python 3.9 or later, started as `python`, `python3`, or `py -3`.
- For the dry run: Docker, and the Seagull image of this project (`seagull:local`, built from its `Dockerfile`). On
  Windows without Docker in PowerShell, run the shell scripts through `wsl`.

## Run

1. **Check the steps folder.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/check_steps.py <steps folder>
   ```

   Stop at a `PROBLEM` line. A line without it is a repair: a comment or a broken closing tag in a recorded message. The
   generator makes the same repairs, so say which steps had them and carry on.
2. **Generate.**

   ```bash
   python <skill folder>/scripts/generate_scenarios.py --steps <steps folder> --dictionaries-dir <dictionaries folder> \
       --dictionaries <A,B,C> --out <out folder> [--timeout-ms <ms>] [--dest <host:port>] [--host-ip <ip>]
   ```

   Options that the arguments table does not list: `--check-avps <A,B,...>` sets the AVPs that the scenario compares in
   each answer (default `Result-Code,Session-Id,Auth-Application-Id,CC-Request-Type,CC-Request-Number`; an AVP that the
   recorded answer lacks is skipped and named in the report), `--rename OLD=NEW` renames an AVP for the converter, and
   `--seagull-dictionary <file>` uses a dictionary that is already converted.
3. **Read the report** that the script prints and saves as `generation-report.txt`, and tell the user:
   - The scenarios that were written, one for each Diameter session.
   - Every AVP name with several definitions in the dictionaries (`<name>: definitions (vendor, code) ...; used ...`).
     The
     generator picks the one with the vendor of the enclosing group, else the first. The user knows the real AVP; ask
     for a
     confirmation, and rerun with another `merge=` order if the choice is wrong.
   - The repairs of the recorded messages, and the checks that were skipped.
   - The conversion warnings in `dictionary/conversion-report.txt`: names defined twice, a command replaced by the
     application's. They matter only when a scenario uses the name.
4. **Dry run.**

   ```bash
   sh <skill folder>/scripts/dry-run.sh <out folder> [<image>]
   ```

   It starts a stub OCS that answers with the recorded answers, runs each scenario against it, and prints one line for
   each: `successful calls: 1, failed calls: 0`. A scenario that does not end so is a defect of the generation or of the
   dictionary; read the `|E|` line that the script prints. Never report the scenarios as working without this run.
5. **Say how to run against the OCS**: put the address in `dest` of `config/conf.client.xml`, replace the placeholder
   address of the CER with `host-ip=`, and run one scenario:

   ```bash
   seagull -conf <out>/config/conf.client.xml -dico <out>/dictionary/diameter-dictionary.xml \
       -scen <out>/scenario/<name>.client.xml -log <logs>/<name> -llevel A -bg
   ```

   Without a terminal `-bg` is needed; wait until the log ends with `STOP  log`.

## What the output holds

| Path                              | Content                                                                                          |
|-----------------------------------|--------------------------------------------------------------------------------------------------|
| `scenario/NN-<kind>-steps-<...>.client.xml` | The client scenario of one Diameter session: CER/CEA, then each request and its checks   |
| `scenario/*.stub-server.xml`      | A stub OCS for the dry run: answers with the AVPs of the recorded answers                        |
| `config/conf.client.xml`          | The client configuration with `dest` and the response timeout                                    |
| `config/conf.dry-run.client.xml`  | The same, pointing at the stub OCS                                                               |
| `config/conf.stub-server.xml`     | The stub OCS configuration                                                                       |
| `dictionary/diameter-dictionary.xml` | The merged Seagull dictionary, used by the scenarios and the stub                              |
| `generation-report.txt`           | What the generator did and what to review                                                        |

## What the scenarios do

- One scenario for each Diameter session. Seagull ties an answer to its call by the `Session-Id`, and it refuses an
  answer
  with a `Session-Id` that the call has not used. So steps with the same `Session-Id` are one scenario, and a new
  `Session-Id` starts a new one. Do not join sessions into one scenario.
- Each request carries the recorded AVPs in the recorded order with fixed values. Only the Hop-by-Hop and End-to-End
  identifiers come from counters. The attributes of the recorded root element are not sent, and commented-out AVPs are
  left out.
- A time such as `2026-10-27 14:00:52 +0000 UTC` becomes 4 bytes of NTP time in hex, and an IP address in an AVP of type
  Address becomes the address family followed by the address bytes. The time is a fixed value for now; a later change
  makes it come from the run configuration.
- `TGPP-` at the start of an AVP name is written `3GPP-`, as the converted dictionary names it; the bytes are the same.
- After each answer the scenario checks the AVPs of `--check-avps` against the recorded answer, and any difference
  fails the call with `check failed in [CCA] command, value of avp [Result-Code]. Expected [2001] but got [5012]`.
- The response timeout is `call-timeout-ms` in the configuration. It applies to the wait for each answer, not to the
  whole
  call. The `timeout` attribute of `<receive>` is not read by Seagull 1.8.3.

## Limits

- The check compares top-level AVPs only. An AVP inside a group that has the name of a top-level one, such as the
  `Result-Code` of a Multiple-Services-Credit-Control, cannot be told apart by name.
- The CER carries a placeholder `Host-IP-Address`, and the scenarios do not answer a Device-Watchdog request from the
  OCS.
- A stub OCS that runs the Seagull decoder may log `Current Size: ... is greater than expecting one: ...` for a vendor
  AVP
  whose code is also a base AVP code. It is a log line of the receiver; the bytes that the client sends are correct.

## Don't

- Don't edit a generated scenario by hand; change the input or the options and generate again.
- Don't convert the generated files to Windows line endings. Seagull's configuration parser stops with
  `lexical error : unknown token` on a carriage return, so a configuration file with CRLF does not load.
- Don't commit the output or the recorded messages to a repository unless the user asks: they hold subscriber data.
- Don't pick between several definitions of an AVP on your own; show the user the line from the report.
