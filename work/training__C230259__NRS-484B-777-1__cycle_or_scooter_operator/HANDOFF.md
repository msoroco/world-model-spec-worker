# training__C230259__NRS-484B-777-1__cycle_or_scooter_operator

Status: partial. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.777(1); with 484B.777(2). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

right-edge position and passing clearance sweep; practicability unresolved. Compare only `cycle_lateral_distance_from_right_edge` (m) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Incomplete CPU work and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.

Update 016 status correction: missing construction, cases, proofs and audits are actionable CPU work under START_HERE.md, so this assignment is partial rather than externally blocked. Existing scope, plan and next actions are retained.

## Current CPU construction checkpoint

Added `native/measure_right_edge.py` and `native/measurement-contract.json`: a source-hashed, 600-frame at 20 Hz saved-readback processor for cyclist right-edge margin and clearance to a standing vehicle. It requires frame/time/camera joins, a bicycle or scooter actor identity, roadway edge geometry, and standing-vehicle footprint. It reports observed distances and pass frames without making a practicability, due-care, exception, or legal-verdict claim.

`native/prove_right_edge.py` passes a full-window source-shaped positive/contrast pair with right-edge margins 0.40/1.45 m, standing-vehicle clearances 0.60/1.65 m, and 39 joined passing frames. Six fail-closed negatives reject changed source hashes, synthetic data labeled original, missing camera, changed frame joins, motorcycle identity, and short capture. Proof SHA-256: `aca0eebd71e24e5e571f8f189c831022134847184641e4cd173b5a942554851a`. Processor SHA-256: `c5297c91872c494a27e4fbf4dae50bd67335c4113396e94cd2fff6e8d137b192`; contract SHA-256: `1a12754b8fc2e8a8788dcdf6e5b1e794d6ed3cebc43d22bc7d02c9611f951459`. Pinned runtime preflight and scoped `worker_check.py --complete` pass.

Remaining CPU construction: executable Native bicycle/scooter capture with original camera and map readbacks, selected primary and three distinct fallbacks per case, pinned offline and compatibility proofs, saved-path positives/negatives on captured sources, due-care and statutory exception branch analysis, then independent acceptance and controlled-comparison audits. The synthetic pair is a processor test and is not accepted evidence or a selected recording. Status remains partial.

## Exact reference primary draft integration

`build-draft.py` packages the reference case as `draft-right-edge/reference/primary/construction.json` and binds `native/runner.py --process-saved` to `measure_right_edge.py`, its 30-second/four-camera contract, and the exact law/cell/actor. The saved entrypoint requires an explicit complete SHA-256 inventory and original Native provenance; a synthetic diagnostic bundle is rejected. Pinned `runtime.py offline` passes the materialized `--check` and two unit tests without starting simulation. Construction SHA-256: `42652465b5e2f67a0f15481a8a1134b7794460006bd843569e57a9d65f8a6e27`; draft manifest SHA-256: `7cfd405d39eeadc176b0a381157885df4c9148adb074bcc70d3131cd0b1680c1`; returned offline log SHA-256: `b5e06d8306c102fd51016947057be85507b918e78be240d8d9522ba167ba7438`.

This draft is a saved-source integration, not a Native capture construction. A saved-source positive cannot run until original Native bicycle, camera, roadway-edge and standing-vehicle readbacks are produced. The contrast case, four candidates per exact case, selected-case compatibility receipts, statutory exception review, and independent audits remain CPU work. Status remains partial and no recording is selected.

## Native primary construction checkpoint

Added exact reference and contrast primary drafts with common `native/capture.py` and `native/geometry.py`. The authored 160 m straight OpenDRIVE road has a 3.5 m driving lane and a 2.5 m right shoulder. The Native runner requires an exclusive idle asynchronous world, surveys the road/lane/shoulder readback and driving-lane waypoints, spawns a `vehicle.bh.crossbike` bicycle and a stationary `vehicle.tesla.model3` on the shoulder, and records 600 frames at 20 Hz. Requested bicycle center y is -2.65 m (reference) or -1.45 m (contrast); other construction settings are equal. Four 1280x720 original camera streams are frame joined and FFV1 encoded. The runner writes original bicycle body footprints, standing-vehicle footprint, map readback, camera raw-frame hashes, source inventory, and then invokes the source-bound right-edge measurement on that original attempt. World restoration and owned-actor cleanup are in `finally`.

Both exact cases pass pinned `runtime.py offline` (`runner.py --check` and four unit tests: exact config, synthetic-as-original rejection, Native map readback adapter, changed lane-width rejection). Reference construction SHA-256 `6cd3c1489bf701cc54d427a5ea29c952ecd7763b0a092d30a5932453800160b7`, offline log `bef646098ab8981e30776b4e1e93cdc59fb2db0f17abcb98a57474759806463f`. Contrast construction SHA-256 `bcb0acee49f1c456ca3ddfa72835fa1e54b664e52467e3180802be1bd463f028`, offline log `98cc2f07a6c13af25fd6dc504795355a86834cef233bd4c0a801b9a56baa89d0`. Draft manifest SHA-256 `a536b9fc6c700ec47e62b3e6e56f586a0ad51acdfc2a9a2afbe10eb83de71666`. Capture source SHA-256 `26d1b02e2a54c67fea4d7247f51096ccfb1bd00672bd7008ed2b19a824bb0149`.

This proves CPU construction and source-path wiring only. Neither case was run in Native here. Bicycle dynamics, standing-vehicle placement, image content, safety and practicability remain physically unverified. Further CPU work includes physical-risk fallback constructions, selected-case positive/negative compatibility recipes and receipts, saved-result/finalization integration, statutory exception branch coverage, and independent delivery/comparison audits. The two draft primaries are unselected and status remains partial.
