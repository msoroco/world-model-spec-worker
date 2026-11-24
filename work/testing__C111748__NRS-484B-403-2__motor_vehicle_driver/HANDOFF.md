# testing__C111748__NRS-484B-403-2__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.403(2) — If an official traffic-control device indicates that a U-turn is prohibited, the driver shall obey the directions of the device.
Assigned branch(es): Applicable official-device duty, including observation before any attempted turn..
Cell: C111748 (intersection, u_turn, turn_prohibition_device); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111748__NRS-484B-403-2__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable CPU checkpoint

The frozen evidence inventory is empty. `case-plan.json` now defines three exact cases: `__prohibited_obey`, `__prohibited_attempt`, and `__neutral_device_turn`. The `device_obedience` comparison changes only the driver's U-turn action after observation. The `device_applicability` comparison changes only the reviewed device direction while retaining the driver turn. All cases require a physical-risk review for sign legibility and U-turn route envelope; fallback constructions remain to be implemented and proved if needed.

`construct.py` loads a SHA-sealed, case-bound site, requires original map/highway/official-device/display sources and an opposite-lane route, and lazily spawns the motor vehicle and device with failure cleanup. `native_device.py` measures a SHA-sealed original-frame packet, rejects gaps, identity or live-display mismatches, missing governed-approach frames and visibility, and detects whether a turn starts after device visibility. Its `visible_to_ego` readback requires later video review; it does not establish actual driver perception or legal device status. The original law has no numeric threshold. The conditional official-device applicability needs reviewed placement authority, regulatory purpose and external legal-consistency evidence.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111748__NRS-484B-403-2__motor_vehicle_driver/tests -v` passed 9 tests. The exact log/hash is in `result.json`.

Next CPU work: add source-bound full-turn pose/heading corroboration; implement exact per-case runner/config/construction bundles, measurement contracts, semantic proposals, execution manifest, source-hashed positive/negative compatibility fixtures, saved-only processing, independent delivery and comparison audits, and risk-triggered candidate fallback proofs. Review the full statutory device clause independently before a ready claim. A later CARLA run must verify route motion, actual sign pixels and four-camera coverage. No package here is ready yet.

The saved measurement now additionally rejects a claimed completed U-turn unless original ego poses show at least 135 degrees of heading reversal and an opposite destination lane on the same road. The focused suite passes 10 tests; `result.json` binds the renewed log hash.

`comparison_audit.py` independently reruns both sealed Native sources. It verifies the exact obedience/applicability case pairs, fixed map, route, actor, highway, official-device authority, governed approach, camera plan, duration and frame window; then verifies exactly the declared driver-action or display-direction difference. It produces no legal conclusion. Positive and negative CPU tests cover both pairs, fixed-route drift, missing action difference and source tampering. The focused suite now passes 15 tests; see renewed `cpu-tests.log` and `result.json` hash. This is a saved-source comparison component, not a completed delivery audit or exact manifest proof.

## 2026-11-24 source-bound Native acquisition checkpoint

`native_capture.py` adds lazy exact-case 20 Hz acquisition from injected local live callbacks. It verifies the SHA-bound reviewed site, identity, stable live display, 900-frame delivery length, frame/time continuity, four camera frame identities, and guaranteed brake on capture errors. The produced Native packet binds site, map, route, highway, official-device sources, camera plan, original ego/device readbacks and a sealed measurement. Short test runs require `diagnostic=true`; returned booleans explicitly leave actual pixels and physical completion false. No CARLA connection or physical sign visibility was claimed.

`native_device.py` now requires source-reported device visibility on the governed approach before an observed turn. This is still only a Native visibility readback; final pixels need independent review. `tests/test_capture.py` covers source drift, display drift, time drift, camera-frame mismatch, brake on errors, positive packet sealing, and rejection of a short delivery run. The focused command in `result.json` passed 22 tests; `worker_check.py --assignment testing__C111748__NRS-484B-403-2__motor_vehicle_driver --complete` passed. The exact scoped `--require-delivery-ready` command failed because the package remains partial. Logs are `cpu-tests.log`, `assignment-check.log` and `assignment-strict.log`.

Next CPU work: bind the live callbacks to an exact runner/controller and reviewed physical site, author exact case bundles and manifest, semantic proposals, source-hashed compatibility and saved-processing proofs, independent delivery audit and physical-risk fallbacks. Verify legal device status from independent reviewed authority sources; a simulator sign cannot establish it.

## 2026-11-24 live map and saved source integrity checkpoint

`native_map.py` checks the loaded map name and exact OpenDRIVE bytes against the reviewed, SHA-sealed site before spawning. It rejects stale site bytes, wrong live map and route lane drift; its receipt explicitly leaves physical turn verification false. The local CARLA runner still needs to call this preflight and supply a genuinely reviewed site packet.

`saved_delivery.py` independently reloads the sealed Native packet and a single-attempt `saved-sources.json`, enforces the exact three case identities, 900 original frames at 20 Hz, four per-frame camera identities, attempt-confined hashed media sources, expected driver action and expected device display. It rejects diagnostic captures, missing or tampered media, path escapes, short captures and case drift. Its receipt leaves participant coverage, full decode, actual pixels, physical completion and legal device status unproved. It is source-integrity CPU work, not the final canonical `delivery_audit.py` or a video-quality receipt.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111748__NRS-484B-403-2__motor_vehicle_driver/tests -v` passed 30 tests. `.venv-cpu/bin/python worker_check.py --assignment testing__C111748__NRS-484B-403-2__motor_vehicle_driver --complete` passed. The same command with `--require-delivery-ready` fails because this result remains partial. Exact log hashes are in `result.json`.

Next CPU actions: call the live map guard from an exact CARLA runner/controller, author per-case inline config/construction bundles and semantic proposals, implement full saved processing and video decode receipt, add independent delivery acceptance and case-specific positive/negative compatibility receipts, then author risk-triggered fallback proofs where the reviewed physical site justifies them. Review official-device authority and placement from an independent source; a simulator sign or self-declared hash is insufficient.

## 2026-11-24 exact local control and runner checkpoint

`control_policy.py` implements a case-bound, original-frame decision for all three exact cases. It holds the vehicle until a prior governed-approach device readback, holds for the obey case after observation, and applies a waypoint pursuit command only for the two turn cases. It rejects display, approach, route geometry and pose drift. This is requested control, not observed motion or a legal conclusion.

`runner.py` now joins the SHA-bound live OpenDRIVE map check, exact vehicle/device construction, 20 Hz acquisition and the control policy. It supplies brake on failures, destroys both owned actors and restores world state. The local CARLA adapter must provide reviewed transforms, live synchronized camera/device/ego readbacks, `VehicleControl` construction and world snapshot/restore callbacks. No CARLA connection was attempted here. A fake-world CPU fixture covers turn command, source drift before mutation, brake and cleanup on readback failure.

The focused suite now passes 38 tests. The scoped `--complete` check passes; scoped strict still rejects the truthful partial package. The current exact commands and SHA256 log bindings are in `result.json`. Further CPU work: original authority and display source review, exact bundles/manifest, semantic proposals, positive/negative compatibility and process-saved proofs, full video decode plus independent delivery acceptance, and candidate fallback implementation and proofs.
