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

## 2026-11-24 Native original-source capture checkpoint

`native_capture.py` adds a lazy, source-gated 45-second synchronous 20-Hz loop for all seven exact case suffixes. It validates independent reviewed dispatch and equipment documents and the reviewed OpenDRIVE-bound site before creating actors. A caller supplies motion, device-command, independent device-readback and four-camera capture adapters. The loop records command and observed siren/lamp states separately on every Native frame, checks contiguous frame IDs and timing, retains camera source references for front/rear/left/right, hashes each original source and writes a capture receipt that explicitly claims no physical acceptance. The device reader rejects missing booleans, missing citations and declared command echoes. Finally cleanup turns devices off and destroys owned actors. `warning_audit.py` now joins the optional original camera trace to the same Native frame IDs, rejecting missing or altered synchronization. This is executable capture architecture; the actual adapters, camera media, physical device source and reviewed map packet are still needed. The CPU fixture is synthetic and does not establish a siren’s audible output or a pedestrian’s hearing.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109035__NRS-484D-400-5__emergency_vehicle_driver/tests -v` passed 16 tests, including a complete 900-frame capture-to-audit join and negative source/camera/dispatch cases. `.venv-cpu/bin/python runtime.py preflight` passed with Lean 4.28.0; `worker_check.py --updates` showed version 0 and no pauses. `.venv-cpu/bin/python worker_check.py --assignment testing__C109035__NRS-484D-400-5__emergency_vehicle_driver --complete` passed static checks. The same assignment-scoped command with `--require-delivery-ready` failed on partial status, as expected; its log is retained. This checkpoint is partial. Next worker-owned CPU steps are to implement the genuine device/camera adapters, case-specific finalizer, canonical semantic proposals and seven per-case bundles, then run offline, compatibility, saved-only and independent delivery proofs before changing status.

## 2026-11-24 saved-only source finalization checkpoint

`saved_finalizer.py` now reopens the four original source files recorded by `native_capture.py` and requires their SHA-256 hashes, exact C109035 case identity, reviewed dispatch/equipment document identities, the declared event, 900 contiguous Native device and camera frame IDs, independent readback citations and the command state for the exact case. It delegates observed siren/lamp and event-window measurements to `warning_audit.py` and returns a source-bound observational result. Physical completion, actual camera pixels, 500-foot audibility, recipient hearing, warning purpose and legal conclusion remain unverified. The fixture references synthetic camera strings and makes no media-decode claim.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109035__NRS-484D-400-5__emergency_vehicle_driver/tests -v` passed 22 tests (`cpu-tests.log`), including cross-case document, event mismatch, rehashed Native-frame gap, wrong-case command and original-source tamper rejection. Assignment-scoped `worker_check.py --complete` passed (`cpu-static-check.log`); the exact `--complete --require-delivery-ready` command failed on truthful partial status (`cpu-strict-check.log`). Next CPU work is original media acquisition/full decode and canonical seven-case bundles, proposals, manifest, offline/compatibility and saved-only/delivery receipts.

## Original four-camera pixel audit checkpoint

`pixel_audit.py` accepts an exact-case `camera_media.json` bound to the SHA-256 of `capture_receipt.json`; each front/rear/left/right ZIP has its own SHA-256 and exactly the 900 expected Native-frame PNG names. Every camera trace reference must point to its exact archive/frame, and Pillow fully decodes all 3,600 original images. The 8x8 synthetic PNG fixture proves the software checks, not physical visibility or capture quality. An actual Native camera adapter must produce these archives and original references.

Final proof this round: 25 focused tests passed in `cpu-tests.log`; assignment-scoped static check passed in `cpu-static-check.log`; assignment-scoped strict check failed on truthful partial status in `cpu-strict-check.log`. All three logs are SHA-256 recorded in `result.json`.

## 2026-11-24 original camera recorder checkpoint

`camera_recorder.py` is an executable four-camera adapter for `native_capture.capture`. It takes the exact Native frame from a caller-owned sensor reader, verifies each original CARLA-style image frame and declared dimensions, converts BGRA bytes to lossless PNG, and writes front/rear/left/right source archives. `native_capture.capture` calls its `finish` method only after sealing `capture_receipt.json`; this binds `camera_media.json` to the receipt SHA and each archive SHA. Its failure path closes archives and still releases actors. The synthetic 2x2 fixture ran the full 900-tick capture and decoded all 3,600 saved PNGs with `pixel_audit.audit_pixels`; a wrong-frame image was rejected before any archive was written. These tests establish software joins only, not physical visibility.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C109035__NRS-484D-400-5__emergency_vehicle_driver/tests -v` passed 33 tests (`cpu-tests.log`). Assignment-scoped `worker_check.py --complete` passed (`cpu-static-check.log`); the exact `--complete --require-delivery-ready` check failed on partial status (`cpu-strict-check.log`). All hashes are current in `result.json`. Next CPU work: bind a documented independent device readback and a reviewed Native site, then build seven canonical case bundles, exact offline/compatibility and saved-only proofs, semantic proposals, manifest and independent delivery receipts.

## 2026-11-24 independent device sample checkpoint

`device_readback.py` now accepts original JSON bytes from a caller-supplied instrument reader on each Native frame. It requires exact frame identity, unique sample IDs, boolean siren/lamp states and a fixed independent instrument citation. It rejects command fields as readback and seals 900 source samples in `device_samples.jsonl` with a SHA-256 reference in the original capture receipt. `native_capture.py` uses this adapter when supplied. `saved_finalizer.py` and the independent `warning_audit.py` reopen and hash the sample file, then join each observation to its device trace frame, state and citation. CPU tests reject stale frames, reused IDs, command fields, changed source citations, incomplete samples and a rehashed state mismatch. These checks establish a verifiable original-source join; an actual instrument backend and evidence of its physical independence still require local integration. They do not establish 500-foot audibility, pedestrian hearing, warning purpose or legal compliance.

The exact seven per-case canonical bundles, semantic proposals, manifest and offline/compatibility/saved-only/delivery receipts remain worker-owned CPU work. The reviewed map-specific site and real device instrument are physical integration inputs. This assignment remains partial until its strict delivery gate passes.

## 2026-11-23 seven-case diagnostic bundle checkpoint

`build_offline_draft.py` binds all seven exact case IDs to a source-hashed embedded plan, event and siren/lamp command choices, 20-Hz/900-frame four-camera profile, existing original-source capture, source-finalization, pixel and comparison modules. The bundled runner validates case identity and approach geometry, then refuses an unsourced Native launch. These constructions are diagnostic drafts, not canonical delivery manifests. All seven pinned `runtime.py offline` commands passed, with generated materializations under `.runtime-work/`. The 36-test focused suite and pinned preflight passed.

Proof SHA-256 (all logs within this assignment):

- `cpu-tests.log`: `be4b0c7708c97ec63386d0977a39089843ccc410c07c801f1f1ad317d70473e7` (exit 0)
- `cpu-preflight-bundles.log`: `84b60b9df8f0a38248264dd32c7f667e514145f7c804793a41ba2c974d80d608` (exit 0)
- `cpu-static-check.log`: `32e62cb6e91814924f616a183d2853a36a45e94373b9a42a674a6c5529226c0d` (exit 0)
- `cpu-strict-check.log`: `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` (exit 1)
- `cpu-offline-response_siren_pedestrian.log`: `3ba9e977272ec94ff847e42a608c9023fdd1f8bc47a8797fa074e881ba20d592` (exit 0)
- `cpu-offline-response_lamps_only.log`: `c3eb4a5245593be7c84bfd7057483f08d67d41be474c26629ac8981cf0bf8007` (exit 0)
- `cpu-offline-response_silent.log`: `c98723a8debc5a87b91515bfe76d43d1fede78042ee7efdbe1bc82d508757044` (exit 0)
- `cpu-offline-pursuit_actual_siren.log`: `b3c5b37867f8a7c3887ecd473c850193001e70b0480de9beecf1d10923403268` (exit 0)
- `cpu-offline-pursuit_suspected_siren.log`: `471f96c073c9fe968e7f6143ee690220077c6bc63e8212b4a1b4854ece5d1244` (exit 0)
- `cpu-offline-unqualified_siren.log`: `433a4b2e4e0eee1c01561df714c150538468f59d5ebeb2d54b4e6a638590f8c8` (exit 0)
- `cpu-offline-unqualified_lamps_only.log`: `7a3e50f751c88bd05858ea21a95e69a612978a76099624b18c17831749845a4b` (exit 0)

Next CPU work: bind a real reviewed Native site and independent siren/lamp instrument and source documents to a production runner; author canonical proposals and execution manifest; run exact source-shaped positive/negative compatibility, saved-only processing and independent delivery/comparison checks for every selected case. Physical audibility and recipient hearing remain unverified. The scoped strict command fails on truthful `partial` status.
