---
name: seagull-diameter-dictionary-convert
description: Use only when the user types /seagull-diameter-dictionary-convert. Converts the project's Diameter dictionaries into Seagull dictionaries from explicit arguments; can validate the sources against XSD files and check the result in the Seagull image.
disable-model-invocation: true
argument-hint: "<dictionaries folder> [out=<folder>] [combine=yes|no|<A,B> ...] [rename=<OLD>=<NEW> ...] [command-flags=<KEY>=<N> ...] [avp-flags=<AVP>=<N> ...] [vendor-mandatory=source|yes|no] [options=<file>] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [xsd=<folder>] [validate-commands=yes|no] [seagull-base=<file>] [check=yes]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-dictionary-convert

A command frontend for [seagull-diameter-convert-dictionaries](../seagull-diameter-convert-dictionaries/SKILL.md). It
reads the user's arguments literally and runs the steps of that skill; the steps, the scripts, the rules for flags, and
the limits stay there. For an ordinary request in plain language ("convert the dictionaries in C:\work\dictionaries"),
follow that skill directly instead.

## Arguments

```text
/seagull-diameter-dictionary-convert <dictionaries folder> [out=<folder>] [combine=yes|no|<A,B> ...] [rename=<OLD>=<NEW> ...] [command-flags=<KEY>=<N> ...] [avp-flags=<AVP>=<N> ...] [vendor-mandatory=source|yes|no] [options=<file>] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [xsd=<folder>] [validate-commands=yes|no] [seagull-base=<file>] [check=yes]
```

| Argument             | Meaning                                                                                                                                                                               | Default                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| first argument       | The folder with the project's AVP dictionaries. They must define the base protocol (CER and DWR, and the AVPs the handshake uses), in any file                                        | required                                                                                   |
| `out=`               | The folder to write to. It must be new or empty                                                                                                                                       | a new folder, `Seagull-Dictionary` or `Seagull-Dictionary-2`, ... next to the input folder |
| `combine=`           | Without it, or `yes`: one file of all the dictionaries. `no`: one file for each. `A,B` (no spaces): only one file of those, in that order, `A+B.xml`; repeat for more files           | one file of all, `diameter-dictionary.xml`                                                 |
| `rename=`            | `OLD=NEW`: renames an AVP in every output, for example to match the name a scenario uses; repeat for more pairs                                                                       | none                                                                                       |
| `command-flags=`     | `<KEY>=<N>`: the flags byte, 0 to 255, of every request (`request=`), of every answer (`answer=`), or of one request or answer by its Seagull name (`CCR=192`); repeat for more pairs | requests 128, answers 0                                                                    |
| `avp-flags=`         | `<AVP>=<N>`: the flags byte of one AVP, by its name in the output (after `rename=` and the `3GPP-` prefix); repeat for more pairs                                                     | what the source gives                                                                      |
| `vendor-mandatory=`  | The M bit of every vendor AVP: `source` keeps what the source says, `yes` sets it, `no` clears it. A named `avp-flags=` pair wins                                                     | `source`                                                                                   |
| `options=`           | A `dictionary-options.ini` that an earlier run wrote, to start from. The pairs of the command win over it                                                                             | none                                                                                       |
| `keep-tgpp=`         | `yes` keeps the `TGPP-` prefix of AVP names instead of writing `3GPP-`                                                                                                                | no                                                                                         |
| `no-comments=`       | `yes` leaves the enumeration values and the group members out of the output                                                                                                           | no                                                                                         |
| `validate=`          | `yes` first checks the sources against their XSD files. Without `yes`, no schema is looked for or opened                                                                              | no                                                                                         |
| `xsd=`               | The folder of the XSD files, for `validate=yes`. Without it only the schema references inside the files are used                                                                      | `[validate] xsd` of the `options=` file, else none                                         |
| `validate-commands=` | `yes` also validates the `*Commands.xml` files, in a group of their own; the conversion does not use them. Only with `validate=yes`                                                   | `[validate] commands` of the `options=` file, else no: the Commands files are skipped      |
| `seagull-base=`      | A `base_draft08.xml` of the Seagull distribution that supplies the base protocol the folder lacks. The user's definitions win. Pass it only when the user gives it or allows it       | none: a folder without the base protocol is refused                                        |
| `check=`             | `yes` then loads each result in Seagull and runs one Credit-Control exchange with it                                                                                                  | no                                                                                         |

## Behavior

- When the only argument is `help`, `--help`, `-h`, or `?`, do nothing else. Print the usage from the "Arguments"
  section above, the syntax line and the table of arguments, and nothing else.
- Never infer a missing first argument. Ask for it.
- When an argument can't be parsed unambiguously, run nothing. This covers a word with no `=`, a value with spaces and
  no quotes, and any extra token. Reply with the corrected command and let the user send it or change it.
- Run the steps of the skill with the given values. `name=value` becomes the script option `--name value`, so
  `combine=Gy,Sy` becomes `--combine Gy,Sy`; `keep-tgpp=yes` and `no-comments=yes` become `--keep-tgpp` and
  `--no-comments`. `validate=yes`, `xsd=`, and `validate-commands=` decide step 1 of the skill, and `check=yes`
  decides step 4. Step 1 validates only the files that the result is made of, so with `combine=Gy,Sy` it validates
  Gy, Sy, and the file of the base protocol.
- The arguments are the user's instruction, so don't ask again before a step they name. Without `validate=yes`, look
  for no schema. Without `check=yes`, don't start Seagull.
- Without `combine=`, the result is one file of all the dictionaries. Never pick a list for `combine=`, a flag option,
  or a rename yourself.
- When the converter reports that the base protocol is missing, stop and offer the two ways of
  [The base protocol](../seagull-diameter-convert-dictionaries/SKILL.md#the-base-protocol). Never add `seagull-base=`
  yourself.
