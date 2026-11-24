# NRS-484B-270-2a at C247014

Actor: `motor_vehicle_driver`. Frozen cell: `same_direction_multilane` / `overtake` / `cyclist`.

Exact statutory source: NRS 484B.270(2)(a). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Due care and conditional immediate-left-lane movement. Planned comparison variable: `immediate_left_lane_for_cycle_pass`. Requests: driver changes to available immediate left lane before cyclist pass; driver passes cyclist without moving into available immediate left lane. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject overtakes or passes a bicycle, electric bicycle or electric scooter going the same way; there is more than one lane for traffic in that direction; the lane to the immediate left is available.

Timing to retain: the lane change precedes the abreast phase — the subject must already be in the left lane when it passes; the left lane is held for the whole of the pass.

Exceptions and numeric alternatives planned: the lane to the immediate left is not available, or moving into it would not be reasonably safe.

Unresolved judgment or rule composition: 'due care' and 'reasonably safe' are judgement elements needing declared bounds. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU same-direction bicycle-pass source diagnostic

Added `native/cycle_pass_measure.py` and `native/prove_cycle_pass_measure.py`. The saved-source diagnostic requires a covered bicycle, electric bicycle or electric scooter; at least two same-direction lanes; distinct subject and immediate-left lane IDs; full 600-frame, 20 Hz same-direction actor histories; and four pinned camera identities. It measures the body-overlap passing span and counts subject frames in the immediate-left lane, including when that lane was first entered. Left-lane availability and reasonable safety remain source declarations needing original evidence; due care is not judged.

Four planned synthetic case shapes keep the longitudinal bicycle pass fixed at frames 320 through 480. The lane-change witness enters the immediate-left lane at frame 300, before passing, and stays there through the pass. The no-change witness and exception-absent comparator remain in the right lane; the exception-present shape declares the left lane unavailable. A fifth diagnostic exercises the alternative that moving left would not be reasonably safe, without claiming a new selected case. Six missing-source mutations reject wrong machine type, one-lane roadway, missing availability, truncated history, camera loss and opposing direction. These are `synthetic_native_sample` traces, not Native observations or legal acceptance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_cycle_pass_measure.py > native/cycle-pass-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C247014__NRS-484B-270-2a__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `358a532f07479557fa65f8572695379b2e0bc71070a13909103edbc6dbfeb0ce`; proof script `fc325c6a0557e66661e27c75e08c96e9782842e878693c3304b4d6dce7f0247c`; proof result `3c27ce88496480666cade1dab183cf7afbb36abc51281f30a71f0a90e65216af`; preflight log `d546e6a47654da70b2bef89b1f480f704459d050e515a3f2372fb7947428b431`; scoped checkpoint log `0c03e118d73f22a45253a0657526a0a4ff41fb4c51a1e7b2320878c09b4270f5`.

Next CPU work: implement exact multilane Native scene and both lane controllers with source-based lane availability and safety diagnostics, four source camera videos, execution manifest, pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. Make the linked comparison hold the bicycle path fixed and prove lane change before the full pass. No exact construction bundle exists yet; keep `result.json` partial.
