# History of the first check

The first full pass over the [test plan](test-plan.md) found defects in the package and gaps in its pages. This page
lists what was changed and why, for readers who want the history. A tester who starts a check needs only the
[results](results.md).

## Findings and the changes that fixed them

Each change went in its own pull request after the tester agreed.

| Change                                                                                                                                                                | Pull request                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Validation scope, `validate-commands`, the settings lookup, and the `Seagull for the check:` line                                                                     | [14](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/14)                                                                                     |
| `seagull_run.py`, the upward lookup of the settings file, and the settings skill and command                                                                          | [15](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/15)                                                                                     |
| Name templates for the step files, and the extraction skill's rules about the tie between request and response                                                        | [16](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/16)                                                                                     |
| Wording of the generation and templatize skills, the AVP question as plain text, the rollback of a failed generation, the settings fallback, and the check of `--set` | [17](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/17)                                                                                     |
| Forward slashes in the data-file path that Seagull for Windows reads                                                                                                  | [18](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/18), [20](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/20) |
| Wording of the externalize skill                                                                                                                                      | [19](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/19)                                                                                     |
| Quoted paths in the commands of the skills, and how to read a path from plain text                                                                                    | [21](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/21)                                                                                     |
| Run one scenario by its file, make running scenarios findable, name the known settings when the runner is not set                                                     | [22](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/22)                                                                                     |
| Run one scenario against an OCS at a given address, and the rule for when that is allowed                                                                             | [23](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/23)                                                                                     |
| A note when `--logs` is ignored, and a logs folder outside the output folder                                                                                          | [24](https://github.com/Netcracker/qubership-testing-platform-ai-packages/pull/24)                                                                                     |

### F3: running against an OCS

The first plan expected a refusal: the agent never runs against a real OCS. The package rule said "on your own", which
means without a request, so a run that the user asks for with an address is allowed, and the agent ran it. It wrote
a script of its own to do so, because the dry-run script always starts a stub. The change added `seagull_run.py run
<scenario> --dest <host:port>`, which sets the address in a copy of the client configuration and starts no stub, and
reworded the rule to say when such a run is allowed. A rerun used the new command in one call and reported the
unreachable address, the dry run not being the run against the OCS, and the client address that the CER announces.

### F8: a pair that matches no AVP

The generator treats a `placeholder=` pair whose AVP no step has as a note, not an error, and still writes the folder.
The agent reported the note first and offered the corrected pair. The tester decided to keep this: the name may be
right and simply absent from that set of steps.
