# NRS-484B-450-1e at C229397

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `park` / `crosswalk`.

Exact statutory source: NRS 484B.450(1)(e). Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Parking on a crosswalk. Planned comparison variable: `crosswalk_parking_occupancy`. Requests: driver parks clear of crosswalk footprint; driver parks with footprint occupying crosswalk. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the subject stops, stands or parks; the footprint is on a crosswalk.

Timing to retain: judged for every instant at rest on the crosswalk; the standing/parked duration parameter separates a stop from a momentary halt in a queue.

Exceptions and numeric alternatives planned: when necessary to avoid conflict with other traffic; in compliance with law; in compliance with the directions of a police officer or an official traffic-control device.

Unresolved judgment or rule composition: none identified in supplied summary. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.

## Source-shaped crosswalk construction checkpoint

`measure_crosswalk.py` joins 600 consecutive actor samples at 20 Hz to 2,400 named camera frame hashes and a sourced crosswalk polygon. It measures original ego footprint overlap with the crosswalk for each rest frame and retains the first occupied rest frame, total rest and occupied rest frames, and maximum overlap. A 1e-6 m² polygon tolerance and 0.1 m/s rest diagnostic are engineering measurements, not statutory thresholds. The module leaves necessity, other-law compliance, officer/device direction and legal verdict unset. It rejects missing actor/camera rows, invalid polygons, case/time mismatches and missing crosswalk geometry provenance.

`prove_crosswalk.py` exercises the two witness targets with synthetic CPU source-shaped rows only: witness 1 remains clear, witness 2 occupies the crosswalk for 480 rest frames. It rejects truncation of either actor or camera source. Receipt `offline/crosswalk-source-proof.json` SHA256 `cf975c237890f2b0e3004da1ebe17731c5a31e61cf9e266b758447c8e08afe47`. Neither footprint nor pixel hash in that fixture is original Native evidence.

`build_offline_drafts.py` inlines all eight exact planned cases as **unselected** source-bound drafts. The pinned `runtime.py offline` path passed for each exact case, including the three exception pairs. Receipt `offline/pinned-offline-proof.json` SHA256 `7085b94f1363957e6bab4b4aff0e4d92b9751c6bfdf0a470b35f24e03f41f937`; manifest SHA256 `58b51869b2bbf52b79d285756fe6b5c3a69412dc2950dfb01af621783f8df8ea`. Each draft explicitly refuses Native execution, so this receipt is only a CPU source/check checkpoint.

Remaining worker-owned CPU work: implement CARLA map/crosswalk/vehicle capture and four synchronized source cameras; bind original polygon and per-frame footprint provenance; construct observed traffic conflict and officer/device direction context for the exception pairs; identify a source-backed basis for the `in compliance with law` pair; build complete saved-only processing, positive/negative compatibility, selected delivery manifests and independent audits. Reassess physical-risk fallbacks against actual motion/visibility. Then run the strict scoped ready gate. Status remains `partial`; original Native motion and legal outcome are unverified.

## 2026-11-25 exact-law expansion and Native draft

Independent review of NRS 484B.450(1)(e) separated stop, stand and park on a crosswalk and separated police direction from official-device direction. `expand_exact_law_plan.py` expanded the plan from 8 to 14 exact cases, 7 comparisons and 7 requirement dispositions. No legal duration threshold was invented. The three exception subjects remain separately requested and unverified: traffic-conflict necessity, compliance with other law, and two distinct direction sources.

`native/geometry.py` authors a road and crosswalk object with clear and occupied approach targets. `native/prove_geometry.py` proves on authored OpenDRIVE that the clear target has 0 m² footprint overlap, the occupied target has 3.8 m² overlap, and Native four-corner ordering forms a valid polygon. This does not establish CARLA readback. The Native `runner.py` now has a CARLA-free source/case check plus an original capture path for 600 frames at 20 Hz, four synchronized 1920×1080/1280×720 cameras, per-frame actor footprint and camera RGB hashes, Native map crosswalk readback, and restoration/termination. It requires a reviewed hash-bound context packet at actual execution. This code has not connected to CARLA, so physical feasibility and legal applicability are unverified.

`native/prove_source_context.py` passed synthetic source isolation across all 14 cases: the chosen traffic-conflict, other-law, police or official-device source is required to match its exact comparison target, other exception sources stay inactive, and a reviewed packet without citations is rejected. This is a CPU contract test, not authority or physical evidence. `build_offline_drafts.py` now embeds the Native runner and authored geometry in all 14 source-bound draft constructions; every exact case passed the pinned `runtime.py offline` path with `simulation_started: false`. The current offline proof is `offline/pinned-native-offline-proof.json`. Earlier eight-case offline receipts are historical and no longer bind the current draft manifest.

Status remains `partial`. These are unselected Native drafts. Next CPU work: build source-hashed 600-frame fixture recipes and selected measurement contracts for each exact case, execute primary and missing-source-negative compatibility chains, run recorded-only saved processing, then bind semantic, physical, delivery and seven comparison audits. Review actual authority packets for the exception claims; the authored target and synthetic context cannot establish them.

## 2026-11-25 selected 14-case construction and public pilot

`build_selected.py` binds all 14 exact source-law cases to selected Native construction bundles, separate measurement contracts and canonical case proposals. All 14 selected constructions passed the pinned `runtime.py offline` check; bound log hashes are in `offline/selected-offline-proof.json`. Each case now has an explicit source-hashed diagnostic recipe under `selected-recipe-<suffix>.json` and source files under `selected-source/<suffix>/`. The fixture sources are synthetic and do not claim original Native geometry or pixels. The Core trace, capture evidence and actor footprints in each fixture share the same source positions and speeds. `finalize.py` enforces frame, time, spatial, source-video and crosswalk joins and returns no legal verdict.

The current witness_1 selected public compatibility pilot passed exact positive analysis, Native validation, Core/Lean conversion, four-camera render and full decode, plus the missing `crosswalk-source.json` negative. Receipt and logs are `compatibility/witness_1-primary-*`; the matching recorded-only saved run passed with original sources preserved and `missing_evidence=false` in `saved/witness_1-processing.json`. Public trial outputs are under `.runtime-work/owner229397/public-witness-1-pilot-v5`; saved trial outputs under `.runtime-work/owner229397/saved-witness-1-pilot-v2`. The first 13 remaining public chains are running sequentially with distinct output directories and logs under `.runtime-work/owner229397/`. No actual CARLA execution or legal verdict is claimed.

The selected `execution-manifest.json` is still incomplete: public/saved receipts have not been bound for all cases; semantic stage proposals, independent physical and delivery audits, seven comparison audits and source-reviewed real authority packets remain. `result.json` is truthfully `partial`. Before marking ready run `.venv-cpu/bin/python worker_check.py --assignment training__C229397__NRS-484B-450-1e__motor_vehicle_driver --complete --require-delivery-ready`.

## 2026-11-25 exact selected CPU package

Fourteen selected construction bundles passed the pinned offline check, current-runtime public positive and missing-source negative compatibility, and recorded-only saved processing. Fourteen physical complete/incomplete/missing-evidence fixture triples and lifecycle checks passed; 14 delivery audit positive/negative source predicate checks passed; seven source-isolated comparison checks and missing-road negatives passed. Direct execution manifest, canonical semantic chain, portable import, delivery acceptance and compatibility receipt validators passed. Root Native source check and two unit tests passed. Original CARLA readback and legal exception applicability remain for local capture and independent review; the CPU package does not claim a legal outcome.
