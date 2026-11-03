---
name: seagull-diameter-common
description: Support files for the other seagull-diameter skills, and the format of the folder of recorded Diameter steps. Not a task; never invoke it.
user-invocable: false
disable-model-invocation: true
metadata:
  opencode/autoinvoke: "false"
---

# seagull-diameter-common

This folder holds the code and the format that
[seagull-diameter-steps-extract](../seagull-diameter-steps-extract/SKILL.md)
and [seagull-diameter-scenario-generate](../seagull-diameter-scenario-generate/SKILL.md) share. It is a skill only
because APM deploys the files of a skill folder next to each other, so the scripts of the other skills can import
`../../seagull-diameter-common/scripts`.

| Script                       | Purpose                                                                                      |
|------------------------------|----------------------------------------------------------------------------------------------|
| `scripts/steps_format.py`    | Reads a folder of recorded steps; repairs and reports the faults of hand-edited text         |
| `scripts/check_steps.py`     | Checks a folder of recorded steps; run it before generating                                  |
| `scripts/dict2seagull.py`    | Converts the project's AVP dictionaries into one Seagull dictionary                          |

## The folder of recorded steps

One folder holds the Diameter steps of one recorded run, in the order they ran.

```text
<folder>/
  Step-001-request.txt
  Step-001-response.txt
  Step-002-request.txt
  Step-002-response.txt
  Steps-index.csv          optional
```

- `NNN` is a number of any width; the steps are read in numeric order. A step needs both of its files.
- The text of a file is one Diameter command as XML, written exactly as it was recorded, in UTF-8. The root element is
  the
  command (`CCR`, `CCA`, and so on). Each child element is an AVP, named as the project dictionary names it. A grouped
  AVP
  holds its members as child elements; any other AVP holds its value as text.

  ```xml
  <CCR Description="CCR-I" Service="peer-1">
    <Session-Id>VOICE94156515166</Session-Id>
    <Auth-Application-Id>4</Auth-Application-Id>
    <CC-Request-Type>1</CC-Request-Type>
    <Subscription-Id>
      <Subscription-Id-Type>0</Subscription-Id-Type>
      <Subscription-Id-Data>491700000001</Subscription-Id-Data>
    </Subscription-Id>
  </CCR>
  ```

- The attributes of the root element (`Description`, `Service`, and any others) are settings of the system that recorded
  the step. They are never sent. `Description` names the step in the generated scenario.
- Every request has a `Session-Id`. Steps with the same `Session-Id`, one after another, are one Diameter session.
- A value is written the way the recording system took it: numbers as digits, a time as `2026-10-27 14:00:52 +0000 UTC`,
  an IP address in dotted form, bytes as `0x...`, an enumeration in a request as its number (an answer may use its
  name).
- `Steps-index.csv` is optional: UTF-8 with a BOM, separator `;`, columns `Step file number` and
  `Step number in the scenario`, and any others. The generator uses the second column only in comments.

The reader repairs two faults that hand editing leaves, and reports every repair: a comment (`<!-- ... -->`, also one
that
ends in `--` without `>`) is removed together with the AVPs inside it, and a closing tag without `>` is completed.
Anything
else that is not XML is an error: send the folder back to the person who made it.

## Python

The scripts need Python 3.9 or later and no other package. Start them as `python`, `python3`, or `py -3`, whichever the
machine has.
