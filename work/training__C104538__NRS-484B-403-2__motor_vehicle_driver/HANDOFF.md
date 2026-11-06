# NRS-484B-403-2 at C104538

Actor: `motor_vehicle_driver`. Frozen cell: `hill_crest` / `u_turn` / `turn_prohibition_device`.

Exact statutory source: NRS 484B.403(2). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Duty to obey an applicable official U-turn prohibition.. Planned comparison variable: `signed_u_turn`. Requests: driver continues without U-turn at the signed location; driver initiates a U-turn within the sign-governed location. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: an official traffic-control device prohibits a U-turn at the place; the subject makes one there.

Timing to retain: the manoeuvre is the violation, judged where it occurs within the device's region.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Source-bound signed U-turn measurement seed, 2026-11-06

`native/measure_u_turn.py` joins 480 saved Native body/heading samples to the exact original frame map and a source-hashed sign review, then tests whether a 160-degree reversal with the complete body occurs inside the sign-governed region. The six CPU tests distinguish straight continuation, a governed-region U-turn and a reversal outside that region; they reject changed source video, changed Native rows, missing sign applicability and a mismatched frame join. `prove-saved-u-turn.py` stores the straight/U-turn synthetic source pair and measurement receipts, and `audit-saved-u-turn.py` independently recomputes both receipts, checks fixed frame/time/road/lane inputs, and rejects a changed video source. The placeholder camera bytes and sign review are synthetic, so this proves measurement logic only. Native construction, original sign pixels/designation, four candidate packages per case, exact offline/positive-negative compatibility, statutory closure, selected delivery audit and queue remain unfinished worker-owned work. Status stays blocked and unselected.

## Pinned draft measurement contracts, 2026-11-06

Both planned witness cases now have `worker-measurement-contract-v1` draft contracts bound to the exact NRS 484B.403(2) disposition. The proposed `native/finalize.py` reads the saved Native rows, frame map, sign review and approach video and emits `signed_u_turn` with exact source hashes. `prove-measurement-contracts.py` passes the pinned validator, positive synthetic saved finalization and removal-of-`native_samples.jsonl` negatives for both cases. `audit-measurement-contracts.py` independently checks frozen law identity, both contract hashes and the fixed source pair. No case is selected; the video bytes and sign review are synthetic. Native map and controller construction, four distinct candidates per case, exact offline/portable compatibility and independent selected delivery audit remain to build.

## Authored hill-crest Native proposal and candidate policies, 2026-11-06

`native/geometry.py` now authors a two-direction hill-crest OpenDRIVE road with an approach no-U-turn signal cue and separate straight/reversal routes reflected into CARLA Native coordinates. The two routes are continuous, keep an approximate full vehicle body on the authored road, and the reversing route exits in the opposing lane. Ten local CPU tests pass. `audit-native-construction.py` uses the pinned source-map parser to recover three roadway regions and both opposed driving lanes, and checks every authored route point on the parsed pavement. This is CPU authored-map evidence; the signal's official status, Native readback and vehicle feasibility remain unobserved.

`native/engineering.py` defines a primary plus three distinct law-context-preserving draft policies for each case: lower target speed, longer lookahead and a changed sign camera viewpoint. Saved-source fallback gates use maximum approach route error >0.35 m, failure to complete the requested straight/reversal movement, and sign-plus-body visibility <0.95. The source-bound synthetic pair isolates all three gates in both cases; an independent threshold audit checks 113/120 versus 114/120 visible frames and rejects changed video bytes. These policies are not exact materialized bundles and no candidate is selected or proven ready. Native runner, exact offline/portable packages, full video, original sign review, selected delivery audit, statutory closure and queue still need worker-owned construction.

## Native route and map-readback preflight, 2026-11-06

`native/controller.py` now computes throttle, brake and steering from each observed Native pose for the straight and reversing route; the requested route and target speed do not count as observed completion. `native/cameras.py` specifies four synchronized views, including the fallback3 sign-camera location from the engineering policy. `native/runner.py --check` validates all eight case/candidate combinations without importing CARLA. Its `map_survey` verifies live road/lane IDs, eastbound signed-approach and westbound opposing-exit directions, lane width and landmark ID/station before a later capture. A synthetic CPU map checks the positive path and rejects reversed Native lane direction; it does not establish CARLA behavior or the sign's official legal designation. Fifteen local CPU tests pass (latest log SHA-256 `5d8eea5168c27579f7b3a5024c72f900624a185bc82a85a5a8158daaf9be2925`); the witness-2 fallback3 preflight exits 0 (log `e8d6a56e49ea0c798f79e7a2e7f9781fb2157e2ec2e7799297f300f0d5e13f71`).

The runner now also implements an unexecuted 480-frame, 20 Hz Native source-capture attempt: it checks exclusive world ownership, generates the authored map, surveys Native lanes/landmark, uses the observed-pose controller, retains four FFV1 camera streams plus Native body/lane/heading rows and canonical frame map, destroys owned actors and restores the world. It emits an unaccepted capture report and does not fabricate a sign review. The capture loop has passed syntax/import and CPU preflight checks, but has not been exercised against CARLA or a synthetic whole-loop mock. Exact offline and positive/negative portable bundles, tested captured-source saved/Core integration, original-pixel sign review, independent selected delivery audit, statutory closure and GPU queue rows remain worker-owned. Both cases stay blocked and all eight policies unselected.
