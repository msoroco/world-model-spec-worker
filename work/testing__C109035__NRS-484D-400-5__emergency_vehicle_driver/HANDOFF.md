# testing__C109035__NRS-484D-400-5__emergency_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: NRS 484D.400(5) — An authorized emergency vehicle may be equipped with a siren, whistle or bell, capable of emitting sound audible under normal conditions from a distance of not less than 500 feet, but the siren must not be used except when the vehicle is operated in response to an emergency call or in the immediate pursuit of an actual or suspected violator of the law, in which event the driver of the vehicle may sound the siren to warn pedestrians and other drivers of his or her approach. A driver of an emergency vehicle may operate the vehicle’s warning lamps without sounding the siren.
Assigned branch(es): Emergency-call response with pedestrian recipient context.
Cell: C109035 (intersection, emergency_response, pedestrian); actor: emergency_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109035__NRS-484D-400-5__emergency_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU construction checkpoint

The exact law has a separate permission to equip an audible warning device, a 500-foot normal-condition audibility condition on that equipment, an emergency-call or immediate-pursuit alternative for siren use, approach-warning purpose, and an independent lamps-without-siren permission. The assigned emergency-call pedestrian recipient remains the primary case. The seven exact case IDs in `case-plan.json` cover response siren, response lamps alone, response silent, actual pursuit siren, suspected pursuit siren, unqualified siren, and unqualified lamps alone. Three controlled comparisons hold intersection route, actor, recipient geometry, capture profile, equipment inventory, weather and speed policy fixed while varying only the declared event or device commands. No accepted recording exists in the frozen evidence inventory; no case is physically verified or a legal verdict.

`emergency_scene.py` computes approach geometry for eastbound and westbound routes with a separately placed pedestrian ahead and outside the vehicle lane, and returns independent siren/lamp control targets. This is portable authored geometry; it still needs a reviewed Native site, CARLA controller/capture and physical camera checks. `warning_audit.py` reads SHA-bound original 900-frame device traces plus dispatch and equipment sources. It rejects absent/tampered sources, missing original frames and malformed device states; outputs actual siren/lamp counts, event temporal overlap and unresolved audibility, hearing and purpose. `native_scene.py` requires a reviewer, citation, exact case/cell/actor, OpenDRIVE hash, correct approach geometry and vehicle/pedestrian blueprint types before spawning actors; no real site packet is supplied. `comparison_audit.py` rejects changed source hashes for map, site, route, pedestrian, equipment, profile, weather or speed policy, as well as undeclared device differences. Its positive/negative fixtures use synthetic test documents solely to test software behavior.

Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C109035__NRS-484D-400-5__emergency_vehicle_driver/tests -v` (12 passed; log `cpu-tests.log`) and `.venv-cpu/bin/python worker_check.py --assignment testing__C109035__NRS-484D-400-5__emergency_vehicle_driver --complete` (passed static; log `cpu-static-check.log`). The strict exact command remains necessary and its failure is retained in `cpu-strict-check.log`.

Next CPU construction: bind the seven cases into executable per-case Native runner/config/construction, source capture and case-specific finalizer; produce canonical semantic proposals, exact manifest, offline and case-specific positive/negative compatibility, saved-only and delivery audit receipts. Independently source authorization and installed device; 500-foot audibility under normal conditions cannot be inferred from simulated audio, and missing Department standards/definition references remain review questions. Do not mark ready on these drafts.
