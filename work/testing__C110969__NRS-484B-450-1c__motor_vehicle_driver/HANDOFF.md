# testing__C110969__NRS-484B-450-1c__motor_vehicle_driver

Status: partial CPU observables and Native acquisition draft. Nine exact cases and eight controlled comparisons are proposed in `case-plan.json`; none is a realized recording or accepted review result.

Exact law: NRS 484B.450(1)(c) — A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within an intersection.
Assigned branch(es): Stopping or standing within an intersection.
Cell: C110969 (intersection, stop_stand, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## CPU construction checkpoint

The case IDs are this assignment ID followed by `__outside_reference`, `__inside_stop`, `__inside_stand`, `__inside_park`, `__traffic_conflict`, `__law_direction`, `__officer_direction`, `__device_direction`, and `__through_motion`. The eight comparisons isolate boundary contact, stop versus stand, stop versus park, traffic necessity, law direction, officer direction, official-device direction, and transient motion. The frozen evidence inventory contains no recordings, so each proposed branch retains an original-evidence gap. The exact law supplies no numeric parking duration or legal spatial epsilon; the checker reports original frame observations without issuing a legal conclusion.

`intersection_observables.py` measures original body-footprint contact against a reviewed highway intersection polygon and retains per-frame speed and independent activity/exception context. It requires reviewed highway and joining-roadway basis, matching map IDs, monotonically increasing 20 Hz frames, and all source references. `finalize_observables.py` consumes an exact-case source manifest with SHA256-sealed original boundary, Native trace, and activity packets. It rejects absent or changed packets and attempts to escape the attempt directory. The initial CPU tests exercise contact including edge/crossing overlap, outside control, false/unreviewed joining status, map mismatch, missing activity source, nonmonotonic frames, successful finalization, and tampered trace rejection. The synthetic test geometry demonstrates only software behavior, not actual map geometry, motion or acceptance.

`comparison_audit.py` checks two original measurement records against each comparison's measured fixed-condition and deliberate-difference keys. It rejects missing source seals, absent observations, changed intersection boundaries or fixed conditions, and an unobserved declared difference. It returns no legal judgment. The checker needs actual condition receipts from the runner before canonical comparison delivery; the current test uses synthetic receipts.

`native_acquisition.py` adds a lazy Native capture adapter. It requires a separately reviewed map-boundary packet matching the live map, synchronous 20 Hz settings, an exact case/run identity, a controller request source, and an independent per-frame activity/context observer. Each tick records Native frame/time, actual bounding-box footprint, measured velocity, controller request and activity source; it seals the boundary, trace and activity packets with SHA256 for `finalize_observables.py`. The finalizer now checks exact case/run identity and per-frame activity/trace joins. This CPU proof uses a fake Native world, so it is not physical boundary or exception evidence. The adapter does not implement the full scene controller or four-camera capture.

`cpu-intersection-tests.log` records thirteen passing tests. `cpu-static-check.log` records a passing assignment-scoped static check. `cpu-strict-check.log` records the exact strict delivery check failing at the partial-status acceptance line; the substantive delivery artifacts below remain unfinished. `result.json.tests` carries the hashes and exit codes.

## Next CPU actions

1. Integrate a case-specific CARLA scene runner/controller and four-camera capture for the planned cases, using `native_acquisition.acquire` for original packets. Establish the Native map polygon by reviewed roadway geometry rather than test coordinates, and source actual intentional activity and any claimed exception from original observations. Keep the case and comparison variables fixed.
2. Build the canonical case bundles, measurement contracts, semantic proposals and execution manifest. Bind this finalizer to original capture and saved-only processing, then run each case's exact offline and positive/negative compatibility proofs.
3. Implement and CPU-test independent delivery and comparison audits, including rejection of missing or stale original sources, physical-completion claims without support, and differences in fixed conditions. Assess physical risks per manifest case and add fallback constructions only where justified.
4. Rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C110969__NRS-484B-450-1c__motor_vehicle_driver --complete --require-delivery-ready`. Do not mark ready before it passes.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 Native scene and camera-source checkpoint

`native_scene.py` now validates exact route case/map identity, a separately reviewed Native approach lane and joining-roadway intersection packet, body extent, source refs, and whether the planned destination body footprint intersects the reviewed boundary. The through-motion route ends beyond the intersection; the eight halt cases use the planned inside/outside destinations. `DestinationController` requests approach throttle/steer, destination braking, and a guaranteed final brake through `native_acquisition.acquire`. These are controller requests; actual motion and activity are measured from Native packets rather than inferred from case names. Its 13.5 m/s upper limit is an engineering cap, not a legal stopping definition.

`native_media.py` joins four original camera callback PNGs to each just-ticked Native frame, verifies the exact overview (1920×1080) and three detail (1280×720) sizes, seals four camera archives and an exact frame map, and independently reopens and fully decodes every saved image. `native_acquisition.acquire` now defaults to 900 samples (45 seconds at 20 Hz), accepts `NativeMediaWriter`, and binds the media manifest SHA256 into the original source manifest. `audit_saved_acquisition` rejects altered trace/media seals, missing archives, camera frame mismatch, and changed PNGs. No source string or CPU fixture establishes actual Native origin or physical visibility; those need local review.

Proofs: `.venv-cpu/bin/python -m unittest discover -s work/testing__C110969__NRS-484B-450-1c__motor_vehicle_driver/tests -v` passes 20 focused tests (`cpu-intersection-tests.log`). `.venv-cpu/bin/python work/testing__C110969__NRS-484B-450-1c__motor_vehicle_driver/tests/prove_900.py .runtime-work/c110969-450-1c/diagnostic-900` joins 900 synthetic Native-shaped frames and fully decodes 3,600 synthetic camera PNGs (`cpu-900-media-proof.log`); this is a software stress proof only. Assignment-scoped static check passes (`cpu-static-check.log`), exact strict check fails on truthful partial status (`cpu-strict-check.log`). Log SHA256 values are in `result.json`.

Remaining CPU construction: implement a real map-source review/binding and Native camera sensor adapter rather than relying on abstract callbacks; author case-specific canonical bundles, semantic proposals, manifest, and exact offline/positive-negative/saved-only proofs; bind independent delivery/comparison audits to those bundles. Original legal exception observations and physical intersection contact remain subject to later Native capture and independent review. The package is not delivery-ready.

## 2026-11-23 full saved finalizer checkpoint

`finalize_delivery.py:finalize_saved` now joins `finalize_observables.py` original boundary/trace/activity seals to `native_media.py:audit_saved_acquisition` for the same exact case and Native run. It requires all 900 20 Hz frames and a full decode of all 3,600 saved camera PNGs before returning an observation result. It keeps physical completion false and legal conclusion null. `tests/test_finalize_delivery.py` rejects a short capture even with complete short media, missing media, and wrong exact case. The full-length `tests/prove_900.py` now invokes this saved finalizer after its synthetic Native-shaped acquisition; the retained log confirms the 900/3,600 join. The diagnostic does not prove real contact or a statutory exception.

The pinned CPU preflight and 22 focused tests passed. Canonical case bundles, source-reviewed map/exception context, semantic proposals, exact compatibility receipts, runtime saved processing and complete independent delivery audits remain CPU work. The result stays partial until the exact scoped strict gate passes.

## 2026-11-23 independent saved audit checkpoint

`audit_finalized.py` independently reopens SHA256-sealed original boundary, trace and activity packets for the exact case/run. It joins all 900 consecutive trace, activity and finalized frame IDs, recalculates contact from the original footprint and boundary, compares measured speed and every activity/exception context field to the independent original activity packet, then runs the saved four-camera audit for all 3,600 decoded images. It rejects changed finalized contact, incomplete joins, source-seal mismatches and unsupported physical or legal claims. This is a CPU source-integrity check; the diagnostic source is synthetic and makes no physical or legal finding.

`tests/prove_900.py` now exercises the independent positive audit and a modified finalized-contact negative using a full 900-frame synthetic acquisition (`cpu-900-audit.log`). The 23 focused tests and pinned preflight passed. The nine exact diagnostic constructions were rebuilt to include the audit code and each passed a fresh exact offline check (`cpu-offline-*-audit-v2.log`). Assignment-scoped static passed; exact strict still exits 1 on truthful partial status (`cpu-strict-audit.log`). Current test SHA256 claims are verified in `result.json`.

Next CPU work: reviewed original Native intersection geometry and independent exception source packets; production Native scene and camera adapter; canonical semantic proposals and delivery manifest; each case's positive/negative compatibility and saved-only processing; and independent canonical delivery/comparison receipts. Do not infer an exception from the case name or mark ready until the exact scoped strict command passes.

## 2026-11-23 nine-case diagnostic bundle checkpoint

`build_offline_draft.py` now emits nine exact inline constructions and `execution-manifest.draft.json`, preserving each planned activity, inside/outside destination, exception context, original 20-Hz/900-frame interval and pinned four-camera dimensions. The bundles embed the current Native acquisition, scene, media, saved finalization and comparison code. Their runner verifies the embedded source-hashed plan and exact case attributes, then refuses an unsourced Native launch. This is diagnostic preparation, not a canonical delivery manifest or original exception evidence.

Pinned preflight and builder passed; all nine exact `runtime.py offline` checks passed with materializations under `.runtime-work/`. The focused suite passed **23** tests, including plan/manifest/source joins. Scoped static passed; exact scoped strict exited 1 on truthful partial status. Commands and cleaned log hashes are in `result.json.tests`. Next CPU work remains a surveyed map and original exception source, production runner, canonical semantic proposals/manifest, positive/negative compatibility, process-saved and independent delivery receipts.

## 2026-11-24 Native box-local yaw footprint continuation

`native_acquisition.body_footprint` now applies the Native bounding box local yaw before the actor world yaw. The earlier projection ignored box-local rotation, potentially misclassifying intersection contact for a rotated vehicle body. A focused test verifies the four world XY corners for a 45-degree local box on a 90-degree actor. This preserves observed geometry without a legal conclusion.

The 24-test suite and pinned CPU preflight pass. `build_offline_draft.py` refreshed all nine exact diagnostic bundles with the corrected Native capture code; all nine pinned `runtime.py offline` checks pass. Scoped static passes. Exact scoped strict exits 1 on truthful partial status. These are diagnostic software checks, not reviewed map/exception or original Native evidence.

Current SHA-256 log receipts:
- `cpu-box-rotation-tests.log`: `2a48eb1744a587171859131f4dd4f81861e383a7b4c4e398fce35e4aadbee3ea`
- `cpu-box-rotation-build.log`: `d358dc7f98d860236bb4d45d9111d5f9bcd5d29620582bfe5c64d9df01129a1e`
- `cpu-box-rotation-preflight.log`: `ecc244ba0d1e72dc82e9ac21464c489a59c7c1b2490e8e58ef13fcfda2d54979`
- `cpu-box-rotation-static.log`: `9296c9674fd98ad66bd320223857489a92ea91ac01b71648282fd5cbe42399d7`
- `cpu-box-rotation-strict.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
- `cpu-box-rotation-offline-outside_reference.log`: `d02262ef6acc45d54b102952d737a3af3d09382a4f3c5cdd854e3ccc3330a7d6`
- `cpu-box-rotation-offline-inside_stop.log`: `5f7c435e6367c1241f2877134425ddd4836c7200b39db0d2339ef61fe1299d55`
- `cpu-box-rotation-offline-inside_stand.log`: `56bbebf8399938c16d8ffff5a28f34d94161db6c771858ea73649aaab757ce49`
- `cpu-box-rotation-offline-inside_park.log`: `3b1b73c90b3e0357c4e73ed1f483efcf1c9ce7e87649808edadd1469e9e206e5`
- `cpu-box-rotation-offline-traffic_conflict.log`: `ea1105d73dbc8d1f4b20d456a628d280d53db43941d71884c071a08cc045d19c`
- `cpu-box-rotation-offline-law_direction.log`: `ad24c0044259435786fae8c720da560b1791654122579dd2dec40ddd71b23fff`
- `cpu-box-rotation-offline-officer_direction.log`: `77403855aaf808c3fe5daf8a09739ee4334084c50d7af8e7145914f478175c73`
- `cpu-box-rotation-offline-device_direction.log`: `22bb22a2888440c299ffb20a08822f587be51797f41062dda76a2607b070d835`
- `cpu-box-rotation-offline-through_motion.log`: `0cf3f71557bad2fb8b36d356fe957fee57700ede800e9cbdabbfddc68de560e0`

Next CPU work: review and retain original map/exception source packets, implement the production camera sensor adapter, then prepare source-bound canonical proposals/manifest, positive/negative compatibility, saved-only processing and independent delivery receipts. Keep physical contact and legal outcome unresolved until original capture and review. No Git or frozen/runtime/batch/shared edit was made.

## 2026-11-24 Native RGB camera callback adapter

`native_camera_adapter.py` now consumes four existing Native RGB camera sensors at the exact just-ticked frame. It validates sensor type and configured dimensions, rejects missing callbacks and invalid BGRA length, converts callback bytes losslessly to PNG, and closes sensors on cleanup. Sensor placement and physical visibility still require original review. The adapter is embedded in all nine rebuilt exact diagnostic bundles.

The pinned preflight, 28 focused tests, nine exact offline checks, and scoped static check pass. Exact scoped strict exits 1 because result status remains truthful partial. New log receipts are SHA256-bound in `result.json.tests`. Next CPU construction remains reviewed map/exception context, production scene integration and original capture, canonical proposals/manifest, positive/negative compatibility, saved processing and independent delivery audit.
