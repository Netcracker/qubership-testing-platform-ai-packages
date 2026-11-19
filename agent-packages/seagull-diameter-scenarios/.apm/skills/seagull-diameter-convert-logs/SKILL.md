---
name: seagull-diameter-convert-logs
description: Use when the user asks to turn a Seagull log (a *.client or *.stub file) into XML, to see the sent and received Diameter messages as XML, or to save each message of a run in its own file. Reads the AVP tree of each message and writes one XML file for each, named by the number, the direction, and the command.
user-invocable: false
---

# Convert a Seagull log to XML

A Seagull log shows each message twice: as a list of AVPs and as hex bytes. This skill writes the AVP tree of every
message as XML, one file for each message, so a message can be read, compared, and searched as a document.

The command [/seagull-diameter-logs-convert](../seagull-diameter-logs-convert/SKILL.md) runs the same steps from formal
arguments. For an ordinary request in plain language, follow this page.

## Required inputs

- **From the user:** the log file. Seagull is not started, and no setting is read.
- **Optional:** the output folder (it must be new or empty), the numbering, the XML format, pretty-printing, and, for the `steps` format, a dictionary file.

## What to take from the request

| Parameter | How the user says it                                       | Rule                                                                         |
| --------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| log       | "convert C:\work\run.client"                               | Required: a Seagull log file                                                 |
| out       | "write the XML to C:\work\xml"                             | Optional. It must be new or empty. Default: a new folder next to the log     |
| numbering | "one number for a request and its answer", "in log order"  | `step` (default) or `sequence`. When the user does not say, use `step`       |
| format    | "like the recorded steps", "as input for the generator"    | `avp` (default) or `steps`. When the user does not say, use `avp`            |
| pretty    | "on one line", "without indentation"                       | `true` (default) or `false`. When the user does not say, use `true`          |
| dictionary | "the dictionary is C:\work\diameter-dictionary.xml"       | Optional, for `steps` only: used when the file that the log names is missing |

The two numberings:

- `step`: a request and its answer share one number, for example `001_sent_CCR.xml` and `001_received_CCA.xml`. An
  answer belongs to the open request of the opposite direction with the same cmd-code, Hop-by-Hop, and End-to-End
  identifiers, so a received DWR and the DWA that answers it also share a number. The direction stays in the file name.
- `sequence`: the messages are numbered in the order of the log, so a received DWR before the sent DWA shows in the
  numbers.

## Run

Write every path in a command in quotes: single quotes keep a Windows path whole, and forward slashes
(`'C:/work/run.client'`) work too. Don't search the disk for the log. When the path does not exist, say so and ask.

```bash
python <skill folder>/scripts/log_to_xml.py '<log>' [--out '<folder>'] [--numbering step|sequence] \
    [--format avp|steps] [--pretty | --no-pretty] [--dictionary '<file>']
```

The script exits with 2 when the log does not exist or the folder is not empty, with 1 when the log holds no message,
and with 3 when `--format steps` finds no dictionary. Don't write into a folder that holds files, and don't delete one; ask the user for another folder.

## What the files hold

The file name is `NNN_sent_CCR.xml` or `NNN_received_CCA.xml`. The log names an answer after its request (`CCR`), so
the script names an answer by its flags: without the R bit, a name that ends in R ends in A.

Each file holds one message, in one of two forms.

**`avp` (the default)** keeps everything the log shows. The root is a `message` element (`name`, `direction`, `step`,
`sequence`, `time`), with a `header` element that holds the header fields of the log, and one `avp` element for each AVP,
nested for a grouped AVP. An `avp` carries `name`, `code`, `flags`, and `vendor-id` when it has one, and either `value`
(a number the log prints in decimal) or `hex` (the bytes the log prints). When every byte of `hex` is a printable ASCII
character, `text` holds the same bytes as text. The text is a hint: the log carries no dictionary, so the script cannot
tell a string from a number.

**`steps`** has the form of the recorded steps that the scenario generator reads (see
[the folder of recorded steps](../seagull-diameter-common/SKILL.md#the-folder-of-recorded-steps)): the command is the
root element, each AVP is an element named as in the log, and a grouped AVP holds its members. The log shows each
value as Seagull printed it, and the Seagull dictionary says how to read it back:

- A `Time` is written as a date such as `2026-10-27 14:00:52 +0000 UTC`, an `Address` as an IP address, and a
  `UTF8String` or a `DiameterIdentity` as text.
- An `Enumerated` is written as the name of its value, when the dictionary lists the names in a `values:` comment above
  the definition, as the dictionary converter writes them. Without the comment it stays a number.
- An `OctetString` has no rule in the dictionary: printable bytes are text, and any other bytes are `0x` and the hex
  digits. The same holds for an AVP that the dictionary does not define; the script lists such AVPs on stderr.
- The definition of an AVP is found by its code and vendor, so two AVPs of one name from different vendors are read
  each by its own type.
- `3GPP-` at the start of an AVP name becomes `TGPP-`, because an XML name cannot start with a digit.
- The root has no `Description` and no `Service`: they belong to the system that recorded the steps, and the log does
  not have them. Add them when the generator needs them.

**The dictionary** is the file that the line `option_dico_file` at the start of the log names, the one Seagull ran
with. When that file exists, the script uses it without a word. When it does not exist on this machine (the run was on
another machine or in a container), the script says so on stderr and takes the file of `--dictionary`, and says so.
Without a usable `--dictionary` it writes nothing and exits with 3: tell the user which path the log names and ask for
a dictionary file; don't search the disk for one. `--dictionary` is ignored, with a line on stderr, when the file of the
log exists and for the `avp` format.

The files keep the names `NNN_sent_CCR.xml`. To read a folder with `check_steps.py` or the generator, pass the name
templates, or rename the files to `Step-NNN-request.txt` and `Step-NNN-response.txt`.

With `pretty` set to `true` the XML is indented; with `false` each file is one line.

Report the folder, the number of files, the numbering, and the format used.
