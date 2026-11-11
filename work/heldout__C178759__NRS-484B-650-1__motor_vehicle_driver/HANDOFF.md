# heldout__C178759__NRS-484B-650-1__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.650(1) — A driver commits an offense of aggressive driving if, during any single, continuous period of driving within the course of 1 mile, the driver does all the following, in any sequence: (a) Commits one or more acts of speeding in violation of NRS 484B.363 or 484B.600 [NRS-484B-363-1, NRS-484B-363-2, NRS-484B-600-1a, NRS-484B-600-1b, NRS-484B-600-1c, NRS-484B-600-1e]. (b) Commits two or more of the following acts, in any combination, or commits any of the following acts more than once: (1) Failing to obey an official traffic-control device in violation of NRS 484B.300 [NRS-484B-300-1]. (2) Overtaking and passing another vehicle upon the right by driving off the paved portion of the highway in violation of NRS 484B.210 [NRS-484B-210-3]. (3) Improper or unsafe driving upon a highway that has marked lanes for traffic in violation of NRS 484B.223 [NRS-484B-223-1b, NRS-484B-223-2, NRS-484B-223-3a, NRS-484B-223-3b, NRS-484B-223-3c, NRS-484B-223-4a, NRS-484B-223-4b]. (4) Following another vehicle too closely in violation of NRS 484B.127 [LVMC-11-12-080-A, NRS-484B-127-2, NRS-484B-127-3]. (5) Failing to yield the right-of-way in violation of any provision of NRS 484B.250 to 484B.267, inclusive [NRS-484B-250-1, NRS-484B-250-2, NRS-484B-250-3, NRS-484B-250-4, NRS-484B-253, NRS-484B-257-1, NRS-484B-257-2, NRS-484B-260, NRS-484B-263, NRS-484B-267-1a, NRS-484B-267-1b, NRS-484B-267-1c, NRS-484B-267-2a, NRS-484B-267-2b, NRS-484B-267-2c, NRS-484B-267-2d, NRS-484B-267-2e, NRS-484B-267-2f]. (c) Creates an immediate hazard, regardless of its duration, to another vehicle or to another person, whether or not the other person is riding in or upon the vehicle of the driver or any other vehicle.
- Cell/actor: C178759 / motor_vehicle_driver; layout `paved_road`, maneuver `overtake_right`, control `other_vehicle`.
- Exact input: `inputs/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/assignment.json` (SHA256 `462017cc248d05f689e74d207d3afb650a0cfeefcdb2799662e80902f0a32f3a`).
- Witness: `inputs/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: kin.path_length, kin.speed, dev.speed_limit_sign, dev.traffic_signal, drv.overtaking, st.shoulder, drv.lane_change, drv.following, drv.time_gap, drv.yields_to, drv.time_to_conflict, kin.time.

## Required source and construction review

1. Establish another vehicle or person and physical evidence bearing on driver-created hazard.
2. Establish the same driver and continuous driving period, qualifying vehicle and highway status.
3. Identify the fixed other vehicle as a vehicle overtaken on the right and specify supported trajectories for two separate passing episodes.
4. Identify the fixed other vehicle as the vehicle overtaken on the right.
5. Map paved highway, roadway, traveled portion and shoulder boundaries separately, including traversable space outside the paved portion.
6. Measure the distance enclosing all conduct within the statutory course of 1 mile.
7. Measure the event-enclosing distance within the course of 1 mile without requiring a full mile of travel.
8. Provide NRS 484B.210 operative requirements and exceptions and applicable speeding authority.
9. Provide traversable space outside the paved highway and map paved, roadway and traveled-portion boundaries separately.
10. Retain another vehicle or person interaction and evidence bearing on creation of the hazard.
11. Same driver performs two separately documented right-passing episodes during one continuous period.
12. Supply operative NRS 484B.210 requirements and exceptions and applicable NRS 484B.363 or NRS 484B.600 authority; full incorporated texts remain unresolved.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C178759__NRS-484B-650-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C178759__NRS-484B-650-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-11 event-envelope construction checkpoint (latest)

Status remains **partial**. `aggressive_sequence.py` now implements a source-joined original-frame measurement for a single continuous driver, cumulative traveled path, the first-to-last conduct envelope, and separate rightward off-pavement order-reversal episodes. It uses 1609.344 m for one mile and returns an event-enclosing distance; it does not require a full mile of driving or decide speeding, passing lawfulness, immediate hazard, or the composite offense. It rejects frame gaps, driver changes, unbound conduct frames, unsupported rightward reversals, missing off-pavement frames and overlapping episodes. `test_aggressive_sequence.py` exercises below/at/above one mile and the rejection branches; `cpu-sequence-tests.log` shows two passing tests.

This helper is not yet wired to a Native capture or saved finalizer. The next CPU construction is an exact first case with paved-road versus traveled-portion boundaries, the overtaken vehicle and independently sourced speed/hazard facts retained per original frame. Build its four-camera Native runner, source packet, measurement contract and saved-only finalizer; pass offline and positive/negative compatibility, then add two separated right-pass episodes and the other required comparisons/fallbacks. Do not pass derived event flags as original pavement evidence or treat a time-to-conflict value as a legal hazard cutoff. The scoped `worker_check.py --assignment heldout__C178759__NRS-484B-650-1__motor_vehicle_driver --complete` passes as a partial checkpoint; the strict gate remains unsatisfied by design.
