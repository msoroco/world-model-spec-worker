# testing__C111260__NRS-484B-270-5a__motor_vehicle_driver

Status: partial construction and saved-source checkpoint. Six exact cases are proposed; no physical recording or legal conclusion is claimed.

Exact law: NRS 484B.270(5)(a) — The driver of a motor vehicle shall: Exercise due care to avoid a collision with a person riding a bicycle, an electric bicycle or an electric scooter.
Assigned branch(es): Person riding a bicycle.
Cell: C111260 (intersection, travel, cyclist); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and comparison checkpoint

Six exact cases now map bicycle, electric bicycle and electric scooter to observed brake/maintain pairs; three comparisons hold Native map, rider type, routes, camera plan, duration and starting speeds fixed. There are no frozen accepted recordings or exact-law judgment ranges. `case-plan.json` carries case IDs, evidence gap, observations and requirement dispositions. This is a construction target, not measured delivery or a due-care conclusion.

`cyclist_encounter.py` validates original map route crossing and mounted rider classification, spawns the motor vehicle and rider with source-selected blueprints and cleanup, computes an engineering response trigger, and audits continuous 20 Hz original Native actor/gap/contact/response samples. `comparison_audit.py` independently rejects missing source histories, changed fixed conditions and unobserved response. `tests/` exercises positive and negative paths.

CPU proof: `.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver/tests -v` passed 12 tests; `cpu-tests.log` SHA256 316da4e1f72eace539616763d1255a5baf84c234d222725e7cd6f9e30118210c. Assignment strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete --require-delivery-ready` fails `Preparation acceptance failed: partial/missing packages remain`; log `strict-gate.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Remaining CPU work: wire the selected Native map packet into the canonical runner/config/construction and per-case bundles; implement source-hashed case-specific finalizer, full 900-frame capture and delivery audit; run exact offline, positive/negative compatibility and saved-only proofs for every case; write semantic stage proposals and execution manifest. Physical CARLA motion, rider visibility and video quality remain later verification.

## 2026-11-24 saved encounter finalizer checkpoint

`saved_encounter.py` now joins an exact-case original Native encounter packet to SHA256-bound site, 900-frame 20 Hz history and four camera frame maps. It confines all source paths to the attempt directory, revalidates the map's crossing route and statutory rider classification with `cyclist_encounter.py`, and checks the observed rider identity, mounted state, response, gap/contact and frame continuity. It rejects a changed case, missing/tampered source, nonoriginal request history, missing camera, frame mismatch and path escape. The returned observation explicitly leaves full video decode, actual pixels, physical completion and due-care judgment unresolved. The local tests use synthetic small text packets solely to exercise software checks. The packet is not yet bound to a canonical Native receipt; that is CPU work.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C111260__NRS-484B-270-5a__motor_vehicle_driver/tests -v` passed 17 tests; `cpu-tests.log` SHA256 9e0c0dc97d200f893871f3b7e4387ea0559d98e055605bdb65a5543e4976b24e. `.venv-cpu/bin/python worker_check.py --assignment testing__C111260__NRS-484B-270-5a__motor_vehicle_driver --complete` passed; `static-gate.log` SHA256 f64ad44f5d127b586b1fb76505cab0d9d90073885ce063d9098ced2614020366. The exact command with `--require-delivery-ready` exited 1 because this result remains partial; `strict-gate.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Next CPU steps: bind this packet to a canonical sealed Native result, implement actual 900-frame sensor acquisition and source readback, wire the runner and all six exact case bundles, implement semantic proposals, compatibility and saved-only proofs, then independent delivery and comparison audits and manifest. Actual motion and camera visibility require later local physical review.
