# testing__C111278__LVMC-11-16-040__motor_vehicle_driver

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.16.040 — The prima facie speed limit shall be fifteen miles per hour when traversing any intersection or street or highway if during the last one hundred feet of his approach to such intersection the driver does not have a clear and unobstructed view of such intersection and of any traffic upon all of the streets or highways entering such intersection for a distance of one hundred feet along all such streets or highways, except on a through street or highway or at a traffic-controlled intersection.
Assigned branch(es): Sight-conditioned traversal with neither stated exception..
Cell: C111278 (intersection, travel, intersection_boundary); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 construction and measurement checkpoint

Exact law: LVMC 11.16.040 is a 15 mph **prima facie traversal** value conditioned on view during the last 100 feet of approach, extending 100 feet along every entering street/highway. The through-road and traffic-controlled-intersection exceptions are distinct; no approach-speed duty or legal cutoff for view was invented. Frozen evidence.json has zero accepted recordings.

`case-plan.json` now has six exact case IDs (`blocked_below`, `blocked_at`, `blocked_above`, `clear_at`, `through_blocked`, `controlled_blocked`) and four comparisons (`speed_boundary`, `sight_condition`, `through_exception`, `control_exception`); each ID is prefixed by this assignment ID. Every case retains a physical-risk assessment. The blocked variants depend on a map-reviewed west-arm occluder site and actual source rays; no fallback is claimed without tested construction and receipts.

`sight_construction.py` validates jurisdiction, qualifying street intersection, all entering arms, route distance, source-backed through/control designations and map/occluder identity before lazy CARLA spawn. Caller owns spawned actor cleanup. `sight_measurement.py` rejects incomplete/noncontiguous original frames, missing 100-foot approach endpoints, an omitted entering arm, short ray extent, absent per-frame ray provenance or missing traversal. It retains actual measured traversal speed relative to 15 mph and gives no legal conclusion. `delivery_audit.py` joins exact case, map, four source camera files and SHA256, 900 contiguous original frames, candidate receipt and measurement provenance.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` exits 0; `cpu-tests.log` SHA256 46165d8706eba4647e1a54c7dda79927816330219136a54e52e41bd3a51b1625. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passes static checkpoint. Exact strict command with `--require-delivery-ready` exits 1 at partial/missing acceptance (see `cpu-strict-check.log`).

Next CPU actions: bind a reviewed Native map and site source packet; implement case-specific CARLA runner/controller and original capture, saved finalizer, full config/construction/measurement contracts and semantic proposals; generate exact offline and positive/negative compatibility receipts and saved-only process tests for all six cases; build and independently test comparison/pixel audits; create execution manifest and queue. Then rerun exact strict assignment check. Actual CARLA visibility, motion and media quality remain subsequent GPU checks.

## 2026-11-24 original sight acquisition and saved proof checkpoint

`native_sight_capture.py` now records exactly 900 synchronized 20 Hz original Native ticks from an injected world, ego velocity reader, signed route/boundary reader and per-entering-arm ray reader. It rejects missing map/authority source packets before acquisition, tick/snapshot mismatch, frame gaps, timing drift, invalid velocity or route data, missing arm rays, absent ray provenance and reused output. It seals original frame, ray, speed and site packets, recomputes the sight/traversal measurement and always invokes the supplied brake callback after an attempted run. The caller must supply real CARLA bindings and own actor cleanup; no test fixture is physical evidence. Camera capture is explicitly pending.

`saved_sight.py` independently checks the exact saved source SHA, 900-frame receipt and per-channel seals, then recomputes the measurement and rejects a forged Native summary. It reports physical visibility, camera coverage and legal conclusion as unresolved. `tests/test_native_sight_capture.py` and `tests/test_saved_sight.py` exercise positive original acquisition plus frame-gap, missing-arm, missing-source, modified bytes, case mismatch and forged-measurement negatives.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 14 tests; `cpu-tests.log` SHA256 b3d6d25c95f064151d6d39e392d08f9324f14513cbace448199b115a0d9715cc. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca. The exact scoped command with `--require-delivery-ready` exited 1 on truthful partial/missing acceptance; `cpu-strict-check.log` SHA256 3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a.

Next CPU work: bind a reviewed municipal street intersection and real Native route/ray readers; add four-camera original capture and decode checks; author canonical per-case config/construction/semantic bundles, compatibility and saved-only process receipts, complete manifest and comparison/pixel audits. Reassess physical fallback placement only with reviewed map geometry and corresponding proof receipts. Then rerun the exact strict scoped check.

## 2026-11-24 synchronized camera checkpoint

`native_sight_capture.py` now accepts an injected original sensor reader during the same 900 world ticks as the route, speed and sight rays. It requires all four named cameras (`overview` 1920x1080; `approach`, `reference_corner`, `driver_reference` 1280x720), exact snapshot frame identity, PNG bytes and successful full image decode before sealing the per-frame source map. It writes the image paths and SHA256 values beneath the attempt, and it keeps the 900-frame map synchronized with the sight rows. A reader failure applies the supplied brake callback and cleans its temporary camera staging directory. The caller remains responsible for real CARLA sensor wiring, frame-safe queues and actor cleanup; the fake test reader is software evidence only.

`saved_sight.py` reopens the sealed camera map, joins every frame and timestamp to the original sight packet, hashes and fully decodes all 3,600 PNGs, checks the capture profile, and rejects missing or altered source images. The full positive and image-tamper test plus frame-mismatch and missing-camera negatives are in `tests/test_sight_cameras.py`. The positive case uses small compressed solid-color PNG fixtures at the required resolutions; they establish decode and join behavior, not physical visibility.

Proof: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 17 tests (66.252 seconds), `cpu-tests.log` SHA256 `6344a4dbc9aada6007932ddee9532bafacbd18eed91ec58698f4989d482b66db`. `.venv-cpu/bin/python worker_check.py --assignment testing__C111278__LVMC-11-16-040__motor_vehicle_driver --complete` passed; `cpu-static-check.log` SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`. Exact strict command with `--require-delivery-ready` remains exit 1 on the truthful partial status; `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Remaining CPU work: bind reviewed municipal map/through/control/occluder source packets; implement the real CARLA sensor adapter and case-specific runner; write all six canonical config/construction/semantic bundles, offline and positive/negative compatibility receipts, saved-only process receipts, physical lifecycle/pixel and comparison audits, and execution manifest. Preserve the six cases and four comparisons. Do not assert that camera pixels show the required approaches until actual Native review.

## 2026-11-24 CARLA sensor adapter checkpoint

`carla_camera_adapter.py` is a lazy bridge for four operator-owned CARLA RGB sensor actors. It attaches listeners, requires every original frame ID and timestamp to match the world snapshot within 1 ms, rejects absent/extra channels, frame gaps, wrong dimensions, incomplete BGRA buffers, queue overflow and sensor timeout, then losslessly encodes the original RGB pixels into the PNG bytes consumed by `native_sight_capture.capture(camera_reader=adapter.read)`. The operator calls `adapter.start()` before ticking, `adapter.stop()` in cleanup, and destroys the sensors itself. The bridge does not assert that real approach geometry is visible.

`tests/test_carla_camera_adapter.py` tests BGRA-to-PNG values and frame/time, missing-source and overflow negatives with fake sensors; the separate 900-frame test still fully decodes all 3,600 required-profile images. Complete focused suite: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111278__LVMC-11-16-040__motor_vehicle_driver/tests -v` passed 20 tests (66.054 seconds); `cpu-tests.log` SHA256 `cd286e80db7bac2581d2684e58998f7728ef3640a395a976ca269761e95ba8d1`. Scoped static check passed with log SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`. Scoped strict delivery check exited 1 at truthful partial/missing acceptance with log SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

Next CPU work: write the operator case runner that binds a reviewed site packet, route/ray readers and actual CARLA sensors; complete all six canonical bundles, semantic proposals, receipts, manifest, and independent comparison/pixel audits. The source-backed municipal map and exception designations are still unreviewed, and actual motion/video remain later physical checks.

## 2026-11-23 independent saved comparison checkpoint

`comparison_audit.py` names all four exact comparisons and reopens each selected case with `saved_sight.verify`, which validates the original source seal and fully decodes four synchronized cameras. It checks exact case identity/order, shared map/site/boundary source hashes, fixed Native approach and traversal frame windows, and the intended speed, sight, through-road or control contrast. The speed triplet must measure below, at (within 0.01 m/s measurement tolerance) and above the statute's 15 mph prima facie value. This tolerance is an engineering equality check, not a legal speed band. The receipt makes no physical visibility or legal conclusion. The audit also requires all 900 original camera frames and 3,600 decoded images per saved attempt. Synthetic mocked saved measurements exercise four positive pairs and missing inventory, changed fixed source/window, and absent speed-boundary and missing-camera negatives; full original-pixel join remains covered separately by the existing 900-frame tests.

All 24 assignment tests passed, including the full 3,600-image decode suite; pinned preflight and scoped static passed. Exact scoped strict exited 1 on truthful partial status. Five normalized log SHA256 receipts are in `result.json`. Reviewed site and real route/ray readers, canonical bundles, semantic proposals, offline/compatibility/process-saved proofs, and independent physical audit remain worker-owned CPU work.

## 2026-11-24 source-bound six-case semantic checkpoint

`build_semantic_proposals.py` binds the frozen LVMC 11.16.040 text, assignment and case plan into draft relevance, template, bindings, cases and semantic-index stages. All six exact cases preserve requested traversal speed, occluder, through-street and traffic-control values. Four controlled comparisons change only the declared variable. The template separates last-100-foot approach sight from traversal speed and retains the two independent exceptions; measured visibility, municipal authority and legal application stay unresolved. Four negative/positive semantic tests reject quote, case and comparison drift.

All 28 focused assignment tests passed, including the complete 3,600-original-image decode fixture. Pinned preflight and scoped static pass; exact scoped strict exits 1 on truthful partial. Reviewed Native site, real route/ray acquisition, six canonical bundles, exact compatibility, saved-only and delivery receipts remain CPU work.

- `cpu-semantic-build.log` SHA256 `a8a748310e0e9bd929427372bc281ad21aae569c807f0a889bdbae9d1ac397d7`; exit 0.
- `cpu-semantic-focused.log` SHA256 `7966bf11bdc1846187dcb6b3c2b05ba191280b7661d69cb555dd18b78c1b9b64`; exit 0.
- `cpu-semantic-all-tests.log` SHA256 `9ca3be370ca464dc91d37cfd36c50d9b587d05625e8761da68170149f4d96cfa`; exit 0.
- `cpu-semantic-preflight.log` SHA256 `150546123c921440b331d0b888173bc28999c62e5e9eabf4f34297cde36304df`; exit 0.
- `cpu-semantic-static.log` SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`; exit 0.
- `cpu-semantic-strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; exit 1.

## 2026-11-24 reviewed-source Native runner checkpoint

`native_case_runner.py` now gates each exact case on a reviewer-identified site packet, actual world OpenDRIVE hash, and six cited source documents for jurisdiction, road kind, entering arms, through designation, traffic control and intersection boundary. It verifies each document hash and its source claim before starting sensors or spawning the occluder. The runner invokes original 900-frame sight/camera capture and stops camera listeners and destroys its occluder on exit, including a partial sensor-start failure. Test sources are synthetic and do not establish municipal authority, a viable physical occluder or actual visibility.

Five new runner tests and the complete 33-test assignment suite pass; pinned preflight and scoped static pass. Exact scoped strict exits 1 on truthful partial status. Logs and SHA-256 values are in `result.json`. Next CPU work: reviewed municipal source packet with real route/ray readers, six canonical bundles, compatibility and saved-only/delivery receipts. Actual Native sight and pixels still require physical review.

## 2026-11-24 reviewed intersection boundary coordinate join

`native_case_runner.read_reviewed_site` now requires the independent cited boundary source document to equal `intersection_boundary_xy` in the reviewed site packet, and requires two finite numeric coordinates before sensor or occluder acquisition. The prior boundary check verified only the hash and citation, allowing a rehashed contradictory boundary value. A focused negative test changes the source coordinate and updates both hashes; the runner still rejects the contradiction. Six focused runner tests and the full 34-test assignment suite pass, as do pinned preflight and scoped static. Exact scoped strict exits 1 on truthful partial. Five SHA-bound logs are in `result.json`. Remaining CPU work is reviewed real municipal site and route/ray readers, six canonical bundles and pinned compatibility/saved delivery proofs.

## 2026-11-24 source readers and six-bundle checkpoint

Reviewed-route reader independently checks cited route geometry, original frame continuity, signed center and eight-vertex body traversal, and the 30.48 m approach. Reviewed ray reader binds every entering-arm 30.48 m corridor, original Native ray hit trace and eight-vertex actor census; saved measurement rehashes both. Blocked occluder placements require their own cited source. These are engineering sight proxies, not legal driver-visibility findings.

Full assignment suite passed 49 tests, including the 3,600-camera full-decode fixture. Scoped static check passed after six case-specific construction bundles and source-gated runner were built. The blocked_below exact offline bundle passed. Five more exact offline bundles, pinned compatibility, saved-only delivery, physical-preparation and strict gate are next CPU work. No real municipal site packet or physical Native capture has been reviewed.

- `cpu-source-readers-sealed-all-tests.log` SHA256 `41ccc31e04fc562f3e828979d7fc00df0d5ab7b96c707502de9a2e1dcb294f7a`.
- `cpu-six-bundle-static.log` SHA256 `72449632cf9a16d56c5f784f1942dfac109e8eabdff0d9004f271a08c68250ca`.

## 2026-11-24 canonical semantic, physical and offline checkpoint

Six exact C111278 construction bundles and one case-preserving bounded speed-controller fallback per case are current. Nine semantic stages validate, including six selected cases, four isolated comparisons and four explicitly incomplete source-judgment sweep plans. The incomplete sweeps preserve municipal and original Native uncertainty. All twelve current primary/fallback offline checks pass and their construction/log hashes are pinned in `execution-manifest.json`. Six synthetic physical proofs independently classify complete motion, incomplete motion and missing evidence and verify capture/owner-release ordering; no physical Native acceptance is claimed. The complete assignment suite passed 54 tests, including 3,600 full camera PNG decodes, in 84.343 seconds. The current scoped static check passed.

The exact scoped strict gate was run and still exits 1 on truthful partial/missing package acceptance. Direct execution-manifest validation reaches `Fallback lacks positive/negative compatibility receipt` after semantic, physical and offline checks. Next CPU work is to author source-hashed diagnostic fixture recipes, positive/negative primary and fallback compatibility, selected saved-only result production, acquisition mappings and independent delivery receipts. Actual reviewed municipal site sources and Native sight/motion/cameras remain unverified.

- Current scoped static log: `cpu-current-static.log`.
- Current scoped strict log: `cpu-current-strict.log`.
- Physical outcome and lifecycle receipts: `physical-<case>-proof.json`.
- Exact offline logs: `proof-offline-<case>-<candidate>.log`.
