# testing__C229404__LVMC-11-52-130-A7__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.52.130(A)(7); with 11.52.130(B) — No person shall stop, stand or park a vehicle except when necessary to avoid conflict with other traffic in compliance with law or the directions of a police officer or a traffic control device, in any of the following places: In front of or within five feet of a public or private driveway; provided, however, that this provision does not apply to the parking of a vehicle in or near a private driveway by a person who owns or is in control of that driveway, or who is a family member or invitee of the person so owning or controlling the driveway. The provisions of Paragraphs (1) and (7) of Subsection (A) of this Section do not apply to a United States Postal Service vehicle while it is being operated on official business.
Assigned branch(es): parking at road driveway interface.
Cell: C229404 (road, park, driveway_entrance); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C229404__LVMC-11-52-130-A7__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 exact driveway cases and saved measurement checkpoint

`case-plan.json` now contains sixteen unexecuted exact targets and eleven controlled comparisons. The targets separate public/private driveway, front/within-five-feet/outside-five-feet positions, stop/stand/park activities, ordinary/owner/family/invitee relationships, necessary traffic conflict, device/police/law direction, and official versus unofficial postal business. The private driveway relationship cases preserve the parking-only scope of that exception. The witness remains conditional; no original recording has been accepted.

`driveway_measurements.py` accepts an exact case only with a hash-sealed original Native context and 20 Hz trace. It requires source references for the driveway mouth, frontage, use, responsible person, relationship, purpose, traffic direction and postal status, plus eight original vehicle body vertices, frame cadence, speed and control activity. It computes sampled vertex-to-mouth distance and records the five-foot metric conversion as a reference. A vertex distance is not a complete vehicle-footprint distance. Whether the vehicle is in front of the driveway, whether a stop is necessary, and whether private or postal exceptions apply remain unresolved legal/factual judgments. No diagnostic fixture is accepted as delivery evidence.

Pinned preflight passed (`cpu-preflight.log`, SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`). Six focused tests passed (`cpu-driveway-tests.log`, SHA256 `7bf0446fb7c08f6a704634a0b97e01202a506b378c4e334b583411487c982a90`). Scoped static check passed (`assignment-check.log`, SHA256 `9e0f830ca52b025f15cfdecd0c412351fe47ca5cecb2baefc1ef32416fdb6ae4`). Exact scoped strict exited 1 on truthful partial status (`strict-gate.log`, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`). Source hashes: plan `a5d07f1b56e4378a59a6c73a8cd42ed5c8c968393ad5b0ae75d5a06592cf15ad`, measurement `d061494cab08aa7a7859fc12eabb3482bb5fe50a273514412878de6219937391`, focused test `5870b46f5a87cd78955d0dd2e0948ef52fafdd60652bda3d65546619424958e9`.

Remaining CPU work: bind a reviewed Native driveway map and independent fact records; build all sixteen exact physical scenes/controllers, original synchronized camera and actor capture, complete vehicle-footprint geometry, case finalizers and semantic proposals. Then run exact offline, positive/negative compatibility, saved-only delivery and eleven comparison audits. Physical placement, camera coverage and all legal exceptions remain unverified.
