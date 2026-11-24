# NRS-484B-413-3 at C230259

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `other_vehicle`.

Exact statutory source: NRS 484B.413(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Historical witness label: Source text branch requires exact review. Exact-source reviewed selected branch: sudden decrease in speed with a vehicle immediately to the rear. The separate stop alternative is still pending.

Controlled planning variable: `signal_before_sudden_deceleration`. Proposed requests: driver signals immediately trailing driver before sudden slowing; driver suddenly slows without prior signal to same follower. These are scene/controller targets, not observed conduct or legal verdicts.

Prior signal must be measured before deceleration onset; a brake lamp first illuminated by the same deceleration does not itself prove prior warning. The frozen clause supplies no numeric lead time, so appropriateness remains for independent review.

Statutory alternatives and exceptions still to cover or disposition: stop alternative; appropriate signal modality; immediately to rear.

Accepted membership: 2 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

Added `native/prior_signal_meter.py` with canonical 600-frame/20 Hz source joins for ego velocity, rear pose/extent, and separately observed warning signal. It derives event onset and signal precedence; the -2 m/s² probe is engineering only. Source-shaped proof `native/prior-signal-proof.json` (SHA-256 `dbcb882c20e726dc55d94d984bdfc87e9073b40183179ae6fdd659ab8846f446`) passed five 30-second variants and three negative source/frame-map tests. A same-frame brake lamp is recorded as **not prior**.

Added `native/measurement-contract.json`. The exact unselected `probe_1` draft construction `native/draft-prior-construction.json` (SHA-256 `7b57b479679f305895c740ad1fcc24f6ca098bc7758f331aab2af4a1a2cf8b67`) passed pinned `runtime.py offline` with four named 20 Hz cameras and 600 frame controller coverage. Log `native/draft-prior-offline.log` (SHA-256 `cf257b83c11db861c63946d96226a07a3fd7248bca6de887b36dbb872433aabf`) contains five passing checks. This is an offline contract; the draft runner intentionally refuses noncheck execution until Native route, acquisition and capture implementation exists.

Still partial: source membership for two accepted recordings has no reviewable original receipts; no evidence equivalence is claimed. Complete the stop branch, signal modalities and immediately-rear comparison; implement selected Native capture and retained source joins; run exact compatibility, saved-only positive/negative proofs, independent audits and scoped strict gate. Actual rear-driver signal appropriateness remains for independent source review.
