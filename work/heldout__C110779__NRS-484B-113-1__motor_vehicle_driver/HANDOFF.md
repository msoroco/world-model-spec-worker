# heldout__C110779__NRS-484B-113-1__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 reverse feedback continuation

`reverse_feedback.py` now provides a bounded, CARLA-independent closed-loop
reverse command from original position, heading and signed speed readbacks to a
point behind the vehicle. It brakes at a fixed engineering stop radius, brakes
when reverse speed exceeds the requested target and reverses steering sign for
reverse kinematics. The target and controller are construction inputs; the
original motion measurement remains authoritative for realized backing.

Six tests pass, including speed correction, steering direction, target stop and
invalid input rejection. Run `.venv-cpu/bin/python -m unittest discover -s
work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`27135f224f88402772379f61d65606f2aae6bd3b09605a52e62ec6cb18efae3b`.
The scoped complete checkpoint passes; scoped strict still rejects the partial
result. Next, bind a sourced intersection backing corridor and independently
specified other vehicle to Native spawn and source capture, then run the first
exact case through offline, positive/negative compatibility and saved-only
processing. No reverse movement or safety judgment has been physically verified.

## Frozen scope and source

- Law: NRS 484B.113(1) — The driver of a vehicle: Shall not back the vehicle unless such movement can be made with reasonable safety and without interfering with other traffic.
- Cell/actor: C110779 / motor_vehicle_driver; layout `intersection`, maneuver `reverse`, control `other_vehicle`.
- Exact input: `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/assignment.json` (SHA256 `cea1a7b04dc28362442d4962618eb853bcf512afc0cb0496bfe7d17b194c20f1`).
- Witness: `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/witnesses.json`, source index 61; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.backing, drv.time_to_conflict, rel.surface_gap, drv.hard_deceleration, ru.pedestrian, rel.bearing, rel.contact.

## Required source and construction review

1. Establish eligible vehicle and driver attribution and supported reverse control.
2. Highway-use facts and observation of all relevant traffic, surrounding objects and responses.
3. Intersection backing corridor with proposed onset, course and end.
4. Observe all relevant traffic, surrounding objects, clearances, responses, and contact throughout backing.
5. Preserve drv.backing, drv.time_to_conflict, rel.surface_gap, drv.hard_deceleration, ru.pedestrian, rel.bearing, and rel.contact as observations.
6. Qualifying motor vehicle and driver in actual physical control.
7. Reasonable safety and interference remain uninterpreted; no conflict-time, braking, or contact rule is supplied.
8. Separate other vehicle with specified position, motion, purpose and relationship to the backing corridor.
9. Specify proposed backing, actual onset, course, end, and intersection corridor.
10. Specify the other vehicle's position, motion, travel purpose, highway use, and relationship to the backing route.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C110779__NRS-484B-113-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-11 backing source measurement checkpoint

The frozen accepted-evidence inventory contains zero recordings. `case-plan.json` now plans six exact cases and five controlled comparisons for wider/narrower traffic clearance, observed other-vehicle braking, contact, pedestrian proximity and a forward-only activation control. All exact cases remain unconstructed; the conditional witness remains only a planning lead.

`backing_safety_measurement.py` joins original 20 Hz ego and surrounding-user motion to original contact packets, with independently cited actor position, motion, purpose and highway use. It measures negative longitudinal ego speed relative to actual heading, the continuous backing interval, participant surface gaps and relative bearings, participant acceleration during backing, and contact frames during backing. A forward-only trace returns a null backing interval for the activation control. A backing interval with an interruption is rejected for separate review. Reasonable safety and interference judgments remain null; no gap, braking or contact cutoff is treated as law. Native source acquisition, actual other-vehicle purpose, four cameras and saved finalizer remain CPU work.

`.venv-cpu/bin/python runtime.py preflight` passes (`preflight.log`, SHA256 `57b007d9ed610f0eb62a59bd93915c811343fae28526b476261efa74e5fbbc9a`). `.venv-cpu/bin/python -m unittest discover -s work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver/tests -v` passes four CPU tests (`cpu-tests.log`, SHA256 `524ec85fd5f2cf8f482fe7a8d31d29c36faf6d1a097f41ff990479d464e1efec`). They check measured reverse geometry/contact and reject uncited traffic context, frame mismatch, changed actor IDs, missing original contact source and interrupted backing. These fixtures do not establish physical safety or traffic interference.

Next CPU work: construct a primary Native backing corridor with reverse control and a separately motivated other vehicle, acquire source packets and four cameras, add the saved finalizer, and run exact offline, positive/negative compatibility and saved processing. Then implement the linked cases, risk-based fallbacks, semantic proposals and independent audits. Keep `result.json` partial until its scoped strict gate passes.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C110779__NRS-484B-113-1__motor_vehicle_driver --complete` check passes (`worker-check.log`). Adding `--require-delivery-ready` fails because the result remains partial (`strict-gate.log`).

## 2026-11-12 first selected case saved-processing checkpoint

The first selected exact case is `heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__backing_clear_vehicle`. Ignored `.runtime-work/c110779-native-stage/` contains its Native runner, source recorder, four-camera acquisition, source-bound finalizer, inline construction, measurement contract, execution manifest, case plan, proposal draft, CPU diagnostic specification and recipe. The runner consumes an operator-reviewed corridor and checked OpenDRIVE hash; no CARLA run has occurred. The diagnostic is synthetic and carries no physical or legal acceptance claim.

Current inline construction SHA-256 is `ec802c3ac8c00d7079714e9ca6521509318e491bb11caefa4dba81e5c3ad1a2e`. Eight staged component tests pass using `PYTHONPATH=work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver .venv-cpu/bin/python -m unittest discover -s .runtime-work/c110779-native-stage -p 'test_*.py' -v`. Exact offline passed at `.runtime-work/c110779-native-stage/offline-first-v4/`; exact positive/negative compatibility passed at `.runtime-work/c110779-native-stage/compat-first-v4/compatibility.json`, including all four original camera sources and rejection of a missing `backing_motion.jsonl` source. The selected saved-processing proof passed via `.venv-cpu/bin/python .runtime-work/c110779-native-stage/prove_saved_first.py`: 9 joined frames, acquisition originals byte-for-byte preserved, no missing evidence, and the missing-motion negative classified as `incomplete_or_unavailable_law_evidence`. It claims neither physical nor legal acceptance.

The 2.6 MiB diagnostic source exceeds the 2 MiB returned-file limit. It and its recipe were moved into ignored staging after proof. To reprove with the pinned fixture generator, temporarily copy `.runtime-work/c110779-native-stage/diagnostic-first-primary.json` and `.runtime-work/c110779-native-stage/diagnostic-recipe-first-primary.json` into this assignment directory under the same basenames, run the exact offline/compatibility/saved checks, then move them back to ignored staging before the scoped worker check. This staged proof is a checkpoint, not a returned ready package. The scoped complete check passes with the temporary files removed.

Status remains **partial**. Next CPU work: construct the remaining five exact cases, justify and test three distinct physical-risk fallbacks per selected case, run each affected offline/compatibility/saved proof, return the current source-bound package within the file cap, implement independent delivery/comparison audits and finish the original-law sweep. The current proposal draft is not yet canonical returned semantic coverage. No actual movement, camera visibility, reasonable-safety conclusion or traffic-interference conclusion has been verified.

## 2026-11-12 current primary and fallback checkpoint

The preceding primary construction hash was superseded by a runner that reads three bounded engineering controls from its exact config. Current primary SHA-256: `0a16db5d53eaa69ab7d0b1e8f92dec404001a6c591317de1bbff84d1935024e4`. Current fallback hashes: `fallback1` slower reverse target `552dc47c74334a8def63a0a4cbab528a62361ecd8f26045020a67a0dadd3c292`; `fallback2` stronger through-vehicle motion `50695b2f8503d7d55fe4a526ded2ae281e43e2dd7318b3847422fc9c06c8de01`; `fallback3` raised overview source camera `f499c5124c5de82f7d6de79d80d93b8e8d07ce5b8ebad97b269a240ff20f1720`. Each fallback has a distinct predeclared source, metric and physical failure trigger in staged `execution-manifest.json`; the fixed law/cell/actor, case, 20 Hz duration, four named camera sources and recording description are unchanged.

All four candidates passed exact offline, positive/negative compatibility, and positive/negative saved processing with nine joined frames and byte-preserved originals. Current logs/receipts live under ignored `.runtime-work/c110779-native-stage/offline-{primary,fallback1,fallback2,fallback3}-current*`, `compat-{primary,fallback1,fallback2,fallback3}-current*`, and `saved-{primary,fallback1,fallback2,fallback3}-current.json`. The saved missing-motion negative is classified as incomplete evidence for each candidate. The eight staged component tests passed after the runner change. The oversized diagnostic specification and recipe have again been moved from this return directory into ignored staging; their temporary restoration procedure is above. The scoped `worker_check.py --assignment heldout__C110779__NRS-484B-113-1__motor_vehicle_driver --complete` check passes. Scoped strict remains unsatisfied because `result.json` is correctly partial and the other exact cases, canonical returned proof bindings and audits are incomplete.

## 2026-11-12 staged Native corridor, original capture and saved analysis

Ignored `.runtime-work/c110779-native-stage/` now contains source-backed CPU construction components. `backing_corridor.py` validates an operator-reviewed intersection polygon, exact Native map/OpenDRIVE hash, bounded reverse start/end inside the polygon, independently positioned other vehicle, lane identity and authored travel purpose; it rejects stale map, forward path and outside traffic placement. `backing_source_capture.py` writes original 20 Hz ego/participant body, velocity and contact packets with exact actor IDs, independently cited traffic context and source hashes. `backing_camera.py` creates all four named original RGB streams, enforces source dimensions and synchronized frame receipt. `backing_finalizer.py` joins backing measurement to the original frame map, requires all four camera sources, creates a derived observation channel, and prepares a Native result with a separate engineering reverse-displacement check; no legal safety or interference cutoff is applied.

Eight staged CPU tests pass, exercising map/route rejection, Native recorder output through `backing_safety_measurement.measure`, unknown contact rejection, four-camera creation/synchronization, finalizer positive source read and missing-camera/frame-map rejection. Run `PYTHONPATH=work/heldout__C110779__NRS-484B-113-1__motor_vehicle_driver .venv-cpu/bin/python -m unittest discover -s .runtime-work/c110779-native-stage -p test_*.py -v`. Source SHAs: corridor `0b6ddb96f21c35119e27acf1a8afad451bad625ab0bd6fea489e10f9a5cef48b`, recorder `b24e59a8558ff98999497c8d78aa74bcec69bbd5520516470311d8d01f7482b5`, camera `39a2c6688c11d82076825e95f4c8a4c8c9fd94e11fb22fd63a95a0ef2c90777e`, finalizer `024caf8dd93e9e756d6392cbd626bf10f9faa098db64cd741d10597a2cc6db74`. The finalizer result builder is implemented but has not yet passed a full Native-shaped saved-processing receipt.

Status remains **partial**: these components are staged, not returned or bound to an exact selected construction. Next CPU work is the Native runner/actor and collision-sensor lifecycle, one exact primary inline construction and source-shaped four-video fixture, offline/positive and missing-source compatibility, saved-only processing, then the five remaining cases, three fallbacks per case, semantic stages and independent audits. Actual movement, visibility, reasonable safety and interference remain unverified.
