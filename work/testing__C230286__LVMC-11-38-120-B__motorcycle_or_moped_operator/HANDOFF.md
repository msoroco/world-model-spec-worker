# testing__C230286__LVMC-11-38-120-B__motorcycle_or_moped_operator

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.38.120(B); with 11.38.120(A) — All vehicles covered under this Section, as provided in Section 11.38.080, shall carry at least one lighted headlamp capable of showing a white light visible at least three hundred feet in the direction in which the same are proceeding, and one tail lamp mounted on the rear which, when lighted, shall emit a red light plainly visible from at least five hundred feet to the rear. The lights required by this Section shall be burning whenever such vehicles are in motion during the period from one-half hour after sunset to one-half hour before sunrise and at any other time when, due to insufficient light or unfavorable atmospheric conditions, persons and vehicles on the streets are not clearly discernible at a distance of at least five hundred feet ahead.
Assigned branch(es): Equipment requirements and motion-dependent burning.
Cell: C230286 (road, travel, sidewalk); actor: motorcycle_or_moped_operator.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C230286__LVMC-11-38-120-B__motorcycle_or_moped_operator --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 lamp equipment and burning-state checkpoint

`case-plan.json` now has seventeen exact unexecuted cases and fourteen comparisons. Cases separate covered motorcycle from trail-ride and enclosed-three-wheel coverage probes; nighttime motion and stopped state; clear daytime, insufficient light and adverse atmosphere; head/tail burning; calibrated white forward 299/300/301-foot and red rear 499/500/501-foot capability probes; and wrong-color controls. Daytime low-light and clear controls now hold both lamps off to isolate the trigger. The adjacent sidewalk remains separate from the roadway route.

`lamp_observations.py` accepts only a hash-sealed original Native context and 20 Hz trace. It requires source references for vehicle coverage, the excluded categories, road/sidewalk context, local date/time, sunrise/sunset, light/atmosphere, 500-foot discernibility, and calibrated head/tail photometry. It retains observed discernibility, calibrated color, mount and tested range, plus independent frame-by-frame lamp burning states and speed. It never infers calibrated range or color from simulator image pixels. Coverage, visibility, timing and burning duty remain unresolved review questions. Diagnostic fixtures are rejected as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Eight focused tests passed (`cpu-lamp-tests.log`, SHA256 `f175e2d2bb27353ae48822b68300581d9d573c3cbeaa8444e5a67e68cf5c516e`). Scoped static check passed (`assignment-check.log`, SHA256 `757df303f489e04b3c2e75a79601c1379c29e24c6ab9e40db62c6a33e144d169`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `869982591921fcb98025c5f3a024d8cef6fcf88d1bf1adb764fd8a49565c932f`, measurement `980464106315c9cf118cbde7df78a79111411f32d2adaba6a960dc63247e85a4`, focused tests `003a09785224f6992dcde3df62bb70e004bbab32659daf236a71345d89e3dbab`.

Remaining CPU work: bind a reviewed Section 11.38.080 covered motorcycle blueprint and the fixed sidewalk geometry, source-backed local astronomical and atmosphere records, calibrated lamp photometry, seventeen Native constructions/controllers and synchronized camera capture, finalizers and semantic proposals, exact offline and positive/negative compatibility, saved-only delivery and fourteen comparison audits. Physical and legal acceptance remain unverified.
