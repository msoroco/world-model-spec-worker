# testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.22.120(B); with 11.22.120(A) — The City Traffic Engineer is authorized to determine and designate those heavily traveled streets upon which shall be prohibited the use of the roadway by motor-driven cycles, bicycles, horse-drawn vehicles or other nonmotorized traffic and shall erect appropriate signs giving notice thereof. When signs are erected giving notice thereof, no person shall disobey the restriction stated on such signs.
Assigned branch(es): Signed street restriction adjoining a nonmotorized trail.
Cell: C143687 (nonmotorized_trail, travel, access_restriction_sign); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 executable CPU checkpoint

The frozen law covers the City Traffic Engineer designation and erected restriction sign, then forbids disobeying the stated restriction. The assigned actor is a human-propelled bicycle operator; this package does not claim coverage of motor-driven cycles, horse-drawn vehicles or every other nonmotorized class. No accepted recording exists. The witness is conditional on original designation, sign, trail-to-roadway connection, and actor identity. No exact-law judgment range applies; the broad frozen judgment file contains other laws and is not a threshold for this clause.

Exact planned cases are `__posted_enter`, `__posted_stop`, and `__posted_remain_trail` appended to this assignment ID. `posted_roadway_entry` holds site, designation, sign and bicycle class fixed while changing roadway entry. `trail_vs_roadway_use` holds the same sources fixed while changing whether the bicycle uses the governed roadway or remains on the trail. The legal outcome remains unresolved. Each case has physical-risk assessment in `case-plan.json`; the entry case flags the narrow trail junction and sign camera visibility for physical preflight, with no untested fallback asserted.

`native_site.py` requires an original engineer designation for the same street, a posted bicycle roadway-restriction sign with wording and facing direction, connected trail/street segments, and source-bound bicycle blueprint. It invokes Native spawn and velocity control only after these checks and reads the live actor back. `native_measurement.py` requires a sealed original 900-frame, 20-Hz capture with exact case, map, street, actor, sign, and route segment continuity. It measures actual governed-roadway frames and rejects absent entry or contradictory entry. `comparison_audit.py` rejects changed fixed site/designation, incomplete original measurement or missing contrast. These are executable CPU checks; fake packets in tests are not physical evidence.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator/tests -v` passed 4 tests; log `cpu-tests.log`, SHA-256 `45ba38fcb870b086d05d92d4ed86e306f50c65d11065d648c24dfdf1657121ea`. Assignment `--complete` static gate passed; exact strict gate still exits 1 because status is partial and deliverables below remain.

Next CPU actions: build case-specific config/construction/runner/manifest and semantic proposals; bind actual map and designation acquisition to the Native packet; run exact offline, positive and missing-source negative compatibility for all three cases; implement saved delivery audits, source decode receipts and post-capture process-saved fixture proof. Rerun exact strict gate, and mark ready only after it exits 0. Actual Native motion and camera visibility remain physical checks.

## 2026-11-25 selected CPU closure

Pinned v2 diagnostic proofs passed: four offline, four positive/negative compatibility (11 checks each), three recorded-only process-saved, three physical/lifecycle, two fixed-site diagnostic comparisons, six unit tests, and three positive/negative synthetic delivery protocol tests. The diagnostic manifest SHA-256 is c7b655499a53bdcd067164ec2596a2c798d4967f7326be0ecd72a74c32f7a7be. Selected production manifest SHA-256 is d64a552b8d26135a55b77f97799281060954a30eec2826fa1323176a23004d66. `prove_selected_validators.py` passed pinned selected execution, semantic, compatibility, physical and exact full-test delivery validators for all three cases; see `selected-validator-report.json`.

The original attempt is source-gated. Required original bytes are the reviewed City Traffic Engineer designation, erected sign wording/orientation/placement, connected trail and governed roadway route, and qualifying bicycle blueprint. No such reviewed packet or released four-camera Native attempt has been supplied. `native_adapter.py` and `delivery_audit.py` implement capture and independent acceptance after those inputs arrive. Diagnostic proofs remain diagnostic, and `result.json` remains partial.

Exact scoped `worker_check.py --assignment testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator --complete` passes. The `--require-delivery-ready` variant exits 1 with `Preparation acceptance failed: partial/missing packages remain`, consistent with the truthful partial status; see `scoped-strict.log`.
