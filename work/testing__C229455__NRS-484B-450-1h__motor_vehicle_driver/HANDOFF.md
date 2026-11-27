# testing__C229455__NRS-484B-450-1h__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.450(1)(h) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Between a safety zone and the adjacent curb or within 30 feet of points on the curb immediately opposite the ends of a safety zone.
Assigned branch(es): Parking between a safety zone and adjacent curb..
Cell: C229455 (road, park, safety_zone); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229455__NRS-484B-450-1h__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-27 source-gated CPU package

Exact original text: NRS 484B.450(1)(h), source `inputs/testing__C229455__NRS-484B-450-1h__motor_vehicle_driver/assignment.json`. Frozen `evidence.json` lists zero accepted recordings. Witness index 440 is a conditional, low-confidence proposal and is not accepted physical evidence. No exact-law judgment range occurs in the frozen range snapshot.

The twelve selected case IDs are:

- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_park` — between, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__outside_corridor_park` — outside, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__west_end_below_30ft` — end_band, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__west_end_at_30ft` — end_band, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__west_end_above_30ft` — end_band, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__east_end_below_30ft` — end_band, park, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_stop` — between, stop, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_stand` — between, stand, none.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_stop_conflict` — between, stop, conflict_avoidance.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_park_law` — between, park, law.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_stand_officer` — between, stand, officer_direction.
- `testing__C229455__NRS-484B-450-1h__motor_vehicle_driver__between_park_device` — between, park, official_device.

The ten controlled comparison IDs are: `between_vs_outside`, `west_below_vs_at`, `west_at_vs_above`, `west_vs_east_below`, `park_vs_stop`, `park_vs_stand`, `ordinary_vs_conflict`, `ordinary_vs_law`, `ordinary_vs_officer`, `ordinary_vs_device`. `west_end_below_30ft`, `west_end_at_30ft`, and `west_end_above_30ft` retain 9.044, 9.144 and 9.244 m original body-centre stations at the curb point opposite the west end. The east-end case probes the other end at the same below-boundary station. These physical measurements do not select a legal distance convention.

`safety_zone.py` computes bounded body placement and signed end station and verifies exact scene variables; `site_review.py` requires a reviewed original source packet for the highway, official pedestrian-exclusive designation, visible markings/signs, curb, both ends, route, traffic and authority. Markers cannot establish legal designation. `native_zone.py` spawns four zone boundary props, ego and traffic, runs 45 seconds at 20 Hz, joins four cameras and original frame map, writes source-hashed histories, and restores world settings. `analysis.py` is saved-only and rejects missing or changed original sources. `delivery_audit.py` independently checks original source custody, 900-frame joins, selected terminal body placement/station, full video decode receipt, physical completion and actual pixels. `comparison_audit.py` requires accepted original reports, checks fixed source hashes/cameras/duration and each declared difference.

Proofs: 24 selected/fallback exact offline and case-specific positive/negative compatibility receipts in `cases/`; 12 saved-only proofs in `proof-saved-*.log`; 12 physical/lifecycle receipts in `physical-*-receipt.json`; 12 delivery positive/negative protocol logs in `delivery-*.log`; ten comparison positive/changed-source negative logs in `comparison-*.log`; six focused tests in `cpu-tests.log`. The diagnostic fixtures are synthetic and make no physical or legal acceptance claim. `gpu-queue-proposal.json` proposes exact local prepare/execute/accept, owner release, saved processing, original source audit and comparison commands.

Resume local execution only with a reviewed original site packet and the original CARLA environment. Then independently inspect designation, curb adjacency, both opposite-end references, body footprint, halt and exception circumstances, full four-view pixels and delivered Core/video before acceptance. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229455__NRS-484B-450-1h__motor_vehicle_driver --complete --require-delivery-ready` for the CPU package.

The scoped strict CPU gate passed on 2026-11-27 after byte-exact compatibility logs were restored from their proof runs and the canonical semantic proposal linked west-end below, at and above probes to the exact 30-foot condition. The command was `PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c229455-check .venv-cpu/bin/python worker_check.py --assignment testing__C229455__NRS-484B-450-1h__motor_vehicle_driver --complete --require-delivery-ready`; it exited 0 with `static_checks_passed: true`. These are CPU preparation proofs; the original GPU delivery checks listed above remain pending.
