# testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator

Status: partial construction and audit draft. Six exact cases are planned; no Native recording or physical acceptance is claimed.

Exact law: NRS 484B.307(9)(b) — Where the signal is a steady red with a green turn arrow: A person driving a motorcycle, moped or trimobile or riding a bicycle, an electric bicycle or an electric scooter facing the signal may proceed straight through or turn in the direction opposite that indicated by the green turn arrow if: (1) The person stops before entering the crosswalk on the nearest side of the intersection where the sign or pavement marking indicates where the stop must be made or, in the absence of any such crosswalk, sign or marking, before entering the intersection; (2) The person waits for two complete cycles of the lights or lighted arrows of the applicable official traffic-control device and the signal does not change because of a malfunction or because the signal failed to detect the presence of the motorcycle, moped, trimobile, bicycle, electric bicycle or electric scooter; (3) No other device at the place prohibits the turn, if applicable; and (4) The person yields the right-of-way to pedestrians lawfully within an adjacent crosswalk and to other traffic lawfully using the intersection.
Assigned branch(es): Straight-through permission.
Cell: C111125 (intersection, straight, traffic_light); actor: motorcycle_or_moped_operator.
Frozen accepted recordings reviewed at metadata level: 0. `case-plan.json.evidence_review` identifies the empty inventory and exact missing original evidence.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Resolve source-surveyed C111125 Native map, official composite steady-red plus green-arrow head, exact stopping-reference hierarchy and motorcycle blueprint; make the source packet used by `signal_exception.py` for each case. Its detector/malfunction packet must document a positive causal source; unchanged light alone is insufficient.
2. Build the six exact runner/config/construction/finalizer bundles and measurement contracts for `case-plan.json.cases`. Connect the tested source-gated `signal_exception.py` controller and measurement to original capture and saved processing. Add lawful-status source facts and participant motion for the pedestrian and traffic cases.
3. Produce canonical semantic proposals, exact offline and positive/negative compatibility receipts, saved-only receipts, independent pixel review and risk-triggered candidate receipts. Bind `comparison_audit.py` and `delivery_audit.py` to the saved attempt path; expand tests to those integration paths.
4. Rerun the exact strict gate and mark ready only if it passes. Keep original inputs and runtime frozen.

## Implemented coverage and CPU proofs

`case-plan.json` maps the fixed straight task to `two_cycles_clear`, `one_cycle_entry`, `rolling_entry`, `no_causal_record`, `pedestrian_crosswalk`, and `lawful_traffic`. Five comparisons cover complete-cycle timing, stop evidence, causal failure evidence and yielding to crosswalk pedestrians and other traffic. The rolling case cannot have two cycles *after* a stop that never happened; its separate approach-phase cycle target is explicit, and the comparison records that resulting temporal coupling. The opposite-arrow turn named by the statute is outside this fixed straight cell; a separate compatible turn cell is needed for that branch in the shared branch matrix.

`signal_exception.py` source-seals the map/route/head/stop/crosswalk/cause packets, requires the fixed actor and straight route, verifies Native map/head/blueprint readback before spawn, measures original stop and composite aspect-return cycles, and applies a conservative hold/yield controller. The causal packet must affirm malfunction or missed detection with a supported original method and matching head, actor and interval. `comparison_audit.py` checks fixed source hashes and deliberate measured differences without legal verdicts. `delivery_audit.py` checks an independent saved attempt for sealed original sources, 900 contiguous frames, head/actor continuity and four synchronized 20 Hz camera inventories; a later pixel review must establish legibility and visibility.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator/tests -v` passed 11 tests. See `cpu-tests.log` and its SHA-256 in `result.json`. The tests use small source-shaped fixtures and fake Native world injection, not a CARLA run. Exact strict assignment check fails with `Preparation acceptance failed: partial/missing packages remain`, as expected for the truthful partial status; see `cpu-strict-check.log`.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.
