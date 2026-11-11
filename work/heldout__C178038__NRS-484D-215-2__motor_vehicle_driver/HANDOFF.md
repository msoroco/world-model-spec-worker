# heldout__C178038__NRS-484D-215-2__motor_vehicle_driver CPU checkpoint

Law: NRS-484D-215-2, cell: C178038, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C178038__NRS-484D-215-2__motor_vehicle_driver/assignment.json` (2f105d16236025597cabc7739a57b53a7442fc2321118497538a014738ce3687).

Exact law text: Whenever a motor vehicle is being operated on the traveled portion of the highway, or shoulder adjacent thereto, during the times specified in NRS 484D.100 [NRS-484D-100-1], the driver shall use a distribution of light, or composite beam, directed high enough and of sufficient intensity to reveal persons and vehicles at a safe distance in advance of the vehicle, subject to the following requirements and limitations: Whenever the driver of a vehicle follows another vehicle within 300 feet to the rear, the driver shall use a distribution of light permissible under this chapter other than the uppermost distribution of light specified in subsection 1 of NRS 484D.210 [DEF-NRS-484D-210-1-2].

Accepted recording summaries to review: 0; inventory `inputs/heldout__C178038__NRS-484D-215-2__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C178038__NRS-484D-215-2__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- nighttime or other NRS 484D.100 activation context with follower within/below/at/above 300 ft
- within 300 ft: uppermost beam versus permitted lower distribution
- traveled portion versus adjacent shoulder
- outside 300 ft comparison without treating it as permission to use an otherwise impermissible beam

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.
