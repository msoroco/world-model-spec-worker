# NRS-484B-413-3 at C179480

Actor: `motor_vehicle_driver`. Frozen cell: `paved_road` / `stop_stand` / `other_vehicle`.

Exact statutory source: NRS 484B.413(3). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Intentional stop with a rear-driver recipient. Planned comparison variable: `advance_rear_signal`. Requests: driver signals rear vehicle before stopping; driver stops before signaling rear vehicle. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject stops or suddenly decreases speed; a vehicle is immediately to the rear.

Timing to retain: 'without first giving' — the signal must precede the stop or the deceleration; a lead time for the signal must be declared; the text gives no distance for this case.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: 'suddenly' is a judgement element: a deceleration bound must be declared; a brake lamp is an actuation, not the deceleration: the rule reads both. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Update 080 signal-timing construction slice

`advance_rear_signal.py` defines the two selected CPU target schedules on a fixed 20 Hz clock. The reference commands the ego brake lamp at frame 100, 20 frames before the planned frame-120 stop/deceleration; the contrast commands it at frame 121. The same action frame, rear-vehicle same-lane requirement, declared 12 m rear gap, declared 3 m/s² suddenness diagnostic bound and retained-source row list apply to both. The plan rejects unknown cases and invalid lead/bounds. This schedule does not attest actual lamp state, deceleration, rear-vehicle proximity, appropriate signaling or a legal conclusion. Its construction SHA-256 is `f4ce9ae11775747c8a2fc671c498ed804b9413306004924955e182241197f1dc`. Focused tests pass (`update080-timing-tests.log`, SHA-256 `0bc33e3535e3fd20b82de97cd5512d0e197268f9390995d59050062b0ca01741`); scoped static complete passes (`update080-scoped-static.log`, SHA-256 `4da12ad50b0dba6ed9c573b8ce462628c74054a24e730e2d235e9e106db81b6e`). `result.json` stays `partial`.

Next: integrate this schedule into a work-owned Native runner with source-retained ego/rear actor state and four cameras, create four distinct risk-triggered candidate constructions for each exact selected case, author current JSON-graph CPU diagnostic recipes, run exact offline/compatibility/recorded-only saved chains, then physical/delivery/comparison audits and scoped strict. Keep the declared suddenness/gap bounds diagnostic; original Native and legal judgment remain unobserved.
