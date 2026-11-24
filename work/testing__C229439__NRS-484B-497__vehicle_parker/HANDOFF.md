# testing__C229439__NRS-484B-497__vehicle_parker

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484B.497 — If a laned roadway is restricted to one direction, a person shall not stand or park a vehicle upon the left-hand side of such one-way roadway unless official traffic-control devices are erected permitting such standing or parking.
Assigned branch(es): Left-side parking with explicit device-permission comparison.
Cell: C229439 (road, park, parking_restriction_device); actor: vehicle_parker.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229439__NRS-484B-497__vehicle_parker --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 exact one-way parking controls and saved measurement checkpoint

`case-plan.json` now has twelve unexecuted exact targets and ten comparisons. It separates a left-side park/stand on a marked one-way roadway with no device, official permitting and restricting devices, an unofficial permitting sign, activity-specific park-versus-stand permission, a right-side park, a stop control, a two-way road and a one-lane road. These are controlled construction targets. No source recording is accepted.

`parking_measurements.py` requires a hash-sealed original Native 20 Hz context and trace. It checks public-roadway, roadway boundary, marked-lane, direction-restriction, device inventory/erection/official status/instruction/governed-space, parking-person and halt-purpose source references. Eight original vehicle body vertices yield sampled signed lateral coordinates in the road-forward frame. Speed and activity control are retained per frame. Side of the *roadway* and whether an erected official device permits this activity in the governed space remain unresolved; a positive signed coordinate alone does not establish either proposition. Diagnostic fixtures are rejected as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Seven focused tests passed (`cpu-parking-tests.log`, SHA256 `c87f8482630ef1bab74a47789c05a4514dd2464bcc89b24355d52c5cd3682690`). Scoped static check passed (`assignment-check.log`, SHA256 `c88b023aa5881ab5eedc2caaacd7f4a4b13798c566c744e412b037ec7b095da0`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `f7f4b50c682456a8411a09e2317fa9bf33ade47d42c41888ef4f5fa087769bc8`, measurement `743d03b57a84a083073582b726b1b67c3acb54c32b8240747b39ff29d47c9077`, focused tests `bf30151d0cd39a87d87edd353fc1b6702e77489d29696607037831b8f11b44ab`.

Remaining CPU work: bind reviewed Native public roadway and marked lane map with source-backed official device governed-space geometry and real person/purpose facts; build twelve physical scenes/controllers and synchronized original four-camera capture, resolve roadway-body placement, then implement finalizers/proposals, exact offline and positive/negative compatibility, saved-only delivery and all ten comparison audits. Physical and legal acceptance remain unverified.
