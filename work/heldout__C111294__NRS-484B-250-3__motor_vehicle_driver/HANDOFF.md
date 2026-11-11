# heldout__C111294__NRS-484B-250-3__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-250-3, cell: C111294, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver/assignment.json` (24e209f870de9b286b901327faf3d6e109e3857a41d349abed5cea2c1a157320).

Exact law text: When two vehicles enter an intersection at approximately the same time, one vehicle traveling on a highway which ends at the intersection and the other vehicle traveling on a through highway, the driver of the vehicle on the highway which ends at the intersection shall yield the right-of-way to the other vehicle. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484B-250-3__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- two vehicles enter approximately together: ending highway yields to through highway
- separated arrival timing as applicability comparison
- official traffic-control device exception, unless subsection 4 applies
- opposite-direction approaching left-turn exception

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 topology and original-entry checkpoint

`ending_road_measurement.py` now requires a retained lane graph with a cited highway identity, a common junction, a subject approach with no same-highway continuation beyond it, and an other approach with a connected same-highway outgoing lane. It computes intersection occupancy from original body corners against a convex conflict polygon at 20 Hz, then reports entry-frame delta, occupancy overlap, and whether the subject entered after the through vehicle's last conflict frame. It rejects a falsely declared ending highway and bad frame joins. It does **not** turn “approximately the same time” or observed entry order into a legal finding. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111294__NRS-484B-250-3__motor_vehicle_driver/tests -v` passes three geometry/source tests (`cpu-tests.log`); `.venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484B-250-3__motor_vehicle_driver --complete` passes (`worker-check.log`). Status remains partial.

`case-plan.json` now names the ending-yields/ending-enters-first, separated-arrival, official-device-control, and opposite-direction-left-turn cases with four controlled comparisons and physical-risk triggers. The source inventory has no accepted recordings. The subsection 4 cross-reference and legal meaning of approximately simultaneous remain explicit uncertainties. The fixed C111294 travel cell may not support a real opposite left turn; inspect `inputs/coverage/candidate-cells.json` and add a compatible binding only if required by the final construction. Do not call an unsupported branch a GPU blocker.

Next CPU work: integrate the lane/topology check with an actual CARLA-lazy Native route/spawn/controller bundle, retain topology and body polygons from the original run, construct both approaches and a governing official device, and run the first exact case through offline, positive/negative compatibility and saved-only processing. Then complete the remaining exact cases, three physical fallbacks each, semantic proposals and independent delivery/comparison audits before the strict assignment gate. Actual map suitability, motion and pixels remain later operator checks.

`ending_road_comparison_audit.py` independently recomputes the two original entry traces, requires byte-identical retained lane topology and initial actor footprints, verifies a delayed-entry versus earlier-entry contrast, and rejects changed or missing originals. The assignment suite now passes 4 CPU tests; `cpu-tests.log` and `result.json` bind the new log hash. This is a source-shaped software comparison only, so the assignment remains partial until the exact Native and saved-processing proofs above pass.
