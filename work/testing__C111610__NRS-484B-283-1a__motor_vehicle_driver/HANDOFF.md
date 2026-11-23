# testing__C111610__NRS-484B-283-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.283(1)(a); with 484B.283(4) — Except as otherwise provided in NRS 484B.287 [NRS-484B-287-1c, NRS-484B-287-1d, NRS-484B-287-1e, LVMC-11-30-060-A, LVMC-11-30-060-B], 484B.290 [LVMC-11-30-140-B] and 484B.350 [LVMC-11-46-030]: When official traffic-control devices are not in place or not in operation, the driver of a vehicle shall yield the right-of-way, slowing down or stopping if need be so to yield, to a pedestrian crossing the highway within a crosswalk when the pedestrian is upon the half of the highway upon which the vehicle is traveling or onto which the vehicle is turning, or when the pedestrian is approaching so closely from the opposite half of the highway as to be in danger. As used in this section, “half of the highway” means all traffic lanes of a highway which are designated for traffic traveling in one direction, and includes the entire highway in the case of a one-way highway.
Assigned branch(es): Pedestrian on the half onto which ego turns..
Cell: C111610 (intersection, turn, pedestrian); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction checkpoint

- `case-plan.json` now lists seven exact cases and five controlled comparisons for the fixed left turn. It separates destination-half occupancy, complete device absence versus nonoperation/operation, opposite-half proximity requiring independent danger review, and source-classified crosswalk placement. This is a plan, not accepted coverage. The introductory NRS 484B.287, 484B.290 and 484B.350 exceptions remain explicitly source-reviewed rather than inferred. There is no frozen accepted recording or exact-law judgment range.
- `crosswalk.py` verifies original map/site and all destination-direction driving lanes, complete relevant official-device inventory, source classifications, separate participant identities, original frame joins and geometric projection. `native_setup.py` checks connected original lane waypoints, spawns separate CARLA actors lazily with cleanup and applies a source-gated engineering hold policy. `scenes/*.json` are seven nominal specifications awaiting original map binding; their coordinates are not asserted physical facts.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111610__NRS-484B-283-1a__motor_vehicle_driver/tests -v` passed 9 tests; output is `cpu-tests.log`, with SHA256 recorded in `result.json`. Positive and negative tests exercise source rejection, full directional-half lane inventory, frame join, spawn cleanup, participant position, fixed comparison conditions and device gating.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111610__NRS-484B-283-1a__motor_vehicle_driver --complete` passed static checks (`check-complete.log`). The same command with `--require-delivery-ready` failed at `Preparation acceptance failed: partial/missing packages remain` (`check-strict.log`), correctly reflecting partial status.
- Next CPU work: bind an original map/site survey to every scene, implement full 20 Hz Native capture and four-camera frame map, source-sealed saved finalizer, semantic proposals, execution manifest, per-case offline and source-bound positive/negative compatibility checks, saved processing, independent delivery audit and comparison receipts. Re-run exact strict gate. Physical CARLA realization and pixel visibility follow CPU preparation.
