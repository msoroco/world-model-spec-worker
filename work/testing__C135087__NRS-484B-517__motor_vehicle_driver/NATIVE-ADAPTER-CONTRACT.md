# C135087 Native source handoff

`runner.py` requires an adapter module with `open_session(host, port, config)`.
The two input references must hash-match real, separately reviewed site and
vehicle JSON; records labeled as synthetic diagnostics are rejected before
the Native session starts.
The session supplies the live world, three actors, observer, controller and four
camera lifecycle methods already used by the case bundle. After the 900th tick
and camera finalization, it must also implement
`export_converter_sources(output_dir, constructed_case, attempt_source)`.

The export must retain observations from that same original Native run:
`road.xodr`, `capture/manifest.json`, `capture/native_map_facts.json`,
`capture/recorder_info.txt`, `capture/evidence.jsonl`,
`capture/native/frames.jsonl` and one source graph per frame under
`capture/native/graphs/`. The manifest must declare `original_live_run`,
`diagnostic_fixture: false`, 900 extracted frames, exact hashes for the road
and trace, and a hash-bound Native map facts file. Every frame must join the
actor rows, frame map, telemetry, evidence and Native graph by original frame
number and timestamp. Evidence must retain the subject, entrant, passenger
and original RGB sensor identities. `stand_converter_source.py` checks these
conditions before the runner seals the capture.

`stand_source_sweep.py` additionally requires independently reviewed SHA-256
values for the site and vehicle source records. It reruns the saved actor,
converter and full four-camera audits, then exports measured stop, loading,
entrant and access observations. It leaves designation/sign adequacy,
temporary stopping, expeditious loading and noninterference undecided. The
current synthetic diagnostic fixture is rejected by both source gates.

No reviewed original stand/sign, site geometry or subject and entrant
classification packet is present in this assignment's frozen inputs. Native
source acquisition and legal review therefore remain pending; diagnostic
software receipts do not establish physical or legal acceptance.
