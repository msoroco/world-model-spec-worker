# heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver CPU checkpoint

Law: LVMC-11-12-100-C, cell: C374648, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver/assignment.json` (6366d357ca323359ec0aaf0fd375c7bd4c9bd7c058a0f693e378c42cb0fff23b).

Exact law text: A vehicle shall not be driven in a designated two-way left-turn lane except when preparing for or making a left turn. A left turn shall not be made from any other lane where a two-way left-turn lane has been designated.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- designated two-way left-turn lane: left-turn preparation or making versus unrelated travel
- left turn from designated two-way left-turn lane versus any other lane

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 original turn-origin measurement checkpoint

The frozen evidence inventory has zero C374648 accepted recordings. `case-plan.json` now lists six exact case intents and five controlled comparisons: center-lane and outer-lane left turns in both east and west directions, unrelated straight travel in the designated center lane, and straight travel outside it. The two full-text clauses have explicit selected requirement dispositions. Every case remains `planned_unimplemented`; this plan is not a capture or proof receipt. Cross-cell C394300 accepted summaries are not imported or asserted equivalent to this cell's missing original evidence.

`turn_origin_measurement.py` is the first source-bound CPU measurement component for the assigned second clause. From retained 20 Hz `turn_origin_native.jsonl` rows, it checks exact actor/frame/time continuity, a single junction entry, original center and approach lane IDs, stable designation source/marking actor IDs, and observed left deflection after entry. It reports the last nonjunction lane of origin and whether that lane ID matches the center lane ID. The 60-degree deflection detector is an engineering motion check, not a legal definition or intention inference. Designation authority, physical completion, and legal acceptance remain explicitly false. Four CPU tests exercise center/outer origin in both approach directions and reject missing source, stale frames, nonfinite time, absent designation, wrong turn and a broken junction sequence.

Proof: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver/tests -v` exits 0 with four tests (`cpu-tests.log` SHA-256 `81d4fb98c1c661349939b610f3776b91d803fb61a475060babdf220a47dd0b38`). `.venv-cpu/bin/python worker_check.py --assignment heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver --complete` exits 0 (`worker-check.log` SHA-256 `9b973458443d622ad23c68b9f2e6cae2e7b3a98f75057def94e8fd49005124a2`). Status remains partial.

Next CPU work: implement Native lane/designation acquisition and the paired center/outer route/controller on a verified selected cell layout, four synchronized source cameras, exact construction, saved finalizer and measurement contract; then run positive/negative compatibility and `process-saved` for the first selected case before sweeping the remaining cases, three risk-based fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Intention to prepare a turn must be sourced from an authored plan with exact actor/target/time binding; no intention is inferred from indicator state or outcome. Actual CARLA lane markings, lane adjacency, turn motion, source pixels and physical completion remain GPU checks after CPU preparation.
