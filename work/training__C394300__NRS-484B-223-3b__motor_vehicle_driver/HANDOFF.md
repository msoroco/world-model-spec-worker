# NRS-484B-223-3b at C394300

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `left_turn` / `center_turn_lane`.

Exact statutory source: NRS 484B.223(3)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Center-lane travel before a left turn from the highway. Planned comparison variable: `center_turn_lane_distance`. Requests: driver begins left turn within 200 feet of entering center turn lane; driver travels over 200 feet in center turn lane before left turn. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject is in a centre turn lane preparing to turn left from the highway.

Timing to retain: the distance is cumulative from entry into the lane to the start of the turn; the trace must cover both; the violation is the instant the accumulated in-lane distance passes 200 feet before the turn begins.

Exceptions and numeric alternatives planned: center turn lane travel numeric boundary 200 feet.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 200-foot measurement prototype

The exact NRS 484B.223(3)(b) text has a 200-foot (60.96 m) upper bound on travel in a dual-direction turn-only center lane before a left turn from the highway. `native/measure_center_lane.py` now reads original Native body/pose rows and authored lane geometry, brackets first body contact and observed left-turn onset, and reports a cumulative path-distance interval. Seven adversarial CPU tests pass. On synthetic one-foot probes, 199 and 200 feet remain unresolved because the event brackets straddle the threshold; 201 feet resolves above it in that fixture. This is a sampled geometry diagnostic, not Native design or legal outcome proof. The five case drafts remain unselected; executable map/runner, four candidates, exact offline/compatibility, saved Core and independent acceptance are still required.
