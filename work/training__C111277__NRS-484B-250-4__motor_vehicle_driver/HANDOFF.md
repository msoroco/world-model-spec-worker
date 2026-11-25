# training__C111277__NRS-484B-250-4__motor_vehicle_driver

Status: partial. The source-grounded plan and synthetic controller diagnostic are checkpoints; this is not a deployable delivery package.

Exact law: When a vehicle enters an intersection controlled by a traffic-control signal which is installed and has its vehicular signals uncovered, but is inoperative at the time the vehicle enters the intersection, the driver of the vehicle shall proceed as if a stop sign had been erected at each entrance to the intersection and shall stop at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After making such a stop, the driver shall proceed cautiously, yielding to vehicles which have previously completed a stop or are within the intersection.

## 2026-11-23 controller checkpoint

`native/controller.py` implements an observation-driven stop, hold and yield policy for the selected no-stop-line, near-crosswalk branch. It requires an installed uncovered inoperative signal governing the ego lane and a present crosswalk; it rejects changed stop-line hierarchy. The 20-frame hold and 0.05 m/s speed tolerance are engineering choices for observable source measurement, not legal cutoffs. A prior-stop approaching vehicle or one inside the intersection keeps the ego held. Native scene activation and source pixels remain unproven.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python native/prove_controller.py native/controller-proof.json` passed over 600 frames at 20 Hz. The controller entered hold at frame 150, yield at 169, and released at 241 after conflict clearance; a no-conflict trace released at 169. Operating signal, missing crosswalk and unexpected stop line were rejected. Controller SHA-256: `139b5fa43f73f43e65f2268fe16b518b80ad1a5843251215e678cd2e6af60990`; proof SHA-256: `7883579d7e64e503c92f0a3dccc118859f83f79a0d98c4fdedd0c33f65aa1f00`; log SHA-256: `6f4b701e0966917f8714caf0d0026b7f4a0718b55f7e0c2bfeac31de93ba3eca`. `runtime.py preflight` and assignment-scoped `worker_check.py --complete` exited 0. Status remains partial. Next CPU work: bind this policy to exact construction and capture, prove observed signal/geometry source binding, run current offline and compatibility, saved processing and candidate proofs, and independently review the two accepted recordings before proposing new captures.

Selected witness scope: No stop line; near-side crosswalk.. The case plan inventories 4 source topics and drafts one controlled comparison on `complete_halt_before_applicable_boundary`. Neither case has a Native realization or legal outcome.

The local snapshot lists 4 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

Remaining work: Native physical mechanism, exact primary construction and risk-assessed fallbacks, exact offline/compatibility recipes, measured saved fixtures and independent audit are not yet produced for the selected law branch and source alternatives.

Resume: validate source alternatives and exceptions against the exact law; implement the selected comparison and each additional runnable source branch with semantic proposals, exact primary and risk-based fallback plans, native and camera configuration, offline and compatibility proofs, saved positive/negative audit, and comparison audit. Reuse a historical original only with an exact source-hashed equivalence receipt. Set ready only after all CPU proofs pass.

Physical prerequisites: Use an installed uncovered but physically inoperative vehicular signal; verify stop-line, near crosswalk and nearest-view-point hierarchy, actual halt, cautious movement and priority.

Legal limit: The inoperative-signal branch cannot be replaced with an ordinary functioning red-light stop.

## 2026-11-23 source-driven controller replay

`native/prove_source_controller.py` regenerates the retained 600-frame halt and roll inputs under `.runtime-work/c111277/source-controller/`, verifies their source indexes, then feeds their actual geometry, signal, ego speed and conflicting vehicle rows through the controller. The halt trace enters hold at frame 151, yield at 170 and releases at 241 after the other vehicle clears. The rolling trace crosses the selected crosswalk boundary before release and is rejected; an altered raw row file fails its source hash. Script SHA-256 `2fe0fa9daa3ad64f960d0824ba78b7d9a8fc61becbcbc0b83fbf101fdc631cdf`; proof SHA-256 `2b1490d060fe0d823e8dcb4df2b98653c9666d6debd1a8e249129e597c4dece2`. This binds the earlier policy to source-shaped observations but does not establish physical signal failure or a legal outcome. Status remains partial.

## 2026-11-24 retained-row finalization checkpoint

`native/finalize_source.py` now consumes the source-indexed 600-frame geometry, signal and native rows for each comparison condition. It derives ten 600-row channels with frame/time joins and source hashes; it does not accept fixture-provided derived channels or alter the retained sources. The independent `native/prove_source_finalization.py` exercised both conditions, verified source hashes and channel rows, rejected a missing `signal.json`, rejected an altered native row file, and checked the fixed frame-300 crosswalk entry and yield against the halt-versus-roll contrast. This is a synthetic source-only finalizer proof, not the current public compatibility or actual recorded-only process-saved path.

Finalizer SHA-256 `2d3cb0f36cabae651e1aa7a2940f6ec012e63ea7c6fcdcd9b37d91fb8842185a`; proof SHA-256 `649d0dd9ab23b0c1027d6f598bfa71962e14cb15bfba66694f7bacf4788b2c4b`. The proof ran with temporary sources under `.runtime-work/`. Exact primary Native construction, four-camera capture, current public compatibility, actual process-saved, fallbacks, independent delivery audits and source review of accepted recordings remain CPU work. Native signal/device/geometry pixels and physical movement remain unverified. Status remains partial.

## 2026-11-25 accepted-source review

Reviewed the two unique accepted recording entries in `inputs/training__C111277__NRS-484B-250-4__motor_vehicle_driver/review-context/review.json` (SHA-256 `ce2b04e86608b50dbfc8798cb7b1c960412ccacee1bbf6762c1861d573155087`), which occur in both demo-train and full-train memberships. The halt case commands a full halt before an applicable stop line; the no-halt case commands travel through an applicable stop line. The review context explicitly leaves stopping attainment and route completion unverified, and lists no source-hashed receipt sources. It does not demonstrate absence of a stop line, a near-side crosswalk, actual inoperative uncovered signal at entry, realized stop, cautious movement, or priority history. `case-plan.json.evidence_review` records each fact and the two resulting gaps. No original is claimed equivalent or reused.

The exact scoped strict command currently fails because `result.json` remains partial. CPU work still needed: executable exact Native construction for selected cases and all law alternatives, four-camera source capture, public positive and missing-source compatibility, recorded-only saved processing, risk-based candidates, semantic proposals, physical fixture checks, and independent delivery/comparison audits. The synthetic source-finalization proof does not satisfy those contracts.

## 2026-11-25 independent source comparison checkpoint

`native/comparison_audit.py` independently reads source-indexed retained geometry, signal and 600 native rows for both conditions. It verifies source hashes and frame/time joins, equal fixed geometry and signal, the no-stop-line near-crosswalk hierarchy, governing signal, other-vehicle priority history, the halt/no-halt contrast, and yield until conflict clearance. `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111277__NRS-484B-250-4__motor_vehicle_driver/native/prove_comparison_audit.py` passed and rejected missing signal, changed native rows and absent condition contrast. Proof SHA-256 `a1f90ea847e4e203e2d8e559f9380a0b63b3d5778bd7069e85782e08e885f1be`; log SHA-256 `4ec15529f96557ada76f6c39f8b1b57e54363725413e88bfe7562f609a645995`. This is a synthetic retained-source comparison audit only; it is not linked to actual process-saved or delivery acceptance.

Latest exact scoped strict command: `.venv-cpu/bin/python worker_check.py --assignment training__C111277__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready`, exit 1. `current-strict-check.log` SHA-256 `d2929cd361a0bd1fb47cb67e009250981e9b9a159c8f52b614476bc8bf5f67ba` reports `Preparation acceptance failed: partial/missing packages remain`, consistent with truthful partial status.
