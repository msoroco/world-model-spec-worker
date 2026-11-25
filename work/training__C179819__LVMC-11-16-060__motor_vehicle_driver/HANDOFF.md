# LVMC-11-16-060 at C179819

Actor: `motor_vehicle_driver`. Frozen cell: `paved_road` / `travel` / `speed_limit_sign`.

Exact statutory source: LVMC 11.16.060. The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Twenty-five-mile-per-hour prima facie default without a different applicable posted limit..

Controlled planning variable: `speed_mph`. Proposed requests: measured 20 mph within applicable default-limit portion; measured 25 mph within applicable default-limit portion; measured 30 mph within applicable default-limit portion. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: different posted limit governs; prima facie meaning requires review.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/controller.py` requests 20, 25 and 30 mph using one 600-frame / 20 Hz feedback policy. Its source-shaped proof `native/controller-proof.json` (SHA-256 `e7bcd79657c2641d1d93f07e0c6f0e311e02ee7e8f9d2cbebcfca4ce1a0419bf`) passes all three requests and rejects the wrong speed, shortened trace and nonfinite observed speed. Synthetic speeds are not original CARLA velocity.

`native/measure_speed.py` and `native/measurement-contract.json` require original Native velocity and route position, full 600-frame/time and four-camera joins, public-street status, and a source-hashed complete sign survey over the traveled route. The CPU proof `native/speed-proof.json` (SHA-256 `c16b5ad291592b7ac373913257c92b1d093af06f0bb8fec3579f80ccfc5d92ce`) compares 20/25/30 mph under the default and tests a sourced 35 mph posted-governance interval; it rejects five survey, route and camera defects. The fixture sign and speed sources are placeholders. Above-default frames are measured observations; prima facie status and legal outcome require independent review.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire CARLA capture and four source cameras, construct exact cases, add the different-posted-limit branch with original sign authority and governance, run exact offline/compatibility/saved-only proofs and independent audits, then run scoped strict ready gate before promotion.

## 2026-11-23 partial posted-governance CPU checkpoint

The meter now reports frames above a *different posted* governing limit separately from frames above the 25 mph default. Two partial-route source-shaped sign intervals preserve the same 30 mph trace: a 35 mph posted interval has zero posted-above frames, while a 15 mph interval has every posted-governed frame above its limit; default-governed frame counts remain the same. A sixth negative rejects overlapping conflicting posted limits. Refreshed receipt `native/speed-proof.json` SHA-256 `83f3107724816c5f306b43a4f591b0a9b33400512e15d9ac583907487ac099c3`; meter SHA-256 `e312cc8ffc41d5b7d42c36d8dd3655e9e6703f583dccf258b151c5293bebce7e`; proof script SHA-256 `73655f74056d3724c1a0e9cf1fdc84107552ac4778e3222d62024fca467f0da6`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c179819-posted-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C179819__LVMC-11-16-060__motor_vehicle_driver/native/prove_speed.py`. These are synthetic governance diagnostics only; original sign authority, Native speed/route capture, prima facie legal interpretation, selected delivery paths and audits remain unfinished.

## 2026-11-24 exact primary acquisition-draft checkpoint

`native/geometry.py`, `native/runner.py`, `native/tests/test_native.py`, and `build-draft.py` bind three exact primary current-v2 constructions in `draft-execution-manifest.json`. The 800 m authored paved road supports 20, 25, and 30 mph requests with one feedback policy. The Native acquisition draft surveys the lane, retains original velocity/route/control rows, a sign-survey inventory, a Native frame map, and four RGB source-camera videos for 600 frames at 20 Hz. Public-street and sign authority are explicitly unverified; the draft does not claim a physical run or legal outcome.

Pinned preflight and all three `runtime.py offline` commands pass. Scoped `worker_check.py --assignment training__C179819__LVMC-11-16-060__motor_vehicle_driver --complete` passes partial static checks. The exact commands, construction hashes and hashed logs are in `current-v2-primary-offline-checkpoint.json` (SHA-256 `cd5283272ed73dd0698718231968f12ba265b88e9181ba02c9df6660a95b897e`).

Public compatibility for probe 1 returned nonzero at `KeyError: measurement_contract`; fixture generation, positive/negative source tests, and recorded-only saved processing were not reached. Next worker-owned CPU steps: construct the runtime-format measurement contract and selected-case finalizer, a source-bound positive/negative fixture with all four source streams, and pass public compatibility and process-saved. Then construct distinct alternatives and the different-posted-limit branch, inspect original Native speed and route capture, establish street/sign authority and governance, and complete independent delivery/comparison audits. The Native runner is an acquisition draft without sealed `result.json`, source graph or owner-release output. Status remains partial.

## 2026-11-25 current-v2 source-contract checkpoint

`native/finalize.py` and `draft-exact/probe_{1,2,3}/measurement-contract.json` now bind selected requirement 0 to recorded road, street-status, complete sign-survey and Native actor-pose files. The finalizer rejects missing sign survey and rejects unsourced road or incomplete review context. The fixture unit in `native/tests/test_finalize.py` passes its synthetic positive and missing-sign tests; it is not a physical recording. `native/runner.py` now uses the four runtime camera names and records meter-readable source-camera frame identities. The draft uses the declared 1920x1080 overview and 1280x720 detail profile.

Current-v2 `runtime.py offline` passes for all three exact primary constructions after rebuild. Construction SHA-256: 1a2693e55df8961455b37eedfba0a667432419b796ee0a51518b1e62af9098d3, 6a7e0af1f2b01a1757db44a116ec18d0aee5b0799e0e533c71886bb2eb1a9eb2, 002ae88bd91bc2508fb7529ee5c0c1b2c933678e67d1924f205960067258182e. `worker_check.py --assignment training__C179819__LVMC-11-16-060__motor_vehicle_driver --complete` passes partial static checks. The finalizer still lacks sealed `result.json`, `trace.jsonl`, and derived channels, so public compatibility and `process-saved` are not claimed. Complete those, capture/review original sign and public-street sources, construct the posted-limit branch, proposals, justified fallback candidates, independent audits, and run the strict gate. Status remains partial.

## Current-v14 selected construction checkpoint

Four exact cases cover the 25 mph prima facie default at requested 20, 25 and 30 mph and a different authored 35 mph posted-limit branch at the unchanged 30 mph request. Each has an exact primary and common controller-gain fallback. The fallback trigger is fewer than 500 of 600 original samples within one mph of the unchanged request; its only engineering change is speed-error gain 0.08 to 0.10. This trigger needs original Native speed evidence and does not select by legal outcome. The source-bound finalizer measures original speed, street status and sign governance, preserves prima facie legal status as unassessed, and rejects a missing sign survey.

Current-v14 primary/fallback offline checks pass for all eight constructions. The three physical-outcome and lifecycle CPU fixtures pass for each selected case. Canonical semantic proposals validate as seven stage artifacts and four selected cases, with both legal judgment questions unresolved. Revised original Native acquisition now retains road.xodr, trace and four RGB source streams, writes Native provenance, verifies world restoration and seals the original capture before owner release. Original public-street status, sign face and posting authority remain for independent review after actual Native execution. Two current-v14 public compatibility streams are running; selected manifest receipts and independent audit proofs will be refreshed from those exact outputs. The assignment remains partial until the exact scoped strict gate passes.
