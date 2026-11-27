# NRS-484B-413-3 at C230259

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `other_vehicle`.

Exact statutory source: NRS 484B.413(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Historical witness label: Source text branch requires exact review. Exact-source reviewed selected branch: sudden decrease in speed with a vehicle immediately to the rear. The separate stop alternative is still pending.

Controlled planning variable: `signal_before_sudden_deceleration`. Proposed requests: driver signals immediately trailing driver before sudden slowing; driver suddenly slows without prior signal to same follower. These are scene/controller targets, not observed conduct or legal verdicts.

Prior signal must be measured before deceleration onset; a brake lamp first illuminated by the same deceleration does not itself prove prior warning. The frozen clause supplies no numeric lead time, so appropriateness remains for independent review.

Statutory alternatives and exceptions still to cover or disposition: stop alternative; appropriate signal modality; immediately to rear.

Accepted membership: 2 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU gap: Exact selected public compatibility, recorded-only saved processing, semantic proposals, independent delivery/comparison audits and scoped strict are still open. Original physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

Added `native/prior_signal_meter.py` with canonical 600-frame/20 Hz source joins for ego velocity, rear pose/extent, and separately observed warning signal. It derives event onset and signal precedence; the -2 m/s² probe is engineering only. Source-shaped proof `native/prior-signal-proof.json` (SHA-256 `dbcb882c20e726dc55d94d984bdfc87e9073b40183179ae6fdd659ab8846f446`) passed five 30-second variants and three negative source/frame-map tests. A same-frame brake lamp is recorded as **not prior**.

Added `native/measurement-contract.json`. The exact unselected `probe_1` draft construction `native/draft-prior-construction.json` (SHA-256 `7b57b479679f305895c740ad1fcc24f6ca098bc7758f331aab2af4a1a2cf8b67`) passed pinned `runtime.py offline` with four named 20 Hz cameras and 600 frame controller coverage. Log `native/draft-prior-offline.log` (SHA-256 `cf257b83c11db861c63946d96226a07a3fd7248bca6de887b36dbb872433aabf`) contains five passing checks. This is an offline contract; the draft runner intentionally refuses noncheck execution until Native route, acquisition and capture implementation exists.

Still partial: source membership for two accepted recordings has no reviewable original receipts; no evidence equivalence is claimed. Selected CPU construction and exact offline now cover stop and sudden decrease with early/late signal; run exact public compatibility, saved-only positive/negative proofs, semantic proposals, independent audits and scoped strict gate. Actual rear-driver signal appropriateness remains for independent source review.

## 2026-11-27 selected Native checkpoint

Four selected 600-frame/20 Hz constructions now exist in `native/bundles/`: `stop_early`, `stop_late`, `probe_1` (sudden decrease/early), and `probe_2` (sudden decrease/late). Each bundles the authored 300 m OpenDRIVE lane, ego and immediately rear actor controller, four synchronized cameras, per-frame signal/kinematic/pose/extent source rows, saved finalizer, and guaranteed world restoration. The selected draft manifest is `selected-draft-manifest.json`; all four exact `runtime.py offline` checks passed, with cleaned logs in `native/selected-offline-*.log`. Those checks do not establish original Native motion or camera coverage. The frozen two accepted recording memberships remain provenance only; no equivalence or reuse is claimed.

The selected source timing policy compares observed lamp/arm onset with observed stop or diagnostic decrease onset; a same-frame brake lamp is not prior. The 3 m/s² decrease bound and 0.1 m/s stop bound are engineering diagnostics, not statutory cutoffs. Remaining CPU tasks: current-runtime positive/missing-source-negative compatibility for all four exact cases, recorded-only saved processing, semantic stage proposals, source-bound independent delivery/comparison audits, final manifest, and scoped strict gate.
