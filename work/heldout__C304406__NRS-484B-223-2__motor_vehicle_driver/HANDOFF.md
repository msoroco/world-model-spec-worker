# heldout__C304406__NRS-484B-223-2__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-223-2, cell: C304406, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C304406__NRS-484B-223-2__motor_vehicle_driver/assignment.json` (f5fb9b129d7c026444219f3e595695032918e1bdf3c980a8143eab4133c3976d).

Exact law text: Upon a highway which has been divided into three clearly marked lanes, a vehicle must not be driven in the extreme left lane at any time. A vehicle on such a highway must not be driven in the center lane except: (a) When overtaking and passing another vehicle where the highway is clearly visible and the center lane is clear of traffic for a safe distance; (b) In preparation for a left turn; or (c) When the center lane is allocated exclusively to traffic moving in the direction in which the vehicle is proceeding and a sign is posted to give notice of such allocation.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C304406__NRS-484B-223-2__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C304406__NRS-484B-223-2__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- extreme-left-lane driving prohibited at any time
- center lane default prohibited
- center lane overtaking/passing with clear visibility and safe-distance traffic gap
- center lane preparation for left turn
- center lane exclusive same-direction allocation with posted sign

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 three-lane source geometry checkpoint

The frozen accepted-evidence inventory contains zero recordings. `case-plan.json` now plans nine exact cases and eight controlled comparisons spanning the extreme-left prohibition, center-lane default, passing visibility and clear-distance conjuncts, left-turn preparation, and exclusive same-direction allocation with posted notice. The occluded passing case needs a constructed obstruction in the eventual Native runner; a context flag alone is not sufficient. These cases remain unconstructed.

`three_lane_measurement.py` joins original 20 Hz ego and three named lane polygons and checks right, center, extreme-left ordering against the map traffic direction. It reports the fraction of the subject body overlapping each lane, including partial extreme-left and center overlap. `three_lane_context.json` separately addresses clearly marked lanes, passing, visible highway, clear safe distance, turn preparation, allocation direction and posted sign. Known true or false values require citations; unknown values remain null. Measured lane area does not establish visible markings, safe distance, posted sign or a legal verdict.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `48aadc1db48d9b0c290ef9db464f8b25f4e8c2dd684730378c8ab95a283bd6ed`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C304406__NRS-484B-223-2__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `cd214ecf86a95c652fd07ff65e57ad4e9007acb38e9927f7241bb5c41d9449f1`). The tests cover center and extreme-left body overlap, both travel directions, reversed lane ordering, uncited allocation, missing posted-sign context, missing original source and frame discontinuity. They are geometry fixtures only.

Next CPU work: Native three-lane map/actor acquisition and construction of the passing obstruction, traffic clearance and posted sign; four source cameras, saved finalizer and one selected exact offline/positive-negative compatibility/saved-processing proof; then linked cases, fallback candidates, proposals and independent audits. Keep `result.json` partial until its strict scoped gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C304406__NRS-484B-223-2__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result correctly remains partial (`strict-gate.log`).
