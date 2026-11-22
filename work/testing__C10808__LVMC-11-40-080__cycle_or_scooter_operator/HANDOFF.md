# testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.40.080 — Whenever authorized signs are erected indicating that no right turn, left turn or U-turn is permitted, it shall be unlawful for any person operating a bicycle, electric bicycle, or electric scooter to disobey the direction of any such sign, except where such person dismounts from the bicycle, electric bicycle, or electric scooter to make any such turn, in which event such person shall then obey the regulations applicable to pedestrians.
Assigned branch(es): Dismount to make the U-turn, followed by pedestrian obligations.
Cell: C10808 (alley, u_turn, turn_prohibition_device); actor: cycle_or_scooter_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Construction and proof checkpoint

Exact cases: `testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__dismount_before_uturn` and `testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator__mounted_uturn`. Their comparison `uturn_dismount_exception` fixes alley geometry, operator, bicycle, governing sign, cameras and duration; only the observed dismount/afoot state may differ. `runner.py` and `scene.json` specify the sign station before the dismount station, a distinct hold, and return geometry. `construction.json`, `cases/mounted/construction.json`, and `execution-manifest.json` bind exact inline files and hashes. Both `runtime.py offline` runs passed; logs: `proof-dismount.log`, `proof-mounted.log`. `analysis.py` rejects absent/stale Native acquisition files and computes event timing without a legal label. `comparison_audit.py` rejects missing original Native evidence, late dismount, and changed fixed conditions. Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator/tests` (11 passing tests; `cpu-tests.log`).

The configured no-U-turn sign and bicycle prop blueprint names are unverified on the local CARLA version. The runner checks their presence and rejects a non-sign object, but its Native execution/capture path is unfinished. The CPU fixtures exercise spawn calls and event schema only; they do not establish an authorized erected sign, a human-powered bicycle classification, an actual visible dismount, or applicable pedestrian-regulation compliance. The returned manifest has no fallback because no tested alternate physical sign asset is available. It must remain partial.

Next CPU actions: implement Native motion and synchronized four-camera capture using the pinned runtime; emit original `phase-events.jsonl`, `sign-inventory.json`, and hashed `acquisition.json`; validate actual body pose rather than commanded phase alone; bind `analysis.py` into the pinned saved-processing contract; add both source-bound positive/negative compatibility receipts, semantic proposals, independent delivery audit, and a tested sign/bicycle fallback only if supported. Review the applicable pedestrian regulations and jurisdictional sign authorization from supplied or local source material. Then run `.venv-cpu/bin/python worker_check.py --assignment testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator --complete --require-delivery-ready`.

Final checkpoint gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C10808__LVMC-11-40-080__cycle_or_scooter_operator --complete` passes. `.venv-cpu/bin/python worker_check.py --complete` passes static checks for all 242 partial packages. `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 with `Preparation acceptance failed: partial/missing packages remain`; retained log: `.runtime-work/strict-check-final.log`. The failing readiness gate reflects unfinished CPU deliverables listed above, not a missing CPU dependency or a claim of GPU readiness.
