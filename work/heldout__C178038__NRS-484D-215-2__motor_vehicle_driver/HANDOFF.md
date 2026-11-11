# heldout__C178038__NRS-484D-215-2__motor_vehicle_driver CPU checkpoint

Law: NRS-484D-215-2, cell: C178038, actor: motor_vehicle_driver. Frozen assignment: `inputs/heldout__C178038__NRS-484D-215-2__motor_vehicle_driver/assignment.json` (2f105d16236025597cabc7739a57b53a7442fc2321118497538a014738ce3687).

Exact law text: Whenever a motor vehicle is being operated on the traveled portion of the highway, or shoulder adjacent thereto, during the times specified in NRS 484D.100 [NRS-484D-100-1], the driver shall use a distribution of light, or composite beam, directed high enough and of sufficient intensity to reveal persons and vehicles at a safe distance in advance of the vehicle, subject to the following requirements and limitations: Whenever the driver of a vehicle follows another vehicle within 300 feet to the rear, the driver shall use a distribution of light permissible under this chapter other than the uppermost distribution of light specified in subsection 1 of NRS 484D.210 [DEF-NRS-484D-210-1-2].

Accepted recording summaries to review: 0; inventory `inputs/heldout__C178038__NRS-484D-215-2__motor_vehicle_driver/evidence.json` (e0673877b9b6d5cc1dac09658216b3e834dc00c19e63d0d6a55c0355de648c8f). No accepted membership is treated as complete coverage.

Status: partial. CPU preparation incomplete: exact case coverage and controlled comparisons, portable construction and controllers, four-camera capture plan, finalizer and measurement contract, three distinct tested fallbacks per selected case, source-bound offline/compatibility/saved-processing proofs, semantic proposals, and independent delivery/comparison audits remain to implement.

Resume: read each accepted metadata source, decompose full law text and exceptions, then implement cases/comparisons and all CPU proofs; run `.venv-cpu/bin/python worker_check.py --assignment heldout__C178038__NRS-484D-215-2__motor_vehicle_driver --complete --require-delivery-ready`. The pinned CPU environment now passes `runtime.py preflight`; see `work/_shared/preflight.log`. Do not treat the earlier transient install failure as a current blocker.

## Full-text branch inventory (planning, unimplemented)

- nighttime or other NRS 484D.100 activation context with follower within/below/at/above 300 ft
- within 300 ft: uppermost beam versus permitted lower distribution
- traveled portion versus adjacent shoulder
- outside 300 ft comparison without treating it as permission to use an otherwise impermissible beam

No legal judgment threshold is inferred from these engineering comparisons. Verify cell compatibility and governing cross-references before selecting exact cases.

## 2026-11-11 300-foot source measurement checkpoint

The frozen evidence inventory lists zero accepted recordings. Six controlled cases and five comparisons now span the 299/300/301 ft boundary, uppermost versus other distribution, separately cited lighting time, and traveled portion versus adjacent shoulder. `headlamp_follow_measurement.py` reads original 20 Hz body polygons and lamp readback with actor/frame joins, and keeps legal/safe-distance judgments null. Three CPU tests pass, log SHA-256 0e50407d53a68fc80e17ca54764ad2465e4b97d7d7671eb40f2c30084c34c4b4. The 300 ft value is statutory; no engineering tolerance is used as a legal verdict.

Next CPU work: actual Native headlamp readback/source capture and lighting-time/roadway context, four-camera runner, saved finalizer, exact cases/fallbacks, positive/negative compatibility, semantic proposals and independent audits. The current measurement is not physical proof.

`headlamp_source_capture.py` now writes original Native actor bodies, headings and both high/low beam bit readbacks with 20 Hz joins. The measurement rejects a missing low-beam readback and distinguishes lamps off from a non-uppermost beam. Its source-shaped integration test passes; five tests total, log SHA-256 2dab77a15d687a6321fdbe2419e7abd7790871f750c3675b84ee8138a35d0808. A CARLA high-beam bit is an engineering mapping to the uppermost distribution; legal permissibility of other distributions remains for source review.

`headlamp_finalizer.py` now joins original body/lamp rows to the Native trace and video frame map, emits source-hashed observations and a derived gap channel, and builds a canonical Native result with physical/legal acceptance false. Positive, missing-original and stale-frame CPU fixtures pass pinned result-shape validation; seven tests total, log SHA-256 e2f5895306e86a030273f55a9c8f86a74ed8b5a3b8781d2a7cd43176441d60de. The finalizer has a saved-only CLI; full runtime compatibility remains to implement.

`headlamp_follow_route.py` selects a connected long same-lane Native route and provides feedback control exercised in both approach directions. `headlamp_camera.py` captures four named original RGB streams with exact frame joins, including a CPU rejection test for missing frames. `native_headlamp_probe.py` now creates a distinct lead and subject, applies and reads back upper-beam state, drives both vehicles, records original body/lamp source rows, captures all four streams, and restores world settings. `probe-config.json` fixes its first 299-foot case and explicitly identifies it as a construction probe. Eleven local CPU tests pass; `native_headlamp_probe.py --check --config probe-config.json` and the assignment scoped `worker_check.py --complete` pass. `construction-probe.json` now passes exact `runtime.py offline`; `probe-proof.json` binds its current SHA-256 and successful command. The probe has not been run in CARLA, and its requested separation and visibility are not physical outcomes. Next CPU actions: construct a source-complete diagnostic for compatibility and saved processing; complete other exact cases, fallback constructions, proposals and independent audits. Keep `result.json` partial until the scoped strict gate passes.

## 2026-11-11 roadway source checkpoint

`headlamp_roadway_capture.py` now records each original ego frame's nonprojected Driving/Shoulder waypoint identity, lane type and Native sun altitude. `native_headlamp_probe.py` invokes it in the same 20 Hz capture loop. `headlamp_finalizer.py` requires this raw stream, joins it to the trace, frame map, body/lamp rows and ego actor identity, and hashes it in the analysis. Neither sun altitude nor lane type alone establishes the statutory NRS 484D.100 civil-time premise or actual traveled/shoulder occupancy; those require separately cited source context and physical review. The positive saved finalizer fixture and negative missing/wrong-actor tests pass. Thirteen CPU tests pass (`cpu-tests.log`, SHA256 `6d23e08add9a6d9ec3a3132fcd34253111e2833381c100ed928a241e57c26970`).

The inline `construction-probe.json` was refreshed with this source capture and finalizer; SHA256 `71bde84db0c454ad10f43fcb0d2af8eba1c44be9fb652dfd4c32003f1206bfaf`. Exact offline check passed using the command in `probe-proof.json` (`probe-offline.log`, SHA256 `2469da3980442d9df2684965665c3468b309fb1e3883a7081016d960a50e4a2d`). An initial offline attempt with a relative `--python .venv-cpu/bin/python` failed because the runtime executes in a changed working directory; the successful attempt uses the absolute interpreter path. This is a construction probe only, not full compatibility or delivery readiness. Next CPU step is a source-complete diagnostic with a cited lighting-time premise and raw video sources, then positive/negative compatibility and saved processing for this exact case.

The scoped `.venv-cpu/bin/python worker_check.py --assignment heldout__C178038__NRS-484D-215-2__motor_vehicle_driver --complete` check passes. Adding `--require-delivery-ready` fails because the result is correctly partial; its trace is in `strict-gate.log`.
