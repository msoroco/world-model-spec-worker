# testing__C378132__LVMC-11-60-030-A2__bus_driver

Status: delivery prepared on the pinned CPU runtime. The exact assignment gate passed on 2026-11-27:

`.venv-cpu/bin/python worker_check.py --assignment testing__C378132__LVMC-11-60-030-A2__bus_driver --complete --require-delivery-ready`

The package makes no physical or legal acceptance claim. Its ten selected cases target full-test only. No accepted recording was supplied for reuse, and the supplied judgment range file contains no entry for this law and actor. The frozen assignment, witness and evidence inventory remain unchanged.

## Exact law and branch mapping

LVMC 11.60.030(A)(2) governs a non-tour bus operator's street stop for the purpose of loading or unloading passengers or their baggage. It lists a bus stop, bus stand, passenger loading zone, and designated assigned-route origin or destination as place alternatives, with an emergency exception. The qualifier scope under Section 11.60.010, bus-stop definition, loading-zone terminology and emergency interpretation remain for source review and legal judgment. No numeric lawful cutoff is inferred.

| Case suffix | Constructed target | Measured source condition |
| --- | --- | --- |
| outside_passenger | Ordinary non-tour passenger loading outside all five places | Stopped footprint, purpose, bus class, route and circumstances |
| inside_bus_stop | Same passenger stop at designated bus stop | Official stop polygon and full bus footprint |
| inside_bus_stand | Same at designated bus stand | Official stand polygon and full bus footprint |
| inside_loading_zone | Same at passenger loading zone | Official zone polygon and full bus footprint |
| at_route_origin | Same at assigned-route origin | Designation, route and origin polygon |
| at_route_destination | Same at assigned-route destination | Designation, route and destination polygon |
| outside_baggage | Ordinary baggage loading outside all places | Independent baggage purpose review |
| outside_cargo | Cargo-only stop outside all places | Independent excluded-purpose review |
| outside_emergency | Passenger loading outside during emergency | Independent emergency circumstance review |
| outside_tour_bus | Passenger loading outside by tour bus | Independent bus-class exclusion review |

The nine comparisons in `case-plan.json` pair the common outside passenger case with five place alternatives, baggage, cargo, emergency and tour status. `comparison_audit.py` checks the unchanged site/designation/route, activity duration and relevant identity/purpose/circumstance sources while testing exactly one observed difference. Its diagnostic proof rejects changed observations. All exact case IDs are in `case-plan.json` and `queue-proposal.json`.

## Construction and sources

`runner.py` selects one exact inline construction from `cases/<suffix>/construction.json`. `native_capture.py` requires a source-hashed independent original site review, all five official location polygons, assigned route, bus/operator classification, reviewed Native approach/stop/exit poses and four camera mounts before connecting to CARLA. It owns the bus and cameras, records 900 synchronized 20 Hz frames, full bus footprint and velocity samples, encodes four original camera streams, writes a frame map, seals capture and checks world settings restoration. It does not assert the original physical target was achieved.

`assemble_reviewed_activity.py` binds an independent source-hashed post-capture review of the stopped interval, passenger/baggage/cargo purpose and emergency circumstances after sealed Native exit. `bus_location.py` measures the actual 900-frame footprint against all five polygons, checks the complete stopped interval, route/identity and original source hashes, and requires `original_native_capture` for Native evidence and `original_independent_review` for seven review packets outside diagnostics. Diagnostic packets require `synthetic_diagnostic` on every source. `analysis.py` writes the source-bound measured result and recording channels; it does not produce a legal verdict. The common `camera_plan` and each config use the pinned four-view capability profile for 45 seconds.

Every case has a documented `candidate_risk` of none in `execution-manifest.json`: CPU geometry and source-shaped diagnostics did not diagnose a specific alternate Native construction. Local original runs may reveal an actionable risk requiring a reviewed fallback and renewed CPU proofs. The emergency and tour cases are construction targets that require independent original cause/classification review; the config labels alone are never accepted as evidence.

## CPU proof and local handoff

`runtime.py verify --runtime runtime` and `runtime.py preflight` pass. All ten primary `runtime.py offline` checks pass. All ten source-hashed `runtime.py compatibility` checks pass through analysis, Native validation, conversion, Lean decode, full video decode and rejection of missing designation; receipts/logs are under `cases/<suffix>/`. All ten `runtime.py process-saved` diagnostics pass with original source preservation, 900 frame joins and full final decode. `prove_physical_outcomes.py` records synthetic complete/incomplete/missing-evidence and lifecycle outcomes; this is checker preparation only. `independent/prove_delivery_audit.py` passes positive source joins and a negative missing designation for all ten cases; `independent/delivery_audit.py` is the original-source auditor. The nine comparison audits and changed-observation negatives pass. `cpu-tests.log` records the focused unit suite. After source-class hardening, refreshed exact offline, compatibility and saved-only proofs passed for all ten cases; the nine comparison audits and four focused tests passed. The exact strict assignment gate above passed again on 2026-11-27 with exit code 0 and `static_checks_passed: true`. The final source-bound proposal is frozen for lead review.

`queue-proposal.json` gives the lead ten ordered prepare, execute, capture, saved-processing, owner-release, independent audit and accept commands, plus nine comparison commands. Its GPU commands are prospective and were not run here. The first command in `result.json` dispatches the exact outside-passenger job. Original City designation and route documents, true bus motion, purpose/emergency/classification, real pixels, physical completion, independent delivery and legal comparison acceptance remain local checks.
