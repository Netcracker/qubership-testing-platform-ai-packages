---
name: seagull-diameter-convert-dictionaries
description: Use when the user asks to convert the project's Diameter dictionaries into Seagull dictionaries, to merge several of them into one file for Seagull, or to check that Seagull loads a converted dictionary. Reads a folder of project dictionaries, writes a new folder of Seagull dictionaries with a conversion report, and validates the sources against XSD files only when asked.
user-invocable: false
---

# Convert the project's Diameter dictionaries for Seagull

Seagull reads AVP and command definitions from a dictionary in its own XML format, and the project keeps its
dictionaries in another one. This skill converts a folder of project dictionaries into a Seagull dictionary. Seagull
takes one dictionary file for each run, so the result is one file, `diameter-dictionary.xml`, made of all the AVP
dictionaries of the folder and its base protocol, plus a report of everything that looked inconsistent. When the user
asks, it writes one file for each dictionary, or one file of only some of them.

[seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) already converts and merges the
dictionaries it needs. Use this skill when the user wants the converted dictionaries themselves: to run a handwritten
scenario with `-dico`, to read the conversion report before generating, or to check a dictionary in the image.

The command [/seagull-diameter-dictionary-convert](../seagull-diameter-dictionary-convert/SKILL.md) runs the same steps
with formal arguments. What this page says about a parameter holds for both.

## What to take from the request

Take each parameter from the user's words, and apply the rule in the last column.

| Parameter           | How the user says it                                   | Rule                                                                                      |
| ------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| dictionaries folder | "convert the dictionaries in C:\work\dictionaries"     | Required. Ask for it when missing. Never look for the folder yourself                     |
| `out=`              | "write them to C:\work\out"                            | Optional. The folder must be new or empty. Without it, use `--out-auto`                   |
| `combine=`          | "one file for each", "only Gy and Sy together"         | Default: one file of all. `no`: one for each. A list: only if the user specifies one      |
| `rename=`           | "call the AVP Foo Bar instead"                         | Only pairs that the user gives                                                            |
| flags               | "CCR flags 192", "set the M bit on vendor AVPs"        | Only values that the user gives. See "Flags"                                              |
| `options=`          | "start from the options of the earlier run"            | The `dictionary-options.ini` of that run                                                  |
| `validate=yes`      | "validate the dictionaries against their schemas"      | Only when the user asks for validation. Otherwise do not look for or open any schema file |
| `xsd=`              | "the schemas are in C:\work\xsd"                       | Only with validation                                                                      |
| `check=yes`         | "check that Seagull loads them", "try them in Seagull" | Starts Seagull. Run it only when the user asked; otherwise offer it at the end            |

When you had to interpret the wording to fill a parameter, say how you understood it before you run anything, for
example `combine=Gy,Sy`, and let the user correct it. When the folder or the list of dictionaries is unclear, ask.

Seagull loads one dictionary for each run, so without `combine=` all the AVP dictionaries of the folder go into one
file, in the alphabetical order of their filenames. For an AVP name that several of them define, the first one keeps the
name. When the user specifies the dictionaries to use, or an order, pass them in `combine=`; the result is then only that
file. Pass `combine=no` only when the user asks for one file for each dictionary. A folder may hold a dictionary that
already merges the others, for example `CombinedDictionary.xml`. Do not drop it on your own; mention it, and let the
user decide whether to list the dictionaries.

## Run

1. **Validate (only when the user asked for validation).** Needs Java 11 or later. In every other case, do not look for
   schema files at all. Never search the disk for them; the validator takes the schema of each file only from the
   places below.

   ```bash
   sh <skill folder>/scripts/validate.sh [--xsd-dir <folder>] <dictionaries folder>
   ```

   Pass `--xsd-dir` when the user gave the schema folder, or the options file has `[validate] xsd`. The validator
   chooses the schema of each file in this order:
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
       [--combine yes|no|A,B ...] [--rename OLD=NEW ...] [--command-flags KEY=N ...] [--avp-flags AVP=N ...] \
       [--vendor-mandatory source|yes|no] [--options FILE] [--xsd-dir FOLDER] [--keep-tgpp] [--no-comments] \
       [--seagull-base FILE]
   ```

   Pass `--out-auto` when the user gave no output folder. A folder that is not empty is refused (`the output folder is
   not empty: ...`) and nothing is written; tell the user what the message says and ask for another folder. Never
   delete or empty a folder to get past the refusal. Exit status 2 means that a combination names a file that is not in
   the input folder, or that the folder lacks the base protocol; see "The base protocol".
3. **Read the report** (the script prints it and writes `conversion-report.txt`) and tell the user:
   - How many AVPs and command pairs each file has.
   - Every `WARNING` line. The usual ones are an AVP name that the sources define twice with another vendor or code
     (both stay in the file under the name, and Seagull sends the first one wherever a scenario uses the name, so
     a message that needs the other cannot be sent), and an application command that replaced a base command of the same abbreviation. The script
     reports what looks inconsistent and corrects nothing: the dictionary's owners decide which definition is intended.
   - Every `NOTE` line: a flags byte that differs from the default. It names the command or AVP and both values, or
     gives the number of vendor AVPs whose M bit the policy changed. A name in the flag options that matches nothing is
     a `WARNING`.
   - That the multiplicities, the enumeration values, and the group members are dropped or kept only as comments, so
     Seagull cannot check that a message is complete.
   - That the options in effect are in `dictionary-options.ini` in the output folder. Pass it as `options=` to repeat
     the run.
4. **Check in Seagull.** Needs a Seagull 1.8.3: an image in Docker (by default tagged `seagull:local`; on Windows run
   the script through `wsl`) or a Seagull for Windows. Where it runs is a setting: read it, and ask when it is not set,
   as [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs) describes. Run the check only when
   the user asked for it, either in the request or in the answer to your offer. When the request did not mention it,
   end your reply by offering the check in one sentence and do not start Seagull.

   ```bash
   sh <skill folder>/scripts/check-converted.sh <output folder> [IMAGE]
   python <skill folder>/../seagull-diameter-common/scripts/seagull_windows_run.py check-converted <output folder> --seagull-exe <path>
   ```

   The first line is for `docker`, the second for `windows`.

   For each result that defines `CCR` the script runs a stub OCS and a client with invented values and prints
   `<name>: successful calls: 1, failed calls: 0`. A dictionary without `CCR` is `skipped`. A line that says anything
   else, with the `E` error lines Seagull printed beside it, means Seagull could not load the dictionary or could not
   encode a message with it. The check shows that Seagull loads the dictionary and finds the AVP names of the
   scenario in it. It does not show that a real OCS accepts the messages.
5. **Say how to use the result.** Pass one file to Seagull with `-dico`:

   ```bash
   seagull -conf <config> -dico <output folder>/diameter-dictionary.xml -scen <scenario> -log <log>
   ```

   To compare a converted dictionary with one of the dictionaries that ship with Seagull, by AVP name:

   ```bash
   python <skill folder>/scripts/compare_with_seagull.py <converted>.xml <seagull dictionary>.xml
   ```

## The base protocol

Seagull needs the commands `CER`/`CEA` (code 257) and `DWR`/`DWA` (code 280) and the AVPs 257, 258, 263, 264, 266,
268, 269, and 296 in the dictionary it loads. The converter looks for them by code in every `.xml` dictionary of the
folder, whatever the files are called. Nothing else supplies them: the project's service does not have a built-in base
protocol for Seagull, and Seagull reads only the dictionary file it is given.

When the folder lacks any of them, the converter writes nothing and exits with status 2; the message lists the missing
codes. Then stop, show the message to the user, and offer two ways, without choosing one yourself:

1. The user puts the files that define the base protocol into the folder, and you run the conversion again.
2. The user allows the dictionary that ships with Seagull (`base_draft08.xml`). Warn that the dictionaries of the
   Seagull distribution can be wrong in places and have not been checked against the project's OCS. Where the user's
   dictionaries define the same name or code, the user's definition wins and nothing is renamed. Every item the
   converter takes from Seagull is named in the report.

Run the second way only after the user said yes to it. Get the file from the Seagull that the user runs, and ask where
Seagull runs when the setting is missing, as [Where Seagull runs](../seagull-diameter-common/SKILL.md#where-seagull-runs)
describes:

```bash
python <skill folder>/scripts/export_seagull_base.py --runner windows --seagull-exe <path> --out <scratch>/base_draft08.xml
python <skill folder>/scripts/export_seagull_base.py --runner docker [--image IMAGE] --out <scratch>/base_draft08.xml
```

The script prints the path of the file; pass it to the conversion as `--seagull-base <file>`. Write the file to a
scratch folder, never into the user's dictionaries folder. Never use a Seagull dictionary that the user did not allow,
and never look for one on the disk by yourself.

The Seagull dictionary does not define every base AVP. `Event-Timestamp` (code 55), for one, is missing. A scenario or
the check of step 4 that uses such an AVP then fails with `No definition found for [Event-Timestamp]`. Tell the user
which AVP it is and that their own dictionaries have to define it.

## Flags

The project dictionaries give the V, M, and P bits of an AVP, and no flags for a command. Without options the
converter writes 128 (R) for every request and 0 for every answer, and each AVP gets the bits that its source gives.
That is the converter's own choice, not a fact about the project. RFC 4006 describes CCR and CCA with the P bit, which
is 192 and 64, and another converter may differ from this one on the M bit of vendor AVPs.

Change the flags only when the user asks, or when they say which value their OCS or their reference dictionary has.
Never pick `--command-flags`, `--avp-flags`, or `--vendor-mandatory` yourself. Flags that contradict the V bit of an AVP
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
