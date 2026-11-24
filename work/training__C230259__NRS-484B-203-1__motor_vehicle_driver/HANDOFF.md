# NRS-484B-203-1 at C230259

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `other_vehicle`.

Exact statutory source: NRS 484B.203(1). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Keeping right during opposite-direction passing. Planned comparison variable: `oncoming_pass_side`. Requests: drivers meet while each keeps to the right; subject meets opposing vehicle while occupying left half. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject meets a vehicle proceeding in the opposite direction; on a road with width for not more than one line of traffic in each direction, the second duty also applies.

Timing to retain: judged at the meeting — the frames in which the two bodies are abreast; the approach to the meeting matters too: the half must be given up before the vehicles are abreast, not at the last instant.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: 'as nearly as possible' is a judgement element bounding the lateral offset. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## 2026-11-23 CPU opposing-pass body geometry diagnostic

Added `native/opposing_pass_measure.py` and `native/prove_opposing_pass_measure.py`. The saved-source diagnostic requires a source description of one traffic line per direction and the paved portion, 600 joined frames at 20 Hz, both vehicles' poses and opposing headings, body width, and four pinned camera identities. It identifies the sampled longitudinal body-overlap meeting interval and counts frames where either full vehicle body encroaches on the half assigned to the opposite direction. It leaves the statutory phrase 'as nearly as possible' for source and independent judgment, without inventing a lateral cutoff.

Two synthetic traces hold the opposing vehicle, paved width and longitudinal meeting fixed while moving the subject body's lateral position. `witness_1` stays on its right half; `witness_2` encroaches during every meeting frame. The opposing vehicle remains on its own right half in both. Six missing-source mutations reject road-width context, body width, truncated approach history, camera loss, other body pose and opposing direction. These `synthetic_native_sample` poses are not Native observations or legal acceptance.

Commands, each exit 0 with `TMPDIR`, `PYTHONDONTWRITEBYTECODE=1`, and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`:

- `.venv-cpu/bin/python runtime.py preflight > native/current-preflight.log 2>&1`
- `.venv-cpu/bin/python native/prove_opposing_pass_measure.py > native/opposing-pass-proof.json`
- `.venv-cpu/bin/python worker_check.py --assignment training__C230259__NRS-484B-203-1__motor_vehicle_driver --complete > native/current-static-check.log 2>&1`

SHA-256: measurement code `73d01f8d8ebeedc3d9907a038166493f04257e7f5403ae88894e8ad99f0e6efe`; proof script `95c24e78053d820529bc5bc7ba78c9b15057fb1a499c83aad3d1bfb4d54b776e`; proof result `ed57d40d38d9193eed3826d2f32bfb446e76fafa4a970a4927971c960cb9001d`; preflight log `953ce464ce1b2666445cf1573b6851cd42d0c92f8bdf7be7895e33c7ff7ef3f4`; scoped checkpoint log `3e2e9a95ce510704b38c0e724d6ef2a523982b931164ad29ee7781f2d2cad9bb`.

Next CPU work: implement the exact opposing-traffic Native roadway and two lateral controllers, four camera streams and source body geometry, execution manifest, pinned offline, positive/negative compatibility, saved-only, semantic and independent audits. Physical lane feasibility and 'as nearly as possible' remain unverified. No exact construction bundle exists yet; keep `result.json` partial.
