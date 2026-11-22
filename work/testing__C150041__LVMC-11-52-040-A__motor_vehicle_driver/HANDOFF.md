# testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.040(A) — Except as otherwise provided in this Chapter: No person shall stand or park a vehicle in a roadway other than parallel with the edge of the roadway headed in the direction of lawful traffic movement.
Assigned branch(es): parallel orientation and lawful heading.
Cell: C150041 (one_way_road, parallel_park, road_edge); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-22 six-case parking geometry construction start

`case-plan.json` now proposes six exact case IDs: `__park_parallel_lawful`, `__park_angled_lawful`, `__park_parallel_reverse`, `__stand_parallel_lawful`, `__stand_angled_lawful`, and `__stand_parallel_reverse`. Four controlled comparisons hold the activity and other setup conditions fixed while changing requested orientation or heading. These are draft cases, with no recording or physical realization claimed. The shared baseline is reused within each activity, and no numerical legal angle or curb-distance threshold was introduced.

`parking_measurement.py` reads source-hashed original body frames and reports nearest-edge distance, absolute parallel deviation, lawful-heading deviation, heading dot product and count of original body corners inside the roadway. It requires an ordered frame/time series and source-described edge, roadway and lawful direction. `tests/test_parking_measurement.py` proves the distinction between parallel-but-reverse and angled-but-lawful headings, nearest-edge selection, roadway footprint, changed-source rejection and duplicate-frame rejection. Three focused tests pass in `cpu-tests.log`.

Next CPU actions: author a source-reviewed one-way roadway/edge/context packet with responsible person, halt purpose and applicable Chapter exception review; build six CARLA-lazy exact construction/controller/camera bundles; retain original standing/parking histories and a saved finalizer; create canonical semantic stages, pinned offline/compatibility and saved-only proofs, and independent delivery/comparison audits. Physical motion and actual camera visibility remain later verification. C150041 remains partial. Frozen inputs/runtime/batch were preserved; no Git command was run.

## 2026-11-22 gate and return check after five-pair and parking work

Pinned `runtime.py preflight` passed; update check returned version 0 and no paused assignments. C125714's full 69-test suite passes with one diagnostic-root skip; C150041's three focused geometry tests and three repository tests pass. Exact static `worker_check.py --assignment ... --complete` exits 0 for both changed assignments. Both exact `--require-delivery-ready` checks exit 1 at `Preparation acceptance failed: partial/missing packages remain`, as does `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`. C125714 and C150041 remain truthful partials.

Read-only returned-file inspection covered 2,901 files; largest was 1,226,018 bytes. No file exceeded its size limit, failed UTF-8 decoding, contained trailing whitespace or conflict markers, or had a mismatched recorded test-log hash. No Git command was run.

## 2026-11-22 parking source custody continuation

`source_review.py` now checks retained original bytes and SHA-256 values for roadway, one-way direction, responsible-person/activity and Chapter-exception context. It rejects unsafe paths, missing reviewer/citation, a non-reviewed packet, inconsistent edge/direction geometry and an activity outside standing or parking. Its output feeds `parking_measurement.py` while retaining an unresolved legal judgment. The positive fixture is explicitly synthetic and does not establish public roadway, lawful direction or Chapter applicability.

`tests/test_source_review.py` exercises source tampering, path traversal, direction conflict and invalid activity, plus measurement from a validated source packet. Six focused tests pass in `cpu-tests.log`. Resume with genuine reviewed source bytes and a source-hashed packet before Native construction and pinned delivery proofs. C150041 remains partial; no Git command was run.
