---
name: seagull-diameter-dictionary-convert
description: Use only when the user types /seagull-diameter-dictionary-convert. Converts the project's Diameter dictionaries into Seagull dictionaries, each merged with the base protocol, and can validate the sources against their XSD files and check the result in the Seagull image.
disable-model-invocation: true
argument-hint: "<dictionaries folder> [out=<folder>] [combine=<A,B> ...] [rename=<OLD>=<NEW> ...] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [check=yes]"
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# /seagull-diameter-dictionary-convert

Seagull reads AVP and command definitions from a dictionary in its own XML format, and the project keeps its
dictionaries in another one. This skill converts a folder of project dictionaries into Seagull dictionaries. It writes
one file for each AVP dictionary, merged with `DiameterBaseProtocol.xml`, one more for each combination the user asks
for, and a report of everything that looked inconsistent.

[seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) already converts and merges the
dictionaries it needs. Use this skill when the user wants the converted dictionaries themselves: to run a hand-written
scenario with `-dico`, to read the conversion report before generating, or to check a dictionary in the image.

## Arguments

```text
/seagull-diameter-dictionary-convert <dictionaries folder> [out=<folder>] [combine=<A,B> ...] [rename=<OLD>=<NEW> ...] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [check=yes]
```

| Argument        | Meaning                                                                                                                                                                 | Default                                                                                    |
| --------------- |-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| first argument  | The folder with the project's AVP dictionaries. `DiameterBaseProtocol.xml` must be among them                                                                           | required                                                                                   |
| `out=`          | The folder to write to. It must be new or empty                                                                                                                         | a new folder, `Seagull-Dictionary` or `Seagull-Dictionary-2`, ... next to the input folder |
| `combine=`      | File names without `.xml`, separated by commas and without spaces; repeat for more combinations. Writes one merged file for each, named after its parts joined with `+` | none                                                                                       |
| `rename=`       | `OLD=NEW`: renames an AVP in every output, for example to match the name a scenario uses; repeat for more pairs                                                         | none                                                                                       |
| `keep-tgpp=`    | `yes` keeps the `TGPP-` prefix of AVP names instead of writing `3GPP-`                                                                                                  | no                                                                                         |
| `no-comments=`  | `yes` leaves the enumeration values and the group members out of the output                                                                                             | no                                                                                         |
| `validate=`     | `yes` first checks the sources against the XSD files in the input folder's `xsd` subfolder                                                                              | no                                                                                         |
| `check=`        | `yes` then loads each result in the Seagull image and runs one Credit-Control exchange with it                                                                          | no                                                                                         |

Seagull loads one dictionary for each run, so a run that sends messages of several applications needs them in one file.
When the user names the dictionaries they use together, pass them in `combine=`; never pick the combination yourself.

## Run

1. **Validate (only when `validate=yes`).** Needs Java 11 or later and the files `xsd/diameter-dictionary.xsd` and
   `xsd/diameter-command.xsd` in the input folder.

   ```bash
   sh <skill folder>/scripts/validate.sh <dictionaries folder>
   ```

   It prints `valid`, or the number of errors for a file and each distinct message once. An invalid file does not stop
   the conversion: tell the user which files failed and what the messages say, then continue. The validator checks the
   structure that the XSD files describe, not that a code or a flag is right.
2. **Convert.**

   ```bash
   python <skill folder>/scripts/convert_dictionaries.py <dictionaries folder> (--out <folder> | --out-auto) \
       [--combine A,B ...] [--rename OLD=NEW ...] [--keep-tgpp] [--no-comments]
   ```

   Pass `--out-auto` when the user gave no `out=`. A folder that is not empty is refused (`the output folder is not
   empty: ...`) and nothing is written; tell the user what the message says and ask for another folder. Never delete or
   empty a folder to get past the refusal. Exit status 2 means `DiameterBaseProtocol.xml` is missing or a `combine=`
   name is not a file of the input folder.
3. **Read the report** (the script prints it and writes `conversion-report.txt`) and tell the user:
   - How many AVPs and command pairs each file has.
   - Every `WARNING` line. The usual ones are an AVP name that the sources define twice with another vendor or code
     (the second is written as `<name>-v<vendor>c<code>`, so a scenario that uses the plain name gets the first
     definition), and an application command that replaced a base command of the same abbreviation. The script
     reports what looks inconsistent and corrects nothing: the dictionary's owners decide which definition is intended.
   - That the multiplicities, the enumeration values, and the group members are dropped or kept only as comments, so
     Seagull cannot check that a message is complete.
4. **Check in the image (only when `check=yes`).** Needs Docker and a Seagull image tagged `seagull:local`. On Windows
   run the script through `wsl`.

   ```bash
   sh <skill folder>/scripts/check-converted.sh <output folder> [IMAGE]
   ```

   For each result that defines `CCR` the script runs a stub OCS and a client with invented values and prints
   `<name>: successful calls: 1, failed calls: 0`. A dictionary without `CCR` is `skipped`. A line that says anything
   else, with the `E` error lines Seagull printed beside it, means Seagull could not load the dictionary or could not
   encode a message with it. The check shows that Seagull loads the dictionary and finds the AVP names of the
   scenario in it. It does not show that a real OCS accepts the messages.
5. **Say how to use the result.** Pass one file to Seagull with `-dico`:

   ```bash
   seagull -conf <config> -dico <output folder>/Gy.xml -scen <scenario> -log <log>
   ```

   To compare a converted dictionary with one of the dictionaries that ship with Seagull, by AVP name:

   ```bash
   python <skill folder>/scripts/compare_with_seagull.py <converted>.xml <seagull dictionary>.xml
   ```

## Limits

- The conversion is our reading of the project format, not a specification of it. Flags, the type mapping, and the
  renamed names were checked by loading the result in Seagull, never against a real OCS.
- Seagull 1.8.3 does not add two `-dico` files together: it stops with `protocol with name [diameter-v1] already
  defined`. A combination has to be one file.
- The `*Commands.xml` files are not merged and not converted. When one sits next to its `<Name>.xml`, the script only
  warns about a command code that the sources do not define.
- The check scenario sends `Gy` messages, so it passes only for a dictionary that defines the Credit-Control AVPs it
  uses. A dictionary that lacks them fails the check without being wrong for another protocol.

## Don't

- Don't edit a converted dictionary by hand. It starts with a comment that says so; change the source or the options and
  convert again.
- Don't commit the project's dictionaries to a repository unless the user confirms that they may be distributed:
  files can carry a notice that restricts it.
- Don't convert the output to Windows line endings.
