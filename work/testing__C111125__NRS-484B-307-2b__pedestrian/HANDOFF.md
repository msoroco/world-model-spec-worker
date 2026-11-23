# testing__C111125__NRS-484B-307-2b__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.307(2)(b) — When the signal is circular green alone: Pedestrians facing such a signal may proceed across the highway within any marked or unmarked crosswalk, unless directed otherwise by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): Straight crosswalk route.
Cell: C111125 (intersection, straight, traffic_light); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Construction checkpoint, 2026-11-23

The five exact cases in `case-plan.json` are `marked_cross`, `unmarked_cross`, `other_device_stop`, `other_device_cross`, and `outside_cross`, all prefixed by the assignment ID. They cover the assigned straight route, marked/unmarked alternatives, other-device direction, and measured crosswalk membership. Three comparisons isolate those variables. The frozen evidence inventory contains zero accepted recordings; `case-plan.json.evidence_review.gaps` records the source-backed need. No numeric legal threshold is inferred. NRS 484B.283 device applicability still requires original-source review.

`native_crossing.py` verifies original map, official signal and device inventory hashes before constructing a pedestrian, checks cell/role, public highway and qualifying crosswalk source assertions, routes and polygon geometry, then measures original frame signal aspects, device indication and location. Spawn readback failure destroys the actor. `pedestrian_control.py` issues a pedestrian walk or wait command. `comparison_audit.py` rejects missing or drifted fixed sources and unobserved differences; it does not issue a legal verdict. `tests/test_crossing.py` checks source rejection, route construction, actor cleanup, measured events and positive/negative comparison branches.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-2b__pedestrian/tests -v` passed 13 tests; `cpu-tests.log` SHA256 a26159c78353f399e99de6c7b7cf33a30c8963ee8a7d8b9769af3a2b92ece2f8. `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2b__pedestrian --complete` passed static validation. `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-2b__pedestrian --complete --require-delivery-ready` failed as expected with `Preparation acceptance failed: partial/missing packages remain`; logs are `static-check.log` and `strict-check.log`.

Next CPU work: resolve the original NRS 484B.283 source provisions and device applicability; bind an actual map/head/device inventory to the site adapter; implement each case bundle, runner, config, measurement contract, source-hashed diagnostics, exact offline and positive/negative compatibility receipts, canonical semantic proposals, execution manifest, saved-only finalizer and independent delivery/pixel audit, then rerun the exact strict gate. Physical Native motion and camera visibility remain later GPU checks. No external blocker is claimed.

Follow-up source binding: `native_crossing.py` now reads and compares the sealed map polygon, crosswalk kind and qualification, public-highway assertion, official facing traffic-light head and complete other-device inventory before spawn. `tests/test_crossing.py` includes unmarked source qualification and missing-device inventory rejection. Latest CPU suite: 15 passed; `cpu-tests.log` SHA256 e53b1d3f8c2a39e4eb3afcd2ba8fd9244bf64a1af2309a4ec231bd3c88cfd7de. This supersedes the earlier 13-test log hash.

Saved-only measurement checkpoint: `saved_measurement.py --attempt-root ROOT --site-ref SITE_REF.json --events-ref EVENTS_REF.json --output OUTPUT.json` hashes the sealed site and frame history and rejects stale events before writing measured facts. This is not the canonical finalizer or accepted delivery audit. `tests/test_crossing.py` covers positive and stale-source rejection. Latest suite: 16 tests passed; `cpu-tests.log` SHA256 38c338120b13c376d92ccfb674f8bd846de7cd9e14191ec28247a0739af71912. This supersedes the prior log hash.
