---
name: seagull-diameter-templatize-scenarios
description: Use when the user asks to turn generated Seagull scenarios into templates, or to make the values of chosen AVPs placeholders in scenarios that already exist, so that the values can be filled in before each run. Replaces the value of each chosen AVP with an @@NAME@@ placeholder and writes a values file that reproduces the original scenario.
user-invocable: false
---

# Turn generated Seagull scenarios into templates

Turns Seagull client scenarios that hold fixed values into templates. In a template, the value of each AVP that the user
specifies is a `@@NAME@@` placeholder, and an external step fills the placeholders in before Seagull runs the scenario.
Use it on scenarios that [seagull-diameter-generate-scenarios](../seagull-diameter-generate-scenarios/SKILL.md) already
wrote. To write a template straight from recorded steps, generate with `mode=template` instead.

The command [/seagull-diameter-scenario-templatize](../seagull-diameter-scenario-templatize/SKILL.md) runs the same
steps from formal arguments. What this page says holds for both.

## What to take from the request

| Parameter      | How the user says it                                            | Rule                                                                                       |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| scenarios      | "templatize the scenarios in C:\work\Seagull-Scenario\scenario" | Required: `*.client.xml` files, or the `scenario` folder of a generation. Ask when missing |
| `placeholder=` | "make the subscriber number a placeholder SUBSCRIBER_ID"        | Only pairs that the user gives. See below                                                  |
| `options=`     | "start from the options of the earlier generation"              | The options file. Default: `scenario-options.ini` next to the scenarios                    |
| `out=`         | "write the templates to C:\work\templates"                      | Optional: a folder for the templates and values files. Default: next to each scenario      |

The pairs are the memory of the work. When the user specifies placeholders in the request, pass each as `--placeholder`;
the script writes them to the options file, and the next run reads them from there until the user changes them. When
there is no options file and the user specifies no placeholder, ask which AVP values should become placeholders; never
pick them.

`<AVP>` is the AVP name as the scenario file spells it. A name alone matches that AVP at any depth. Use a path such as
`Multiple-Services-Credit-Control/Rating-Group` to match it inside one group only, and an index such as
`GGSN-Address[2]` for the second of several sibling AVPs of the same name. The most specific key wins. See
[the options file](../seagull-diameter-common/SKILL.md#the-options-file).

When you had to interpret the wording to fill a pair, say how you understood it before you run anything, for example
`placeholder=Subscription-Id-Data=SUBSCRIBER_ID`, and let the user correct it. When a name could be several AVPs, ask.

## Run

1. **Look for files that the run would replace.** The script writes `X.client.xml.tpl` and `X.client.xml.values` next to
   each scenario `X.client.xml`, over earlier files of the same name. Before you run, look for them. When some exist
   and the user did not ask to replace them, don't run: tell the user which files exist, and ask for another folder
   (`--out`) or for permission to replace them.
2. **Convert.**

   ```bash
   python <skill folder>/scripts/scenario_to_template.py <scenario files> [--options <file>] \
       [--placeholder <AVP>=<NAME> ...] [--out <folder>]
   ```

   For each scenario `X.client.xml` the script writes `X.client.xml.tpl` and `X.client.xml.values`. The values file
   holds one `NAME=value` line for each placeholder, with the value the scenario had. A hexadecimal value keeps its
   `0x` outside the marker (`0x@@CHARGING_ID_HEX@@`), and the values file holds the digits only.
3. **Read the output** and tell the user:
   - Every `replaced existing ...` line: the script wrote over earlier files of the same name. Say which were
     replaced. The earlier check should have prevented it, unless the user allowed it.
   - How many placeholders each file got.
   - Every `<NAME>: values 'a' and 'b'; used the first` line. One placeholder stands for one value, so two AVPs that
     had different values cannot share a name unless the user accepts that the template loses the difference.
   - Every `placeholder <AVP>: matched no AVP` line: a misspelled name, or an AVP that the scenarios do not carry.
4. **Show how to fill the template in.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/apply_placeholders.py X.client.xml.tpl \
       --out X.client.xml --values X.client.xml.values [--env] [--set NAME=VALUE ...]
   ```

   A value comes from `--set`, then from the environment when `--env` is given, then from the values file. The script
   stops and names every placeholder that has no value. With the unchanged values file the result equals the original
   scenario.
5. **The dry run** on the filled-in scenario, as the generate skill describes, starts Seagull. Run it only when the
   user asked for it; otherwise offer it in one sentence and say that the template is not verified in Seagull yet. Where
   Seagull runs is a setting: see [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs).

## Limits

- The script reads scenarios whose `<avp>` elements stand on one line each, as the generator writes them. A scenario
  that another tool wrote with several elements on one line is not converted; say so.
- Only the `<command>` elements change. A fixed `Session-Id` in a `<set-value format=...>` stays as it is; to make
  the Session-Id dynamic, generate again with `generated-session-id=true`.

## Don't

- Don't edit a template by hand to add a placeholder; add the pair and convert the ready scenario again.
- Don't convert the files to Windows line endings: Seagull's configuration parser stops on a carriage return.
- Don't commit the values files to a repository unless the user asks: they hold subscriber data.
