# LVMC-11-40-180-B at C230207

Actor: `cycle_or_scooter_operator`. Frozen cell: `road` / `travel` / `access_restriction_sign`.

Exact statutory source: LVMC 11.40.180(B). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Signed roadway riding restriction. Planned comparison variable: `signed_cycle_access`. Requests: cycle operator rides outside sign-governed prohibited segment; cycle operator rides within sign-governed prohibited segment. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: signs prohibiting riding are in place on the sidewalk or roadway; the subject rides such a machine there.

Timing to retain: judged at every instant the machine is ridden in the signed place.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: the Director's determination is administrative; the erected sign is the observable the rule requires. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU signed-access source diagnostic

Added `native/signed_access_measure.py` and `native/prove_signed_access_measure.py`. The saved-source diagnostic requires a covered bicycle, electric bicycle or electric scooter; sidewalk or roadway; an erected applicable prohibition sign; a bounded governed interval; 600 joined riding frames at 20 Hz; and four pinned camera identities. It counts ridden frames inside the sign-governed interval while keeping administrative authority and actual sign pixels unverified. A source-declared sign alone is not proof that the Director made the statutory determination or that the physical sign was visible and applicable.

Two controlled synthetic electric-scooter routes hold the roadway and sign setup fixed. `witness_1` remains outside the governed interval; `witness_2` enters it at frame 200 and rides inside for 400 frames. Six missing-source mutations reject absent erected sign, uncovered actor type, missing interval, truncated history, camera loss and missing riding state. These are `synthetic_native_sample` traces, not Native motion or legal acceptance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_signed_access_measure.py > native/signed-access-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C230207__LVMC-11-40-180-B__cycle_or_scooter_operator --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `6273d0239873bc6d000de2b156fbb4efc72a38ce471922e225967772593a189b`; proof script `c9e9009d4f1aa885975dba136849949c17522d323e5c47b7f3c398404e1f19f5`; proof result `5f43ce4dce30dc3795ee6da0880d70c6f040203d3f411809610e366ce5681b72`; preflight log `8de2d13a98ec544a4312a317cea6ddd34385b7430b6d900c860434da057eb3bd`; scoped checkpoint log `e16c9661e2b042c524816d014b3116e34d5c022ce00268f6926591a2e30c7ae7`.

Next CPU work: construct the exact roadway and erected-sign Native scene, controller for both route variants, actor identity and sign-visibility source acquisition, four source camera videos, execution manifest, pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. The Director's determination remains administrative context to source; this diagnostic does not infer it. There is no exact construction bundle yet, so keep `result.json` partial.
