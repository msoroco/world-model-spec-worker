# NRS-484B-769 at C229831

Actor: `cycle_or_scooter_operator`. Frozen cell: `road` / `right_turn` / `intersection_boundary`.

Witness branch: general_method_right_turn_signal.

Comparison variable: `cycle_right_turn_hand_signal`. Proposed physical probes: use right arm horizontal signal; turn right without hand and arm signal. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C229831__NRS-484B-769__cycle_or_scooter_operator/assignment.json`, SHA-256 `915f0f5b2b0e44747d960300a1e409d838284629ebded01196cfda52817954e9`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 source-bound arm geometry checkpoint

The frozen law governs bicycle, electric-bicycle and electric-scooter operators on a roadway. The planned pair keeps one bicycle, operator, connected right turn, and four-camera 30-second capture fixed; only the requested arm pose differs. The horizontal-right exception is explicit in NRS 484B.769. The general method is referenced as NRS 484B.420 [DEF-NRS-484B-420] but its definition is not provided in this export, so no general-method verdict is asserted.

`native/measure_hand_signal.py` joins 600 raw 20-Hz samples to sourced rider identity, machine class, roadway polygon, route and calibrated shoulder/elbow/wrist keypoints. The proof has an extended-arm positive run (frames 100–139), no-extension comparison, and six rejections for missing keypoints, bad time join, wrong rider, missing roadway source, wrong machine class, and a derived-only hand-signal channel. The geometry tolerances are engineering diagnostics. No frame is asserted to be real Native capture.

Pinned runtime preflight passed. `.venv-cpu/bin/python worker_check.py --assignment training__C229831__NRS-484B-769__cycle_or_scooter_operator --complete` passed static checkpoint. Source and proof hashes:

- `native/measure_hand_signal.py` SHA-256 `37003dc7be20a39edff254d5c4880680ebd99dee418ff4256ce3d43d9f6ce7de`
- `native/prove_hand_signal.py` SHA-256 `1144ef9059f4d358d7421b1ce985a36fe9875da4e3adb419356fdd61376462ce`
- `native/measurement-contract.json` SHA-256 `16b8d19100b7ef9d9de88057a41a1eb2f800c6f8a7142e15949a295635f49d4c`
- `native/route-and-arm-proposal.json` SHA-256 `2ef83ce177dabc4a3a0b6349fd69551b2a77348ed43a10753d0eaf901b67c24e`
- `native/hand-signal-proof.log` SHA-256 `c42f37cd76bacd467a523a2295ad09869e58b8131a8fd422899e633c39b9e969`

The pinned adapter removes `sig.hand_signal`, so the source acquisition and saved finalizer must be implemented and tested before a selected case can be declared. Native articulated arm control, exact offline and compatibility proofs, process-saved, candidates, and independent acceptance/comparison audits remain CPU work. Physical arm visibility and actual motion remain unverified. Status is partial.
