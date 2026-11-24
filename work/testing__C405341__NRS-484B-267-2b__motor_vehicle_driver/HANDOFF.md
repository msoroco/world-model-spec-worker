# testing__C405341__NRS-484B-267-2b__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No original physical recording or legal conclusion is claimed.

NRS 484B.267(2)(b), with subsection 4, concerns proceeding with caution when approaching a qualifying authorized emergency or regulatory official vehicle that is moving or visibly preparing to move while using qualifying flashing lights, except when otherwise directed by law enforcement. The C405341 witness targets visible vehicle-movement preparation. Frozen accepted evidence contains zero exact-assignment recordings and zero exact-law judgment-range entries.

## Constructed CPU work

`case-plan.json` defines ten unexecuted exact variants and nine controlled comparisons. It isolates visible movement preparation from no movement, occlusion, hand signal, already-moving status, inactive/unqualified lights, law-enforcement direction, no approach, and a regulatory official vehicle. Every case requests original 20 Hz ego/target motion, light-use and subject controls, independent driver-view visibility annotation and four synchronized cameras. Target authorization and flashing-equipment qualification are independent source requirements.

`emergency_movement_observations.py` consumes a hash-sealed original Native context/receipt and 20 Hz ego/target trace. It checks exact identity, source hashes, frame cadence, target class, light qualification, officer direction, approach and subject sources. It reports target interframe displacement, ego-target distance and the first frame with nonzero movement annotated visible from the driver view. Nonzero movement is an observation, not an invented about-to-move cutoff. About-to-move and proceed-with-caution judgments stay unresolved; physical acceptance stays unverified. Seven focused tests cover positive extraction, occlusion and rejection of diagnostic, changed or incomplete sources.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C405341__NRS-484B-267-2b__motor_vehicle_driver/tests -v`: exit 0; `cpu-movement-tests.log` SHA256 `eb2bc743df2be91be3225a45214b5a7d36439bef250415a10f5a061534162f72`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2b__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `6c3da77e53e556af1a458efbf6491c3f490c7b094c25b07e4d4570764ed2ce4e`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2b__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build/prove the exact Native scene/controller, full original 20 Hz four-camera capture, source-bound finalizer and semantic proposal, saved compatibility/processing, and delivery/comparison audits. Establish actual driver-view visibility, equipment qualification and contextual about-to-move meaning from original sources before classification. Actual CARLA motion, lights and camera visibility remain physical checks after CPU preparation. No missing-tool or dependency blocker is asserted.
