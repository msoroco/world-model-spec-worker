# LVMC-11-43-010-C1 at C131364

## 2026-11-23 current CPU continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` passed, as did
`.venv-cpu/bin/python worker_check.py --assignment training__C131364__LVMC-11-43-010-C1__motor_vehicle_driver --complete`.

`native/long_duration_diagnostic.py` constructs two separate 600-frame, 20 Hz,
30-second authored primary left-exit trajectories, one per proposed circulating
lane. Each has entry, circulation and bounded exit phases. It also encodes four
named synthetic FFV1 streams and binds all 2,400 camera frame identities per
witness to the authored track and video byte hashes. Two positive checks and
three altered-source negatives passed: changed fourth camera frame join,
second camera hash, and route phase with rebound track hash. Receipt:
`native/long-duration-proof.json`, SHA-256
`4633af60d92d0333fc500fd7acad8c5d492cdbe86a76aa26ad04e56a387112e2`.

`native/audit_long_duration.py` independently checked both 600-frame routes,
the radial circulating lane positions, exit bounds, eight full video decodes,
and 4,800 camera frame joins. Receipt: `native/long-duration-audit.json`, SHA-256
`3a59dd0d2e4c0085ca61f59f48297f1787b2b8ace159a6dc5f9057b6bb6c81b7`.
Generated media and frame ledgers are in ignored
`.runtime-work/c131364-long-diagnostic-20261123/`.

These are synthetic CPU source-join diagnostics. The existing exact connected
Native bundles, runner, saved processor and comparison still use 240 frames and
two cameras. They must be migrated to 600 frames and four actual source cameras,
then rerun through current pinned offline, compatibility, saved processing and
independent acceptance paths. The two proposed witnesses remain unselected.
Original Native exit, lane occupancy, physical roundabout geometry, camera
pixels, intended exit evidence and legal interpretation have not been reviewed.
The assignment remains `partial`; no delivery readiness is claimed.

Actor: `motor_vehicle_driver`. Frozen cell: `multilane_roundabout` / `left_turn` / `lane_allocation`.

Exact statutory source: LVMC 11.43.010(C)(1). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Intended left-turn exit.. Planned comparison variable: `roundabout_exit_lane`. Requests: left-exiting driver uses left circulating lane; left-exiting driver uses right circulating lane. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject is in a multi-lane roundabout; the subject intends to turn left or complete a U-turn.

Timing to retain: the intended exit is shown by the exit actually taken, so the whole passage from entry to exit is needed; the left lane must be held through the circulating movement.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: 'intends to exit' is intention; the exit taken is the observable substitute. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
