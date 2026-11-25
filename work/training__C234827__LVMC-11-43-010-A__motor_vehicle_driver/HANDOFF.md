# LVMC-11-43-010-A at C234827

Actor: `motor_vehicle_driver`. Frozen cell: `rotary_island` / `circulate` / `traffic_island`.

Exact statutory source: LVMC 11.43.010(A). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: frozen selected witness. Planned comparison variable: `roundabout_rotation`. Requests: driver circulates counterclockwise; driver circulates clockwise. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject operates a vehicle within a roundabout.

Timing to retain: the direction is judged at every instant within the roundabout; the sense of rotation needs a window of frames, not one.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 3 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Current-runtime 30-second rotation checkpoint

The earlier 12-second/240-frame constructions and receipts remain intact as historical diagnostics. `native/build_30s_drafts.py` now creates two exact unselected 30-second/600-frame requests under the current assignment law field. Both request the frozen roundabout cell, a common zero-time starting pose, 23.75 m radius, 8 m/s speed, a 20 Hz frame clock and four named source cameras with the current 1920x1080 overview plus three 1280x720 detail views. Only requested angular direction changes. The inline preflight checks frozen assignment/law and exact track hashes, recomputes every requested position, and requires continuous signed angular progress. These rows are authored requests, not Native motion.

Pinned `runtime.py offline` passes for both exact witness drafts. Receipt `offline/30s-pinned-offline-proof.json` SHA256 `e72b689fb42ef83ec49139144c1d12c996594c9ba128a6ef567511777efe4b5d`; manifest SHA256 `77022ff931c809ee494c70d613e2b8601a20cefe1550040b9b2e23626664558f`. `native/prove_30s_pair.py` confirms fixed speed/radius/clock and opposite continuous rotation requests over more than one full turn, and rejects a removed frame, wrong sign and altered assignment bytes. Receipt `offline/30s-pair-proof.json` SHA256 `9b2facdd8bd35b809e2a6feed719a855124b60fcf11e07cb9038dc2713fc2fc1`.

Remaining worker-owned CPU work: integrate the 30-second requests with the actual CARLA capture runner and four synchronized original source cameras; prove full-duration saved-only processing and source-bound positive/negative compatibility; independently review three accepted recordings for equivalence to this branch; complete semantic proposals and delivery/comparison audits; evaluate candidate risk and run the strict scoped ready gate. Native roundabout geometry, motion, camera pixels and legal result remain unverified. Status remains `partial`.

## 2026-11-24 current-runtime selected construction checkpoint

Two exact selected 600-frame, 20 Hz, 30 s Native requests are now in `selected-construction-witness_1.json` and `selected-construction-witness_2.json`. Each has a `fallback1` in `selected-candidates/` lowering the requested controller speed from 8 to 6 m/s while retaining law, cell, actor, ring radius, cameras, duration, observation contract and rotation sign. All four exact source-bound `runtime.py offline` runs passed; logs and hashes are in `selected-probe-manifest.json`. The case-specific `native/measure_saved_30s.py` verifies 600 original frame/time joins, map readback, full body vertices, signed position and yaw progress, and four decoded source videos. Its source-shaped positive and missing/changed-source CPU tests passed, as did the current measurement contract and candidate-invariant validators. These tests use synthetic diagnostic data only; they establish software behavior, not original Native circulation.

The accepted clockwise, counterclockwise and outside-roundabout rows are membership-only in the frozen input. No source receipt inventory accompanies them, so their source-hashed equivalence cannot be established and reuse remains zero. Exact statutory direction and frozen `rotary_island/circulate/traffic_island` scope remain fixed; physical island/traffic-control realization and legal result remain unverified.

Next worker-owned CPU steps: build source-hashed 600-frame four-view diagnostic fixtures for both cases and fallbacks; run current positive and missing-source negative `runtime.py compatibility`; connect saved finalizer to current processing and pin receipts; add canonical semantic proposals, physical completion criteria, independent delivery/comparison audits and final execution manifest; update case-plan source observation mapping; run exact scoped strict gate. Do not promote the current partial result until these pass.
