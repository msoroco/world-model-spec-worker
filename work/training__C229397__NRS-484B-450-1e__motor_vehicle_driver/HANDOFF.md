# NRS-484B-450-1e at C229397

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `park` / `crosswalk`.

Exact statutory source: NRS 484B.450(1)(e). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Parking on a crosswalk. Planned comparison variable: `crosswalk_parking_occupancy`. Requests: driver parks clear of crosswalk footprint; driver parks with footprint occupying crosswalk. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject stops, stands or parks; the footprint is on a crosswalk.

Timing to retain: judged for every instant at rest on the crosswalk; the standing/parked duration parameter separates a stop from a momentary halt in a queue.

Exceptions and numeric alternatives planned: when necessary to avoid conflict with other traffic; in compliance with law; in compliance with the directions of a police officer or an official traffic-control device.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Source-shaped crosswalk construction checkpoint

`measure_crosswalk.py` joins 600 consecutive actor samples at 20 Hz to 2,400 named camera frame hashes and a sourced crosswalk polygon. It measures original ego footprint overlap with the crosswalk for each rest frame and retains the first occupied rest frame, total rest and occupied rest frames, and maximum overlap. A 1e-6 m² polygon tolerance and 0.1 m/s rest diagnostic are engineering measurements, not statutory thresholds. The module leaves necessity, other-law compliance, officer/device direction and legal verdict unset. It rejects missing actor/camera rows, invalid polygons, case/time mismatches and missing crosswalk geometry provenance.

`prove_crosswalk.py` exercises the two witness targets with synthetic CPU source-shaped rows only: witness 1 remains clear, witness 2 occupies the crosswalk for 480 rest frames. It rejects truncation of either actor or camera source. Receipt `offline/crosswalk-source-proof.json` SHA256 `cf975c237890f2b0e3004da1ebe17731c5a31e61cf9e266b758447c8e08afe47`. Neither footprint nor pixel hash in that fixture is original Native evidence.

`build_offline_drafts.py` inlines all eight exact planned cases as **unselected** source-bound drafts. The pinned `runtime.py offline` path passed for each exact case, including the three exception pairs. Receipt `offline/pinned-offline-proof.json` SHA256 `7085b94f1363957e6bab4b4aff0e4d92b9751c6bfdf0a470b35f24e03f41f937`; manifest SHA256 `58b51869b2bbf52b79d285756fe6b5c3a69412dc2950dfb01af621783f8df8ea`. Each draft explicitly refuses Native execution, so this receipt is only a CPU source/check checkpoint.

Remaining worker-owned CPU work: implement CARLA map/crosswalk/vehicle capture and four synchronized source cameras; bind original polygon and per-frame footprint provenance; construct observed traffic conflict and officer/device direction context for the exception pairs; identify a source-backed basis for the `in compliance with law` pair; build complete saved-only processing, positive/negative compatibility, selected delivery manifests and independent audits. Reassess physical-risk fallbacks against actual motion/visibility. Then run the strict scoped ready gate. Status remains `partial`; original Native motion and legal outcome are unverified.
