# testing__C150640__NRS-484B-413-3__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.413(3) — A driver shall not stop or suddenly decrease the speed of a vehicle without first giving an appropriate signal to the driver of any vehicle immediately to the rear.
Assigned branch(es): Intentional stop with a rear-driver recipient.
Cell: C150640 (one_way_road, stop_stand, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C150640__NRS-484B-413-3__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## CPU construction checkpoint

Added `rear_signal.py` with five exact probes: stop and sudden-decrease alternatives, signal before/after order, and a rear-driver-absence contrast. The lazy constructor requests the one-way route, stop footprint, rear participant and signal policy and cleans owned actors on failure. Original measurement joins 900 frames, participants, displayed signal/visibility, event onset, speed history and rear gap/offset. Signal appropriateness, immediately-to-rear and legal outcomes remain unresolved.

Four focused CPU tests pass, including all five cases and negative source, driver, identity, signal and cleanup paths. Pinned preflight and scoped static pass. Exact scoped strict exits 1 because this package remains partial. Frozen accepted recording inventory is empty; diagnostic values are synthetic only. Canonical capture/offline/compatibility, semantic proposals, independent saved delivery/comparison audits and physical source-backed scene are still worker-owned CPU work.

Proof SHA256:

- `rear_signal.py`: `10918dba0168aaa614144f083a85826f9a9daf81eb6b5db8195dddd83510a8e7`
- `tests/test_rear_signal.py`: `9400d928c2faf757c77eb78e1028158a7eaf9c3d200f35087ceeb6666054aede`
- `cpu-tests.log`: `cb4b6282868dbd033115f1afd8d2d6f19d9f762a13f38b9b1365852711dcf47e`
- `cpu-preflight.log`: `f84245a584a94eeb0a92a10ef649d0517bc7fb846f1c8bfa7f7209dd89518459`
- `cpu-static-check.log`: `aa925a6ca30c94a70b5610b5fe10cef1352bd5d8f9dad27988ef9325c8e73e82`
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
