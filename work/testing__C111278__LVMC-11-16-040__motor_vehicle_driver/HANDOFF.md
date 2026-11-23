# testing__C111278__LVMC-11-16-040__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.16.040 — The prima facie speed limit shall be fifteen miles per hour when traversing any intersection or street or highway if during the last one hundred feet of his approach to such intersection the driver does not have a clear and unobstructed view of such intersection and of any traffic upon all of the streets or highways entering such intersection for a distance of one hundred feet along all such streets or highways, except on a through street or highway or at a traffic-controlled intersection.
Assigned branch(es): Sight-conditioned traversal with neither stated exception..
Cell: C111278 (intersection, travel, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

Exact law: LVMC 11.16.040 is a 15 mph **prima facie traversal** value conditioned on view during the last 100 feet of approach, extending 100 feet along every entering street/highway. The through-road and traffic-controlled-intersection exceptions are distinct; no approach-speed duty or legal cutoff for view was invented. Frozen evidence.json has zero accepted recordings.

`case-plan.json` now has six exact case IDs (`blocked_below`, `blocked_at`, `blocked_above`, `clear_at`, `through_blocked`, `controlled_blocked`) and four comparisons (`speed_boundary`, `sight_condition`, `through_exception`, `control_exception`); each ID is prefixed by this assignment ID. Every case retains a physical-risk assessment. The blocked variants depend on a map-reviewed west-arm occluder site and actual source rays; no fallback is claimed without tested construction and receipts.

`sight_construction.py` validates jurisdiction, qualifying street intersection, all entering arms, route distance, source-backed through/control designations and map/occluder identity before lazy CARLA spawn. Caller owns spawned actor cleanup. `sight_measurement.py` rejects incomplete/noncontiguous original frames, missing 100-foot approach endpoints, an omitted entering arm, short ray extent, absent per-frame ray provenance or missing traversal. It retains actual measured traversal speed relative to 15 mph and gives no legal conclusion. `delivery_audit.py` joins exact case, map, four source camera files and SHA256, 900 contiguous original frames, candidate receipt and measurement provenance.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` exits 0; `cpu-tests.log` SHA256 46165d8706eba4647e1a54c7dda79927816330219136a54e52e41bd3a51b1625. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passes static checkpoint. Exact strict command with `--require-delivery-ready` exits 1 at partial/missing acceptance (see `cpu-strict-check.log`).

Next CPU actions: bind a reviewed Native map and site source packet; implement case-specific CARLA runner/controller and original capture, saved finalizer, full config/construction/measurement contracts and semantic proposals; generate exact offline and positive/negative compatibility receipts and saved-only process tests for all six cases; build and independently test comparison/pixel audits; create execution manifest and queue. Then rerun exact strict assignment check. Actual CARLA visibility, motion and media quality remain subsequent GPU checks.
