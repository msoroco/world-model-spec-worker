# testing__C111610__NRS-484B-307-9a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(9)(a) — Where the signal is a steady red with a green turn arrow: Except as otherwise provided in paragraph (b) [NRS-484B-307-9b], vehicular traffic facing the signal may enter the intersection only to make the movement indicated by the green turn arrow, but must yield the right-of-way to pedestrians lawfully within an adjacent crosswalk and to other traffic lawfully using the intersection. Drivers turning in the direction of the arrow are thereby advised that so long as the turn arrow is illuminated, oncoming or opposing traffic simultaneously faces a steady red signal.
Assigned branch(es): Turn with adjacent-crosswalk pedestrian.
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-307-9a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The frozen evidence inventory has zero accepted recordings. `case-plan.json` now records six exact cases: `yield_pedestrian`, `continue_pedestrian`, `clear_crosswalk_turn`, `wrong_movement`, `yield_other_traffic`, and `continue_other_traffic` (each prefixed by the assignment ID). Four controlled comparisons cover pedestrian yield, pedestrian presence, arrow movement, and other-traffic yield. These are prospective cases, not completed recordings. Paragraph (b) applies to specified motorcycles, mopeds, trimobiles, cycles, and scooters, not the assigned motor vehicle driver. No judgment range for this exact law/actor appears in the frozen range file.

`native_turn.py` verifies original map, signal heads, crosswalk adjacency, permission source, route lanes, actor identities, frame continuity and measured movement. It constructs three Native actors through injected CARLA APIs only after source-sealed transforms and blueprints are checked, and destroys previously spawned actors on failure. It does not create official signals or infer lawful pedestrian/vehicle use from fixture labels. `comparison_audit.py` rejects missing fixed-source joins, missing measurements and unrealized differences.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-9a__motor_vehicle_driver/tests -v` exited 0 (6 tests); see `cpu-tests.log`, SHA256 182094487d492f2ee9e8f89e2bfe98546e158779a2b0b6b4e5d81056e20751c4. The exact strict gate remains failing because status is partial; see `cpu-strict-check.log`.

Remaining CPU work: implement case-specific finalization into the pinned runtime format; write semantic proposals/index; exact construction/configuration/measurement contracts and execution manifest; offline and positive/negative compatibility receipts for all six cases; saved-only processing, delivery acceptance, and comparison integration proofs. Rerun exact strict gate afterward. Remaining physical checks are original CARLA phase/actors, motion, pixel coverage and duration.

Additional controller and measured-precedence proof: `native_turn.py` now emits occupancy-dependent brake/throttle intents and audits each original-frame case for actual entry, route lane, lawful occupant and clearance order. Eight focused tests pass; current `cpu-tests.log` SHA256 819ce00c7b7cd18a045844bd510a6df9911baeacc50acaca6310acf37be25e57 supersedes the earlier six-test hash.

## 2026-11-23 saved-source audit checkpoint

`saved_turn.py` consumes a SHA256-sealed manifest, site, telemetry, camera profile and each original PNG. Production default enforces 600 consecutive original frames at 20 Hz across front/left/right/rear. It decodes every PNG, rejects missing/repeated/out-of-order/changed/corrupt/escaping sources, binds the existing `native_turn.py` measured turn case, and emits a comparison row from actual approach and entry observations. This is software preparation only; it does not establish official signal status or physical visibility.

Focused proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-307-9a__motor_vehicle_driver/tests -v` exited 0 with 12 tests; `cpu-tests.log` SHA256 9b18302a48a7d778135a1b378a4ddab9bc8dc63277b3aae0fdedb87251df73d1. The runtime preflight rerun exited 0 and is retained under `.runtime-work/c111610-9a-preflight.log`. Tests use a short source-shaped fixture; the production default remains 600 frames.

Remaining CPU work: canonical semantic proposals/index, exact manifest and six case bundles, positive/negative offline/compatibility proofs, runtime process-saved integration and delivery audit. The saved auditor is not yet wired to `runtime.py process-saved`. Preserve partial status.

The expanded CPU suite includes an exact 600-frame original telemetry and 2,400-image full PNG decode fixture. All 13 tests pass; the superseding `cpu-tests.log` SHA256 is 36e38a62404f7d7d9d619c00727fa709239f79cafe901f6e17a0acffdb2a230c. The assignment-scoped static gate exited 0 (`cpu-static-check.log`); the exact strict gate exited 1 (`cpu-strict-check.log`) because this truthful checkpoint is partial.
