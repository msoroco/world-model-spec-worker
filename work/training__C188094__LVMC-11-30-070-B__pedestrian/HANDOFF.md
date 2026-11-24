# LVMC-11-30-070-B at C188094

Actor: `pedestrian`. Frozen cell: `pedestrian_overpass` / `cross_road` / `crosswalk`.

Exact statutory source: LVMC 11.30.070(B). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Pedestrian crossing near an overpass in an established business district..

Controlled planning variable: `crosswalk_occupancy_at_crossing`. Proposed requests: cross in marked or unmarked crosswalk in business district; cross roadway outside any marked or unmarked crosswalk in same district. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: business-district condition.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

`native/path.py` requests paired 600-frame / 20 Hz at-grade pedestrian crossings near the overpass. Both use the same northbound path and speed; only crossing x position changes. The route proof `native/path-proof.json` (SHA-256 `9c67e7f5fa696903e43e75090fc1bd01a55891a37e5f5278b90eca52b3837883`) verifies this controlled difference and rejects three invalid requests. It is a path proposal, not observed CARLA motion.

`native/measure_crossing.py` and `native/measurement-contract.json` require original pedestrian position, 600 Native frame/time joins, all four source-camera identities, complete marked and unmarked crosswalk geometry, at-grade roadway/overpass geometry and independently sourced business-district evidence. The CPU proof `native/crossing-proof.json` (SHA-256 `802340d07195abf6c2a76cdfebc5843259e8713f60012b6e307ca6038d038e89`) distinguishes crossing entry in a marked crosswalk from entry outside the inventoried crosswalks, and rejects six district/crosswalk/source/deck/camera defects. Placeholder source hashes and synthetic pedestrian positions establish no original business-district status or physical crossing.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. The package remains `partial`. Next CPU work: wire Native pedestrian and four-camera capture, construct exact cases, establish business-district frontage and complete unmarked/marked crossing evidence, run exact offline/compatibility/saved-only proofs and independent audits, then run scoped strict ready gate before promotion.

## 2026-11-23 full roadway point-path CPU checkpoint

The crossing meter now reports every roadway point-path frame outside the complete surveyed crosswalk inventory, rather than classifying entry alone. A source-shaped unmarked-crosswalk trajectory remains inside throughout. A smooth trajectory entering in a marked crosswalk and drifting outside it retains marked entry but fails full-path containment. A seventh negative rejects a one-frame pedestrian teleport. Refreshed receipt SHA-256 `6bad3899770410356edc4e59d86658d2b724bc39d0297bffe8a1d52d4fa7a577`; meter SHA-256 `df0d5aaab43cbc16800b26ee0dbec4522bf51775d1d762fc6bbfaa291eaeb00b`; proof script SHA-256 `6c54e34b5f2daf519ae2eaebc0466d97fc31b93719684ca8bead4dd18fc60110`. Command: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c188094-path-output PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C188094__LVMC-11-30-070-B__pedestrian/native/prove_crossing.py`. Point-path membership does not establish full body containment. Original business-district and complete crosswalk sources, Native capture, selected delivery paths and audits remain unfinished.
