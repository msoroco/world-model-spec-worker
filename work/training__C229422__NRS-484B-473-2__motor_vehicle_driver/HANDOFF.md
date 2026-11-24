# NRS-484B-473-2 at C229422

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `park` / `lane_marking`.

Exact statutory source: NRS 484B.473(2). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Displayed lights without cowl or parking lamps. Planned comparison variable: `parked_night_lamp_dimming`. Requests: lawfully parked vehicle uses dimmed lamps at night; lawfully parked vehicle uses undimmed lamps at night. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the vehicle is lawfully parked on a highway at nighttime; lights are displayed on it; cowl or parking lamps are not in use.

Timing to retain: the lamp state is judged for the whole time the vehicle stands with lights displayed at night; 'nighttime' is a clock condition relative to sunset and sunrise, declared by the reading.

Exceptions and numeric alternatives planned: where cowl or parking lamps are used, the depressing or dimming requirement does not apply.

Unresolved judgment or rule composition: 'lawfully parked' is a reference to the parking rules — rule composition. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU parked-lamp source diagnostic

Added `native/parked_lamp_measure.py` and `native/prove_parked_lamp_measure.py`. The draft lamp controller requests dimmed, full, cowl or parking-lamp modes and rejects unsupported modes. The saved-source diagnostic requires a nighttime clock and highway-location source, 600 joined parked frames at 20 Hz, four pinned camera identities, and a displayed lamp-state source on every frame. It counts dimmed, full and cowl/parking frames separately. The 0.05 m/s stop check and requested 0.4 lamp intensity are engineering diagnostics; neither proves optical dimming. Lawful parking remains separately unverified.

The proof exercises the four planned case IDs with synthetic full-interval dimmed, full and parking-lamp source shapes; the undimmed witness and exception-absent comparator intentionally share the same synthetic shape pending source-backed reuse review. It also checks the cowl controller alternative, rejects an unsupported mode and rejects five missing-source mutations. No Native pixels, actual lamp intensity or legal status is inferred.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_parked_lamp_measure.py > native/parked-lamp-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C229422__NRS-484B-473-2__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement/controller code `48a9b9054bc9a443c2fdf510093d8a498b8abc49611bad56f0beefc80b0bdf21`; proof script `9394410bf21fba414f5f05b7e23584b379ceca80534ed7af82d9d093fb3bfbce`; proof result `bc8f2e01330248b8d472b3ceec08e0783069f8065658ef4775525423369e0ba6`; preflight log `f1bcaf8de7ead0cc6b0ebfcf4c641ba8f8924ef83596a97c550bf25f832ab314`; scoped checkpoint log `4887ae8d60f613c8f9bf66b0b967983cd732e98b613291a61caf8acab913f7df`.

Next CPU work: establish lawful parking from the applicable source rules and record nighttime clock and highway facts, then implement exact Native parking and lamp controller, optical lamp-state capture and four source camera streams. Bind selected cases and any justified reuse in an execution manifest and run pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. There is no exact construction bundle yet, so keep `result.json` partial.
