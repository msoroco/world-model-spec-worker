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

## Update 17: source-bound timing diagnostic and pinned offline drafts

The exact NRS 484B.413(3) sentence and frozen `paved_road` / `stop_stand` / `other_vehicle` cell remain the source. `measure_timing.py` requires 600 consecutive actor frames at 20 Hz, 2,400 named camera frame hashes, an immediate same-lane rear vehicle with positive surface gap, observed brake-lamp or hand-signal state, and longitudinal speed/acceleration. It reports first observed signal, stop and diagnostic 3 m/s² deceleration frames separately. The diagnostic threshold is engineering only; legal appropriateness and verdict are unset. The controller's lamp command never substitutes for observed lamp state.

`prove_timing.py` creates source-shaped **synthetic CPU** samples for both exact witness IDs in `.runtime-work/`, proves signal-before-deceleration for witness 1 and post-deceleration signal for witness 2, and rejects removed actor and camera source rows. Receipt `offline/source-timing-proof.json` SHA256 `ef987bf8d9798aa7ba2f9bdec3301d91ce0ecb25b205d24db58c39495ed20768`. This is a software test, not Native motion or original pixels.

`build_offline_drafts.py` inlines two unselected exact constructions. The pinned `runtime.py offline` command passed for both; `offline/pinned-offline-proof.json` SHA256 `70bfe385ce257344b238fb64c7edb97824a2ceee535e6fc028eb6c0b79783f93`, manifest SHA256 `149f07d91c1b404287b8d858153f7627d3c352e529d535a7c06a529424bdbb37`. Each draft explicitly refuses Native execution, and remains unselected. Scoped `worker_check.py --assignment training__C179480__NRS-484B-413-3__motor_vehicle_driver --complete` passed.

Remaining worker-owned CPU work: implement actual CARLA Native runner with four synchronized cameras and original actor/light-state capture; bind the exact saved-processing path and complete positive/negative compatibility; finalize the full statutory branch inventory including stop versus sudden decrease and the signal form/appropriateness judgment; implement and test risk-based fallbacks if physical risk warrants them; add independent delivery and comparison audits; then run the strict assignment ready gate. Physical motion and original pixels await local execution. Status remains `partial`.
