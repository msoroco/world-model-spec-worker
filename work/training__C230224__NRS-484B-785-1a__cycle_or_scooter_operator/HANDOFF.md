# C230224 / NRS 484B.785(1)(a) handoff

Status: **partial**. Accepted memberships: 0. The frozen `road/travel/cycle_path` cell and `cycle_or_scooter_operator` actor are retained. Exact source law and source hashes remain in `case-plan.json`.

## Construction and proof

- `selected-primary-construction.json` (SHA-256 `480de6e8502097db4150448dbf42a39f952863474d8c3750da2b2d4c8c43d964`) is an inline Native primary for `__controlled_1`: a 600-frame, 20 Hz, four-camera electric-scooter path capture. `native/runner.py` requires a reviewed scooter blueprint/classification, mass at most 100 lb excluding rider, motor-only maximum at most 20 mph, path/road geometry and local ordinance sources. It rejects bicycle blueprint names and requests at or above the selected 15 mph operating cap. Actual speed is measured later, never inferred from request.
- `measure_scooter.py` (SHA-256 `9593d7a484ab6547146a76df215bda41635a81f063cb1bd3efab3c7623a2bef1`) joins 600 original frames to rider/device identity, device center, speed, reviewed path and ordinance context. For original source review it decodes all four cameras with `ffprobe`, requires 600 frames at 20 Hz, and binds review context to camera byte hashes. It returns no legal verdict.
- `prove_scooter.py` exercises 12 mph and 17 mph 600-frame source fixtures; it rejects bicycle identity, absent ordinance review, classification maximum above 20 mph and rider identity drift. `prove_saved.py` exercises four saved FFV1 streams with 600 joined frames and rejects a tampered camera hash. These are diagnostic fixtures, not Native recordings.
- Pinned `runtime.py preflight` passed (`pinned-preflight.log`). Pinned `runtime.py offline` passed for the exact primary (`scooter-cpu-2.log`); simulation was not started. Assignment-scoped `worker_check.py --complete` passed (`scoped-check.log`). `--require-delivery-ready` failed as expected because status remains partial (`strict-check.log`). CPU source proofs and optimized source proof passed.

## Remaining exact work

Build and offline-check the above-15-mph `__controlled_2` construction and distinct candidate bank; verify a genuine rideable electric-scooter Native asset and reviewed path geometry; obtain applicable ordinance/contrary posting sources; capture original 30-second Native sources; measure and audit both operating-speed cases against original evidence. The 20 mph motor-only classification criterion remains separate from the 15 mph operating cap. Roadway, bicycle-lane and route alternatives and the ordinance exception need their own dispositions. No physical or statutory outcome is claimed.

All scratch and temporary files for this work are under `.runtime-work/c230224-785-*`; no temporary directory is under `work/`.
