# testing__C111304__NRS-484B-653-1a__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.653(1)(a) — It is unlawful for a person to: Drive a vehicle in willful or wanton disregard of the safety of persons or property on a highway or premises to which the public has access.
Assigned branch(es): Intersection travel with person and property context.
Cell: C111304 (intersection, travel, person); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and source-audit checkpoint

Status remains partial. The frozen evidence inventory has zero accepted recordings. `case-plan.json` now names eight exact proposed cases across highway person encounter (northbound and southbound), property proximity, and public-access-premises person encounter, with five controlled comparisons. They are planned captures, not accepted evidence or Native executions. Public-access premises must have a source-hashed site; C111304 catalog metadata alone does not establish one. The willful/wanton term has no numeric worker cutoff or automatic legal label.

`encounter.py` implements source-gated map-lane and public-access checks, separate ego and crossing vehicle spawns, fixed occupant registration, property placement, route commands, failure cleanup, and original synchronized distance/speed measurement. `saved_audit.py` independently requires a hash-matched 900-frame original history, stable identities/map/site/camera context, occupancy join, and source-bound controls; it also rejects missing comparison differences and changed fixed conditions. Nine CPU tests pass, including negative branches, in `cpu-tests.log` (SHA256 `e1723f501ded87c3b9334363c16a229e0c3d5312266e62c3004f459529294b1f`).

The exact command `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete --require-delivery-ready` still fails with partial/missing packages; see `strict-check.log`. Next CPU work: bind a concrete source-hashed Native site and adapter; author the exact runner/manifest and selected requirement finalizer for each case; run offline and positive/negative compatibility receipts, semantic proposals, full delivery and video audit, and source-bound comparison proofs. Physical motion and four-camera pixel visibility then require local Native execution.

## 2026-11-24 original Native acquisition and saved-source checkpoint

`native_acquisition.py` now provides a lazy adapter-driven 900-frame, 20 Hz acquisition for all eight planned exact cases. It requires an original sourced site/map/camera plan and matching public-access basis, records ego/crossing/occupant/property original actor and control packets, checks occupancy and stable identities, and records four original camera readback hashes for every frame. It rejects missing frames, cadence gaps, a missing camera, unchanged actor identities, and absent actor movement. On success it writes sealed `original-history.jsonl`, `original-packets.jsonl`, `original-cameras.jsonl`, and `native-receipt.json` into the operator-supplied attempt directory. It brakes ego and destroys constructed actors on both success and failure. The adapter must bind its operations to the original CARLA world; the fixture tests only verify the software contract.

`saved_audit.py audit_native_acquisition` independently reopens the three sealed files and rejoins every actor/control packet, frame, 20 Hz elapsed time, site/map/camera plan, occupancy, and four camera readback hashes. It explicitly leaves full-video decode, actual pixels, physical completion, and legal judgment unresolved. `tests/test_native_acquisition.py` exercises complete 900-frame acquisition, saved rejoin, tampering, missing camera, actor frame mismatch, occupancy mismatch, source basis mismatch, cleanup, and attempt overwrite rejection. The full assignment suite has 13 passing CPU tests in `cpu-tests.log`. The scoped static command `.venv-cpu/bin/python worker_check.py --assignment testing__C111304__NRS-484B-653-1a__motor_vehicle_driver --complete` exits 0 in `cpu-static-check.log`; the exact strict command with `--require-delivery-ready` exits 1 in `strict-check.log` because the package remains partial.

Next CPU work: bind the adapter to a reviewed source-hashed C111304 highway/public-access-premises site and actual four-camera sensor bytes; author exact per-case runner, manifest, finalizer/converter and semantic proposals; run per-case offline and positive/negative compatibility; add source-bound full-video delivery and fixed-condition comparison audits. No actual Native run or pixels were claimed by this checkpoint.

## 2026-11-24 saved-media and measurement checkpoint

`media_audit.py` now independently verifies a four-camera saved-media inventory against the sealed Native receipt and a source-hashed camera plan. It rejects missing, reused, redirected or hash-changed encoded files; checks exact 900-frame, 20 Hz metadata and configured dimensions with ffprobe; and fully decodes each file with ffmpeg. The synthetic fixture creates four small 900-frame videos only in a temporary test directory. It proves the CPU decoder path, not actual body visibility or correspondence between compressed pixels and original sensor packet hashes. `saved_audit.finalize_saved_measurements` independently rejoins all sealed acquisition sources before applying the original actor-history measurement, and refuses a foreign exact case or a modified history.

The 17 focused assignment tests pass in `cpu-tests.log`. Scoped static check exits 0 in `cpu-static-check.log`. Scoped strict delivery check exits 1 in `strict-check.log` because status remains partial. Outstanding CPU work: source-reviewed actual highway and public-access-premises map packets, CARLA world/camera adapter binding, eight exact runners and manifests, semantic proposals, per-case offline and positive/negative compatibility, saved processing and source-bound comparison proofs. Actual Native execution and visibility checks follow the CPU package. No numeric definition of willful or wanton conduct is asserted.

The acquisition and independent saved audit now additionally bind each original control packet to the exact case's ego target speed, crossing target speed and crossing release time. This closes the earlier risk that a timing comparison could rely only on planned values. The late-case positive and wrong-release negative tests pass. The media audit defaults to rejecting diagnostic footage; the synthetic fixture is admitted only by an explicit test option. Current focused suite: 18 passing tests. `result.json` contains hashes for the current passing test and scoped static logs.

## 2026-11-24 loaded-site source binding

`site_binding.py` now binds a case's actual loaded OpenDRIVE bytes and map name to the site packet, joins a separately sourced public-access review and source document, verifies the camera-plan hash, and then applies encounter site validation. Highway and premises variants both pass diagnostic fixture tests; map, access-source, and camera-plan drift are rejected. Diagnostic review is accepted only with the explicit `allow_diagnostic=True` test option. No original C111304 site packet or public-access review has been supplied or claimed. Lane waypoint geometry and real access status still need review against original sources. Current focused suite: 20 passing tests; scoped static exit 0 and strict exit 1 with truthful partial status.

## 2026-11-24 source-bound timing comparison checkpoint

`saved_audit.audit_saved_timing_pair` now reopens and independently rejoins both 900-frame sealed Native attempts for each declared northbound, southbound, or premises early/late timing pair. It checks exact case order, original actor/control/camera packet hashes, common site/map/camera/public-access and speed/fps/duration sources, unchanged actor blueprints, ordered release commands, and a real difference in measured ego-to-occupant center distance. It retains source and receipt hashes and makes no pixel, physical-completion, or legal finding. Positive and negative CPU tests reject reversed cases, modified packets, changed fixed map, identical measured encounter, and unsupported pair IDs. This is a proof of the comparison-audit code using diagnostic fixtures, not original C111304 evidence.

The focused suite passes 23 tests (`cpu-tests.log`); scoped static check exits 0 (`cpu-static-check.log`). The exact scoped strict command exits 1 (`strict-check.log`) because this assignment is still partial. Remaining CPU work includes source-reviewed highway and public-access-premises map packets, CARLA world/camera adapter binding, eight exact runner and manifest bundles, semantic proposals, per-case offline and positive/negative compatibility, full saved delivery, and source-bound property-position and approach-direction comparison audits. Physical motion and camera visibility still require Native execution.
