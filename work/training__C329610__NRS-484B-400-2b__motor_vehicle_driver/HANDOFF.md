# NRS-484B-400-2b at C329610

Actor: `motor_vehicle_driver`. Frozen cell: `two_way_to_two_way_intersection` / `left_turn` / `centerline`.

Exact statutory source: NRS 484B.400(2)(b). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Left-turn exit onto a two-directional destination highway.. Planned comparison variable: `left_turn_exit_centerline_side`. Requests: driver exits intersection right of destination centerline; driver exits intersection left of destination centerline. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject has entered the intersection to turn left; both intersecting highways are two-directional.

Timing to retain: judged at the exit from the intersection: the footprint must leave right of the centreline; entry, then the turn, then the exit — the exit position is the test.

Exceptions and numeric alternatives planned: none in supplied clause.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 4 membership rows; exact source-hashed equivalence and reuse are unverified.

Current gap: The unselected Native construction drafts and offline checks are described below. Exact positive/negative compatibility receipts, saved Core processing and independent delivery acceptance remain absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
# Source review continuation, 2026-11-05

The exact NRS 484B.400(2)(b) clause concerns the **exit** of a left turn, after intersection entry, on a two-directional destination highway. It differs from the C329610 (2)(a) approach-position assignment. The duplicate witness label was collapsed. `case-plan.json` now specifies the full-body exit event, a destination-centerline signed-position measurement draft, activation facts and three measurable construction risks. For the authored northbound destination, the right side is east of the destination centerline. The Native runner and saved proof drafts are described below; the result remains blocked.

## Exit geometry continuation

An authored same-cell map and two exit-side routes pass CPU pavement, route-continuity and prospective vehicle-body checks. A simple bicycle diagnostic follows both requested paths. The saved Native-frame measurement computes the complete vehicle footprint's side at the first measured full-body exit; positive right/left fixtures and negative incomplete-turn/two-way-direction fixtures pass. The wrong-side route traverses an opposing lane by design and has not been verified in Native CARLA. No selected runner, exact positive/negative compatibility proof, saved Core processing, or independent delivery audit exists, so the assignment remains blocked.

## Exact unselected draft continuation

The package now contains an observed-pose Native runner proposal, fixed approach and two controlled destination exit-side routes, four synchronized camera policies, a source-bound saved finalizer, five semantic stage drafts, and a measurement contract for each case. The full-body exit measurement rejects a reversed Native right axis. Two case IDs each have primary plus three distinct fallback construction bundles with measured triggers; all eight pass exact `runtime.py offline` checks with ten CPU tests per bundle. Independent bundle/source-hash and controlled-input audits pass. Semantic stage validation passes with the in-memory `law_record` to `law` alias necessitated by the separately documented frozen checker defect.

Both case IDs pass four-frame synthetic positive saved finalization, original-source hash checks, four source-video decodes, Native attempt validation, and a negative test removing `native_samples.jsonl`. The Native validator returns `rebuild_required: true`. These fixtures do not establish the full 480-frame pinned compatibility recipe, saved Core processing/render, independent delivery acceptance, camera-pixel coverage, wrong-side Native lane feasibility, or a legal outcome. The selected case count remains zero and the result remains blocked. Use `draft-execution-manifest.json`, the two audit scripts, `saved-fixture-proof.py`, and the hashes in `case-plan.json` to resume.

## Full-duration synthetic saved continuation

Both planned exit-side cases now pass 480-frame, 20 Hz, 24 s synthetic saved positive processing, measurement-contract verification, four source-video decodes, Native attempt validation with `rebuild_required: true`, and missing-Native-samples negative rejection. An independent saved audit holds the first 160 approach frames, map, law, actor, rate, cameras, channels and frame/time/y/heading trace fixed; it varies only the destination lateral exit and measures full-body right versus left exits. This does not establish CARLA physical feasibility, pinned-runtime Core/render compatibility, legal outcome or independent delivery acceptance. Both cases remain unselected and the result remains blocked.

## Canonical original frame identity continuation

The proposed Native runner now writes `video_frame`, `native_frame`, canonical `carla_frame` and `time_s` together for every source camera frame. An independent CPU audit checks this row against the pinned frame-map writer and rejects invalid identities. All eight exact unselected primary/fallback bundles were rebuilt and passed pinned offline checks and source/controlled-input audits after this source change. No CARLA run, Core/render compatibility receipt or delivery acceptance is inferred; this assignment remains blocked.

The saved exit-side measurement now requires an observed pre-entry approach and a sampled intersection entry before the first complete destination exit. Two CPU negatives reject exit-only and approach-only histories. The finalizer carries the entry bracket into the saved result, and independent saved and package audits check entry before exit for both controlled cases. Twelve CPU tests and all eight rebuilt exact offline bundles pass. Two 480-frame synthetic saved positives and independent controlled comparison pass. All eight full synthetic v1 package positives, missing-source negatives, Core/Lean/render/final decode and independent package audits pass with refreshed construction hashes. `case-plan.json` and `result.json` now bind the current proof hashes and retain blocked/unselected status. Strict v2 portable recipe, original physical trigger and Native camera/motion evidence, statutory closure and delivery acceptance remain unfinished.

## Exact package diagnostic continuation

The copied authored map's turn connector was repaired to 3.3 m lane widths; the pinned OpenDRIVE parser now accepts it. All eight exact primary/fallback bundles were rebuilt and pass pinned offline, source and controlled-input audits. A full 480-frame synthetic Native-shaped capture passes pinned Core, decoder, render and final decode. All eight bundles pass exact pinned v1 package positives with full-resolution synthetic source video and packaged missing-Native-source negatives. `draft-package-probe-summary.json` independently verifies their current hashes, four source-video audits and negatives. These are unselected software diagnostics using retained graph templates. Strict recipe-backed v2 receipts, physical Native lane/route/camera evidence, statutory branch closure and independent delivery acceptance remain unfinished. The assignment remains `blocked`, with zero selected cases and no dispatchable GPU jobs.

## Source-bound fallback trigger continuation

`native/fallback_triggers.py` now evaluates the three distinct retry conditions from saved source evidence: complete 480-frame Native samples and a map survey for missing full-body exit or measured controller route error, and a source-video-hash-bound contiguous pixel audit for joint body/centreline visibility. Four CPU tests exercise positive/negative decisions and a changed-video rejection; the complete Native unit set is 16 tests. This evaluator and tests are embedded in each of the eight rebuilt exact construction bundles. Pinned offline/source/controlled-input audits and all eight exact synthetic v1 packaged positives and missing-source negatives pass again with current hashes; `draft-package-probe-summary.json` records their independent audit. The pixel audit rows in these tests are synthetic annotations, not observations of original CARLA pixels. The assignment remains blocked and unselected pending strict v2 and delivery proofs.

## Native closure and sealed saved-path continuation, 2026-11-06

The proposed Native runner now copies completed mandatory channels to immutable `source_channels/`, closes the capture and all four encoders, verifies world restoration, composes the original four synchronized videos into `raw.mkv`, and calls the pinned `seal_capture` before writing a truthful `native-run-status.json`. Failed capture, encoding, composition or sealing produces a failed status; no accepted recording is claimed. This path has not executed in CARLA.

All eight rebuilt exact unselected primary/fallback bundles pass pinned offline (16 tests each), independent source and controlled-comparison audits, and refreshed full-resolution synthetic v1 package positives and missing-Native-source negatives. The current manifest SHA-256 is `7e62f5b497b2653f523d1d904343066204acd63e31dab1765d705f1aa01f4c71`, offline summary `b7abddae48e3da54d801c3f25de1b00b690dc5b8abc3f052b38b48964fbb33fd`, and independent package audit `f266cc671595dacd4f96c69f98edbff90ebc90fa53db732dc9a6692528b07022`. Older bundle hashes are historical.

A separate 480-frame **synthetic diagnostic** attempts the proposed closure sequence through the pinned four-view composer, `seal_capture`, native-exit receipt and saved closure check. It passes, and mutation of the sealed Native samples rejects (log SHA-256 `e19f1ee3dec3397c788e66717daee8c1b602fb197ab7a8ea37efe17207228b8e`). The diagnostic explicitly records `native_executed: false`; its mock restoration and seal do not attest a CARLA run, owner release, original pixels, physical trigger measurements or accepted recording. Selected v2 compatibility, independent delivery acceptance, statutory runnable closure and ordered queue rows remain worker-owned. Both cases stay blocked and unselected.

## Saved acquisition provenance correction, 2026-11-06

The saved exit-side finalizer now uses the pinned acquisition provenance classifier. Both 480-frame synthetic cases retain measured full-body exit-side facts while reporting `synthetic_local_diagnostic`, `native_executed: false`, and false setup, attempted-behavior and maneuver-completion flags. The independent saved pair audit checks those fields and the controlled right-versus-left exit comparison. Only a later sealed Native capture can carry physical attempt flags. Strict v2 compatibility, physical trigger observations, statutory closure, selected delivery acceptance and queue rows remain unproved; the assignment stays blocked and unselected.

The saved finalizer now requires a complete pinned capture seal with unchanged source hashes, non-diagnostic provenance, completed restoration and closed encoders before setting Native physical flags. A synthetic 480-frame sealed fixture passes the pinned closure path yet remains `synthetic_local_diagnostic` with all physical flags false; mutating its sealed Native samples rejects in both closure and finalizer provenance checks. Exact refreshed offline and package proofs are recorded in `result.json`. This is a CPU source-protocol test, not physical CARLA evidence.

## Current Native speed-frame repair, 2026-11-07

The saved `speed_mps` now comes from the same post-tick Native state as the recorded pose and body. The controller retains the pre-tick speed for its command. A two-test CPU mock checks changed and nonfinite velocity; both tests are embedded in every rebuilt draft. All eight exact unselected primary/fallback bundles pass pinned offline with 18 Native tests each, independent source/receipt and controlled comparison audits, and refreshed full-resolution synthetic v1 package positives plus missing-Native-source negatives. The independent package audit passes. Current manifest SHA-256 `4f9c9bbb4666e18e02d5f22873e16960ace265f66683499236e6a9f8a3238b6c`; offline summary `3fa31279eba54618672ca736a88d1110d2b7da053b6a4134c6d15b5c24d7e23b`; package audit `706e2bebaee11a2579dfcd5af035f6cc8e4a648e1594629a5dc81957eb3a8eb8`. `case-plan.json` and `result.json` bind current hashes. These are synthetic software diagnostics; strict v2, physical Native observations, statutory closure, independent delivery acceptance and a dispatchable GPU queue remain unfinished. The assignment stays blocked and unselected.
