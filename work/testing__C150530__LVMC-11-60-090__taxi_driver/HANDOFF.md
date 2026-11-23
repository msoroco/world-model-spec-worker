# testing__C150530__LVMC-11-60-090__taxi_driver

Status: **partial CPU source-join and trace chain**, not ready for local delivery. No original recording, physical success, or legal finding is claimed.

## Exact scope and evidence

LVMC 11.60.090: “Any cab, upon leaving any stand designated in accordance with the provisions of this Section, shall execute a right-hand turn, when a sign is posted giving notice of this requirement, at the first street intersection after it leaves such stand.” The fixed assignment is C150530, one-way road, right turn, mandatory-turn-sign control, taxi_driver, full-test target. The sole frozen witness (`inputs/testing__C150530__LVMC-11-60-090__taxi_driver/witnesses.json`, source index 322) is conditional and low-confidence. `evidence.json` lists zero accepted recordings; `judgment_ranges.json` has no exact LVMC 11.60.090/taxi_driver range entry. No judgment phrase has a numeric legal cutoff here.

The source-backed branch is posted requirement after departure from a designated stand. Its conditions are a qualifying cab and driver, a designated curb-adjacent stand, a posted right-turn notice, the first street intersection *after* departure, and an actual right-turn trajectory there. The frozen witness asks for designation, licensing, sign, one-way receiving-road, jurisdiction and referenced-section applicability context. Those original records have not been supplied to this candidate; OpenDRIVE objects and CPU fixture assertions cannot establish them. `case-plan.json` records four explicit evidence gaps G1–G4 and preserves the source hashes.

## Exact CPU candidates and comparison

- `testing__C150530__LVMC-11-60-090__taxi_driver__near_stand`: `candidates/near_stand.json` and `candidates/near_stand.xodr`.
- `testing__C150530__LVMC-11-60-090__taxi_driver__far_stand`: `candidates/far_stand.json` and `candidates/far_stand.xodr`.

`stand_route.py` generates and checks the one-way approach, right-turn and straight junction connectors, south and east exits, stand, departure, sign location and first-intersection order. `candidate_opendrive.py` materializes a seven-road OpenDRIVE engineering candidate with connected -1 driving-lane endpoints and a quarter-circle right-turn arc; its two topology receipts include exact map SHA-256 values. The cross street has its own one-way incoming connector into the south exit. The sign and stand are candidate map markers only.

The controlled `stand_to_first_intersection_distance` comparison moves the stand, departure and notice 20 metres upstream together. It keeps the law, actor, one-way approach, first junction, receiving exit, turn route and sign meaning fixed. `candidate_comparison_audit.py` compares the two materialized layouts and XML maps and rejects changes outside those positions; `candidates/comparison-audit.json` is its CPU candidate receipt. No statutory stand distance is inferred from this engineering variation. Both exact cases have a `candidate_risk` assessment of `none`: the CPU topology work has not established a case-specific failure requiring a fallback. Physical curb departure, radius and visibility need an original Native attempt before deciding a measured fallback trigger.

`taxi_native_motion.py` is a lazy Native construction component: it checks actual `world.get_map().to_opendrive()` bytes against the candidate hash before spawning, places the taxi at the candidate stand, follows a curb departure and right-turn path, and issues finite steering/throttle/brake commands. The map readback and actor calls have only been exercised with CPU fakes; no CARLA import or motion occurred. `saved_turn_check.py` takes saved event references plus documented source-file hashes, rejects missing/stale context and wrong first-intersection order, and reports a measured turn angle/exit lane. Its geometric right-turn classification is an engineering observation, not a legal cutoff or acceptance.

## Original-source and saved-frame chain added in this continuation

`reviewed_context.py` requires six retained, hash-matched UTF-8 source categories under an attempt's `reviewed_sources/`: cab licence, stand designation, stand marking, posted notice, jurisdiction and referenced designation provisions. It requires a source quote present in each retained file, exact candidate map hash and exact stand/notice coordinates. `reviewed-context.template.json` is intentionally incomplete; it must not be used as an original reviewed packet. The validator proves byte and quote joins only, not document authenticity or legal applicability.

`native_trace_capture.py` now records original 20 Hz frame number, time, vehicle pose and Native road/lane IDs into `original-trace.jsonl`. It seals the trace only after a completed, contiguous run and binds its hash, frame count, candidate map and retained context packet. `turn_trace_finalizer.py` independently reads that saved file and derives the stand departure, first post-departure junction road, receiving road and turn angle. It rejects missing frames, implausible frame jumps, stale seal/map/context, absent stand departure, wrong source quote and wrong road order. Its CLI wrote a source-joined measurement in a synthetic CPU fixture. No original CARLA trace, actual video or pinned `runtime.py process-saved` attempt has been run.

`measurement-contract.json` binds both exact case IDs, candidate map hashes, component code hashes, original acquisition filenames and the three selected requirement dispositions. `case-plan.json` maps those dispositions to gaps G1–G4. The technical turn-angle range is explicitly an engineering classifier and does not supply a legal threshold.

## Proven commands

- `.venv-cpu/bin/python runtime.py preflight` exited 0 with pinned Lean 4.28.0 and CPU requirements.
- `.venv-cpu/bin/python work/testing__C150530__LVMC-11-60-090__taxi_driver/stand_route.py` materialized both candidate layouts.
- `.venv-cpu/bin/python work/testing__C150530__LVMC-11-60-090__taxi_driver/candidate_opendrive.py` materialized both candidate maps and topology receipts.
- `.venv-cpu/bin/python work/testing__C150530__LVMC-11-60-090__taxi_driver/candidate_comparison_audit.py` wrote the passing candidate comparison receipt.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C150530__LVMC-11-60-090__taxi_driver/build_measurement_contract.py` wrote the current source-hashed measurement contract.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C150530__LVMC-11-60-090__taxi_driver/tests -v` passed 36 tests; `cpu-tests.log` SHA-256 is `37433d66c27598348bfe06cef20e57cb3ba5fb2beb25e746f956afef413e4071`. Tests include negative topology, notice, context quote/hash, event ordering, stale trace/map/packet, missing frame, teleport, changed comparison, Native map readback and blueprint probes.

## Exact remaining CPU work and resume actions

1. Bind genuine original stand designation, licence, notice, jurisdiction and referenced-section applicability sources to the exact Native road. Populate a retained reviewed-context packet only after source review; the current template has no original records.
2. Complete the Native runner around the tested trace writer with four-view 20 Hz camera capture, frame map, sealed video output, guaranteed restoration and owner release. Exercise both exact candidates with offline and pinned source-bound positive/negative compatibility proofs, not only fake spawn calls.
3. Integrate the partial measurement contract/finalizer into the exact pinned `runtime.py process-saved` path, implement canonical semantic stage proposals and case-specific physical/pixel checks, then CPU-test independent delivery/video and measured comparison audits and the complete execution manifest.
4. CPU test the exact `runtime.py process-saved` path, prepare the ordered local GPU queue and integration proof, then run `.venv-cpu/bin/python worker_check.py --assignment testing__C150530__LVMC-11-60-090__taxi_driver --complete --require-delivery-ready`. Keep `result.json` partial until every required CPU proof passes. Run the complete-batch strict gate after the assignment gate.

The only later GPU checks are real Native trajectory, sign/stand visibility, camera coverage and original video acceptance. No absent CPU package or tool is classified as an external blocker. The independent timer publishes checkpoints; no Git command was run by the worker.

Current gates: exact static `worker_check.py --assignment testing__C150530__LVMC-11-60-090__taxi_driver --complete` exits 0 (`.runtime-work/c150530-static-trace.log`). Its exact strict gate exits 1 at the truthful partial status (`.runtime-work/c150530-strict-trace.log`). The complete-batch strict gate exits 1 at the same partial/missing-package acceptance condition (`.runtime-work/full-strict-c150530-trace.log`).
