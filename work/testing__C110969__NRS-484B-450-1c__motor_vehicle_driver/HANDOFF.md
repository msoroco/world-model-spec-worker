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
