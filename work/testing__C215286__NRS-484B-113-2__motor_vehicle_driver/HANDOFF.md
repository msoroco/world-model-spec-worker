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

## Integrated primary selected case checkpoint

The primary `reverse_over_crosswalk` construction now contains an executable lazy CARLA runner, four named raw camera streams, source-bound reverse history, saved finalizer, and synthetic site documents. The runner reads the Native map, road and start geometry, controls actual reverse, preserves original frame/video joins and seals restoration; its `--check` path needs no simulator. The site documents in this construction are explicitly diagnostic, so the residence-district and marked-crosswalk claims still need independent real-source review.

Twelve assignment unit tests pass (`cpu-tests.log`; SHA-256 in `result.json`). Exact `runtime.py offline` passes at `.runtime-work/c215286-primary-offline-v3` (`exact-offline.log`). Exact positive/negative `runtime.py compatibility` passes at `.runtime-work/c215286-primary-compat-v6` (`compatibility.log`, `primary-compatibility-receipt.json`), including original-source finalization, source camera decode, Native result validation, graph conversion, pinned Lean decoder and render. Deleting `reverse_history.jsonl` fails with the specified missing-source error. Exact recorded-only `runtime.py process-saved` passes at `.runtime-work/c215286-primary-saved-v1` (`process-saved.log`, `processing-receipt.json`), rebuilding from retained sources. These are synthetic software proofs, not Native trajectory, legal-site or visibility acceptance.

`execution-manifest.json` binds the current construction, commands and copied receipts. Assignment-scoped `worker_check.py --complete` passes (`assignment-check.log`). Scoped strict readiness exits 1 with `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`) because `result.json` correctly remains partial. Remaining CPU work: replace the synthetic site packet with reviewed real district, crosswalk geometry and visible-marking sources; build the stop-short selected case and fixed-source comparison; add and test three distinct physical-risk fallbacks per case; complete semantic, physical-preparation and independent full-duration delivery audits; rerun exact proofs after any construction/finalizer change. Actual Native run and camera visibility remain later physical checks.

Pinned `worker_exchange.package_compatibility.check_receipts` passes against the current copied primary receipt, diagnostic fixture, selected measurement report, missing-source log, and acquisition map. The four camera videos and Native graphs in that recipe are synthetic; the software receipt does not prove physical capture.

## Stop-short selected case and matched-source comparison

`cases/reverse_stops_before_crosswalk-construction.json` selects the same runner, vehicle, site packet, source cameras and 45-second capture, changing the authored reverse target from 6.0 m to 2.0 m. The stop-short synthetic diagnostic starts with the same complete body and reverse schedule as the over-crosswalk diagnostic, then backs 2.5 m while retaining a clear complete body. This fixture is a software check; actual Native stopping distance is unresolved.

The stop-short case passes exact `runtime.py offline` at `.runtime-work/c215286-short-offline-v1` (`cases/short-offline.log`), positive/negative `runtime.py compatibility` at `.runtime-work/c215286-short-compat-v1` (receipt and negative log under `cases/`), and recorded-only `runtime.py process-saved` at `.runtime-work/c215286-short-saved-v1` (receipt under `cases/`). The pinned `package_compatibility.check_receipts` passes for both selected cases with current construction hashes, diagnostic recipes, source measurements, negative missing-source logs and acquisition maps.

`comparison_audit.audit` passes against both retained compatibility attempts and writes `cases/comparison-receipt.json`: nine paired original frames, identical hashed crosswalk context and site documents, identical starting complete body and reverse-state schedule; backward body motion enters the crosswalk only in the over-crosswalk case. The audit rejects changed site or a short-case overlap in its unit test. This comparison is diagnostic, with physical and legal acceptance explicitly unresolved.

Twelve tests pass (`cpu-tests.log`; current SHA-256 in `result.json`). Remaining CPU work is reviewed real district/crosswalk/marking sources, three distinct risk-triggered fallbacks per selected case and their exact proofs, semantic chain, physical-preparation proof and independent full-duration delivery audit. Retain partial status until these and the scoped strict gate pass.

## First distinct physical-risk fallback

`cases/reverse_over_fallback1-construction.json` keeps the same over-crosswalk case, source packet identity, camera plan, measurement procedure and 45-second capture. If the primary Native attempt's original complete body stops clear of the sourced crosswalk before the attempt ends, this fallback lengthens only `site_packet.target_distances_m.over` from 6.0 to 7.0 m. It is an engineering control response to a measured shortfall, with actual deceleration and body entry still unresolved until Native capture.

Exact `runtime.py offline --candidate fallback1` passes at `.runtime-work/c215286-over-fallback1-offline-v1`; positive/negative `runtime.py compatibility --candidate fallback1` passes at `.runtime-work/c215286-over-fallback1-compat-v1`; recorded-only `runtime.py process-saved` passes at `.runtime-work/c215286-over-fallback1-saved-v1`. Logs and copied compatibility/saved receipts are in `cases/` and bound in `execution-manifest.json`. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=2)` passes for this selected case. The fallback diagnostic reuses synthetic source observations to test software compatibility; it does not prove that a Native vehicle reaches the longer target.

Five distinct risk-triggered fallbacks remain across the two selected cases, followed by exact proofs and independent delivery audit. Real reviewed site sources, semantic and physical-preparation checks also remain. The assignment stays partial.

## Complete over-crosswalk fallback set

`fallback2` selects the alternate `vehicle.tesla.model3` blueprint if the primary `vehicle.audi.tt` subject cannot spawn. It fixes the starting pose, route, crosswalk source and four-camera contract. `fallback3` raises the overview camera from 35 to 42 m above the site start and moves the reference-corner camera from `(8,8,8)` to `(12,12,12)` m relative to the crosswalk when the original complete body or markings are clipped; the selected case, route, source packet and recording observations remain fixed. Both triggers require original Native status or source video before selection. No fallback is considered physically successful from synthetic media.

Each new fallback passes exact `runtime.py offline`, positive/negative `runtime.py compatibility`, and recorded-only `runtime.py process-saved` in its `.runtime-work/c215286-over-fallback{2,3}-*` attempt. `cases/` contains the current command logs, negative missing-source logs, copied compatibility and saved receipts; `execution-manifest.json` binds construction and receipt hashes. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=4)` passes for the over-crosswalk case, confirming three distinct bounded alternatives with measured triggers and current proofs.

The stop-short selected case still needs three distinct physical-risk fallbacks. Reviewed real site sources, semantic chain, physical-preparation proof and independent full-duration delivery audit also remain. Keep `result.json` partial.

## Complete stop-short fallback set

`fallback1` shortens the authored stop target from 2.0 to 1.0 m if original complete-body history shows the primary stop reaches or crosses the sourced crosswalk. `fallback2` selects `vehicle.tesla.model3` when the primary vehicle blueprint cannot spawn. `fallback3` raises and moves the overview/reference-corner source cameras if their original images clip the settled complete body or crosswalk boundary. Each alternative retains the exact stop-short case identity, 45-second/20 Hz recording description, site/crosswalk identity and law observations. Their triggers require Native status, original body history or source pixels; synthetic media cannot establish that a fallback is physically needed or successful.

Each stop-short fallback passes exact `runtime.py offline`, positive/negative `runtime.py compatibility` and recorded-only `runtime.py process-saved` under `.runtime-work/c215286-short-fallback{1,2,3}-*`. `cases/` holds the command and missing-source logs plus copied compatibility/saved receipts, and `execution-manifest.json` binds their current construction and receipt hashes. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=4)` passes for **both** selected cases; pinned `package_compatibility.check_receipts` passes for both primary cases. All eight constructions now have the exact synthetic CPU paths.

Remaining CPU readiness work is independent reviewed real residence-district/crosswalk geometry/marking sources, semantic chain, physical-preparation proof and independent full-duration delivery audit. Then rerun affected exact commands and strict gates. No physical or legal acceptance is claimed from diagnostics; result stays partial.
# 2026-11-20 return-file maintenance

Seven zero-byte command logs referenced by this partial package's execution manifest were rebound to its existing zero-byte `compatibility.log`, preserving the exact empty-file SHA-256. The duplicate files were removed to recover seven work-tree file slots for C378304 construction. The C215286 assignment static check still passes. Status remains partial; this maintenance is not a new compatibility or readiness proof. No frozen input, runtime, batch.json or Git action was taken.


## 2026-11-22 19:45 UTC reversible file-cap staging

Thirteen small historical proof logs were moved byte-for-byte into `work/_shared/archived-unbound-negative-logs-20261119.json` while C215286 remains partial, to make room for C149752 materialized implementation. For each archived row, base64-decode `content_zlib_base64`, zlib-decompress, verify `sha256`, then write exact bytes to `path` before rebinding or reusing its receipt. Current C215286 receipts referencing these paths are historical and must not be claimed current until logs are restored and proofs rerun.
