# testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.27.010(A); with 11.27.010(B) — Except as otherwise provided in Subsection (B), it is unlawful to operate a motorized vehicle upon or within a right-of-way that: (1) Has been designated on an official trails plan as an equestrian trail, multi-use trail, or other trail not intended for use by motorized vehicles; (2) Has been dedicated to the City for use as such a trail; and (3) Has been posted with appropriate signs to indicate that motorized vehicles are prohibited. The provisions of Subsection (A) do not apply to: (1) An emergency vehicle; (2) Any vehicle that is being used in connection with maintenance of the right-of-way; or (3) Any motorized wheelchair or other device that is designed for and used by a mobility-impaired person.
Assigned branch(es): Conjunctive trail prerequisites, subject to all Subsection (B) exceptions.
Cell: C143687 (nonmotorized_trail, travel, access_restriction_sign); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## Construction and source-bound audit checkpoint (2026-11-23)

`case-plan.json` now names six exact cases: all_prerequisites, not_designated, not_dedicated, no_prohibition_sign, emergency_vehicle, and maintenance_vehicle. Five controlled comparisons isolate one official-plan, dedication, sign, emergency-use, or maintenance-use condition against the same baseline. The mobility-device exception remains an explicit compatible-role/cell review, because an ordinary motor-vehicle-driver cell cannot prove qualifying device design and use by relabeling a vehicle.

`trail.py` checks source-backed official plan/dedication assertions, the physical corridor and motor route, sign face and governed access, vehicle/operator records, and separate exception-use status. It installs a sign, spawns a vehicle, applies a route and status, and cleans up owned actors on failure. `saved_audit.py` checks a hash-sealed 900-frame Native history for continuous original frame IDs, stable participants and sources, corridor entry, and sign readback; its comparison audit checks fixed and differing fields. Neither module decides legal compliance or physical video acceptance.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver/tests -v` passed 8 tests (see `cpu-tests.log`). `.venv-cpu/bin/python runtime.py preflight` passed (see `preflight.log`). Next: bind source-reviewed administrative and exception records, resolve the mobility-device branch in a compatible allocation, build exact runner/config/measurement contracts and semantic proposals, execute offline and positive/negative compatibility plus saved-only and independent delivery receipts. Actual Native motion, sign visibility and video quality remain later physical checks.

Exact gate checkpoint: `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver --complete` exited 0 (`static-check.log`). The same command with `--require-delivery-ready` exited 1 with `Preparation acceptance failed: partial/missing packages remain` (`strict-check.log`). This status is truthful: exact delivery artifacts and physical-source bindings remain unfinished.

## Exact-case and saved-source audit checkpoint (2026-11-23)

`saved_audit.py` now binds every original-history condition to the full exact case ID and rejects foreign or mislabeled IDs. Its controlled-pair audit requires the altered condition to have a distinct original source hash. The tests exercise all five planned comparisons and negative tampering cases.

`delivery_audit.py` independently checks acquisition case/cell identity, 900 frames at 20 Hz, a sealed original-history JSONL, and hashes of four attempt-confined camera sources. Its result explicitly withholds full video decode, actual-pixel visibility, physical completion and legal judgment. Three CPU tests cover positive source integrity and case, duration, media, and path tampering. This is a source-integrity component, not the full required delivery acceptance audit.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver/tests -v` passed 14 tests (`cpu-tests.log`). `.venv-cpu/bin/python runtime.py preflight` passed (`preflight.log`). `.venv-cpu/bin/python worker_check.py --assignment testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver --complete` passed (`static-check.log`); adding `--require-delivery-ready` failed on truthful partial status (`strict-check.log`). Next CPU work: source-reviewed administrative packet, exact six-case runner/config/measurement bundles and semantic proposals, exact offline and compatibility receipts, manifest-bound process-saved and full delivery/comparison acceptance receipts, plus compatible allocation for the mobility-device exception.

## Original source packet checkpoint (2026-11-23)

`source_packet.py` now verifies seven original administrative, sign, vehicle/operator and exception records against exact source bytes and the source assertions in the construction site packet. Its three tests exercise all six case variants and reject tampered bytes, false administrative assertions and path escape. These test records are CPU fixtures; original City plan, dedication and status records are still required for a deliverable attempt.

The focused suite now passes 17 tests (`cpu-tests.log`). The assignment-scoped `--complete` check passes (`static-check.log`); the assignment-scoped `--complete --require-delivery-ready` check fails on truthful partial status (`strict-check.log`). The next CPU work is six exact runner/config/measurement bundles and semantic proposals, then exact offline/compatibility/process-saved and full delivery receipts. Physical source facts remain unverified until original documents and capture are reviewed.

## Original-frame trail capture checkpoint (2026-11-23)

`trail_capture.py` now adds the producer for the source-bound history audit. It verifies the seven-record administrative packet, exact case/site fields, live OpenDRIVE identity, synchronous 20 Hz world, vehicle/operator IDs, and camera-plan identity before capturing 900 original CARLA frames. Each tick retains the original frame and time, reads the vehicle's actual XY location to compute corridor entry, requires a live sign-face observer result, and writes a separate 900-line snapshot packet stream. Each history row binds its snapshot packet by SHA-256. The output is accepted by `saved_audit.audit_history` only after its original source hash and exact case conditions pass. A diagnostic fake world tests the path; no administrative sufficiency, physical video, or legal conclusion is claimed. The capture refuses to overwrite either history or packet stream before ticking.

`trail_capture.py` SHA-256 `867af5e2b28441a26237de46a8d4879e9e885a9d92f33df7ed353c74b1f164c8`. `PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/.runtime-work/c143687-tmp SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c143687-pipeline .venv-cpu/bin/python -m unittest discover -s work/testing__C143687__LVMC-11-27-010-A__motor_vehicle_driver/tests -v` passed 21 tests (`cpu-tests.log` SHA-256 `02f1a10fddbf8783fc7b5884b1ee58b3406d19391bb3c7afa8009082272ad4b2`). Pinned `runtime.py preflight` passed (`preflight.log` SHA-256 `f0b1393527a70699e006821f737db0bca8b086a899260bd73577455ff5ffee88`). Scoped `worker_check.py --complete` passed (`static-check.log` SHA-256 `2bf0891cf565dc6f0ddf1a0783bfcda93d7142263a08a0de60707beccbd0217d`). Exact scoped strict exited 1 on the truthful partial package (`strict-check.log` SHA-256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`).

Remaining CPU work: source-review real official plan, dedication, corridor, sign, vehicle/operator and exception records; provide the six exact runnable bundles with camera acquisition, Native finalizer and semantic proposals; run offline, positive/negative compatibility, saved processing and independent delivery/comparison acceptance proofs; and resolve the mobility-device exception in a compatible actor/cell allocation. Actual trail motion and pixels remain local physical verification. Status remains partial.

## 2026-11-24 independent original packet join checkpoint

`saved_audit.audit_packet_join` now reopens all 900 SHA-sealed original tick packets and the source-sealed history. It verifies per-row packet hashes, original frame/time continuity, vehicle identity, live sign readback, and trail-corridor occupancy recomputed from the packet location and reviewed corridor box. A changed packet stream and a resealed false corridor observation reject. This is source-consistency proof; administrative sufficiency, video visibility and legal judgment remain unresolved.

The focused suite passed 23 tests; pinned preflight and scoped static passed; exact scoped strict exited 1 on truthful partial. Commands and SHA-bound logs are in `result.json`. Remaining CPU work: real original City plan/dedication/sign/exception records, six exact runner/config bundles and semantic proposals, offline/compatibility, full saved/media/delivery audits and compatible mobility-device allocation.

## 2026-11-24 full saved video decode checkpoint

`delivery_audit.audit_decoded` now extends the sealed original-history and four-camera source audit with ffprobe 900-frame, 20 Hz timestamp and dimension checks plus full ffmpeg decode of each view. It rejects changed bytes and a re-sealed 10 Hz stream. The diagnostic generates four 900-frame video fixtures; its 3,600 decoded frames prove the software join only. Physical completion, actual pixel visibility and legal judgment remain unset.

The focused suite passed 24 tests (`cpu-decoded-tests.log`); pinned preflight and scoped static passed (`cpu-decoded-preflight.log`, `cpu-decoded-static.log`); exact scoped strict exited 1 on truthful partial (`cpu-decoded-strict.log`). Commands and SHA-256 log hashes are recorded in `result.json`. Remaining CPU work: reviewed original official plan, dedication, sign, corridor and exception sources; six exact runnable bundles and semantic proposals; per-case offline/compatibility, saved processing and independent comparison delivery; compatible mobility-device exception allocation.

## 2026-11-25 exact diagnostic bundles and original comparison source audit

All six exact cases now have source-hashed construction bundles under `cases/<case>/construction.json`, with `execution-manifest.json` binding their current hashes. Each materialized bundle checks the exact C143687 identity, 900 frames at 20 Hz, the four current capture-profile cameras, nine original-byte source slots, sign placement, route containment and diagnostic construction calls. `runtime.py offline` passed for all six exact IDs; each offline bundle also rejects changed map source bytes. These records are explicitly diagnostic fixtures, not reviewed City plan, dedication, corridor, sign, vehicle/operator or exception records. `runner.py --output-dir` rejects Native acquisition until those original sources and the four-camera capture path are bound.

`source_packet.py` now includes map and corridor records in the source-byte join. `comparison_delivery.py` independently reopens two distinct sealed saved attempts, checks declared original provenance, four camera hashes, 900-row exact history and fixed conditions, and requires a distinct source hash for each of the five deliberate differences. Three comparison tests cover the five positive diagnostic pairs and negative provenance, altered camera and resealed changed-map cases. The focused suite passes 27 tests. This proves software behavior only; source authenticity, physical pixel visibility and legal sufficiency remain for independent review.

Remaining CPU work: replace diagnostic source packet with reviewed original records and map/corridor readback; implement Native four-camera acquisition, original frame map, finalizer and result; author canonical semantic proposals and selected measurement contracts; run positive/negative compatibility and saved-only processing per exact case; add full delivery acceptance including actual-pixel review and independent comparison delivery of original attempts; review compatible allocation for the mobility-device exception. Actual motion, sign visibility and quality are later physical checks. Status remains partial.
