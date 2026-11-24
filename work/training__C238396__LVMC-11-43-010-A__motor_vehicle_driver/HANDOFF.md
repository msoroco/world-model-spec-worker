# LVMC-11-43-010-A at C238396

Actor: `motor_vehicle_driver`. Frozen cell: `roundabout` / `circulate` / `other_vehicle`.

Witness branch: Vehicular circulation within a roundabout..

Comparison variable: `roundabout_circulation_direction`. Proposed physical probes: circulate counterclockwise; circulate clockwise within same roundabout. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C238396__LVMC-11-43-010-A__motor_vehicle_driver/assignment.json`, SHA-256 `839ad1e35cc443bcccca32b3a0a1c0cac4abb106e4951669ee48460ed23d65ad`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 authored roundabout direction construction checkpoint

The exact law has one continuous within-roundabout direction requirement and no exception in its supplied text. The two existing comparison probes now have separate 30-second, 600-frame, 20 Hz inline construction bundles in `draft-native/probe_a/construction.json` and `draft-native/probe_b/construction.json`. They share the same authored connected roundabout OpenDRIVE road (`native/roundabout-road.xodr`), camera geometry, ego radius (16.75 m), other-vehicle path (20.25 m), duration, and recording description. The only deliberate request difference is ego translational direction. The road bytes are copied from the prior C132497 right-exit package and independently checked for exact hash and circulatory arc geometry. The copy is an authored road proposal, not an observed Native map or proof of jurisdiction.

`native/roundabout_direction.py` measures direction from the signed cross product of consecutive radial *positions* in the road coordinate frame. It rejects missing/truncated source frames, frame/time mismatch, out-of-annulus requests and insufficient within-roundabout window. Heading and yaw rate remain corroborating context; they cannot substitute for translational motion. The authored requests measure counterclockwise for `probe_a` and clockwise for `probe_b`; the independent `native/audit_requested_routes.py` checks the common road source, exact case bindings, fixed conditions and opposite signs. `native/request-comparison-proof.json` is a diagnostic proof of the authored requests only. No original CARLA motion, pixels, map readback, physical completion, legal verdict or accepted recording is claimed.

Both exact bundles passed the current pinned `runtime.py offline` command recorded with hashed logs in `draft-native-manifest.json`. The ordinary assignment-scoped `worker_check.py --complete` checkpoint passed after these additions. The cases remain unselected drafts and `result.json` remains `partial` because Native capture/controller integration, source-bound positive and negative compatibility, actual process-saved, fallback candidates and independent delivery/comparison audits are still worker-owned CPU work. The next construction step is a complete 600-frame Native controller/acquisition path on this road with original actor pose and four sealed source-camera streams; then select and reprove the cases against the final construction. The signed-area meter must consume saved original pose after acquisition. Physical roundabout geometry, jurisdiction, motion and pixel visibility remain for local execution review.
