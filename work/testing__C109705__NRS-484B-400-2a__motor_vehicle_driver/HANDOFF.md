# testing__C109705__NRS-484B-400-2a__motor_vehicle_driver

Status: partial source-bound construction draft. Four accepted recording IDs are
retained as reuse candidates pending original-source review; no new recording
is proposed by this checkpoint.

## 2026-11-23 construction checkpoint

The case plan now names all four existing accepted exact case IDs, reuses their
recording IDs as candidates for **source review**, and binds them into
`approach_lateral_position` and `imaginary_approach_lateral_position`. It does
not request duplicate capture or treat accepted membership as proof of the law.
Each comparison holds two-directional intersection geometry, left turn, camera
plan, duration and controller fixed within its pair; the measured approach
body offset is the deliberate difference. The marked versus imaginary
centerline constructions are separate comparisons. There is no numeric legal
cutoff or verdict. The frozen judgment-range file has no range for this law
and actor in full-test.

`construction.py` prepares all four case variants from a source-hashed Native
map survey: marked or imaginary centerline, approach and departure road IDs,
opposed permitted lane directions on both roads, left-turn waypoint route,
vehicle blueprint, spawn offset and a bounded waypoint controller. The 1.7 m
and 2.7 m target offsets are engineering settings. An original map survey is
required before physical dispatch; the module rejects missing or mismatched
geometry. It has not run CARLA.

`approach.py` requires original Native acquisition hashes for
`intersection-context.json`, `approach-history.jsonl` and `video_frames.jsonl`,
verifies consecutive 20 Hz frames and all four synchronized camera identities,
measures every pre-entry full-body footprint relative to the oriented centerline
and right-half road edge, and requires an observed left-turn departure. Its
source-bound comparison recomputes both sides, verifies exact near/far case
identities and fixed context, rejects source reuse and right-half departures,
and reports the measured difference without a legal cutoff. Thirteen focused CPU
tests passed with `.venv-cpu/bin/python -m unittest discover -s
work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/tests -v`;
the exact hashed log is `cpu-approach-tests.log` in result.json. Assignment
`--complete` static check passed. Exact
`.venv-cpu/bin/python worker_check.py --assignment
testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete
--require-delivery-ready` still rejects the partial package with
`Preparation acceptance failed: partial/missing packages remain`.

`accepted_source_review.py` independently verifies the frozen metadata hash
and exact law/cell/actor/case joins for all four accepted recording IDs. The
generated `accepted-source-inventory.json` has SHA256
`42ed4114ba1dc441e3061736098db6549d5ac3f376871c1e780b4793310ea574`.
It inventories the original trace, video and delivery-audit hashes and leaves
physical coverage unresolved because none of those assets is present in this
export. Tests reject stale metadata and a present but wrong original trace.

Four exact primary bundles under `cases/` now inline the source-bound approach
measurement, construction policy, runner preflight, case config and three bundle
tests each. `execution-manifest.json` seals each construction and its pinned
`runtime.py offline` receipt. All four offline commands passed without starting
simulation; the returned logs are `cpu-offline-*.log`. These checks prove only
bundle materialization and fixed case/camera/timing settings. `runner.py` still
rejects Native execution until capture and source packet binding are authored.
Each manifest entry records a concrete map geometry realization risk but has no
tested fallback yet, so it remains partial.

Next CPU work: obtain or construct a source-hashed Native map survey and exact
runner for the four planned cases; add saved-only finalization and source-bound
diagnostic recipes, offline and compatibility receipts, semantic proposals,
independent delivery audit proofs, and original-recording source review. If the
archived original trace/video confirms complete coverage, retire new capture
plans; if it does not, use the documented gap to prepare new exact captures.
The original archives are not present in this export, so physical coverage,
public highway status and legal nearest-portion judgment remain unresolved.

Exact law: NRS 484B.400(2)(a) — If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: The approach for a left turn must be made in that portion of the right half of the highway nearest the centerline thereof.
Assigned branch(es): Two-directional intersection constructed within the general intersection layout..
Cell: C109705 (intersection, left_turn, centerline); actor: motor_vehicle_driver.
Frozen accepted recordings reviewed at metadata level: 4. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. Frozen `review-context/review.json` and README were read; their case descriptions are authored settings, not measured coverage.

## 2026-11-24 independent saved-delivery source checkpoint

`saved_delivery.py:audit` reopens the exact source-hashed approach context/history/frame map and requires 900 contiguous 20Hz rows with four hash-bound original media references confined to the attempt. It recomputes the approach measurement and rejects diagnostic or unproven sources in delivery mode. It explicitly leaves full decode, pixels, physical completion and legal judgment unresolved. `tests/test_saved_delivery.py` adds positive and tamper/case/path/duration negatives; the full focused suite passes 16 tests in `cpu-saved-delivery-tests.log` (SHA256 8e04aa7d46690f74a744c02dae0a0457cee94f0443857d6c2549fdcf793529aa). Assignment static check passes in `cpu-saved-static.log`; exact strict exits 1 in `cpu-saved-strict.log` because status remains partial.

Next CPU work: bind the original Native map/camera capture and exact four-case runner, case-specific diagnostic/compatibility/process-saved proofs, canonical semantic proposals, independent decoded-media and comparison delivery audits, and tested risk-based candidate construction where the documented geometry risk applies. The original accepted trace/video/audit assets remain absent from this export; no physical coverage claim follows from metadata.

## 2026-11-23 Native adapter capture checkpoint

`native_capture.py` verifies the loaded OpenDRIVE hash and exact case against an intersection packet, then requires 900 sequential 20 Hz ego readbacks and four same-frame original PNG callbacks. It seals context, trace, frame map, and per-camera PNG archives into an attempt and recomputes the approach measurement. Its cleanup path brakes and releases actors after success or failure. The diagnostic adapter test exercises full saved-source reopening and rejects cadence drift and missing cameras. The 19 focused CPU tests pass (`cpu-native-capture-tests.log`). The exact scoped static check passes; the exact scoped strict gate rejects truthful partial status. Real CARLA capture, reviewed public-highway provenance, source media decode, semantic proposals, compatibility, process-saved, and delivery audits remain unfinished.

## 2026-11-23 semantic draft checkpoint

Draft `proposals/semantic-index.json` hashes relevance, template, bindings, all four exact cases and a judgment observable for the statute’s nearest-centerline phrase. The 1.7 m and 2.7 m targets remain construction values, not legal thresholds. Source/highway review and actual original observations remain pending. Scoped static validation passes; scoped strict remains partial.

## 2026-11-23 full original pixel decode checkpoint

`audit_original_pixels` reopens all four hash-bound PNG archives, requires exact 900-frame indexes per view, and decodes all 3,600 images with Pillow. A rebound malformed PNG fails decode. The diagnostic fixture passes all 20 focused tests while preserving physical and legal uncertainty. Scoped static passes; scoped strict rejects partial.

## 2026-11-23 source attestation guard

Native capture remains diagnostic unless both the adapter attests Native origin and the verified map binding reports a reviewed public-highway source. The current map verifier truthfully reports public-highway review false, so no diagnostic capture can be promoted by a packet boolean alone. Twenty focused tests and scoped static pass; scoped strict remains partial.

## 2026-11-23 decoded paired comparison checkpoint

`audit_comparison` reopens the exact near/far original attempts, source-bound geometry, fixed context and all 7,200 camera PNGs before reporting their signed measured lateral difference. It rejects duplicate attempts, diagnostic sources by default and changed case/centerline identity. The 21 focused tests and scoped static check pass; exact strict still rejects truthful partial status. Physical completion and legal nearest-portion judgment remain unresolved.

## 2026-11-23 embedded bundle synchronization

All four exact construction bundles now embed the current source files; their construction hashes and offline command/output receipts were refreshed. All four pinned offline checks pass in new retained attempt directories. Scoped static passes; scoped strict rejects truthful partial status.

## 2026-11-23 saved-only replay command

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/saved_delivery.py --attempt ATTEMPT --case EXACT_CASE --output .runtime-work/c109705-saved-audit.json` reopens a retained source-hashed attempt, checks the exact case and all 900 trace/camera joins, decodes every original PNG in all four cameras, and writes a JSON audit only after success. Diagnostic attempts require explicit `--allow-diagnostic`; they remain physical and legal uncertainty. The focused test exercises positive replay and verifies the default rejection leaves no output. All 21 focused tests pass in `cpu-saved-command-tests.log`; scoped static passes in `cpu-saved-command-static.log`; exact scoped strict rejects truthful partial status in `cpu-saved-command-strict.log`. The corresponding log hashes are in result.json. This command is an independent saved-only CPU audit, not the pinned runtime process-saved/compatibility receipt. Exact per-case runtime receipts, reviewed Native source, candidate construction and delivery acceptance remain unfinished CPU work.

## 2026-11-23 saved paired-comparison replay command

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/saved_delivery.py --near-attempt NEAR --far-attempt FAR --output .runtime-work/c109705-pair-audit.json` reopens both retained exact attempts, checks their source-bound fixed conditions and measured approach difference, and fully decodes all 7,200 original camera PNGs before writing the audit. Diagnostic inputs require `--allow-diagnostic`; default rejection leaves no output. The full 21-test suite passes in `cpu-comparison-command-tests.log`, and the scoped static check passes. The exact scoped strict check exits 1 because this package remains partial: pinned compatibility/process-saved and delivery receipts, tested fallback and reviewed genuine source are still CPU work.

## 2026-11-23 production camera-profile rejection

The full-pixel saved auditor now checks 1920x1080 overview and 1280x720 for all three other original views in production mode. A source-hashed 2x2 diagnostic fixture is accepted only with explicit `--allow-diagnostic`; changing its declaration to production causes the CLI to reject it without writing a receipt. All 21 focused tests pass in `cpu-production-profile-tests.log`; scoped static passes and exact strict still rejects truthful partial status. The test, static and strict logs and hashes are recorded in result.json.

## 2026-11-23 transactional original capture

Native capture now writes into a sibling staging directory and publishes the attempt only after source-bound measurement and full original PNG decoding pass. A bad camera payload or frame cadence leaves no published attempt or staging files; an existing attempt cannot be overwritten. All 23 focused tests and scoped static validation pass, including an adapter cleanup failure that leaves no published attempt. Exact scoped strict exits 1 because the assignment remains partial. Logs and hashes are in result.json. Genuine reviewed Native source, pinned compatibility/process-saved receipts, candidate fallback and delivery acceptance remain to be constructed.

## 2026-11-23 selected-requirement contracts and bundle sync

`analysis.py` reopens sealed original approach context, history and camera frame map, computes three distinct selected-requirement values (observed left-turn motion, two-directional road inventory and right-half body position), and keeps the legal nearest-portion judgment unresolved. Four exact case measurement contracts pass pinned `measurement_contract.validate`; missing original context and wrong saved case are rejected. The source code was embedded in all four construction bundles and each pinned runtime offline check exits 0. All 24 focused tests pass. The retained logs and hashes are in result.json and execution-manifest.json. Positive/negative Core/video compatibility, Native reviewed source and final delivery/comparison receipts remain unfinished; exact strict gate must still pass before ready.

Selected report validation: with `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/`, a diagnostic capture was finalized and its three outputs were accepted by pinned `measurement_contract.verify_report` against original source files. Proof: `cpu-selected-report-validation.log` (SHA256 d27940c2c8cb1eb11e51eee8f150b7812531fdbe3e50aab54b59af61c41ecec0). This is a CPU fixture; it does not establish physical realization.

Analysis CLI checkpoint: `analysis.py --attempt PATH --output PATH` now emits the selected measurement report from sealed original sources. Diagnostic positive and missing-context negative commands pass, with log `cpu-analysis-cli-validation.log` (SHA256 8716f553b606624d59f79a42417c8bfe74dc12302172d7e2d4f083be01997445). All four inline constructions were resynced and their pinned offline checks rerun; this is preparation for full case-specific runtime compatibility, not that proof.

Saved-finalizer output guard: `analysis.py` now opens a new report exclusively and rejects an existing output path before reading or writing acquisition. Diagnostic `cpu-analysis-output-guard.log` (SHA256 ddd417b576a4a612a4750a6c087912be3d7638abb3d8b56acb25a3197f9a3d07) confirms an existing source remains byte-identical. Four inline bundles were synchronized and pinned offline checks rerun after the guard change.

## 2026-11-23 canonical capture frame identities

`native_capture.py` now writes `video_frame`, `carla_frame`, and `native_frame` on each original 20 Hz synchronized camera map row, binding video index to the observed simulator frame during capture. The focused test checks all 900 joined identities. All 24 focused tests pass in `cpu-canonical-frame-identity-tests.log`; all four inline constructions were synchronized and their pinned exact offline commands pass in `cpu-canonical-frame-identity-offline-*.log`. These source identities prepare canonical saved conversion, but no Native result, case-specific compatibility, process-saved, or delivery acceptance is yet proven. Status remains partial.

Canonical frame-integrity follow-up: `approach.py` now checks all present canonical identity fields against each acquisition index and simulator frame; a rebound `video_frame` is rejected even after its declared source hash changes. The 25-test focused suite passes in `cpu-canonical-frame-integrity-tests.log`, and all four currently embedded exact bundles pass pinned `runtime.py offline` in `cpu-canonical-frame-integrity-offline-*.log`. This is an original-source consistency control, not a physical or delivery acceptance claim.

## 2026-11-23 source-bound highway review packet

`native_map.py` now accepts an explicit reviewed public-highway source only when its packet names both exact roads, the loaded OpenDRIVE SHA256 and an attempt-local source document whose bytes match the declared SHA256 and the context source reference. Missing review remains diagnostic; stale source and changed road binding reject. The CPU test uses an authored file solely to exercise this integrity path and does not establish genuine highway status. Twenty-six focused tests pass in `cpu-map-review-source-tests.log`; all four refreshed inline bundles pass pinned offline in `cpu-map-review-offline-*.log`. Source review and actual CARLA capture remain for local execution after complete CPU preparation.

## 2026-11-23 original camera timestamp binding

`native_capture.py` now requires each of the four original camera callbacks to provide a finite Native presentation time matching its CARLA tick within 1 ms, and seals those four times in `video_frames.jsonl`. The saved `approach.py` measurement rechecks every present per-camera time against the source-bound ego frame, rejecting a rehashed timestamp substitution. The focused 27-test suite passes in `cpu-camera-timestamp-tests.log`; all four refreshed exact inline bundles pass pinned `runtime.py offline` in `cpu-camera-timestamp-offline-*.log`. Scoped static exits 0 and exact scoped strict exits 1 on truthful partial status. Current log hashes are recorded in result.json. This is a source-integrity control; actual case-specific compatibility, Native realization, and delivery acceptance remain unfinished CPU work.

## 2026-11-23 original source path containment

`approach.py` now rejects symlinked or escaped original context, history, and frame-map files even if the external file bytes match the acquisition hash. A new test rebinding the context through an external symlink is rejected. All 28 focused tests pass in `cpu-original-source-symlink-tests.log`; the four exact inline bundles were refreshed and pass pinned `runtime.py offline` in `cpu-original-source-symlink-offline-*.log`. Scoped static passes and scoped strict rejects the truthful partial status. Hashes are in result.json. Case-specific positive/negative compatibility, process-saved, and complete delivery acceptance remain CPU work.

## 2026-11-24 Native saved-result projection checkpoint

`analysis.py` now writes `result.json`, a source-derived trace and four 20 Hz recording channels from sealed original approach/body/map/camera rows. It calls the pinned Native `physical_result` and `validate_result` helpers; diagnostic provenance and unverified physical completion remain explicit. A new test runs the CLI on the five-frame diagnostic fixture, checks the result and channels, and rejects a removed original context without writing a result. The full 29-test suite passes. All four exact inline constructions and proposal recording descriptions were synchronized to the same structured channel contract; their hashes and pinned offline proofs were refreshed in `execution-manifest.json`.

Four exact pinned compatibility attempts now pass selected analysis and Native result validation, then each fails at Core conversion because the current five-frame diagnostic recipe has no `capture/evidence.jsonl`. These are retained failing logs, not positive compatibility receipts. The fixture is only five frames while the selected plan requests 45 seconds/900 frames; it cannot be presented as a full-duration physical recording. Next CPU work is to author a source-hashed full diagnostic capture/trace/media recipe under `work/`, generate its files only under `.runtime-work/`, run positive and missing-source negative compatibility, then pinned saved-only processing and independent delivery/comparison audits. Genuine reviewed public-highway source and Native realization remain pending; no legal or physical acceptance is claimed. The exact scoped static gate exits 0; the exact strict gate exits 1 on truthful partial status. No frozen inputs, runtime, batch or shared files were edited; no Git command was run.

### 2026-11-23 Native map byte preservation

`native_capture.py` now saves the loaded OpenDRIVE bytes as `road.xodr` after the 900-frame capture and binds their SHA256 in `acquisition.json`. A second live map read must match the reviewed survey digest before the attempt is published; changed bytes abort the atomic capture. `cpu-native-map-preservation-tests.log` records nine passing focused tests, including the map drift rejection. This adds a source input needed by Core conversion; canonical capture evidence, recorder data, and a complete source-shaped compatibility fixture are still unfinished CPU work.

All 30 assignment tests also pass after the OpenDRIVE byte-preservation change (`cpu-native-map-preservation-all-tests.log`).

### 2026-11-23 Exact capture bundle integration

All four `cases/*/construction.json` now carry `native_map.py`, `native_capture.py`, `saved_delivery.py`, and the updated `runner.py`. `runner.run_capture` checks the frozen exact case and calls the 900-frame Native capture with an injected adapter and surveyed map packet. `cpu-native-capture-bundle-tests.log` records 31 passing focused tests; `cpu-native-capture-bundle-offline-*.log` records four passing pinned offline materializations. The inline runner CLI still needs production adapter connection and the original Core capture packet, including per-frame evidence, recorder metadata, and source-bound positive/negative compatibility. Status remains partial.

The map is read and verified before adapter cleanup, so disconnection cannot prevent source sealing. `cpu-native-capture-bundle-tests-v2.log` records 32 passing tests, including a disconnecting adapter; four `cpu-native-capture-bundle-offline-v2-*.log` checks pass.

The saved audit now verifies the sealed original OpenDRIVE hash when the source is present. A tampered map is rejected even if the body/camera rows remain unchanged. `cpu-native-capture-bundle-tests-v3.log` records 33 passing tests; four `cpu-native-capture-bundle-offline-v3-*.log` checks pass.

The final 33-test run used `TMPDIR` and the pipeline output root under `.runtime-work/c109705-map-preservation`; see `cpu-native-capture-bundle-tests-v4.log`.

### 2026-11-23 survey context sealing

`native_map.verify_live_map` now parses and hashes the same packet bytes, then returns its validated intersection context. `native_capture.capture` writes those retained bytes after the 900-frame run, so a packet edit during acquisition cannot replace the saved context. The focused mutation test changes the survey packet in `adapter.start` and confirms the original validated context is saved. All 34 focused tests and four exact pinned offline materializations pass. The execution manifest and result hashes were refreshed. Status remains partial pending reviewed Native source and complete Core capture, compatibility, processing and delivery proofs.

## 2026-11-23 diagnostic Core frame-join bridge

`core_packet.py` now projects the sealed 900-frame Native approach history and four-camera map into diagnostic `trace.jsonl`, `capture/evidence.jsonl`, and `capture/native/frames.jsonl`. It verifies source hashes and exact frame/time joins, marks speed provenance synthetic, rejects source mutation and output overwrite, and explicitly leaves physical completion and legal judgment unresolved. All 35 package tests pass in `cpu-core-join-tests.log`; the actual Core `verify_join` accepts all 900 diagnostic rows in `cpu-core-join-runtime.log`. Both log hashes are recorded in `result.json`. The scoped static check passes; the exact scoped strict gate still exits 1 for truthful partial status. Adapter graph capture, a complete Core manifest and compatibility receipt, real original Native source review, semantic and delivery audits remain CPU construction work.
