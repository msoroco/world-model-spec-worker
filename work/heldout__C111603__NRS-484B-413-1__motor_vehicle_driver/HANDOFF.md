# heldout__C111603__NRS-484B-413-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-413-1, cell: C111603, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/assignment.json` (42cc01f69660afb23a9167a02ab7151ddd33a1fee873db9920a705453a389cd8).

Exact law text: A driver shall not turn a vehicle from a direct course upon a highway unless and until such movement can be made with reasonable safety, and then only after giving a clearly audible signal by sounding the horn if any pedestrian may be affected by such movement and after giving an appropriate signal if any other vehicle may be affected by such movement.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C111603__NRS-484B-413-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- turn from direct course with measured physical clearance and reasonable-safety judgment retained
- pedestrian may be affected: audible horn signal versus none, with other conditions fixed
- other vehicle may be affected: appropriate signal versus none, with other conditions fixed
- both pedestrian and vehicle may be affected: both signals required

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.
