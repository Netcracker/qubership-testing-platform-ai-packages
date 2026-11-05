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

| In the project dictionary                                           | In the Seagull dictionary                                                                                                                                                                                                                                                 |
|---------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `<avp name code>` inside `<vendor id>`                              | `<define name type>` with `avp-code`, `flags`, and for a vendor AVP `Vendor-ID`                                                                                                                                                                                           |
| `vendor-specific="yes"`, `mandatory="must"`, `protected="must"`     | The flag bits V (128), M (64), and P (32), added up. `mandatory="may"` and `"mustnot"` leave M unset                                                                                                                                                                      |
| `<type type-name>`                                                  | One of the six Seagull types: `Integer32`, `Integer64`, `Unsigned32`, `Unsigned64`, `OctetString`, `Grouped`. `Enumerated` becomes `Unsigned32`; `UTF8String`, `Address`, `Time`, `DiameterIdentity`, `IPFilterRule` and the other string-like types become `OctetString` |
| `<grouped>` with `<gavp>`                                           | `type="Grouped"`. The member list is kept as a comment                                                                                                                                                                                                                    |
| `<enum name code>`                                                  | A comment above the definition, for example `values: INITIAL_REQUEST=1, ...`                                                                                                                                                                                              |
| `<command name code>` in `<base>` and `<application>`               | A request and an answer: the initials of the name plus `R` and `A` (`Credit-Control` gives `CCR` and `CCA`). Requests have flags 128, answers 0; `cmd-code`, `protocol-version` 1, and `application-id` for a command of an application                                   |
| `TGPP-` at the start of an AVP name                                 | `3GPP-`, as in the specifications and in Seagull scenarios. `keep-tgpp=yes` keeps `TGPP-`                                                                                                                                                                                 |
| Two AVPs with one name and different vendor or code                 | The first keeps the name. The second is written as `<name>-v<vendor>c<code>`, for example `MSC-Address-v13421c281`, and the report says so                                                                                                                                |
| An application command with the same abbreviation as a base command | The application command replaces the base command                                                                                                                                                                                                                         |

Each result is merged with `DiameterBaseProtocol.xml`, so that `CER`, `DWR`, and the other base commands are always
defined. The script reports what looks inconsistent and corrects nothing, because it cannot tell which of two names for
an AVP is the intended one.

## What the conversion drops

- The multiplicities of AVPs in a command, and which AVPs each command may carry. Seagull then cannot check that a
  message is complete.
- The values of enumerations and the members of groups, which stay as comments.
- The `<Name>Commands.xml` files. Seagull does not use them. When one sits next to its `<Name>.xml`, the script only
  warns about a command code that the sources do not define.

## Merge several dictionaries into one

Seagull loads one dictionary for each run, and two `-dico` options do not add up: Seagull 1.8.3 stops with
`protocol with name [diameter-v1] already defined`, whichever file comes first. A run that uses several dictionaries
together needs them in one file. Name them in `combine=`:

```text
/seagull-diameter-dictionary-convert C:\work\dictionaries combine=Gy,Integration,RoIMS,RoSCP,RoSMSMMS,Sy
```

`DiameterBaseProtocol` is always merged in, so it need not be listed. The merged file is named after its parts, joined
with `+`; copy it under a shorter name such as `All.xml`. The dictionaries are merged in the order given, after the base
protocol:

- An AVP that several files define in the same way, with one name, vendor, and code, appears once.
- An AVP name that a later file uses for another vendor or code does not replace the first definition. The later one is
  written as `<name>-v<vendor>c<code>`, and the report lists it. If your product resolves such conflicts in another way,
  for example by taking the last definition, the merged file differs from what the product loads.

## Check a result

`check=yes` runs `scripts/check-converted.sh` of the skill. It starts the Seagull image, mounts the converted
dictionaries read-only, and for each one that defines `CCR` runs a stub OCS and a client with invented values. The
client sends `CER` and one initial `CCR` for a data session, and the stub answers with result code 2001. A result passes
if the statistics file reports 1 successful call and 0 failed calls.

The check shows that Seagull loads the dictionary, finds the AVP names of the scenario in it, and can encode and decode
the messages. It does not show that a real OCS accepts them, because the stub does not read the request. The client
sends Credit-Control AVPs, so a dictionary that lacks them fails the check without being wrong for its own protocol.

`validate=yes` checks the sources against their XSD files with `scripts/validate.sh`. It checks the structure that the
XSD files describe, not that a code or a flag is right.

## Limits

- The rules above are our reading of the project format, not a specification of it. The flags, the type mapping, and the
  renamed names were checked by loading the result in Seagull and completing one Credit-Control exchange with a stub
  OCS. None of it was checked against a real OCS.
- A scenario written for another dictionary may use names that the converted one does not have. `rename=` maps them.
- The converted files are generated. They go out of date when a source or the script changes; convert again.
