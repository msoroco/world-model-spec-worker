# training__C234827__NRS-484B-220-2__motor_vehicle_driver

## 2026-11-23 current-format draft primary

`draft-current/manifest.json` now has the pinned runtime `cases` structure, with source-hashed inline `construction.json` for each exact primary request. Both exact cases passed `.venv-cpu/bin/python runtime.py offline` using fresh `.runtime-work/owner201-c234827/offline-*-2` outputs. Each ran the exact copied `runner.check` and two tests, including a changed OpenDRIVE source hash rejection. The manifest is SHA-256 `5c49126f8f45dfbc1ca1b039b2edd9c646f55e65e226e66ab8eb2c52d0c776c8`; reference construction `d34343e17f919e9fff5f7b11cc2b5c5b451a08bb5f939aa5383c22c5cd063f67`; contrast construction `4c499f306b3cf9c445972c79b61abc0cedf8036b76d872093564464f53bf8720`. The cases remain `draft_not_selected`; no Native or delivery claim was made. Scoped `worker_check.py --assignment training__C234827__NRS-484B-220-2__motor_vehicle_driver --complete` passed after this addition.

Next work is full candidate selection and current-runtime compatibility, then a saved attempt with four original cameras and source-bound island geometry/extent evidence for `process-saved`. The current format solves the earlier `entries` mismatch but does not create a captured attempt or accepted equivalence.

## 2026-11-23 copied saved-path integration

`native/measure_saved.py` now calls `validate_body_pose.py` on every saved ego row before measuring island passage. It checks four derived body corners per frame and the full 240-frame inventory. Synthetic readbacks use the stated diagnostic 2.0 m and 0.9 m half extents; original readbacks must supply extents and a source digest, and still require independent source verification. `build_offline.py` copies the validator into all eight Native draft bundles. The copied primary and fallback checks passed, including two saved positives and four saved negatives, with a corrupted final body corner rejected for each primary.

Current receipts: `native/saved-proof.json` `889959c46a71ecd7a3a08ebd766ce57aff73c39fbf6b8557cf516fdc5d80c2d8`; `native/body-pose-proof.json` `16a53f66768db584953f8999c2aa08b3b2bd5926c62131364d0afe25e215a238`; `native/saved-audit.json` `79a02dc212ab5f156d28b60cf51ce9286dc3c0cd906b7a15a7f719bdc69b8892`; `native/drafts/manifest.json` `eeb6ac3f5b837279c53188ca329f67cd42d74ee30e816045c041f28461c069af`; `offline/manifest.json` `2d237565ecd6a91b63461a639a4f660c5f4cf826400ea4376d018be63797408e`; `offline/proof-compatibility.json` `076c4cd6d01dfe3d9d62cf9b6ed83330231904b8a79a24262b0575c828cf6826`; `offline/package-audit.json` `550e6963b31494e8be5b919446d9a0d444b85c087817fb22ca1c5ea9edbd7073`. Copied compatibility: eight bundles and 24 changed-source negatives. Package audit passed those, two saved positives, four saved negatives, two triggers/two trigger negatives, one comparison/one negative, and two preparations/two negatives. Scratch for these proofs was under `.runtime-work/`.

The current pinned `runtime.py offline` diagnostic against `offline/manifest.json` exits at `candidate_constructions.select` with `KeyError: 'cases'`: this is an exact copied draft manifest with `entries`, while the current runtime requires a worker execution manifest with `cases` pointing to source-hashed constructions. There is also no selected `kind: delivery` execution case or generated four-camera saved attempt for `runtime.py process-saved`. A current-format unselected primary draft now exists and passes pinned offline. Remaining CPU work is full candidate compatibility, saved processing, then source-bound physical and legal comparison. Status remains `partial`; the copied bundle proof is not canonical delivery readiness.


Status correction: partial. The historical blocked text below predates current worker-owned construction and proofs.

## 2026-11-23 source-shaped rotary body-pose proof

`native/validate_body_pose.py` computes all four vehicle-body corners from each retained ego center and heading, supplied positive half extents and the complete 240-frame source inventory. `native/prove_body_pose.py` bound both synthetic saved cases to the existing saved-source proof hashes and checked 1,920 corners across 480 source frames. It rejected a 0.1 m final corner change, a one-degree final heading change and a missing final corner for each case: six negatives total. Receipt `native/body-pose-proof.json` SHA-256 `613d5e484baaf9ddd750b2e3b667ab5aba0f9022e7dc769912b16157a8153872`; checker SHA-256 `2dbadc3b9d38642b2c1595d15fec954e3dbf00c9befca232c29f2c85bbe12077`; prover SHA-256 `b5f81a201c6b4a1e89db5230ff09d77edc689c161dbc3639659d1a00c1c8d889`. Command `.venv-cpu/bin/python work/training__C234827__NRS-484B-220-2__motor_vehicle_driver/native/prove_body_pose.py` exited 0. This catches a body-vertex inconsistency that the older center-proximity saved measurement did not itself enforce. The checker is integrated into the copied saved processor, but is not yet bound into a selected current-runtime saved-processing package.

The 2.0 m by 0.9 m extents here are explicitly synthetic. Original Native use requires source-measured bounding-box dimensions and independent island/traffic-control review. The assignment has three catalog accepted recording memberships but no accepted equivalence receipt in the returned plan; these originals have not been replayed or claimed to prove this branch. Selected exact runtime compatibility, recorded-only processing, semantic/delivery and comparison audits, original-source equivalence review and scoped strict readiness remain CPU work. Status is `partial`; no original Native, physical, legal or canonical acceptance is claimed.


Historical status: blocked. No delivery recording was selected or claimed at that time.

## Source review

Law: NRS 484B.220(2). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 1 supplied witness row(s) are planning context, not execution proof. Membership rows: {'full-train': 3}. No accepted equivalence receipt was verified.

## Planned controlled comparison

path right versus left of rotary island. Compare only `island_side_passage` (right_or_left) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 2 case definitions are unselected and have no observed values.

## Blocker and resumption

Executable Native package and all four candidate offline/compatibility proofs absent; exact statutory exceptions and historical equivalence remain unverified. Build and validate semantic stages, exact Native construction, four distinct candidates per selected case, full mandatory capture, saved positive/negative fixtures, independent audits, and comparison audit. Keep unsupported exception branches explicit. Only then set `ready`/`delivery_prepared` and add the exact GPU queue commands. Do not infer legal verdicts from CPU fixtures.
