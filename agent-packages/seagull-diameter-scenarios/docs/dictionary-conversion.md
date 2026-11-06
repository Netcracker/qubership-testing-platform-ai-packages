# Dictionary conversion

Seagull reads the definitions of Diameter AVPs and commands from a dictionary file in its own XML format. A project that
you test usually keeps its dictionaries in another format, which Seagull rejects with a syntax error. The script
`dict2seagull.py` converts them, and
[`/seagull-diameter-dictionary-convert`](user-guide.md#seagull-diameter-dictionary-convert) runs it. This page says what
the conversion does and what it leaves out.

## Why a script

The dictionaries that ship with Seagull cover less than a charging test needs, and some of their definitions are wrong:
in `base_ro.xml`, three AVPs have code 456, and `Used-Service-Unit` has the code that RFC 4006 gives to
`Requested-Service-Unit`. The project dictionaries are not reliable either: they can define a name twice with different
identities, give one code two names, or break their own XSD schema.

Editing a shipped dictionary by hand copies its mistakes and has to be repeated whenever the project dictionary
changes. Changing Seagull to read the project format means changing C++ code that has not been developed since 2013. A
script leaves Seagull unchanged, derives every code and flag from the source, and reports what looks wrong. Rerunning it
is the whole update.

## What the conversion does

| In the project dictionary                                           | In the Seagull dictionary                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `<avp name code>` inside `<vendor id>`                              | `<define name type>` with `avp-code`, `flags`, and for a vendor AVP `Vendor-ID`                                                                                                                                                                                                                  |
| `vendor-specific="yes"`, `mandatory="must"`, `protected="must"`     | The flag bits V (128), M (64), and P (32), added up. `mandatory="may"` and `"mustnot"` leave M unset                                                                                                                                                                                             |
| `<type type-name>`                                                  | One of the six Seagull types: `Integer32`, `Integer64`, `Unsigned32`, `Unsigned64`, `OctetString`, `Grouped`. `Enumerated` becomes `Unsigned32`; `UTF8String`, `Address`, `Time`, `DiameterIdentity`, `IPFilterRule` and the other string-like types become `OctetString`                        |
| `<grouped>` with `<gavp>`                                           | `type="Grouped"`. The member list is kept as a comment                                                                                                                                                                                                                                           |
| `<enum name code>`                                                  | A comment above the definition, for example `values: INITIAL_REQUEST=1, ...`                                                                                                                                                                                                                     |
| `<command name code>` in `<base>` and `<application>`               | A request and an answer: the initials of the name plus `R` and `A` (`Credit-Control` gives `CCR` and `CCA`). By default requests have flags 128 and answers 0 (see [Flags](#flags-of-commands-and-avps)); `cmd-code`, `protocol-version` 1, and `application-id` for a command of an application |
| `TGPP-` at the start of an AVP name                                 | `3GPP-`, as in the specifications and in Seagull scenarios. `keep-tgpp=yes` keeps `TGPP-`                                                                                                                                                                                                        |
| Two AVPs with one name and different vendor or code                 | The first keeps the name. The second is written as `<name>-v<vendor>c<code>`, for example `MSC-Address-v13421c281`, and the report says so                                                                                                                                                       |
| An application command with the same abbreviation as a base command | The application command replaces the base command                                                                                                                                                                                                                                                |

Each result is merged with the base protocol of the folder, so that `CER`, `DWR`, and the other base commands are always
defined; see [The base protocol](#the-base-protocol). The script reports what looks inconsistent and corrects nothing,
because it cannot tell which of two names for an AVP is the intended one.

## The base protocol

Seagull loads one dictionary file and nothing else, so that file has to define the Diameter base protocol: the commands
`CER`/`CEA` (code 257) and `DWR`/`DWA` (code 280), and the AVPs with the codes 257, 258, 263, 264, 266, 268, 269, and 296.
The project's service does not supply them to Seagull.

The converter looks for these items by code in every `.xml` dictionary of the folder; the filename does not matter. If
the folder contains `DiameterBaseProtocol.xml`, it is the base. Otherwise the base is made of the files that define the
handshake commands. When something is missing, the converter writes nothing, exits with status 2, and lists the missing
codes. There are two ways on:

1. Add the files that define the base protocol to the folder and convert again.
2. Allow the dictionary that ships with Seagull, `base_draft08.xml`. It can be wrong in places, for example with an AVP
   code or a flags byte that differs from the RFC, and it was not checked against your OCS. Pass it as
   `seagull-base=<file>`. The skill gets the file from your Seagull with `scripts/export_seagull_base.py` after you say
   yes.

With the Seagull dictionary, the converter adds every AVP and command pair that your dictionaries do not define yet,
because messages use more of the base protocol than the handshake. Your dictionaries win: an item is skipped when its
name or its code is already defined, and nothing of yours is renamed or replaced. The report names the number of added
items and the file they came from.

The Seagull dictionary does not define every base AVP; `Event-Timestamp` (code 55) is missing in `base_draft08.xml` of
Seagull 1.8.3. A message that uses an AVP like that fails in Seagull with `No definition found for [Event-Timestamp]`,
so define such an AVP in your own dictionaries.

## Flags of commands and AVPs

The project dictionaries give the V, M, and P bits of an AVP and no flags for a command. Without options, the converter
writes 128 (R) for every request and 0 for every answer, and each AVP gets the bits that its source gives. These
defaults are the converter's own choice, not a fact about the project:

- RFC 4006 describes `CCR` and `CCA` with the P bit, which makes their flags 192 and 64. An OCS rarely depends on it,
  but a Diameter agent on the path may.
- A dictionary made by other tooling may set the M bit on vendor AVPs where the source says `mandatory="may"` or
  `"mustnot"`. The M bit matters mostly for an AVP that the receiver does not know.

Neither choice is known to be right for your OCS, so the defaults stay and you change them when you know the value that
you need. An options file or the prompt does it:

```ini
[command-flags]
request = 128
answer = 0
CCR = 192
CCA = 64

[avp-flags]
vendor-mandatory = source
PDP-Address = 128
```

| Key                                | Effect                                                                                                      |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `request`, `answer`                | The flags byte of every request or answer that no command key names. Default 128 and 0                      |
| `CCR`, `CCA`, ...                  | The flags byte of one request or answer, by its Seagull name                                                |
| `vendor-mandatory`                 | The M bit of every vendor AVP: `source` keeps what the source says (default), `yes` sets it, `no` clears it |
| An AVP name, such as `PDP-Address` | The flags byte of that AVP, by its name in the output. It wins over `vendor-mandatory`                      |

In the prompt the same keys are `command-flags=CCR=192`, `avp-flags=PDP-Address=128`, and `vendor-mandatory=yes`;
`options=` names a file to start from, and the prompt wins over it. Every run writes the options in effect to
`dictionary-options.ini` in the output folder.

A flags byte is a number from 0 to 255. One that contradicts the V bit of the AVP, such as a vendor AVP without 128, is
refused, and a name that matches no AVP or command is a warning. The report lists each change as a `NOTE` line: a
command whose flags differ from the default, an AVP whose flags differ from its source, and how many vendor AVPs the
`vendor-mandatory` policy changed.

## What the conversion drops

- The multiplicities of AVPs in a command, and which AVPs each command may carry. Seagull then cannot check that a
  message is complete.
- The values of enumerations and the members of groups, which stay as comments.
- The `<Name>Commands.xml` files. Seagull does not use them. When one sits next to its `<Name>.xml`, the script only
  warns about a command code that the sources do not define.

## Merge several dictionaries into one

Seagull loads one dictionary for each run, and two `-dico` options do not add up: Seagull 1.8.3 stops with
`protocol with name [diameter-v1] already defined`, whichever file comes first. A run that uses several dictionaries
together needs them in one file, so the converter writes one by default: `diameter-dictionary.xml`, made of every AVP
dictionary of the folder and the base protocol. `combine=yes` means the same.

```text
/seagull-diameter-dictionary-convert C:\work\dictionaries
```

Two other forms exist:

- `combine=no` writes one file for each dictionary, each merged with the base protocol, for example to compare them.
- `combine=Gy,Sy` writes only one file, `Gy+Sy.xml`, made of the named dictionaries. Use it to leave a dictionary out,
  or to set the order. Without a list, the dictionaries are merged in alphabetical order of their filenames.

The base protocol is always merged in, so it need not be listed. The dictionaries are merged in the order given, after
the base protocol:

- An AVP that several files define in the same way, with one name, vendor, and code, appears once.
- An AVP name that a later file uses for another vendor or code does not replace the first definition. The later one is
  written as `<name>-v<vendor>c<code>`, and the report lists it. If your product resolves such conflicts in another way,
  for example by taking the last definition, the merged file differs from what the product loads.

## Check a result

`check=yes` runs `scripts/check-converted.sh` of the skill `seagull-diameter-convert-dictionaries`. It starts the
Seagull image, mounts the converted dictionaries read-only, and for each one that defines `CCR` runs a stub OCS and a
client with invented values. With a Seagull for Windows, `seagull_windows_run.py check-converted` does the same with
`seagull.exe`; see [Where Seagull runs](user-guide.md#where-seagull-runs). The client sends `CER` and one initial `CCR`
for a data session, and the stub answers with result code 2001. A result passes if the statistics file reports 1
successful call and 0 failed calls.

The check shows that Seagull loads the dictionary, finds the AVP names of the scenario in it, and can encode and decode
the messages. It does not show that a real OCS accepts them, because the stub does not read the request. The client
sends Credit-Control AVPs, so a dictionary that lacks them fails the check without being wrong for its own protocol.

## Validate the sources

The conversion does not read XSD files, and `validate=` is `no` by default: with `no`, nothing looks for a schema.
`validate=yes` adds a separate check of the sources against their schemas, with `scripts/validate.sh` and
`ValidateDictionaries.java` (Java 11 or later). It checks the structure that the schemas describe, such as the order of
elements and the values an attribute may take, not that a code or a flag is right. A file that fails the schema is
still converted.

### Which schema a file gets

The validator never searches the disk. It chooses the schema of each `.xml` file of the folder from these places, in
this order:

1. **The reference in the file.** The root element may carry `xsi:noNamespaceSchemaLocation` (or `xsi:schemaLocation`).
   The path is resolved against the folder of the file, so `xsd/diameter-command.xsd` means the `xsd` folder next to
   that file. If the file exists, it is the schema. A reference that is a URL is not downloaded and counts as not found.
2. **The same filename in `xsd=`.** If the reference does not resolve and a folder was given in `xsd=`
   (`--xsd-dir`), the validator takes the file of the referenced name from that folder, but only if that schema
   declares the root element of the dictionary.
3. **The root element.** If the file has no reference, or the name is not in the folder, the validator looks in the
   `xsd=` folder for the `.xsd` file that declares the root element of the dictionary. The root element is the outermost
   tag: `<dictionary>` for an AVP dictionary and `<diameter-command-dictionary>` for a command dictionary. The filename
   of the schema does not matter.

In step 3 only global elements count, that is, the `xs:element` declarations directly under `xs:schema`. A schema for
command dictionaries declares `diameter-command-dictionary` globally and contains a nested element that is also called
`dictionary`. The nested one does not make that schema a candidate for an AVP dictionary. If no schema declares the root
element, or several do, the file has no schema, and the problem names the candidates.

AVP dictionaries usually carry no reference, so they get their schema in step 3, and a folder in `xsd=` is the way to
name it.

### When no schema is found

If any file has no schema, the validator validates nothing and exits with status 3. It lists each file with its problem
and then each distinct problem once, with the number of files it affects. Files that share a reference, such as
`xsd/diameter-command.xsd` in every command dictionary, give one problem:

```text
NO SCHEMA Sy.xml (dictionary): the file has no schema reference
NO SCHEMA SyCommands.xml (diameter-command-dictionary): the reference xsd/diameter-command.xsd does not resolve; no file C:\work\dictionaries\xsd\diameter-command.xsd
2 distinct problem(s) in 11 file(s):
    the reference xsd/diameter-command.xsd does not resolve; no file C:\work\dictionaries\xsd\diameter-command.xsd (7 file(s))
    the file has no schema reference (4 file(s))
```

The agent then stops and asks two questions in one message: where the XSD files are, and whether to keep the answer.
With the answer it runs the validator again with `--xsd-dir`. Keeping the answer writes it to `dictionary-options.ini`
in the output folder:

```ini
[validate]
xsd = C:\work\schemas
```

A later run that starts from that file (`options=`) uses the folder without asking. The default is not to keep it,
because the path belongs to one machine. If you cannot say where the schemas are, the agent skips the validation and
converts anyway.

### Output and exit statuses

For each file the validator prints the verdict, the schema it used, and the distinct error messages with the number of
occurrences and the line of the first one:

```text
Gy.xml (dictionary): valid
    schema: C:\work\schemas\diameter-dictionary.xsd
Sy.xml (dictionary): 2 errors
    schema: C:\work\schemas\diameter-dictionary.xsd
    x2, first at line 423: cvc-attribute.3: ...
```

`--plan` prints the schema chosen for each file and the reason, without validating.

| Status | Meaning                                                                         |
| ------ | ------------------------------------------------------------------------------- |
| 0      | Every file is valid, or `--plan` found a schema for every file                  |
| 1      | Some file is invalid                                                            |
| 2      | Wrong arguments, `--xsd-dir` is not a folder, or the folder has no `.xml` files |
| 3      | A schema was not found for some files; nothing was validated                    |

The validator rejects files with a document type declaration and turns on the secure processing mode of the schema
factory. A schema that does not compile ends it with a stack trace and not with a validation message.

## Limits

- The rules above are our reading of the project format, not a specification of it. The flags, the type mapping, and the
  renamed names were checked by loading the result in Seagull and completing one Credit-Control exchange with a stub
  OCS. None of it was checked against a real OCS.
- A scenario written for another dictionary may use names that the converted one does not have. `rename=` maps them.
- The converted files are generated. They go out of date when a source or the script changes; convert again.
