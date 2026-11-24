# NRS-484B-913 at C230231

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `fire_hose`.

Exact statutory source: NRS 484B.913. Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Passage over a qualifying hose, subject to command-official consent. Planned comparison variable: `unprotected_hose_crossing`. Requests: driver routes around unprotected fire hose; driver traverses unprotected fire hose without documented consent. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: an unprotected fire department hose is laid on a highway, private way or place; the subject drives over it.

Timing to retain: the violation is the passage over the hose.

Exceptions and numeric alternatives planned: with the consent of the fire department official in command.

Unresolved judgment or rule composition: consent is a communication, not a scene fact; at best an officer's gesture is observable; whether the hose is 'unprotected' depends on a ramp or cover being absent. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Source-shaped hose passage construction checkpoint

`measure_hose.py` joins 600 consecutive original actor rows at 20 Hz, 2,400 named camera frame hashes, and a sourced hose centerline/radius, fire-department use purpose, qualifying way, and cover/ramp inventory. It measures vehicle-footprint overlap with the hose while moving and the ego path length. A 0.1 m/s driving diagnostic and the hose radius are engineering values, never statutory cutoffs. The command-official consent record is checked for official identity, exact case and drive-over permission; a missing record yields unknown consent, not proof of refusal. The legal verdict is unset.

`prove_hose.py` exercises the four exact cases with **synthetic CPU** sources: witness 1 routes clear, witness 2 crosses, and both consent-branch cases cross with documentation only in exception 1 case 2. It rejects removed actor and camera rows in every case. Receipt `offline/hose-source-proof.json` SHA256 `308a0aa5d5c96a2e32dd978eae8963a8a19ef88ad800c96f0758d2eef8dacdef`. These diagnostic rows are not CARLA motion, original pixels, department inventory or real consent.

`build_offline_drafts.py` inlines all four exact planned cases as **unselected** drafts. Each passes pinned `runtime.py offline`. Receipt `offline/pinned-offline-proof.json` SHA256 `9dd8a6a7befa20bd6e11fbb596b094821d3053cc2b67b2766cdad5cef1e5b159`; manifest SHA256 `094edebe1daddca71c1aecfd1912c99cf861b271633ebf4d96b37aa0b816f0eb`. The drafts explicitly refuse Native execution and are not selected delivery recordings.

Remaining worker-owned CPU work: construct original Native hose/cover/fire-apparatus/vehicle scene and four synchronized cameras; bind actual hose asset inventory, way and fire-use purpose, per-frame original actor/camera sources and command-official consent communication; implement exact saved processing and positive/negative compatibility; add appropriate risk-based fallbacks, semantic proposals and independent delivery/comparison audits. Then run the strict scoped ready gate. Status remains `partial`; physical realization and legal outcome remain unverified.
