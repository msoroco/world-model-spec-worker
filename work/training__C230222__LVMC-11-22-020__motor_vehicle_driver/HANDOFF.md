# LVMC-11-22-020 at C230222

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `curb`.

Witness branch: Manner of driving beside a curb.

Comparison variable: `driving_manner_observables`. Proposed physical probes: maintain controlled curbside travel; perform erratic curbside travel; prudence unresolved. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C230222__LVMC-11-22-020__motor_vehicle_driver/assignment.json`, SHA-256 `7198406446a6ff5174fbe72c670a8d546a47ef06713881c037570ad5161d6b17`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 CPU source meter

Built `native/driving_cues.py` and `native/measurement-contract.json`. The meter joins 600 Native motion and video-frame rows at 20 Hz, hashes each source, derives speed, longitudinal acceleration and yaw rate, and retains gap/contact/pedestrian fields as source inputs. It refuses mixed provenance, short traces, frame/time mismatch, absent gap and wrong assignment identity. `native/prove_driving_cues.py` passed controlled and erratic source-shaped synthetic traces plus six negative cases. These are diagnostic fixtures, not observed CARLA motion or legal carelessness. The exact law has no numeric careless/imprudent threshold; legal review stays open. Original geometry, collision events, participant trajectories, four camera streams, highway-in-City context, exact selected constructions, compatibility, saved processing and audits remain pending.

## Unselected Native offline construction

`native/build_draft_bundle.py` materializes two exact 600-frame, 20 Hz, four-camera Native proposals under `draft-native/` and binds them in `draft-native-manifest.json`. Each offline run passed its exact `runner.py --check` and five unittest cases; hashed returned logs and construction hashes are in `draft-native-offline-proof.json`. The runner requests distinct curbside control schedules while keeping the frozen cell/actor/cameras/duration fixed, captures original motion/frame mapping and camera images, and attempts sealed Native output. CARLA was not contacted. The controls do not establish observed motion or legal carelessness. Raw Native gap, contact and pedestrian fields remain null pending original geometry/collision/pixel instrumentation and review. These are unselected diagnostic drafts; the planned probe IDs have not been promoted to delivery.
## 2026-11-24 exact curbside source construction checkpoint

The two frozen planned case IDs `__probe_a` and `__probe_b` now each have a matching unselected Native draft construction in `draft-native/`. Their current construction hashes and nine-test offline logs are bound in `draft-native-offline-proof.json` (manifest SHA-256 `a1ef5ee8a8aa455d331e4681aa8c4906066c9247774b034bc8c646cb4a0654c8`). The runner chooses a spawn only from a Native driving waypoint with an adjacent right-side sidewalk and creates a stationary sidewalk pedestrian there; mocked CPU tests exercise fallback spawn selection, missing curbside topology, actual walker creation calls, both longitudinal directions of body gap and overlap. It records selected Native spawn/waypoint IDs and walker ID. Whether the map is a municipal highway or the pedestrian appears in actual pixels remains subject to original-source review.

`native/body_geometry.py` derives original 2D actor-body footprints, finite planar gaps, and a 30-second constant-velocity swept-box overlap time from same-frame Native positions and velocities. `native/native_runner.py` retains 600 body-geometry rows, original collision sensor events, 600 ego rows, synchronized frame map and four source videos. Absence of a collision callback remains unknown; only an original collision event can support a positive contact cue. `native/driving_cues.py` recomputes the gap and overlap time from saved body corners/velocities and rejects tampered motion, missing source, time/frame mismatches and unbound contact. `native/prove_driving_cues.py` passed two synthetic source-shaped 600-frame traces plus ten negatives; `native/driving-cues-proof.json` SHA-256 `a542559e933d1c9e6c980a7cb4518a458fe19de8024f3103a935b161d96c2f2b`. These are CPU diagnostics and do not prove physical behavior or careless/imprudent conduct. No numeric legal cutoff has been assigned.

Exact next CPU steps: bind the two draft constructions as selected `probe_a`/`probe_b` deliveries with canonical camera names/profile and measurement contracts; author case-specific original-source diagnostic recipe and finalizer producing canonical result/channels; run each exact case through positive and missing-source compatibility plus recorded-only saved processing; write semantic proposals and independent delivery/comparison audits with negative tests; run the exact strict assignment gate. Keep `result.json` partial until that gate passes. Use `PYTHONDONTWRITEBYTECODE=1` and `TMPDIR=.runtime-work` on tests; generated fixture trees and temporary bundles belong under `.runtime-work/`.
