# NRS-484B-510 at C135709

Actor: `motor_vehicle_driver`. Frozen cell: `narrow_road` / `park` / `parking_restriction_device`.

Exact statutory source: NRS 484B.510. Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Restricted-zone parking. Planned comparison variable: `restricted_zone_purpose`. Requests: vehicle occupies restricted zone for its posted purpose; vehicle occupies same zone for an unrelated purpose. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the place is a restricted parking zone; the subject stops, stands or parks there for a purpose other than the one the zone is restricted to.

Timing to retain: 'for any purpose or length of time' — no duration makes the wrong use lawful; but the excepted loading stop is 'temporary', so a duration bound for it must be declared; the interference test runs while another vehicle waits.

Exceptions and numeric alternatives planned: a passenger vehicle may stop temporarily while actually engaged in loading or unloading passengers, provided it does not interfere with a vehicle waiting or about to enter the zone for its restricted purpose.

Unresolved judgment or rule composition: the purpose a zone is restricted to is read from its sign; the subject's own purpose is interior state, evidenced only by a passenger exchange. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU saved-measurement construction

Added `native/restricted_zone_measure.py` as a draft saved-source measurement contract for 600 frames at 20 Hz. It consumes `zone.json` and `raw-frames.json` with four named camera identities per frame; it derives in-zone stationary time, passenger activity overlap and waiting/entering vehicle overlap. It records the restricted purpose and subject purpose declaration separately, marks sign authority unverified and returns no legal conclusion. The 0.05 m/s stationary threshold is an engineering diagnostic, never a statutory cutoff. The source observation term mapping is now in `case-plan.json`.

Command: `.venv-cpu/bin/python work/training__C135709__NRS-484B-510__motor_vehicle_driver/native/prove_restricted_zone_measure.py > work/training__C135709__NRS-484B-510__motor_vehicle_driver/native/restricted-zone-proof.json` (exit 0). The proof exercises three 600-frame synthetic positive cases and five negative source failures. Proof SHA-256: `fafbce19f00362ed5294e468ad6ead76a3b284185c74bb44dc6f0b5db6f7b59b`. Measurement script SHA-256: `b572cf365e530539709a81ddfd80df9eb17d01ce9c9664177b137b308401ca4a`. These are diagnostic fixtures; no Native camera video or original source was captured.

Still required: executable narrow-road Native construction and parking controller; sign/zone authority and effective conditions from original evidence; source-bound vehicle/passenger purpose, waiting driver's purpose and all four decoded camera videos; full selected case and exception matrix; exact current-runtime offline, positive/negative compatibility, process-saved, semantic proposals and independent audits. The temporary loading exception must be reviewed on its observed facts without inventing a legal duration threshold. Keep the assignment partial.
