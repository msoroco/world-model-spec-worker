# testing__C130864__LVMC-11-43-010-B__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.43.010(B) — The following regulations pertain to the operation of vehicles within a roundabout: The operator of a vehicle entering a roundabout shall yield the right-of-way to vehicles already in the roundabout and wait for a gap in traffic before entering.
Assigned branch(es): Multilane roundabout entry with an already-present vehicle..
Cell: C130864 (multilane_roundabout, enter_roundabout, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C130864__LVMC-11-43-010-B__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 exact-case and source-bound roundabout checkpoint

The exact ordinance requires an entering operator to yield to vehicles already in the roundabout and wait for a traffic gap before entering. The frozen multilane witness is accept_conditional and requires the actual entry lane, connected circulating lane, opponent lane/route, possible conflict and jurisdiction. `case-plan.json` now holds six exact targets: connected/adjacent opponent lane wait and enter, plus connected lane wider-requested-gap wait and enter. Five comparisons isolate entry behavior, opponent lane relation and requested initial gap. No numeric gap is a legal threshold. No accepted recording is listed in frozen evidence.

`roundabout_measurements.py` validates source-hashed original map/trace/receipt bytes. It requires two inventoried circulating lanes, a connected ego entry lane, actual opponent route and inside-ring initial point, jurisdiction and conflict-region source references, ring and conflict polygons, original eight-vertex vehicle bodies, and ordered 20 Hz frame/time/speed histories. It measures first sampled ego ring entry, circulating/opponent conflict occupancy at that frame, pre-entry stopped frames and body separation. It leaves right-of-way and gap judgment unresolved; synthetic fixtures cannot prove real map geometry or camera visibility.

Eight focused CPU tests passed in `cpu-roundabout-tests.log`, including CLI replay and rejection of unconnected lane, opponent outside ring, absent conflict source, changed bytes, dropped frames, missing original body and diagnostic provenance. Static scoped check passed in `assignment-check.log`. Exact scoped strict check failed on truthful partial status in `strict-gate.log`. Current passing proof hashes are in `result.json`. Next CPU work: bind a reviewed real Native roundabout packet and six executable scene/controller bundles, synchronize and audit four cameras, author finalizers/proposals, run exact offline/positive-negative compatibility and saved-delivery/comparison proofs. Physical motion, realized traffic gaps and pixel visibility await later local verification.
