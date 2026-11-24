# testing__C110264__NRS-484B-210-1__motor_vehicle_driver

Status: partial exact-case and measurement CPU draft. `case-plan.json` now names `__left_signal`, `__left_turn`, and `__neither`, with controlled signal and motion comparisons. Frozen evidence inventory has zero accepted recordings; no reuse is claimed. Paragraph (a) is selected, while paragraphs (b), (c)(1), (c)(2), (d) and subsection 4 remain explicit and unresolved. The latter exception affects only (c)(1).

`pass_right_route.py` consumes a SHA-sealed original Native map packet and creates case-specific ego/target path and signal requests. It checks source station coverage, right-positive orientation, pavement bounds, actor footprint clearance, lane count and direction. It is CARLA-lazy: the requested path still needs a runner and same-attempt Native recheck. `pass_right_measure.py` consumes a SHA-sealed original Native actor trace. It rejects broken 20 Hz continuity, missing actor fields, non-paved actors, absent pass order, wrong lateral order, and a pass away from the source-bounded intersection. It separates target signal from measured left-turn motion. Its tolerances are event-detection tolerances, never legal cutoffs. Eight CPU tests across `tests/test_pass_right_route.py` and `tests/test_pass_right_measure.py` passed; log is `cpu-construction-measure-tests.log`. `.venv-cpu/bin/python runtime.py preflight` passed with the pinned CPU environment. The assignment static check passed in `cpu-static-check.log`. The exact strict command failed in `cpu-strict-check.log` because the package remains partial; this is a worker-owned CPU gap, not an external blocker.

Next: source-review the Native map for a paved right corridor and target/ego footprints, connect the route requests to a CARLA runner with same-attempt checks, bind original source packets and case-specific finalization, then author semantic proposals, offline/compatibility/saved-only receipts and independent delivery/comparison audits. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110264__NRS-484B-210-1__motor_vehicle_driver --complete --require-delivery-ready` after these are present. Actual motion and visual acceptance remain later GPU checks. No legal outcome or physical acceptance is asserted.

Exact law: NRS 484B.210(1); with 484B.210(4) — The driver of a vehicle may overtake and pass upon the right of another vehicle only under the following conditions: (a) When the driver of the vehicle overtaken is making or signaling to make a left turn. (b) Upon a highway with unobstructed pavement which is not occupied by parked vehicles and which is of sufficient width for two or more lines of moving vehicles in each direction. (c) Upon a highway with unobstructed pavement which is not marked as a traffic lane and which is not occupied by parked vehicles, if the vehicle that is overtaking and passing another vehicle: (1) Except as otherwise provided in subsection 4 [(4) appended below], does not travel more than 200 feet in the section of pavement not marked as a traffic lane; or (2) While being driven in the section of pavement not marked as a traffic lane, does not travel through an intersection or past any private way that is used to enter or exit the highway. (d) Upon any highway on which traffic is restricted to one direction of movement, where the highway is free from obstructions and of sufficient width for two or more lines of moving vehicles. The provisions of subparagraph (1) of paragraph (c) of subsection 1 do not apply to: (a) An authorized emergency vehicle described in NRS 484A.480; (b) A vehicle which has been issued a permit to operate as an authorized emergency vehicle pursuant to NRS 484A.490; (c) A traffic incident management vehicle; (d) A tow car; (e) A coroner vehicle; or (f) A public transit motor bus, that is being driven on the paved shoulder of a highway where lawfully placed signage allows that vehicle to use the shoulder in that manner.
Assigned branch(es): Paragraph (a) near an intersection.
Cell: C110264 (intersection, overtake_right, other_vehicle); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C110264__NRS-484B-210-1__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-24 saved-source audit checkpoint

`pass_right_audit.py` independently reopens the original Native map packet, exact source-built route request, original 20 Hz actor trace, and all four named camera source files from a saved attempt. It rejects missing, escaped or altered source paths, wrong case/actor identity, mismatched map/trace intersection bounds, diagnostic-marked attempts, incomplete camera inventory, and observed target behavior that differs from the exact case. Its comparison command reopens both attempts, checks common source map, ego route, initial actor positions/speeds, 20 Hz count and intersection right-pass before reporting the signal or turn difference. It returns unresolved legal outcome and `physical_acceptance_claimed: false`; its camera checks are byte/provenance checks, not pixel or decode acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C110264__NRS-484B-210-1__motor_vehicle_driver/tests -v` passed 13 source-shape tests; `cpu-saved-source-audit-tests.log` is SHA256 d32a91efbb9cb57f7702784b60855a7cc9abdc3a1f5f840edd4536b7dcfdc955. The exact assignment static check passed; the exact strict check failed because the package is still partial, recorded in `cpu-static-check.log` and `cpu-strict-check.log`.

Next CPU work: collect a reviewed Native map packet and implementation-specific source schema, connect `pass_right_route.py` to a lazy CARLA runner with same-attempt recheck, write the canonical finalizer and frame-map/camera synchronization, author the semantic proposals and complete exact offline, compatibility, saved-only, delivery and comparison proof receipts. The current audit can be integrated into saved processing once those artifacts exist. The absence of these CPU deliverables is not an external blocker.

## 2026-11-24 live-map and original-frame join checkpoint

`pass_right_live.py` now checks the SHA-sealed original map packet against the same attempt's loaded CARLA map name and OpenDRIVE bytes before returning one of the three exact route requests. It imports no CARLA module. The saved-source audit reopens this binding and rejects a stale map, route or variant. The left-turn route now moves left within the source intersection interval; the earlier draft began only beyond that interval. It also rejects a target footprint that would leave the packet's paved bounds. The original synthetic route fixture was widened from a left bound of -2.0 m to -2.5 m because the prior 1.2 m turn displacement plus a 0.9 m target half-width did not fit. These are fixture coordinates, not a reviewed public-highway map.

`pass_right_capture.py` joins 900 original 20 Hz Native actor rows to four camera frame IDs and appends each source identity to the supplied shared FrameMap interface. It rejects clock gaps, identity drift, missing actor fields, missing camera frames and nonboolean turn-signal samples. `pass_right_measure.py` now requires the source actor half-width and compares body extents during the pass; `pass_right_audit.py` independently rechecks 900 original frames, per-frame camera joins, and map/trace footprint agreement. These are source-shape and integrity checks; pixel decode, physical motion and canonical acceptance are not proved.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C110264__NRS-484B-210-1__motor_vehicle_driver/tests -v` passes 21 focused tests in `cpu-native-join-tests.log`. The exact assignment static check passes; the exact strict gate remains exit 1 because the result is truthfully partial. Next CPU actions: implement the CARLA runner that acquires the original map packet and actual actor/sensor callbacks, writes sealed trace/media and canonical finalizer outputs; author semantic proposals; add all exact construction/offline, positive and negative compatibility, process-saved, delivery and comparison receipts. The existing draft audit must be integrated into that path. Physical realization remains a later GPU check, while the listed software work is worker-owned.

## 2026-11-24 original media decode checkpoint

`pass_right_media.py` is an independent full-pixel decoder for four original camera PNG ZIP archives. The production entrypoint verifies each source SHA256 with streaming reads, enforces the pinned four-camera overview/detail dimensions, exactly 900 ordered PNG names and fully decoded images, and returns per-camera pixel digests. The decoder rejects absent, duplicate, reordered, corrupt, oversized or wrong-dimension frames. The tiny diagnostic fixture uses 8x4 pixels only inside direct unit tests; it is not a physical capture or a valid production camera. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C110264__NRS-484B-210-1__motor_vehicle_driver/tests -v` passed 24 tests in `cpu-media-decode-tests.log`, including a full 900-image decode and negative cases. This media check must still be wired to original capture and the final saved-only delivery path. The current source audit remains limited to source integrity and Native frame joins; its tiny JSON camera fixtures must not be treated as media proof. Remaining CPU work includes the CARLA-lazy runner, exact finalizer and receipt chain, semantic proposals, and integration of this decoder into canonical delivery/comparison audits.

## 2026-11-24 saved full-media delivery integration

`pass_right_audit.audit_delivery` now runs the existing source-bound map/route/trace/camera integrity audit and then `pass_right_media.audit_cameras` over every original camera archive. Its CLI `--full-media` applies this to an exact case or both sides of a controlled comparison. Production calls use fixed 1920x1080 front and 1280x720 rear/left/right dimensions; a fixture-only profile override is marked `production_camera_profile_verified: false`. A 900-frame-per-camera diagnostic ZIP integration fixture and altered-source rejection pass in the 25-test suite (`cpu-media-decode-tests.log`, SHA-256 `83605e4ead73ff43b49253989fd9f652c2cd1d4ba53b3be5d88bd9426be30dae`). This proves full PNG decoding in saved processing, not actual pixel visibility, Native provenance or legal acceptance. Exact runner, semantic proposals and canonical per-case offline/compatibility/process-saved receipts remain CPU work.

## 2026-11-23 three-case diagnostic bundle checkpoint

`build_offline_draft.py` binds the exact paragraph-(a) `left_signal`, `left_turn` and `neither` cases to the source-hashed plan, target behavior request, 20-Hz/900-frame and four-camera profile. The inline constructions embed the current source-gated right-pass route, live-map readback, Native actor/camera frame join, saved measurement, independent audit and full PNG media decoder. The runner checks exact variant identity and refuses unsourced Native capture. All three pinned `runtime.py offline` checks passed with materializations under `.runtime-work/`; the 26-test focused suite and pinned preflight passed. These are diagnostic drafts, not a canonical manifest or physical pass evidence.

Proof SHA-256 (logs under this assignment):

- `cpu-bundle-tests.log`: `8ef4b28d993ec663a726e44636a6c549a8bfe7cb2e4d6275744c271c0cf5f0e2` (exit 0)
- `cpu-preflight-bundles.log`: `57621d4ab10c582ab9fdca672e60c39572c222cf383cc793837a5ae753f1ca10` (exit 0)
- `cpu-static-check.log`: `571b76109c783bb1c6eabefd66fe2c2d9475982cc59e67eed260b19f3a556a04` (exit 0)
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-left_signal.log`: `0712d3c783da09b371518a7e6532701dbd755d885f605b357838efecf25665d0` (exit 0)
- `cpu-offline-left_turn.log`: `3561ed9e5311d0c62fc1c85ea4134b9f3a2a53251ec8047aeb77438c42abd5dc` (exit 0)
- `cpu-offline-neither.log`: `a72b1e51b003a10040bf7405264bc2df341d469c47bdc8d6d4da187fde85dbcd` (exit 0)

Next CPU work: bind a reviewed Native map/paved corridor and actual actor/sensor adapters to a production runner; author canonical semantic proposals and manifest; run exact source-shaped positive/negative compatibility, pinned saved-only and independent delivery/comparison receipts. Actual right-pass motion, signal and turn readback, camera visibility and statutory findings remain unverified. Scoped strict fails on truthful `partial` status.

## 2026-11-23 saved finalizer checkpoint

`pass_right_finalizer.py:finalize` now validates the selected `left_signal`, `left_turn` or `neither` case, invokes the independent saved source audit and full four-camera decoder, and returns the measured target signal, measured left-turn motion, right-pass and intersection-passage findings with source and pixel digests. It refuses a saved trace that lacks the exact pass. Its CLI writes only a fresh result and binds the saved manifest SHA256. `tests/test_pass_right_finalizer.py` exercises full 900-frame camera ZIP decode, wrong-case rejection and missing-trace rejection with source-shaped diagnostic fixtures; fixture dimensions are marked outside the production camera profile. No physical visibility, legal permission or acceptance is asserted.

Pinned preflight and scoped static check passed. The 27-test focused suite passed in `cpu-finalizer-tests.log`. The exact scoped strict gate exited 1 on partial status in `cpu-strict-finalizer.log`; the four current log hashes are retained in `result.json`. Canonical semantic proposals, complete manifest, production Native runner, runtime compatibility/process-saved receipts and independent delivery/comparison receipt chain remain CPU work.

## 2026-11-24 synchronized Native camera adapter checkpoint

`pass_right_sensor.py` now provides a CARLA-lazy acquisition adapter for one attempt. The caller supplies a previously source-bound world, four owned camera sensors, an actor sampler, road context and a controller callback. Before acquisition it requires synchronous 0.05-second Native ticks. It runs the controller before each tick, verifies each snapshot frame and the front/rear/left/right callback IDs, checks production camera dimensions and BGRA buffer lengths, encodes original PNGs into ordered ZIP archives, and sends the complete 900-row actor/camera trace through `collect_native_trace` and the shared FrameMap. A failed callback, mismatched frame or malformed image discards all partial archives. No physical behavior, highway status or legal outcome is inferred. The real actor/controller construction and source-reviewed map packet remain separate CPU work.

`build_offline_draft.py` now embeds this adapter in each of the three exact paragraph-(a) diagnostic bundles. The 32-test focused suite covers callback acquisition, full media decode, pre-tick controller ordering, wrong clock, missing camera and stale camera frame. Pinned preflight, three exact `runtime.py offline` checks and assignment static check passed. The exact scoped strict gate exited 1 because the package remains truthfully partial. Diagnostic 8x4 camera images prove software joins only; they are not production footage.

SHA-256 bound check logs:

- `cpu-sensor-tests.log`: `5e2512a23916fbc555f58b878c0ad5515b3aeccfab14f5ab428dcdfea02f381b` (exit 0)
- `cpu-sensor-preflight.log`: `ca94e14748a1678e5c7687be5ea20979aa9396bff2f4c97fdcf84de4e108ba2a` (exit 0)
- `cpu-sensor-offline-left_signal.log`: `28160ee6bde9adfd18a5d9675e4d3c9c672162ebfa6aae5ad308b9586dcddf45` (exit 0)
- `cpu-sensor-offline-left_turn.log`: `6387fd1da5da582ca8ab34aa9e3198063de3b53a3ca8096cb05ba7b4610e1e65` (exit 0)
- `cpu-sensor-offline-neither.log`: `af322fb4b14b9c96afc58ea5f4db938f94178007fed6de0db34b2dbb2e1655a6` (exit 0)
- `cpu-sensor-static.log`: `571b76109c783bb1c6eabefd66fe2c2d9475982cc59e67eed260b19f3a556a04` (exit 0)
- `cpu-sensor-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)

Next CPU work: acquire and review a source Native map packet; implement the CARLA actor spawn, source-station-to-world placement, right-pass controller and live pose/signal sampler; connect this adapter and saved finalizer to a canonical selected-case manifest; author semantic proposals and complete positive/negative compatibility, process-saved, independent delivery and controlled-comparison receipts. Preserve the partial status until the exact scoped strict gate passes.

## 2026-11-24 original actor sampler checkpoint

`pass_right_actor.py` now maps actual Native snapshot actor positions, velocities and target light-state readback into the original 20 Hz row schema. It requires each source map cross section to carry a world XY center point, reconciles centerline length with source station spacing, projects to a right-positive lateral coordinate, interpolates paved bounds, reads both actors from the same Native snapshot, and rejects missing actors, ambiguous/off-corridor geometry or invalid source shape. A caller supplies CARLA's left blinker bit mask; this module does not import CARLA or infer a signal from a requested controller setting. The three exact diagnostic offline constructions now embed this adapter. Their fixture map still has no reviewed world anchors, so none demonstrates physical acquisition.

The 36-test CPU suite, pinned preflight, three exact `runtime.py offline` cases and scoped static check passed. The exact scoped strict gate exited 1 on truthful `partial`. The saved source audit and full-media finalizer remain diagnostic pending a reviewed Native map, actor spawn/controller, semantic proposals, canonical case manifest, compatibility/process-saved and independent delivery/comparison receipts.

SHA-256 source and proof index:

- `pass_right_actor.py`: `c2aba314606d1d7cb392d1304258b3d31f99083dee77c011cdc3f47b8d963f17`
- `tests/test_pass_right_actor.py`: `d17dc36627825adfc7aeff6acd937aba915117e0f4ad61d7a656d3f9395c8fec`
- `build_offline_draft.py`: `abf3afa81ce82f5efc0c32acc5cbca8f6f0926191bdee1d20d7f236ca36fe72e`
- `execution-manifest.draft.json`: `b5515786877c8f2868a3f771d1a924400c744a828b36617540d7dbe8ab79f399`
- `construction-left_signal.json`: `66453b661b441f85edd2ec97aafbd2295a4cc0037c824e3339bd13ed8900d4ac`
- `construction-left_turn.json`: `fe7936c23787a295b7a988b50aef4e6f90aa682d55b75019be581e9d100490ff`
- `construction-neither.json`: `1bf3ec3c1674d64c6b76531aa919525e7bca1cba5f2e3b4e11772ecc07f8e034`
- `cpu-actor-tests.log`: `cecb33c3ca1e7ffcef3d8c79d9de6b12c6cdca0379eb9d8f97c3bae23cf0f828`
- `cpu-actor-preflight.log`: `068c7131d8360344105cd12bcee66d4a175d61e49b506788e5eeaf1efa891183`
- `cpu-actor-offline-left_signal.log`: `4b5b9837ff67b8334fea242bbdbbfafda423a49f4a4fc3dc1763c9255ea93db5`
- `cpu-actor-offline-left_turn.log`: `74a0d1aa3227066551eba01d2f3dd97a51ab1a633f51a4e5151170ce4ff28862`
- `cpu-actor-offline-neither.log`: `7d4ea04c1a7356d4be7d994b448eb0b15562ca0e6ebe8404e05a064b0f433ffb`
- `cpu-actor-static.log`: `571b76109c783bb1c6eabefd66fe2c2d9475982cc59e67eed260b19f3a556a04`
- `cpu-actor-strict.log`: `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`

## 2026-11-24 source-gated Native session integration

`pass_right_session.py` now connects the reviewed map packet, exact route request, source-world actor sampler and four-camera acquisition adapter. Before mutating the borrowed CARLA world it verifies loaded original OpenDRIVE bytes against the packet's `source_opendrive_sha256`; it sets and reads back synchronous 20 Hz settings, invokes operator actor/sensor/controller factories, captures the same-tick original actor and camera sources, rechecks the loaded map, writes a sealed trace in the scratch attempt, destroys owned actors/sensors and restores the original world settings. Requested signal/turn behavior remains separate from sampled motion and light-state readback. Factories must clean up any objects they create before returning if they themselves raise or return an incomplete group.

Five new focused tests cover successful sealing/restoration, changed map before mutation, capture failure, missing camera and clock readback refusal. The full 41-test suite passed. All three exact diagnostic constructions were rebuilt with the session and passed pinned offline. Pinned preflight and scoped static passed. Exact scoped strict exited 1 because status remains truthfully partial. Nine SHA-bound command receipts are in `result.json`.

Next CPU work: acquire and review an original map packet with world anchors and public-highway provenance; implement the local CARLA spawn, controller and sensor callbacks against it; author canonical semantic proposals and manifest, positive/negative compatibility, saved processing and independent delivery/comparison receipts. Native right-pass motion, signal/turn readback, production camera visibility and legal outcome remain unverified.
