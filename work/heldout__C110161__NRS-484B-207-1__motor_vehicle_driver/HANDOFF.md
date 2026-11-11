# heldout__C110161__NRS-484B-207-1__motor_vehicle_driver CPU checkpoint

Law: NRS-484B-207-1, cell: C110161, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C110161__NRS-484B-207-1__motor_vehicle_driver/assignment.json` (3d4775f40455e9e592973ac849f9d6ad0086fe1478cd53ee720257419d49f87d).

Exact law text: The driver of a vehicle overtaking another vehicle proceeding in the same direction shall pass to the left thereof at a safe distance and shall not again drive to the right side of the highway until safely clear of the overtaken vehicle.

Accepted recording summaries to review: 0; inventory `inputs/heldout__C110161__NRS-484B-207-1__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C110161__NRS-484B-207-1__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- overtake a same-direction vehicle on left at varying measured clearance; safe distance remains a judgment
- remain left until safely clear versus early return to right; safely clear remains a judgment

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 source measurement continuation

The next incomplete partition-01 assignment now has four planned exact cases in `case-plan.json`: `__left_pass_wide` and `__left_pass_narrow` compare full-body left clearance while the same-direction vehicles are abreast; `__return_before_clear` and `__return_after_clear` compare the measured order of a rightward return and complete-body longitudinal clearance. The two comparison records declare what stays fixed. The frozen evidence inventory is empty, and the two statutory gaps are source-cited. “Safe distance” and “safely clear” remain legal judgments; the physical sweep dimensions are lateral gap and first-return longitudinal clearance, with no invented legal cutoff.

`overtake_measurement.py` reads retained 20 Hz original participant corners and road/actor headings. It rejects changed actor identity, incomplete frame timing, opposing direction, missing abreast frames and an absent rightward return. It reports the minimum left footprint gap over all abreast frames and the original-frame body clearance when the subject first returns right. It preserves a negative measured clearance as an early-return observation rather than treating it as a legal conclusion. `.venv-cpu/bin/python -m unittest discover -s work/heldout__C110161__NRS-484B-207-1__motor_vehicle_driver/tests -v` passes 3 tests (`cpu-tests.log`); `.venv-cpu/bin/python worker_check.py --assignment heldout__C110161__NRS-484B-207-1__motor_vehicle_driver --complete` passes static validation (`worker-check.log`). Status remains **partial**.

Next CPU work: construct the C110161 intersection and same-direction vehicles with explicit overtaking left and return controllers, retain the required road tangent/heading/body-corner source on every Native tick, add the four named cameras and raw-source finalizer, and make one primary case pass offline, positive/negative compatibility and saved-only processing. Then expand the comparison cases and three physical-risk fallbacks each, implement a source-bound comparison audit and semantic stage proposals, run physical/delivery acceptance fixtures and the assignment strict gate. Physical motion, sight lines and actual pixels remain later local checks, not excuses for the CPU work.
