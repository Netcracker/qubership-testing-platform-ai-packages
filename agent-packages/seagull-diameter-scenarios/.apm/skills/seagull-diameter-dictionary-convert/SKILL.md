---
name: seagull-diameter-dictionary-convert
description: Use only when the user types /seagull-diameter-dictionary-convert. Converts the project's Diameter dictionaries into Seagull dictionaries, each merged with the base protocol, and can validate the sources against their XSD files and check the result in the Seagull image.
disable-model-invocation: true
argument-hint: "<dictionaries folder> [out=<folder>] [combine=<A,B> ...] [rename=<OLD>=<NEW> ...] [command-flags=<KEY>=<N> ...] [avp-flags=<AVP>=<N> ...] [vendor-mandatory=source|yes|no] [options=<file>] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [xsd=<folder>] [check=yes]"
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
dictionaries it needs. Use this skill when the user wants the converted dictionaries themselves: to run a handwritten
scenario with `-dico`, to read the conversion report before generating, or to check a dictionary in the image.

## Arguments

```text
/seagull-diameter-dictionary-convert <dictionaries folder> [out=<folder>] [combine=<A,B> ...] [rename=<OLD>=<NEW> ...] [command-flags=<KEY>=<N> ...] [avp-flags=<AVP>=<N> ...] [vendor-mandatory=source|yes|no] [options=<file>] [keep-tgpp=yes] [no-comments=yes] [validate=yes] [xsd=<folder>] [check=yes]
```

| Argument            | Meaning                                                                                                                                                                               | Default                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| first argument      | The folder with the project's AVP dictionaries. `DiameterBaseProtocol.xml` must be among them                                                                                         | required                                                                                   |
| `out=`              | The folder to write to. It must be new or empty                                                                                                                                       | a new folder, `Seagull-Dictionary` or `Seagull-Dictionary-2`, ... next to the input folder |
| `combine=`          | Filenames without `.xml`, separated by commas and without spaces; repeat for more combinations. Writes one merged file for each, named after its parts joined with `+`                | none                                                                                       |
| `rename=`           | `OLD=NEW`: renames an AVP in every output, for example to match the name a scenario uses; repeat for more pairs                                                                       | none                                                                                       |
| `command-flags=`    | `<KEY>=<N>`: the flags byte, 0 to 255, of every request (`request=`), of every answer (`answer=`), or of one request or answer by its Seagull name (`CCR=192`); repeat for more pairs | requests 128, answers 0                                                                    |
| `avp-flags=`        | `<AVP>=<N>`: the flags byte of one AVP, by its name in the output (after `rename=` and the `3GPP-` prefix); repeat for more pairs                                                     | what the source gives                                                                      |
| `vendor-mandatory=` | The M bit of every vendor AVP: `source` keeps what the source says, `yes` sets it, `no` clears it. A named `avp-flags=` pair wins                                                     | `source`                                                                                   |
| `options=`          | A `dictionary-options.ini` that an earlier run wrote, to start from. The pairs of the prompt win over it                                                                              | none                                                                                       |
| `keep-tgpp=`        | `yes` keeps the `TGPP-` prefix of AVP names instead of writing `3GPP-`                                                                                                                | no                                                                                         |
| `no-comments=`      | `yes` leaves the enumeration values and the group members out of the output                                                                                                           | no                                                                                         |
| `validate=`         | `yes` first checks the sources against their XSD files. Without `yes`, no schema is looked for or opened                                                                              | no                                                                                         |
| `xsd=`              | The folder of the XSD files, for `validate=yes`. Without it only the schema references inside the files are used                                                                      | `[validate] xsd` of the `options=` file, else none                                         |
| `check=`            | `yes` then loads each result in the Seagull image and runs one Credit-Control exchange with it                                                                                        | no                                                                                         |

Seagull loads one dictionary for each run, so a run that sends messages of several applications needs them in one file.
When the user specifies the dictionaries they use together, pass them in `combine=`; never pick the combination
yourself.

## Run

1. **Validate (only when `validate=yes`).** Needs Java 11 or later. With any other value, do not look for schema
   files at all. Never search the disk for them; the validator takes the schema of each file only from the places below.

   ```bash
   sh <skill folder>/scripts/validate.sh [--xsd-dir <folder>] <dictionaries folder>
   ```

   Pass `--xsd-dir` when the user gave `xsd=`, or the `options=` file has `[validate] xsd`. The validator chooses the
   schema of each file in this order:
   1. The reference in the file itself (`xsi:noNamespaceSchemaLocation` or `xsi:schemaLocation`), resolved against the
      folder of the file.
   2. If that file does not exist and `--xsd-dir` is given, the file of the same name in that folder, when it declares
      the root element of the dictionary.
   3. If `--xsd-dir` is given and the file has no usable reference, the one `.xsd` file there that declares the root
      element of the dictionary as a global element. The filename does not matter.

   The exit status tells what happened:
   - 0: every file is valid. Print the result, which names the schema used for each file.
   - 1: some file is invalid. Tell the user which files failed and what the messages say, then continue with the
     conversion. The validator checks the structure that the XSD files describe, not that a code or a flag is right.
   - 3: for some files no schema was found, and nothing was validated. The output lists the distinct problems, each
     with the number of files it affects. Stop, show them to the user, and ask two questions in one message: where the
     XSD files are, and whether to keep the answer in `dictionary-options.ini` (the default is no). Run the validator
     again with `--xsd-dir <answer>`. If the user cannot say, skip the validation, say so, and continue with the
     conversion. When the user wants the answer kept, add `--xsd-dir <answer>` to the conversion command in step 2.
   - 2: wrong arguments or a folder without `.xml` files.

   `--plan` prints the schema chosen for each file without validating.
2. **Convert.**

   ```bash
   python <skill folder>/scripts/convert_dictionaries.py <dictionaries folder> (--out <folder> | --out-auto) \
       [--combine A,B ...] [--rename OLD=NEW ...] [--command-flags KEY=N ...] [--avp-flags AVP=N ...] \
       [--vendor-mandatory source|yes|no] [--options FILE] [--xsd-dir FOLDER] [--keep-tgpp] [--no-comments]
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
   - Every `NOTE` line: a flags byte that differs from the default. It names the command or AVP and both values, or
     gives the number of vendor AVPs whose M bit `vendor-mandatory=` changed. A name in `command-flags=` or
     `avp-flags=` that matches nothing is a `WARNING`.
   - That the multiplicities, the enumeration values, and the group members are dropped or kept only as comments, so
     Seagull cannot check that a message is complete.
   - That the options in effect are in `dictionary-options.ini` in the output folder. Pass it as `options=` to repeat
     the run.
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

## Flags

The project dictionaries give the V, M, and P bits of an AVP, and no flags for a command. Without options the
converter writes 128 (R) for every request and 0 for every answer, and each AVP gets the bits that its source gives.
That is the converter's own choice, not a fact about the project. RFC 4006 describes CCR and CCA with the P bit, which
is 192 and 64, and another converter may differ from this one on the M bit of vendor AVPs.

Change the flags only when the user asks, or when they say which value their OCS or their reference dictionary has.
Never pick `command-flags=`, `avp-flags=`, or `vendor-mandatory=` yourself. Flags that contradict the V bit of an AVP
(a vendor AVP without 128, or an AVP of the base protocol with it) are refused with an error.

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
