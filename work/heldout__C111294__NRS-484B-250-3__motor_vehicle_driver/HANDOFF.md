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
