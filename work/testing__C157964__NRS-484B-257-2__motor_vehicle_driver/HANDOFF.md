# C157964 CPU handoff — NRS 484B.257(2) officer cell

Status: **partial**. The fixed cell is a one-way-to-two-way straight crossing with `police_officer` control. Subsection 2's signed-entrance duty is excepted when an officer actually controls traffic; officer presence alone is insufficient. The within-intersection other-vehicle case and approaching-immediate-hazard sweep remain distinct. Frozen accepted-evidence inventory is empty.

`officer_construction.py` calls Native `world.try_spawn_actor` at a surveyed junction position and cleans up. `officer_yield_exception.py` joins original officer-direction frames to ego entry and other complete-body occupancy, requiring sourced sign inventory, non-through status and a non-obligated other entrance. Three CPU tests pass, including active/inactive control, stale frame, missing direction source and real performer spawn. These tests do not prove police authority, an actual directing gesture or immediate hazard.

Next CPU work: source authority and all sign entrances; construct visible officer directions and non-obligated crossing/approaching vehicle trajectories. Implement exact runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual control/visibility remain later checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C157964__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C157964__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C158196__NRS-484B-257-2__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## 2026-11-25 visible officer direction construction

`officer_direction.py` now provides exact per-frame `officer_controls_go`, `officer_controls_hold`, and `officer_present_inactive` programs. The go case commands stop for the first half of a 20 Hz capture and go for the second half; hold remains stop; inactive issues no direction. Its Native walker bone adapter applies reviewed named arm rotations, reads back each selected bone and rejects unsupported bones or mismatched poses. `tests/test_officer_direction.py` exercises all three programs, a fake Native bone application/readback and missing-bone rejection. The full package suite now passes five tests, and scoped nonready `worker_check.py --complete` passes. This is actuator software only: a programmed/read-back pose is separate from original-camera visibility, police authority and actual traffic control. Next integrate the adapter with an exact runner, officer/ego/other actor trajectories and four source cameras before finalizer and case proofs. Status stays partial.

`officer_ego_controller.py` now separates the three selected behavior branches: an active go pose releases ego after the programmed stop interval, active hold brakes, and inactive officer presence follows the signed-entrance path using explicit within-intersection and approaching-traffic source booleans. It bounds throttle/brake, rejects missing source booleans and applies a real `carla.VehicleControl` through the supplied Native API. `tests/test_officer_ego_controller.py` exercises go/hold/inactive, approach hazard hold, missing source, and fake Native apply-control. The full C157964 subsection 2 suite now passes seven tests; scoped nonready check passes. The controller is not yet called from a complete runner, and the booleans do not decide the statutory immediate-hazard judgment. Next integrate actual original-frame actor/body sampling and controller calls with four-camera capture and a source-reviewed entrance/officer packet; preserve legal uncertainty.

## 2026-11-25 source-bound officer intake

`officer_source_intake.py` now checks exact SHA-256 bindings for road, all-entrance sign inventory, officer authority and actual control review, other route, and original-camera sight review. It rejects changed/unsafe files, missing non-through review, unsigned ego entrance, obligated other entrance and absent officer authority/control review. The intake returns legal exception and immediate-hazard judgments as unresolved. Three new CPU tests exercise the structural accepted fixture, changed sources, missing authority, bad other entrance and unsafe path; ten package tests pass. The fixture is software-only and no selected reviewed site packet exists yet. Continue with exact Native runner integration and source-reviewed physical packet acquisition; do not infer authority from the performer. Status remains partial.

## 2026-11-25 synchronous officer capture step

`officer_capture_step.py` now requires a reviewed source intake, a source-bound other-body and approaching-hazard sample, applies the programmed Native officer pose and ego control, ticks the Native world, and binds `overview`, `approach`, `reference_corner`, and `driver_reference` raw camera frame references to the exact returned CARLA frame. It rejects absent intake/traffic sources, missing cameras, frame mismatches and missing speed readback. Its output keeps observed direction and actual police control `unreviewed`, distinct from applied commands. Two new tests cover the complete fake Native step and negative source/camera branches; the package suite passes 12 tests. This is one frame of an integrated runner, not a persisted full capture or source-reviewed physical result. Next build sensor recording, complete trajectories and saved finalizer before exact-case proofs. Status remains partial.
