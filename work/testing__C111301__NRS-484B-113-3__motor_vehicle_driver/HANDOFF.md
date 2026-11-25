# testing__C111301__NRS-484B-113-3__motor_vehicle_driver

Status: partial CPU construction checkpoint. The exact strict gate still fails because result.json is partial. No Native recording or accepted evidence is claimed.

The frozen cell is C111301 (intersection, travel, pedestrian control), with motor vehicle driver. The assigned witness is the pedestrian alternative of NRS 484B.113(3). The full subsection also says moving traffic; that alternative needs independent branch allocation review. The section heading is limitations on backing. A travel label or pedestrian control does not by itself prove backing, a crosswalk, or legal right of way. Frozen evidence.json lists no accepted recordings, and judgment_ranges.json has no matching range for this law and actor.

## Exact cases and comparison

- `testing__C111301__NRS-484B-113-3__motor_vehicle_driver__pedestrian_yield`: reverse vehicle holds/brakes while a distinct moving pedestrian occupies the backing corridor, then resumes after clearance.
- `testing__C111301__NRS-484B-113-3__motor_vehicle_driver__pedestrian_continue`: same map, actor classes, reverse and walking routes, and pedestrian exposure; driver continues backing.
- `pedestrian_yield_response`: compare measured original-frame brake/reverse speed with measured pedestrian gap, speed and corridor occupancy held fixed. This is an engineering contrast, not a legal label.

`backing_geometry.py` requires an original source-hashed map/junction packet, vehicle and pedestrian blueprints, route coordinates and references, control provenance, and a geometric route intersection. It rejects a pedestrian path missing the reverse body corridor. `native_backing.py` lazily resolves native blueprints and spawns both actors with cleanup on failure. `backing_controller.py` injects a control factory for Native VehicleControl and commands hold/release or continued reverse. `backing_measurements.py` rejects missing original frame fields, identity changes, absent measured backing, absent moving pedestrian conflict, and comparison exposure drift.

## Proven checks

- `.venv-cpu/bin/python runtime.py preflight` passed in this turn.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 7 tests. Exact log and SHA are in result.json.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111301__NRS-484B-113-3__motor_vehicle_driver --complete --require-delivery-ready` reached `Preparation acceptance failed: partial/missing packages remain`; see strict-gate.log. It is deliberately not marked ready.

## Next CPU work

1. Select and review an actual CARLA/OpenDRIVE C111301 site, export its original map packet and Native transforms, and bind reverse motion to the validated path. Do not infer physical geometry from the cell label.
2. Integrate the controller and original-frame measurements into canonical runner/config/construction and exact bundled case variants. Preserve four-view 20 Hz capture and original telemetry.
3. Author canonical semantic proposals, exact measurement contracts, source-specific positive/negative compatibility recipes and offline receipts for each case, plus saved-only processor and independent delivery/comparison audits.
4. Re-read the full statutory subsection and definitions for the moving-traffic alternative and section-context limits. Keep all legal judgments unresolved pending physical review.
5. Rerun the seven CPU tests and exact strict gate. Mark ready only after the gate passes.

Actual CARLA motion and camera visibility remain later GPU checks; the listed package work is worker-owned CPU preparation. No external blocker is asserted.

## 2026-11-24 saved-only source join checkpoint

`saved_backing.py` now accepts only the two exact case IDs and a declared non-diagnostic Native original acquisition. It verifies the SHA-256 and confined path of the original map packet, 900 telemetry rows, 900 original frame-map rows, and four named media files. It checks contiguous original frame identities, 20 Hz time steps, four camera frame readbacks per tick, and measured backing plus a moving pedestrian in the backing corridor. It outputs a source-bound measurement and explicitly leaves video decode, pixels, physical completion, and legal judgment unresolved. The media fixture is textual and proves only hash joining.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 13 tests, including source tamper, missing media, camera frame drift, time gap, diagnostic source, identity mismatch, and path escape rejection. See `cpu-backing-tests.log` and its result.json hash.

Remaining CPU work: connect this saved join to original Native capture and finalizer, validate full media pixels with the runtime auditor, implement independent delivery/comparison audits and canonical bundles/proposals/receipts. The selected C111301 map source and physical vehicle/pedestrian interaction still need local verification.

## 2026-11-24 replayable saved comparison checkpoint

`saved_comparison.py` now runs the exact `pedestrian_yield_response` comparison from two distinct sealed original Native acquisitions. It invokes `saved_backing.process` for each required case, checks that the two original map packets have the same hash (binding map, routes, blueprints and control context), requires the same 900-tick time window, and calls `backing_measurements.compare` to check measured pedestrian exposure and an observed brake or reverse-speed difference. The CLI emits a compact source-hashed comparison receipt only after both attempts pass. It leaves physical completion and legal judgment unresolved.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111301__NRS-484B-113-3__motor_vehicle_driver/tests -v` passed 16 tests. These include a positive CLI replay and rejection of changed source context, telemetry tampering and pedestrian-exposure drift. `.venv-cpu/bin/python runtime.py preflight` passed with the pinned CPU environment and Lean toolchain. The logs and current hashes are in `result.json`.

Next CPU work: attach original four-camera capture and full media decode, then implement the exact delivery auditor, canonical case bundles, proposals and source-specific offline/compatibility receipts. The selected C111301 site and realized interaction remain unverified. This package remains partial; synthetic sealed fixtures are software tests only.

## 2026-11-24 four-camera full-decode checkpoint

`media_decode.py` adds a saved-only full decode for each of the four sealed original camera videos. It checks source hash before and after decode, exact 20 Hz stream rate, production dimensions (1920x1080 front; 1280x720 rear/left/right), and every one of 900 decoded frames. The `process_delivery` path first validates the sealed telemetry/map/frame join and then audits video; its CLI writes a new output only. The 900-frame CPU fixture and negative hash/dimension/frame-count tests passed in the 18-test focused suite (`cpu-backing-tests.log`, SHA-256 `f0692840c78fcbecbfc05de32764b642f980bbf40dd09bbd6c7f881787734d84`). Synthetic video establishes decoder integration only. Actual participant visibility, backed motion, legal right of way and Native capture remain unverified.

## 2026-11-23 source-measured response witness checkpoint

`backing_semantics.py` now requires a continuous 20-original-frame moving-pedestrian corridor witness after frame 20 for each exact case. The yield case needs a sustained measured brake and low reverse speed; the continue case needs sustained low brake and reverse speed. These are controller engineering distinctions, not legal thresholds. `saved_backing.process` attaches the source ID, exact witness frame interval and measured ranges to its sealed-source result. The focused suite now has 20 passing tests, including rejection when an apparent yield response exists only during startup or when a yield case records the continue response. `cpu-backing-tests.log`, `assignment-check.log` and `strict-gate.log` were refreshed; result.json carries the current focused-test hash. Scoped static passes and scoped strict still exits 1 because the package is partial. No Native acceptance is claimed.

Next CPU work remains canonical runner/config/construction bundles, semantic stage proposals, Native capture/finalization integration, and exact source-bound offline/compatibility receipts. The selected map site and physical participant interaction still need local review.

## 2026-11-23 source-derived pedestrian corridor checkpoint

`backing_geometry.pedestrian_in_reverse_corridor` now computes an original pedestrian's distance to the sealed reverse route, using source-bound vehicle half-width and pedestrian radius. `saved_backing.process` requires the recorded per-frame corridor flag to agree with that geometry before measuring either exact case or accepting its 20-frame response witness. A bare telemetry boolean can no longer establish the planned pedestrian exposure. Nonfinite map coordinates and actor extents are rejected. The 21-test focused suite includes altered flag, altered position and nonfinite extent negatives; the existing two-attempt comparison still passes with measured exposure fixed. This is case-specific saved CPU processing, not a canonical `runtime.py process-saved` receipt or physical visibility proof. Canonical bundles, compatibility receipts, Native capture and delivery integration remain unfinished.

## 2026-11-23 original map bytes binding checkpoint

`saved_backing.process` now resolves the map packet's confined, sealed `map_source` and compares the actual original map bytes SHA-256 with `map_sha256`. The packet hash alone cannot establish the original OpenDRIVE file. The diagnostic fixture carries a distinct `road.xodr` source reference; tests reject altered source bytes, a rewritten source reference with a stale map hash, and a missing source. This strengthens saved source provenance without claiming that the diagnostic map is the selected C111301 Native site.

The 23-test focused suite, pinned CPU preflight and scoped static check passed. The exact scoped strict gate exits 1 on the truthful partial status. Commands and current log SHA-256 values are in `result.json`. Canonical bundles, semantic proposals, Native capture/finalizer, positive/negative offline and compatibility receipts, and independent delivery audit remain worker-owned CPU tasks. Physical backing, participant visibility and legal right of way remain unresolved.

## 2026-11-24 sealed original path identity checkpoint

`saved_backing._sealed` now requires a relative regular source path with no symlink component before hashing it. A symlink to the same OpenDRIVE bytes inside the attempt is rejected, so the original map packet cannot redirect the saved processor through a linked path. The new linked-map negative and full 24-test assignment suite pass; test scratch is under `.runtime-work/`. This proves saved-source path integrity only, not physical Native origin.

Pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Four SHA-bound logs are in `result.json`. Remaining CPU work: canonical runner and case bundles, semantic proposals, Native capture/finalization, positive/negative offline and compatibility receipts, and independent delivery audit. Actual backing motion, pedestrian visibility and legal priority remain unresolved.

## 2026-11-24 original Native backing tick source checkpoint

`native_backing_capture.py:NativeBackingRecorder` now reads original Native vehicle and pedestrian transforms, velocities and vehicle control readback on each world tick. It computes corridor occupancy from the source-bound reverse route, requires the four camera image frames to equal the same Native world frame, and retains both world-frame and 0-based saved-frame identities. It writes `telemetry.json` and `frame-map.json` only after 900 ordered 20 Hz ticks. The separate video encoder and actor lifecycle runner remain to be connected; this module makes no physical or legal completion claim.

The 26-test assignment suite, pinned CPU preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial status. Four SHA-bound logs are in `result.json`. Remaining CPU: full CARLA world/camera/video runner, canonical two-case bundles, semantic proposals, exact offline/compatibility/process-saved proofs and independent delivery audit. The original map site, backing motion and pedestrian visibility remain unverified.

## 2026-11-25 original Native frame and camera-time join

`NativeBackingRecorder.append` now requires consecutive Native world frames and each of the four camera image timestamps to match its original 20 Hz tick within 1 ms before a telemetry/frame-map row can be appended. The prior check only required increasing frame IDs and same-frame camera IDs; it could retain a skipped simulator frame or delayed image. Positive 900-frame capture and skipped-frame/altered-timestamp negatives pass in the 27-test focused suite (`cpu-nov25-native-join-tests.log`). Scoped static passes; exact scoped strict remains partial. This is CPU source-join construction, not a Native recording.

Next worker-owned CPU actions: attach the recorder to a borrowed CARLA world with actor/sensor ownership, 900-frame four-camera video encoding and restore readback; then bind both exact cases to canonical inline bundles, semantic proposals, source-specific offline/compatibility/process-saved and independent delivery/comparison proofs. The frozen export has no reviewed original C111301 site/OpenDRIVE bytes or actual backing/pedestrian observation, so physical or legal success remains unasserted.
