---
name: seagull-diameter-scenario-templatize
description: Use only when the user types /seagull-diameter-scenario-templatize. Replaces the values of chosen AVPs in generated Seagull scenarios with @@NAME@@ placeholders, and writes a values file that reproduces the original scenario.
disable-model-invocation: true
argument-hint: "<scenario files or folder> [placeholder=<AVP>=<NAME> ...] [options=<file>]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-scenario-templatize

Turns Seagull client scenarios that hold fixed values into templates. In a template, the value of each AVP that the user
names is a `@@NAME@@` placeholder, and an external step fills the placeholders in before Seagull runs the scenario.
Use it on scenarios that [seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) already
wrote. To write a template straight from recorded steps, give that skill `mode=template` instead.

## Arguments

```text
/seagull-diameter-scenario-templatize <scenario files or folder> [placeholder=<AVP>=<NAME> ...] [options=<file>] [out=<folder>]
```

| Argument         | Meaning                                                                                                | Default                                       |
| ---------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------- |
| first argument   | One or more `*.client.xml` files, or the `scenario` folder of a generation (every `*.client.xml` in it) | required                                      |
| `placeholder=`   | One pair, `<AVP>=<NAME>`; repeat it for more pairs. An empty `<NAME>` removes the pair                  | the pairs in the options file                 |
| `options=`       | The options file                                                                                       | `scenario-options.ini` next to the scenarios  |
| `out=`           | The folder for the templates and values files                                                          | next to each scenario                         |

The pairs are the memory of the work. When the user names placeholders in the prompt, pass each as `--placeholder`; the
script writes them to the options file, and the next run reads them from there until the user changes them in a prompt.
When there is no options file and the user names no placeholder, ask which AVP values should become placeholders; never
pick them.

`<AVP>` is the AVP name as the scenario file spells it. A name alone matches that AVP at any depth. Use a path such as
`Multiple-Services-Credit-Control/Rating-Group` to match it inside one group only, and an index such as
`GGSN-Address[2]` for the second of several sibling AVPs of the same name. The most specific key wins. See
[the options file](../seagull-diameter-common/SKILL.md#the-options-file).

## Run

1. **Convert.**

   ```bash
   python <skill folder>/scripts/scenario_to_template.py <scenario files> [--options <file>] \
       [--placeholder <AVP>=<NAME> ...] [--out <folder>]
   ```

   For each scenario `X.client.xml` the script writes `X.client.xml.tpl` and `X.client.xml.values`. The values file
   holds one `NAME=value` line for each placeholder, with the value the scenario had. A hexadecimal value keeps its
   `0x` outside the marker (`0x@@CHARGING_ID_HEX@@`), and the values file holds the digits only.
2. **Read the output** and tell the user:
   - How many placeholders each file got.
   - Every `<NAME>: values 'a' and 'b'; used the first` line. One placeholder stands for one value, so two AVPs that
     had different values cannot share a name unless the user accepts that the template loses the difference.
   - Every `placeholder <AVP>: matched no AVP` line: a misspelled name, or an AVP that the scenarios do not carry.
3. **Show how to fill the template in.**

   ```bash
   python <skill folder>/../seagull-diameter-common/scripts/apply_placeholders.py X.client.xml.tpl \
       --out X.client.xml --values X.client.xml.values [--env] [--set NAME=VALUE ...]
   ```

   A value comes from `--set`, then from the environment when `--env` is given, then from the values file. The script
   stops and names every placeholder that has no value. With the unchanged values file the result equals the original
   scenario.
4. **Run the dry run** on the filled-in scenario, as the generate skill describes, before the user takes it to an OCS.

## Limits

- The script reads scenarios whose `<avp>` elements stand on one line each, as the generator writes them. A scenario
  that another tool wrote with several elements on one line is not converted; say so.
- Only the `<command>` elements change. A fixed `Session-Id` in a `<set-value format=...>` stays as it is; to make
  the Session-Id dynamic, generate again with `generated-session-id=true`.

## Don't

- Don't edit a template by hand to add a placeholder; add the pair and convert the ready scenario again.
- Don't convert the files to Windows line endings: Seagull's configuration parser stops on a carriage return.
- Don't commit the values files to a repository unless the user asks: they hold subscriber data.
