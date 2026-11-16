# C215286 CPU handoff — NRS 484B.113(2)

Status: **partial**. Fixed cell: residence-district reverse motion at a crosswalk. This assignment covers backing on or over a crosswalk. The frozen accepted-evidence inventory is empty.

`reverse_control.py` requests actual Native reverse control, reads it back and restores prior control. `crosswalk_reverse.py` joins original frames to source-backed crosswalk polygon and complete ego body, then measures on/over and fully-over positions while reverse is active. Three CPU tests pass for positive/negative body overlap, wrong crosswalk ID, stale frame and real control restoration. Actual motion, marked geometry and camera visibility remain unverified.

Next CPU work: source exact crosswalk and residence-district road; construct positive and stop-short reverse trajectories. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual backing and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C376646__NRS-484B-250-4__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## Backward motion and comparison checkpoint

`crosswalk_reverse.py` now computes each original complete-body center displacement projected onto the observed vehicle heading. It counts a crosswalk overlap only when displacement is backward and Native reverse readback is true at both ends of that interval. This avoids treating reverse gear alone, a stationary body or a late reverse command as proof of backing on the crosswalk. The projection sign is an engineering observation, not a numeric legal threshold.

`comparison_audit.py` independently analyzes the positive and short cases and requires the same hashed crosswalk context, starting body center, frame count and reverse-state schedule. It rejects a positive case without backward body entry or a short case whose body actually overlaps the crosswalk. The six-test CPU suite covers wrong heading, missing heading, stale frames, changed context, erroneous short-case overlap and reverse activation only at the overlap frame. These are small synthetic source fixtures; they do not establish real marked geometry or actual CARLA motion.

Current `.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v` passes six tests (`cpu-tests.log`, SHA-256 in `result.json`). Assignment `--complete` passes in `assignment-check.log`. The exact assignment strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete --require-delivery-ready` exits 1 in `strict-gate.log` with `Preparation acceptance failed: partial/missing packages remain`, because the package remains partial. Next CPU work is source-backed crosswalk/district construction and exact runner, four source cameras, saved finalizer, fallbacks, semantic proposals, recorded-only and exact compatibility proofs, and source-decoded delivery audit. These are unfinished work, not an external blocker.

## Hashed site sources for saved analysis

`site_review.py` now requires byte-hashed residence-district, crosswalk geometry and marking documents, a reviewed crosswalk polygon that intersects the selected roadway, and exact map/road/crosswalk identity. `crosswalk_reverse.analyze` requires that packet and all three original source files in the saved attempt; it rejects stale or missing documents and a polygon that differs from the retained context. The comparison audit also requires identical packet and source bytes across the positive and stop-short cases. The synthetic fixture tests stale marking, absent packet and changed marking source between cases. The source check does not determine whether a real site is legally a residence district or whether markings are actually visible.

Seven tests pass in `cpu-tests.log` with the current hash in `result.json`; assignment `--complete` passes. The strict assignment gate exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. A real reviewed site packet, integrated exact runner/four cameras, saved finalizer, fallbacks, semantic proposals, exact runtime receipts and independent delivery audit remain unfinished CPU work. No external blocker is asserted.

## Distinct constructed reverse targets

`reverse_route.validate_pair` now translates the same starting complete body along the same reverse axis to two planned distances. It requires the positive target body to intersect the sourced crosswalk and the short target body to remain clear, with both targets beyond a clear start. `ReverseTargetController` uses the selected target distance and observed body-center progress to apply Native reverse throttle or braking. It begins braking using an engineering stopping-distance estimate; actual deceleration, stopping position and crosswalk overlap remain physical checks. The construction varies the intended reverse stopping point while retaining the same approach, vehicle and crosswalk.

The eighth CPU test checks both target geometries, target completion, early braking and rejected invalid targets. Eight tests pass in `cpu-tests.log`, and `result.json` binds its current hash. Assignment `--complete` passes; strict readiness still exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. The controller is not yet integrated into a CARLA runner; a reviewed real site packet, four cameras, saved finalizer, exact proofs, fallbacks, proposals and delivery audit remain worker-owned CPU work.

`reverse_route.prepare_reviewed_pair` additionally joins the target geometry to the hashed site packet and exact Native map/road/crosswalk identity. The synthetic test exercises this joined preparation. This does not replace the absent real reviewed packet or a Native run.

## Pinned physical checker field alignment

The saved reverse analyzer now requires the same original row fields used by the pinned `worker_exchange.native_output` reverse-goal checker: `body_vertices_m`, `heading_deg` and `velocity_mps`. It rejects a body or heading that differs from the crosswalk measurement fields and a Native velocity that contradicts observed backward displacement. A ninth CPU test runs the pinned `assess_physical` reverse-goal branch on source-shaped frames, observes `setup: met` and `maneuver: met` for the synthetic route, then confirms missing velocity yields `maneuver: unverified`. This tests software field compatibility only; the synthetic body and velocity are not Native motion evidence.

Nine assignment tests pass in `cpu-tests.log` with its current hash in `result.json`; assignment `--complete` passes. Strict assignment readiness exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. Remaining CPU work is unchanged: reviewed real site packet, integrated exact runner/four cameras, saved finalizer, fallbacks, proposals, full runtime proofs and delivery audit.
