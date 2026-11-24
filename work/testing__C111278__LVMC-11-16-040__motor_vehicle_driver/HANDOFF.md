# testing__C111278__LVMC-11-16-040__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.16.040 — The prima facie speed limit shall be fifteen miles per hour when traversing any intersection or street or highway if during the last one hundred feet of his approach to such intersection the driver does not have a clear and unobstructed view of such intersection and of any traffic upon all of the streets or highways entering such intersection for a distance of one hundred feet along all such streets or highways, except on a through street or highway or at a traffic-controlled intersection.
Assigned branch(es): Sight-conditioned traversal with neither stated exception..
Cell: C111278 (intersection, travel, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

Exact law: LVMC 11.16.040 is a 15 mph **prima facie traversal** value conditioned on view during the last 100 feet of approach, extending 100 feet along every entering street/highway. The through-road and traffic-controlled-intersection exceptions are distinct; no approach-speed duty or legal cutoff for view was invented. Frozen evidence.json has zero accepted recordings.

`case-plan.json` now has six exact case IDs (`blocked_below`, `blocked_at`, `blocked_above`, `clear_at`, `through_blocked`, `controlled_blocked`) and four comparisons (`speed_boundary`, `sight_condition`, `through_exception`, `control_exception`); each ID is prefixed by this assignment ID. Every case retains a physical-risk assessment. The blocked variants depend on a map-reviewed west-arm occluder site and actual source rays; no fallback is claimed without tested construction and receipts.

`sight_construction.py` validates jurisdiction, qualifying street intersection, all entering arms, route distance, source-backed through/control designations and map/occluder identity before lazy CARLA spawn. Caller owns spawned actor cleanup. `sight_measurement.py` rejects incomplete/noncontiguous original frames, missing 100-foot approach endpoints, an omitted entering arm, short ray extent, absent per-frame ray provenance or missing traversal. It retains actual measured traversal speed relative to 15 mph and gives no legal conclusion. `delivery_audit.py` joins exact case, map, four source camera files and SHA256, 900 contiguous original frames, candidate receipt and measurement provenance.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` exits 0; `cpu-tests.log` SHA256 46165d8706eba4647e1a54c7dda79927816330219136a54e52e41bd3a51b1625. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passes static checkpoint. Exact strict command with `--require-delivery-ready` exits 1 at partial/missing acceptance (see `cpu-strict-check.log`).

Next CPU actions: bind a reviewed Native map and site source packet; implement case-specific CARLA runner/controller and original capture, saved finalizer, full config/construction/measurement contracts and semantic proposals; generate exact offline and positive/negative compatibility receipts and saved-only process tests for all six cases; build and independently test comparison/pixel audits; create execution manifest and queue. Then rerun exact strict assignment check. Actual CARLA visibility, motion and media quality remain subsequent GPU checks.

## 2026-11-24 original sight acquisition and saved proof checkpoint

`native_sight_capture.py` now records exactly 900 synchronized 20 Hz original Native ticks from an injected world, ego velocity reader, signed route/boundary reader and per-entering-arm ray reader. It rejects missing map/authority source packets before acquisition, tick/snapshot mismatch, frame gaps, timing drift, invalid velocity or route data, missing arm rays, absent ray provenance and reused output. It seals original frame, ray, speed and site packets, recomputes the sight/traversal measurement and always invokes the supplied brake callback after an attempted run. The caller must supply real CARLA bindings and own actor cleanup; no test fixture is physical evidence. Camera capture is explicitly pending.

`saved_sight.py` independently checks the exact saved source SHA, 900-frame receipt and per-channel seals, then recomputes the measurement and rejects a forged Native summary. It reports physical visibility, camera coverage and legal conclusion as unresolved. `tests/test_native_sight_capture.py` and `tests/test_saved_sight.py` exercise positive original acquisition plus frame-gap, missing-arm, missing-source, modified bytes, case mismatch and forged-measurement negatives.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 14 tests; `cpu-tests.log` SHA256 b3d6d25c95f064151d6d39e392d08f9324f14513cbace448199b115a0d9715cc. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca. The exact scoped command with `--require-delivery-ready` exited 1 on truthful partial/missing acceptance; `cpu-strict-check.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Next CPU work: bind a reviewed municipal street intersection and real Native route/ray readers; add four-camera original capture and decode checks; author canonical per-case config/construction/semantic bundles, compatibility and saved-only process receipts, complete manifest and comparison/pixel audits. Reassess physical fallback placement only with reviewed map geometry and corresponding proof receipts. Then rerun the exact strict scoped check.

## 2026-11-24 synchronized camera checkpoint

`native_sight_capture.py` now accepts an injected original sensor reader during the same 900 world ticks as the route, speed and sight rays. It requires all four named cameras (`overview` 1920x1080; `approach`, `reference_corner`, `driver_reference` 1280x720), exact snapshot frame identity, PNG bytes and successful full image decode before sealing the per-frame source map. It writes the image paths and SHA256 values beneath the attempt, and it keeps the 900-frame map synchronized with the sight rows. A reader failure applies the supplied brake callback and cleans its temporary camera staging directory. The caller remains responsible for real CARLA sensor wiring, frame-safe queues and actor cleanup; the fake test reader is software evidence only.

`saved_sight.py` reopens the sealed camera map, joins every frame and timestamp to the original sight packet, hashes and fully decodes all 3,600 PNGs, checks the capture profile, and rejects missing or altered source images. The full positive and image-tamper test plus frame-mismatch and missing-camera negatives are in `tests/test_sight_cameras.py`. The positive case uses small compressed solid-color PNG fixtures at the required resolutions; they establish decode and join behavior, not physical visibility.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 17 tests (66.252 seconds), `cpu-tests.log` SHA256 `6344a4dbc9aada6007932ddee9532bafacbd18eed91ec58698f4989d482b66db`. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`. Exact strict command with `--require-delivery-ready` remains exit 1 on the truthful partial status; `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Remaining CPU work: bind reviewed municipal map/through/control/occluder source packets; implement the real CARLA sensor adapter and case-specific runner; write all six canonical config/construction/semantic bundles, offline and positive/negative compatibility receipts, saved-only process receipts, physical lifecycle/pixel and comparison audits, and execution manifest. Preserve the six cases and four comparisons. Do not assert that camera pixels show the required approaches until actual Native review.

## 2026-11-24 CARLA sensor adapter checkpoint

`carla_camera_adapter.py` is a lazy bridge for four operator-owned CARLA RGB sensor actors. It attaches listeners, requires every original frame ID and timestamp to match the world snapshot within 1 ms, rejects absent/extra channels, frame gaps, wrong dimensions, incomplete BGRA buffers, queue overflow and sensor timeout, then losslessly encodes the original RGB pixels into the PNG bytes consumed by `native_sight_capture.capture(camera_reader=adapter.read)`. The operator calls `adapter.start()` before ticking, `adapter.stop()` in cleanup, and destroys the sensors itself. The bridge does not assert that real approach geometry is visible.

`tests/test_carla_camera_adapter.py` tests BGRA-to-PNG values and frame/time, missing-source and overflow negatives with fake sensors; the separate 900-frame test still fully decodes all 3,600 required-profile images. Complete focused suite: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 20 tests (66.054 seconds); `cpu-tests.log` SHA256 `cd286e80db7bac2581d2684e58998f7728ef3640a395a976ca269761e95ba8d1`. Scoped static check passed with log SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`. Scoped strict delivery check exited 1 at truthful partial/missing acceptance with log SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Next CPU work: write the operator case runner that binds a reviewed site packet, route/ray readers and actual CARLA sensors; complete all six canonical bundles, semantic proposals, receipts, manifest, and independent comparison/pixel audits. The source-backed municipal map and exception designations are still unreviewed, and actual motion/video remain later physical checks.
