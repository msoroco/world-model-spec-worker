## 2026-11-23 additional partial proof log preservation

The original `negative-analysis.log`, `cases/short-negative-analysis.log`, and `cases/current-offline.log` are direct members of `work/_shared/small-archives-consolidated-20261123.tar.xz` (SHA256 `5b5172dfb1f4e12e6eba13e7469dca472443d04ae06f186cd00f728ae5625c90`). Restore their original paths using the shared HANDOFF index or rerun before strict readiness. C215286's scoped nonready check passes and its status remains partial.

## 2026-11-23 short fallback negative log preservation

The `cases/short-fallback1-negative.log`, `cases/short-fallback2-negative.log` and `cases/short-fallback3-negative.log` bytes are direct members of `work/_shared/small-archives-consolidated-20261123.tar.xz` (SHA256 `5b5172dfb1f4e12e6eba13e7469dca472443d04ae06f186cd00f728ae5625c90`). Restore their original paths using the shared HANDOFF index or rerun before strict readiness. C215286's scoped nonready complete check passes and its status remains partial.

## 2026-11-23 fallback negative log preservation

The `cases/over-fallback1-negative.log`, `cases/over-fallback2-negative.log` and `cases/over-fallback3-negative.log` bytes are direct members of `work/_shared/small-archives-consolidated-20261123.tar.xz` (SHA256 `5b5172dfb1f4e12e6eba13e7469dca472443d04ae06f186cd00f728ae5625c90`). Restore their original paths using the shared HANDOFF index or rerun before strict readiness. C215286's scoped nonready complete check passes and its status remains partial.

## 2026-11-23 historical proof log preservation

The byte-verified `physical-fixtures.log` and `semantic-proof.log` are now direct members of `work/_shared/small-archives-consolidated-20261123.tar.xz` (SHA256 `5b5172dfb1f4e12e6eba13e7469dca472443d04ae06f186cd00f728ae5625c90`). Restore them at their original member paths with `tar -xOf ARCHIVE MEMBER > MEMBER` or rerun both proofs before strict readiness. The scoped nonready complete check passed after archival; C215286 remains partial.

The archive named in the next section is now nested in `work/_shared/small-archives-consolidated-20261123.tar.xz` (SHA256 `5b5172dfb1f4e12e6eba13e7469dca472443d04ae06f186cd00f728ae5625c90`); extract it first with the shared HANDOFF command.

## 2026-11-23 C215286 diagnostic physical fixture archive

Six historical `*-physical-result.json` outputs from partial C215286 were byte-verified under their original member paths in `work/_shared/c215286-historical-physical-fixture-results-20261123.tar.xz` (SHA256 `94fa8403032f31b5c4c1d59b8ff659e829cc32ca48a2f856fb905ab95960a032`, 2,092 bytes) and then moved to create return capacity. Recover a member with `tar -xOf work/_shared/c215286-historical-physical-fixture-results-20261123.tar.xz MEMBER > MEMBER`. C215286's nonready scoped complete check passed after archival. Restore or rerun these physical fixture results before strict readiness; its status remains partial.

## 2026-11-23 Native saved-report delivery audit contract

`delivery_audit.py --mode native-delivery` now composes the existing sealed Native provenance, owner-release, exact-construction, reverse-body and four-camera preflight with the pinned saved measurement contract. It requires matching exact case IDs, Native result provenance, original-source hashes, the selected over/short reverse outcome, and complete setup/target/maneuver/attempt checks. Its return keeps pixel, physical and legal acceptance unresolved. Both current 900-frame synthetic attempts were rejected at `Native non-diagnostic provenance required`. With preflight explicitly mocked for an isolated saved-report contract check, the over case passed the source/measurement join and a changed `reverse_history.jsonl` report hash was rejected. Both unchanged synthetic diagnostic delivery audits passed at 900 frames. The 15-test suite, pinned CPU preflight and assignment-scoped nonready complete check passed; `cpu-tests.log` SHA256 is `dec2129c68728b6e7440b88391e843708e4e69597aec64e466d443fe314954b2`.

Status remains **partial**. Worker-owned next steps are source-reviewed real residence-district/crosswalk geometry/marking evidence and the shared ordered GPU queue. The Native audit contract still needs a real capture and owner receipt to execute; this checkpoint makes no Native, pixel, physical or legal acceptance claim. Do not mark ready before the scoped strict gate passes.

## 2026-11-23 historical unbound artifact archival

The two unbound historical over/short-delivery diagnostic JSON files were retained byte-exactly in `work/_shared/c158196-saved-command-logs-20261123.json` (SHA256 `1c49cff1ce19b5aea3738d5e0dc5cde0482e092503cac019de4f9afcfdd40237`) to free return-file slots. Original paths, SHA256 values, and base64 bytes are preserved. The assignment-scoped nonready complete check passed after archival. Status remains partial.

## 2026-11-23 current-runtime reverse completion checkpoint

The short-of-crosswalk primary and fallback1/2/3 embedded configurations now target x=14 m. The previous x=10 m goal was unreachable without body contact with the sourced crosswalk in the short fixture: a nonintersecting body center must be greater than x=13 m, while the pinned reverse-goal tolerance for x=10 m required a center at or below x=13 m. `tests/test_reverse.py::test_short_constructions_bind_a_reachable_goal_before_crosswalk` checks each exact embedded config against the pinned physical assessor. Four short and four over exact offline runs passed in `cases/current-offline.log`; current `.adapter.json` graph diagnostics and frame-map `adapter_graph` bindings replace stale pickle-era diagnostic paths. Eight positive/negative compatibility and eight recorded-only saved runs passed and are rebound in `execution-manifest.json`. `prove_physical.py` generates six three-outcome synthetic results, `physical-fixtures.log`, and two source-hashed physical-preparation receipts; the pinned physical validator passed both cases. The execution-manifest and primary compatibility validators passed. The 14-test CPU suite passed in `cpu-tests.log`.

The assignment remains **partial**. Next CPU work: review real residence-district, marked-crosswalk and crosswalk geometry sources; author the exact semantic stage chain under `proposals/` and its `semantic-index.json`; add positive and tamper-negative independent full-duration `delivery_acceptance` audits for both selected cases; audit the over/short controlled comparison against the current original-source fixtures; add both exact cases and fallbacks to the shared ordered GPU queue; then run `.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete --require-delivery-ready`. The synthetic results do not establish Native physical completion, original camera pixels, or a legal conclusion.

# C215286 CPU handoff — NRS 484B.113(2)

Status: **partial**. Fixed cell: residence-district reverse motion at a crosswalk. This assignment covers backing on or over a crosswalk. The frozen accepted-evidence inventory is empty.

`reverse_control.py` requests actual Native reverse control, reads it back and restores prior control. `crosswalk_reverse.py` joins original frames to source-backed crosswalk polygon and complete ego body, then measures on/over and fully-over positions while reverse is active. Three CPU tests pass for positive/negative body overlap, wrong crosswalk ID, stale frame and real control restoration. Actual motion, marked geometry and camera visibility remain unverified.

Next CPU work: source exact crosswalk and residence-district road; construct positive and stop-short reverse trajectories. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual backing and visibility remain later physical checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C376646__NRS-484B-250-4__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## Backward motion and comparison checkpoint

`crosswalk_reverse.py` now computes each original complete-body center displacement projected onto the observed vehicle heading. It counts a crosswalk overlap only when displacement is backward and Native reverse readback is true at both ends of that interval. This avoids treating reverse gear alone, a stationary body or a late reverse command as proof of backing on the crosswalk. The projection sign is an engineering observation, not a numeric legal threshold.

`comparison_audit.py` independently analyzes the positive and short cases and requires the same hashed crosswalk context, starting body center, frame count and reverse-state schedule. It rejects a positive case without backward body entry or a short case whose body actually overlaps the crosswalk. The six-test CPU suite covers wrong heading, missing heading, stale frames, changed context, erroneous short-case overlap and reverse activation only at the overlap frame. These are small synthetic source fixtures; they do not establish real marked geometry or actual CARLA motion.

Current `.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v` passes six tests (`cpu-tests.log`, SHA-256 in `result.json`). Assignment `--complete` passes in `assignment-check.log`. The exact assignment strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete --require-delivery-ready` exits 1 in `strict-gate.log` with `Preparation acceptance failed: partial/missing packages remain`, because the package remains partial. Next CPU work is source-backed crosswalk/district construction and exact runner, four source cameras, saved finalizer, fallbacks, semantic proposals, recorded-only and exact compatibility proofs, and source-decoded delivery audit. These are unfinished work, not an external blocker.

## Hashed site sources for saved analysis

`site_review.py` now requires byte-hashed residence-district, crosswalk geometry and marking documents, a reviewed crosswalk polygon that intersects the selected roadway, and exact map/road/crosswalk identity. `crosswalk_reverse.analyze` requires that packet and all three original source files in the saved attempt; it rejects stale or missing documents and a polygon that differs from the retained context. The comparison audit also requires identical packet and source bytes across the positive and stop-short cases. The synthetic fixture tests stale marking, absent packet and changed marking source between cases. The source check does not determine whether a real site is legally a residence district or whether markings are actually visible.

Seven tests pass in `cpu-tests.log` with the current hash in `result.json`; assignment `--complete` passes. The strict assignment gate exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. A real reviewed site packet, integrated exact runner/four cameras, saved finalizer, fallbacks, semantic proposals, exact runtime receipts and independent delivery audit remain unfinished CPU work. No external blocker is asserted.

## Distinct constructed reverse targets

`reverse_route.validate_pair` now translates the same starting complete body along the same reverse axis to two planned distances. It requires the positive target body to intersect the sourced crosswalk and the short target body to remain clear, with both targets beyond a clear start. `ReverseTargetController` uses the selected target distance and observed body-center progress to apply Native reverse throttle or braking. It begins braking using an engineering stopping-distance estimate; actual deceleration, stopping position and crosswalk overlap remain physical checks. The construction varies the intended reverse stopping point while retaining the same approach, vehicle and crosswalk.

The eighth CPU test checks both target geometries, target completion, early braking and rejected invalid targets. Eight tests pass in `cpu-tests.log`, and `result.json` binds its current hash. Assignment `--complete` passes; strict readiness still exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. The controller is not yet integrated into a CARLA runner; a reviewed real site packet, four cameras, saved finalizer, exact proofs, fallbacks, proposals and delivery audit remain worker-owned CPU work.

`reverse_route.prepare_reviewed_pair` additionally joins the target geometry to the hashed site packet and exact Native map/road/crosswalk identity. The synthetic test exercises this joined preparation. This does not replace the absent real reviewed packet or a Native run.

## Pinned physical checker field alignment

The saved reverse analyzer now requires the same original row fields used by the pinned `worker_exchange.native_output` reverse-goal checker: `body_vertices_m`, `heading_deg` and `velocity_mps`. It rejects a body or heading that differs from the crosswalk measurement fields and a Native velocity that contradicts observed backward displacement. A ninth CPU test runs the pinned `assess_physical` reverse-goal branch on source-shaped frames, observes `setup: met` and `maneuver: met` for the synthetic route, then confirms missing velocity yields `maneuver: unverified`. This tests software field compatibility only; the synthetic body and velocity are not Native motion evidence.

Nine assignment tests pass in `cpu-tests.log` with its current hash in `result.json`; assignment `--complete` passes. Strict assignment readiness exits 1 with `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. Remaining CPU work is unchanged: reviewed real site packet, integrated exact runner/four cameras, saved finalizer, fallbacks, proposals, full runtime proofs and delivery audit.

## Integrated primary selected case checkpoint

The primary `reverse_over_crosswalk` construction now contains an executable lazy CARLA runner, four named raw camera streams, source-bound reverse history, saved finalizer, and synthetic site documents. The runner reads the Native map, road and start geometry, controls actual reverse, preserves original frame/video joins and seals restoration; its `--check` path needs no simulator. The site documents in this construction are explicitly diagnostic, so the residence-district and marked-crosswalk claims still need independent real-source review.

Twelve assignment unit tests pass (`cpu-tests.log`; SHA-256 in `result.json`). Exact `runtime.py offline` passes at `.runtime-work/c215286-primary-offline-v3` (`exact-offline.log`). Exact positive/negative `runtime.py compatibility` passes at `.runtime-work/c215286-primary-compat-v6` (`compatibility.log`, `primary-compatibility-receipt.json`), including original-source finalization, source camera decode, Native result validation, graph conversion, pinned Lean decoder and render. Deleting `reverse_history.jsonl` fails with the specified missing-source error. Exact recorded-only `runtime.py process-saved` passes at `.runtime-work/c215286-primary-saved-v1` (`process-saved.log`, `processing-receipt.json`), rebuilding from retained sources. These are synthetic software proofs, not Native trajectory, legal-site or visibility acceptance.

`execution-manifest.json` binds the current construction, commands and copied receipts. Assignment-scoped `worker_check.py --complete` passes (`assignment-check.log`). Scoped strict readiness exits 1 with `Preparation acceptance failed: partial/missing packages remain` (`strict-gate.log`) because `result.json` correctly remains partial. Remaining CPU work: replace the synthetic site packet with reviewed real district, crosswalk geometry and visible-marking sources; build the stop-short selected case and fixed-source comparison; add and test three distinct physical-risk fallbacks per case; complete semantic, physical-preparation and independent full-duration delivery audits; rerun exact proofs after any construction/finalizer change. Actual Native run and camera visibility remain later physical checks.

Pinned `worker_exchange.package_compatibility.check_receipts` passes against the current copied primary receipt, diagnostic fixture, selected measurement report, missing-source log, and acquisition map. The four camera videos and Native graphs in that recipe are synthetic; the software receipt does not prove physical capture.

## Stop-short selected case and matched-source comparison

`cases/reverse_stops_before_crosswalk-construction.json` selects the same runner, vehicle, site packet, source cameras and 45-second capture, changing the authored reverse target from 6.0 m to 2.0 m. The stop-short synthetic diagnostic starts with the same complete body and reverse schedule as the over-crosswalk diagnostic, then backs 2.5 m while retaining a clear complete body. This fixture is a software check; actual Native stopping distance is unresolved.

The stop-short case passes exact `runtime.py offline` at `.runtime-work/c215286-short-offline-v1` (`cases/short-offline.log`), positive/negative `runtime.py compatibility` at `.runtime-work/c215286-short-compat-v1` (receipt and negative log under `cases/`), and recorded-only `runtime.py process-saved` at `.runtime-work/c215286-short-saved-v1` (receipt under `cases/`). The pinned `package_compatibility.check_receipts` passes for both selected cases with current construction hashes, diagnostic recipes, source measurements, negative missing-source logs and acquisition maps.

`comparison_audit.audit` passes against both retained compatibility attempts and writes `cases/comparison-receipt.json`: nine paired original frames, identical hashed crosswalk context and site documents, identical starting complete body and reverse-state schedule; backward body motion enters the crosswalk only in the over-crosswalk case. The audit rejects changed site or a short-case overlap in its unit test. This comparison is diagnostic, with physical and legal acceptance explicitly unresolved.

Twelve tests pass (`cpu-tests.log`; current SHA-256 in `result.json`). Remaining CPU work is reviewed real district/crosswalk/marking sources, three distinct risk-triggered fallbacks per selected case and their exact proofs, semantic chain, physical-preparation proof and independent full-duration delivery audit. Retain partial status until these and the scoped strict gate pass.

## First distinct physical-risk fallback

`cases/reverse_over_fallback1-construction.json` keeps the same over-crosswalk case, source packet identity, camera plan, measurement procedure and 45-second capture. If the primary Native attempt's original complete body stops clear of the sourced crosswalk before the attempt ends, this fallback lengthens only `site_packet.target_distances_m.over` from 6.0 to 7.0 m. It is an engineering control response to a measured shortfall, with actual deceleration and body entry still unresolved until Native capture.

Exact `runtime.py offline --candidate fallback1` passes at `.runtime-work/c215286-over-fallback1-offline-v1`; positive/negative `runtime.py compatibility --candidate fallback1` passes at `.runtime-work/c215286-over-fallback1-compat-v1`; recorded-only `runtime.py process-saved` passes at `.runtime-work/c215286-over-fallback1-saved-v1`. Logs and copied compatibility/saved receipts are in `cases/` and bound in `execution-manifest.json`. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=2)` passes for this selected case. The fallback diagnostic reuses synthetic source observations to test software compatibility; it does not prove that a Native vehicle reaches the longer target.

Five distinct risk-triggered fallbacks remain across the two selected cases, followed by exact proofs and independent delivery audit. Real reviewed site sources, semantic and physical-preparation checks also remain. The assignment stays partial.

## Complete over-crosswalk fallback set

`fallback2` selects the alternate `vehicle.tesla.model3` blueprint if the primary `vehicle.audi.tt` subject cannot spawn. It fixes the starting pose, route, crosswalk source and four-camera contract. `fallback3` raises the overview camera from 35 to 42 m above the site start and moves the reference-corner camera from `(8,8,8)` to `(12,12,12)` m relative to the crosswalk when the original complete body or markings are clipped; the selected case, route, source packet and recording observations remain fixed. Both triggers require original Native status or source video before selection. No fallback is considered physically successful from synthetic media.

Each new fallback passes exact `runtime.py offline`, positive/negative `runtime.py compatibility`, and recorded-only `runtime.py process-saved` in its `.runtime-work/c215286-over-fallback{2,3}-*` attempt. `cases/` contains the current command logs, negative missing-source logs, copied compatibility and saved receipts; `execution-manifest.json` binds construction and receipt hashes. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=4)` passes for the over-crosswalk case, confirming three distinct bounded alternatives with measured triggers and current proofs.

The stop-short selected case still needs three distinct physical-risk fallbacks. Reviewed real site sources, semantic chain, physical-preparation proof and independent full-duration delivery audit also remain. Keep `result.json` partial.

## Complete stop-short fallback set

`fallback1` shortens the authored stop target from 2.0 to 1.0 m if original complete-body history shows the primary stop reaches or crosses the sourced crosswalk. `fallback2` selects `vehicle.tesla.model3` when the primary vehicle blueprint cannot spawn. `fallback3` raises and moves the overview/reference-corner source cameras if their original images clip the settled complete body or crosswalk boundary. Each alternative retains the exact stop-short case identity, 45-second/20 Hz recording description, site/crosswalk identity and law observations. Their triggers require Native status, original body history or source pixels; synthetic media cannot establish that a fallback is physically needed or successful.

Each stop-short fallback passes exact `runtime.py offline`, positive/negative `runtime.py compatibility` and recorded-only `runtime.py process-saved` under `.runtime-work/c215286-short-fallback{1,2,3}-*`. `cases/` holds the command and missing-source logs plus copied compatibility/saved receipts, and `execution-manifest.json` binds their current construction and receipt hashes. Pinned `candidate_constructions.validate(..., required=True, require_alternate=True, candidate_count=4)` passes for **both** selected cases; pinned `package_compatibility.check_receipts` passes for both primary cases. All eight constructions now have the exact synthetic CPU paths.

Remaining CPU readiness work is independent reviewed real residence-district/crosswalk geometry/marking sources, semantic chain, physical-preparation proof and independent full-duration delivery audit. Then rerun affected exact commands and strict gates. No physical or legal acceptance is claimed from diagnostics; result stays partial.
# 2026-11-20 return-file maintenance

Seven zero-byte command logs referenced by this partial package's execution manifest were rebound to its existing zero-byte `compatibility.log`, preserving the exact empty-file SHA-256. The duplicate files were removed to recover seven work-tree file slots for C378304 construction. The C215286 assignment static check still passes. Status remains partial; this maintenance is not a new compatibility or readiness proof. No frozen input, runtime, batch.json or Git action was taken.


## 2026-11-22 19:45 UTC reversible file-cap staging

Thirteen small historical proof logs were moved byte-for-byte into `work/_shared/archived-unbound-negative-logs-20261119.json` while C215286 remains partial, to make room for C149752 materialized implementation. For each archived row, base64-decode `content_zlib_base64`, zlib-decompress, verify `sha256`, then write exact bytes to `path` before rebinding or reusing its receipt. Current C215286 receipts referencing these paths are historical and must not be claimed current until logs are restored and proofs rerun.

## 2026-11-22 pinned physical outcome probe and exact primary offline repair

With `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c215286-physical-test` and `PYTHONDONTWRITEBYTECODE=1`, the existing assignment unittest command exited 0 with 13 tests. The new test drives pinned `worker_exchange.native_output.assess_physical` for both exact reverse targets against source-shaped synthetic original frame/body/velocity histories. Each case yields `met` for its authored complete route, `not_met` for contradictory signed velocity, and `unverified` when the original reverse history is absent. It checks the result boolean, realized observables and source/missing-source binding. This is checker branch coverage only, not a Native motion claim. The current combined test/offline `cpu-tests.log` SHA256 is `5958dd229a0eccf3f6e47ee0f52534d685a536eff1bbdb2ed1473614d26a40e4`; `result.json` binds it.

A direct current `execution_manifest.validate` initially failed because historical `exact-offline.log` had been archived. Fresh exact `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case <exact-case-id> --output .runtime-work/c215286-offline-current/<case-suffix>` passed for each of the two selected primary cases, with `offline_passed: true` and `simulation_started: false`. Their exact command/stdout is appended to the existing `cpu-tests.log`, and manifest offline bindings now use the current construction hashes and that log. No returned files were added. The direct validator now advances to `Missing physical preparation proof for case: ...__reverse_over_crosswalk`. The next CPU step is the per-case returned synthetic fixture results, lifecycle log and hashed physical receipt, followed by candidate receipt restoration/rechecks, semantic and independent delivery audits. The assignment stays partial; reviewed district/marking authority, actual camera pixels, Native outcome and legal judgment remain unverified.

## 2026-11-23 saved receipt and physical fixture refresh

The over-crosswalk primary saved-processing manifest binding now names the existing `processing-receipt.json` for both receipt and log; its previous `process-saved.log` binding had the receipt hash rather than that log's bytes. The superseded log is preserved byte-exact in `work/_shared/c125745-stale-axis-diagnostics-2026-11-23.json`, with its original path and SHA-256. `prove_physical.py` now verifies each current recorded-only saved-processing receipt and its `saved_processing_started` event before emitting synthetic physical outcome receipts. The fixture log expressly identifies the six-event lifecycle order as a CPU contract assertion, without claiming observed Native capture or ownership release. Both direct physical-preparation validators, the direct execution-manifest validator, and assignment-scoped nonready complete check pass. The package remains partial: source-reviewed district/crosswalk/marking identity, canonical semantic stages, and independent full-duration delivery acceptance are unfinished.

## 2026-11-23 independent diagnostic delivery source audit

Added `delivery_source_audit.py` and ran it against the two exact current primary compatibility attempts: `.runtime-work/c215286-current-over-compat/primary` and `.runtime-work/c215286-corrected-short-compat-v4/primary`. It checks the bound construction and compatibility receipt, synthetic provenance, original source hashes, 20 Hz frame/time/reverse-body joins, source crosswalk identity, four named camera decodes at planned dimensions, capture evidence hash, and each case's measured crosswalk overlap. Both positive audits exited 0. In isolated source-tree negatives, each rejected a changed `district.txt` with `Original source changed: district.txt`. The exact commands, exit codes, receipt hashes and negatives are in `delivery-diagnostic-proof.log` (SHA-256 `2e7794e8b37b3e571113ff7287e24fc12870b0d07e951b63312447dd945c9a73`). Returned diagnostic receipts are `cases/over-delivery-diagnostic.json` (SHA-256 `569793ac95691ba67d75acea8bfe9f3a03ddefa4c674449f4cff889d965b8248`) and `cases/short-delivery-diagnostic.json` (SHA-256 `50955946d2ee797a159ef0d3a9b3a0932197b8c473203b6c4bb8515e334f9688`). They explicitly report 9 observed versus 900 planned frames, no real site review or actual-pixel review, and `delivery_ready=false`. Pinned CPU preflight and assignment-scoped nonready checker pass. The next CPU actions are to author source-reviewed district/crosswalk/marking evidence, full-duration synthetic source diagnostics with independent delivery and comparison checks, and the canonical semantic stage chain; status stays partial.

## 2026-11-23 canonical semantic stage construction

Authored the complete five-stage CPU semantic proposal chain under `proposals/`: exact-law relevance, a plain prohibition template, direct cell binding, a neutral unselected baseline and the existing paired over-versus-before-crosswalk selected cases. The template preserves the law's intersection, crosswalk and street-corner wording; the selected cell's concrete comparison isolates its crosswalk alternative. Existing selected IDs and recording descriptions remain identical to those in their constructions. Direct pinned `worker_exchange.semantic_delivery.validate` exited 0 with `stage_count=5`, `selected_cases=2`, semantic-index SHA-256 `d36d825fca2aae369e3a25d060cf1f70c7ac813c968d53129a436755f7a8f14e`. Its returned command output is `semantic-proof.log` SHA-256 `0663debed8bbcf3f622f19a0ddce8f93375a695076edd4b0cf0a9750a7016fb0`, bound in `result.json`. The current exact over/short compatibility attempts also reran through the independent `comparison_audit.audit` and produced the same existing 9-frame diagnostic comparison receipt. Pinned CPU preflight and assignment-scoped nonready check pass. C215286 remains partial because the reviewed real district/crosswalk/marking sources and full-duration independent delivery audit are unfinished; no Native, physical or legal acceptance is claimed.

## 2026-11-23 full-duration synthetic reverse pair

Generated a 900-frame, 20 Hz source fixture for each selected case in ignored `.runtime-work/c215286-full-stage/`. The pinned `runtime.py compatibility` path passed positive and missing-source negative checks, Core conversion, render, and final decode for both. Each result's pinned physical checker reports setup, target, maneuver and attempt `met` for this authored synthetic trajectory. Independent `delivery_source_audit.py` passed on both 900-frame attempts, and `comparison_audit.audit` passed their controlled pair at 900 frames. Altered district sources, over-case frame map and comparison crosswalk identity were rejected. Exact hashes, commands and outcomes are in `delivery-diagnostic-proof.log`; returned `cases/over-delivery-diagnostic.json` and `cases/short-delivery-diagnostic.json` now contain the full-duration diagnostic receipts. The earlier nine-frame diagnostic hashes in this handoff are historical. These CPU fixture outcomes explicitly have `delivery_ready=false` and do not establish real district/marking sources, Native motion, actual camera pixels, physical acceptance or a legal conclusion. The assignment remains partial pending reviewed source construction, canonical delivery-acceptance binding, and shared queue integration.

The following builder is preserved here because the returned file count is at the 8,600-file cap; run it from the repository root as `.venv-cpu/bin/python .runtime-work/build_c215286_full_fixture.py over` and `... short` after extracting the block to that ignored path. It stages copies of this assignment and changes only the staged diagnostic recipes.

```python
import copy, hashlib, json, shutil, sys
from pathlib import Path
repo=Path.cwd()
aid='testing__C215286__NRS-484B-113-2__motor_vehicle_driver'
stage=repo/'.runtime-work/c215286-full-stage'
folder=stage/'work'/aid
folder.parent.mkdir(parents=True,exist_ok=True)
if not folder.exists(): shutil.copytree(repo/'work'/aid,folder)
(stage/'.runtime-work').mkdir(exist_ok=True)
kind=sys.argv[1] if len(sys.argv)>1 else 'over'
relative='diagnostic.json' if kind=='over' else 'cases/reverse_stops_before_crosswalk-diagnostic.json'
recipe_relative='diagnostic-recipe.json' if kind=='over' else 'cases/reverse_stops_before_crosswalk-recipe.json'
src=json.loads((repo/'work'/aid/relative).read_text())
files=src['files']
rows=lambda name:[json.loads(s) for s in files[name].splitlines() if s.strip()]
write=lambda name,items:files.__setitem__(name,''.join(json.dumps(item,separators=(',',':'))+'\n' for item in items))
base={name:rows(name) for name in ['reverse_history.jsonl','video_frames.jsonl','trace.jsonl','capture/evidence.jsonl','capture/native/frames.jsonl']}
for name,items in base.items():
 for i in range(len(items),900):
  row=copy.deepcopy(items[-1]); fid=100+i; t=round((i+1)/20,9)
  if name=='reverse_history.jsonl': row.update(frame=fid,time_s=t,velocity_mps=[0,0])
  elif name=='video_frames.jsonl': row.update(video_frame=i,carla_frame=fid,native_frame=fid,time_s=t)
  elif name=='trace.jsonl': row.update(frame=fid,time_s=t,speed_mps=0,velocity_mps=[0,0,0],speed_mph=0)
  elif name=='capture/evidence.jsonl':
   row.update(original_frame=fid,replay_frame=fid,recording_time_s=t,replay_simulation_time_s=t)
   row['ego']['speed_mps']=0
   obs=row['original_observations'];obs.update(frame=fid,time_s=t)
   obs['participants'][0].update(speed_mps=0,velocity_mps=[0,0,0])
  else:
   path=f'{fid:08d}.adapter.json';row.update(frame=fid,simulation_time=t,base=f'graphs/base/{path}',abstract=f'graphs/abstract/{path}',adapter_graph=f'graphs/base/{path}')
  items.append(row)
 write(name,items)
orig=src['graphs'][-2:]
for i in range(9,900):
 fid=100+i;t=round((i+1)/20,9)
 for graph in orig:
  g=copy.deepcopy(graph);kind='base' if '/base/' in graph['path'] else 'abstract'
  g['path']=f'capture/native/graphs/{kind}/{fid:08d}.adapter.json'
  g['attributes'].update(frame=fid,simulation_time_s=t)
  obs=g['attributes']['observed_evidence'];obs.update(frame=fid,time_s=t)
  obs['participants'][0].update(speed_mps=0,velocity_mps=[0,0,0])
  src['graphs'].append(g)
for video in src['videos']:video['frames']=900
manifest=json.loads(files['capture/manifest.json']);manifest['frames']=900
manifest['sources']['trace.jsonl']=hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
spec=folder/relative;spec.write_text(json.dumps(src,separators=(',',':'))+'\n')
h=hashlib.sha256(spec.read_bytes()).hexdigest()
recipe=json.loads((folder/recipe_relative).read_text())
recipe['sources'][0]['sha256']=h;recipe['generator']['sha256']=h
(folder/recipe_relative).write_text(json.dumps(recipe,indent=2)+'\n')
print(json.dumps({'stage':str(stage),'spec_sha256':h,'spec_bytes':spec.stat().st_size,'graphs':len(src['graphs']),'frames':len(base['trace.jsonl'])}))
```

### Archived diagnostic transcript before file-cap reuse

The exact nine-frame and full-duration diagnostic transcript formerly in `delivery-diagnostic-proof.log` is retained below; that path is reused for the canonical CPU delivery audit implementation.

```text
COMMAND /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.venv-cpu/bin/python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/delivery_source_audit.py --attempt /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.runtime-work/c215286-current-over-compat/primary --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_over_crosswalk --output /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/over-delivery-diagnostic.json
EXIT 0
{"case_id": "testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_over_crosswalk", "frames": 9, "software_checks_passed": true}

RECEIPT work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/over-delivery-diagnostic.json
SHA256 569793ac95691ba67d75acea8bfe9f3a03ddefa4c674449f4cff889d965b8248
NEGATIVE over: Original source changed: district.txt
COMMAND /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.venv-cpu/bin/python /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/delivery_source_audit.py --attempt /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/.runtime-work/c215286-corrected-short-compat-v4/primary --case testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_stops_before_crosswalk --output /scratch/fsw/portfolios/av/projects/av_alpamayo_reasoning/users/wcong/scenario-worker-demo/work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/short-delivery-diagnostic.json
EXIT 0
{"case_id": "testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_stops_before_crosswalk", "frames": 9, "software_checks_passed": true}

RECEIPT work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/short-delivery-diagnostic.json
SHA256 50955946d2ee797a159ef0d3a9b3a0932197b8c473203a6c4bb8515e334f9688
NEGATIVE short: Original source changed: district.txt

FULL-DURATION SYNTHETIC CPU CHECKPOINT 2026-11-23
over: 900 original frames at 20 Hz; setup/target/maneuver/attempt statuses {"attempt": "met", "maneuver": "met", "setup": "met", "target": "met"}
over compatibility.json sha256 5e82af8be1d2d4950d2968a7e12f7b328c97ec0c52aad8fa5c5fb502236778ca
over result.json sha256 f6b9f5a5b826d8fd8ddaca18b57cd3daa221edfd432603cb5f84fcf66ef9727c
over delivery diagnostic work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/over-delivery-diagnostic.json sha256 1fc8b79d980156ae0f97cb6f628570e6dd290f9434ad58be7d1b893a30a5c8de; delivery_ready=false
short: 900 original frames at 20 Hz; setup/target/maneuver/attempt statuses {"attempt": "met", "maneuver": "met", "setup": "met", "target": "met"}
short compatibility.json sha256 9cce89dbc453c83bd5406567f09425423514a6b4d1b300fc874ad208260fa996
short result.json sha256 09f6035556627ec8cb8350cd60e518fa1c5149768f8146dea684b16d65d1d0f1
short delivery diagnostic work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/cases/short-delivery-diagnostic.json sha256 44791d55265b583ab96e9535dd117df20f37145ec3517880928cc984596ae8a4; delivery_ready=false
full comparison receipt sha256 715431827b9d2de416b780b8474c92748025894d248870c2ab8d956e7d540f65; frame_count=900, physical_acceptance=unresolved
over changed district: rejected Original source changed: district.txt
over changed frame map: rejected Original source changed: video_frames.jsonl
short changed district: rejected Original source changed: district.txt
comparison changed crosswalk identity: rejected Site packet road/crosswalk identity differs
Staged 900-frame specifications: over sha256 9b2e49a4d0d9c6824283844df899d4d345da851a41e7fffc00323ac55cb2f2e4; short sha256 fea41b84c529c69bdf40392eac5ab3ffd11aeaa27bf13a82c3158bc5acec2e95
Commands: .venv-cpu/bin/python .runtime-work/build_c215286_full_fixture.py over|short (builder source embedded in HANDOFF.md); runtime.py compatibility --manifest .runtime-work/c215286-full-stage/work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/execution-manifest.json --case <exact-case> --output .runtime-work/c215286-full-stage/.runtime-work/<kind>-primary --library runtime/library --validator .runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck
```

## 2026-11-23 exact-case delivery acceptance CPU boundary

Added `delivery_audit.py` as an independent 900-frame source, measurement-contract and four-camera decode boundary. It rejects shorter source histories and uses `delivery_source_audit.py` to reject changed original source hashes. Each selected case passed its positive CPU audit; a hardlink-isolated changed original frame map was rejected with `Original source changed: video_frames.jsonl` (exit 1) for both. The exact four-run transcript is appended to `cpu-tests.log` (SHA-256 `fe89af39d69c029c8c562cc54e1aadf3d729c061df6497fa4810d3d47f3bae23`), and both `delivery_acceptance` entries bind script SHA-256 `25a0b366c865151265e756eff1d8cf3ee95d6fbdaee00ec8e564b4da63b3edb1`, the demo-test target, required independent checks and that log. Direct pinned `delivery_handoff.validate_case` passed for both, and `execution_manifest.validate` passed for the assignment. This remains a software diagnostic boundary: `native_source_accepted=false`, `actual_pixels_reviewed=false`, `physical_acceptance_claimed=false`. Real-site review, local Native auditor integration and shared queue work remain. The package status is partial.

## 2026-11-23 four-camera decoded-frame CPU proof

The independent 900-frame source auditor now decodes each of the four source videos through ffmpeg `framemd5`, requires exactly 900 decoded frame records, and records a SHA-256 of each camera's decoded frame record stream. `delivery_audit.py` returns those four fingerprints for each selected case. The source file SHA-256, dimensions and original-frame joins remain checked. Both exact reverse cases passed positive audits and both rejected a changed original frame map with `Original source changed: video_frames.jsonl`. The four current command transcripts and the 14-test suite are in `cpu-tests.log` (SHA-256 `02caa628621fe98bb6f671dc0d80f24024720fdd3e6b2228eb1b12f0c8d30f23`). Exact per-case camera fingerprints and output receipts are in `case-plan.json.decoded_frame_cpu_audit`; `execution-manifest.json` binds current audit script and log hashes. Both delivery contracts, the pinned execution-manifest validator and the assignment-scoped `--complete` check pass.

C215286 remains **partial**. These are decoded synthetic frames, with no reviewed actual camera pixels or Native source acceptance. The next worker-owned CPU tasks are reviewed real district/crosswalk/marking source construction, local Native auditor integration and the shared ordered GPU queue. Do not mark ready until those are complete and the assignment-scoped strict delivery gate passes.

Pinned `.venv-cpu/bin/python runtime.py preflight` passed with `cpu_preflight_passed=true` and `simulation_started=false`.

## 2026-11-23 Native source preflight integration

`delivery_audit.py --mode native-preflight` now checks exact primary or manifest-selected fallback construction, non-diagnostic Native provenance, a 900-frame capture seal with the required original sources and source digest, Native revision, pinned Native exit and operator-release closure, 900 joined original reverse-body measurements with the selected case outcome, and complete decoded-frame fingerprints for all four cameras. Each case has an exact command in `execution-manifest.json.native_handoff`; the operator must supply `NATIVE_ATTEMPT` and `OWNER_RELEASE_RECEIPT` after local capture and release. The command returns source preflight evidence only and explicitly leaves actual-pixel review, physical acceptance and legal conclusion unresolved.

Both exact synthetic 900-frame delivery positives passed again; both original-frame-map tamper negatives and both Native preflight attempts on synthetic captures were rejected. The 15-test package suite passed. The current transcript is in `cpu-tests.log` (SHA-256 `475f9c1c49fc4c2b86f1c82898999c033d643f5fc14eb2bace1d3a4fdfa70cb0`); `case-plan.json.native_closure_cpu_preflight` and the execution manifest bind script SHA-256 `df4ba56f345f9ca91c4b9485e20784780f904aa4c987fc137e0254a908d2d5c2`. Both pinned delivery contracts, the pinned execution-manifest validator, `runtime.py preflight` and the assignment-scoped `worker_check.py --complete` pass. No Native capture was run.

C215286 remains **partial**. Worker-owned remaining CPU work is reviewed real residence-district/crosswalk geometry/marking source construction, a complete Native delivery audit contract beyond source preflight, and shared ordered GPU queue integration. The assignment-scoped strict ready gate has not passed.

## 2026-11-23 current exact delivery proof and root construction

The first GPU handoff command now selects `reverse_over_crosswalk` through canonical `execute-delivery` with exact job, database, run, CARLA Python, host and port arguments. Both exact delivery-acceptance rows now target the frozen `demo-test` and `full-test` sets. Replayed positive and changed-original `video_frames.jsonl` negative delivery audits for both cases: positives exited 0 and negatives exited 1 with the declared rejection. A combined 15-test and four-command transcript is `cpu-tests.log` SHA256 `2c462d68434bc875bb86de5f49be9847e2fe770723649a65d3dad900a2033fe9`; current delivery script and log hashes are rebound in `execution-manifest.json` SHA256 `8d29b9a2953f921c373ab221b9be79182bc732d7700e5bad1062677584b087e3`. All five missing root construction files were materialized byte-for-byte, and `case-plan.json` now binds the exact 45-second four-camera profile. Fifteen CPU tests, pinned preflight and scoped nonready complete check pass.

A guarded ready-status scoped gate advanced past manifest, semantic, delivery, compatibility, root construction and camera-plan checks, then found the source-observation mapping absent. The mapping now records every frozen term and explicitly labels the intersection and around-corner alternatives pending; the scoped nonready check passes. C215286 remains **partial** because selected cases do not yet measure intersection occupation or a heading change around a corner. Actual Native source and pixel review also remain outstanding. No physical or legal acceptance is claimed.

## 2026-11-24 intersection and corner measurement construction

The frozen NRS 484B.113(2) text names backing into an intersection, on or over a crosswalk, and around a street corner. The existing two selected cases cover only the crosswalk alternative. New `reverse_alternatives.py` measures original 20 Hz frame-joined complete-body overlap with a sourced intersection or corner region, observed backward displacement against the prior Native heading, and continuous heading change while reversing in the corner region. It requires the Native map, geometry and camera source references, and a road-topology source for the corner. The module leaves street-corner status and legal conclusion unresolved pending original site/camera review. Two new tests exercise intersection entry, rejection of forward-only travel, corner heading change and stale frame joining. The full package test suite passes 18 tests with `PYTHONPATH` set to this package; `result.json` binds the updated log.

This is a concrete measurement component, not a newly selected construction. Status remains **partial**. Next CPU work is to author exact intersection and around-corner Native routes and site packets, integrate these measurements into the finalizer, add selected cases/fallbacks/proposals and rerun all affected offline, compatibility, saved-processing, physical and independent audit proofs. The package must pass its own strict ready gate before any readiness claim.

## 2026-11-24 alternative Native route and capture checkpoint

Added `reverse_alternative_route.py` with complete-body planned sweep checks, a straight intersection entry, a continuous 90-degree corner route, and a reverse steering controller whose steering sign accounts for negative longitudinal speed. Added `reverse_alternative_capture.py`, a CARLA-lazy 900-frame capture path for `reverse_into_intersection` and `reverse_around_street_corner`: it checks exact site source hashes and Native map/start road, rechecks the spawned body's planned sweep, records original body/heading/velocity/reverse readback and four original cameras, writes `reverse_site_context.json`, and seals the source after restoration. The separate `intersection_site.json` and `street_corner_site.json` plus their text sources are explicitly synthetic TownX CPU diagnostics, not reviewed legal/map facts.

The focused route and source-tamper tests now join the full 22-test suite in `cpu-tests.log` (SHA-256 `c138505f6c91086f0695f58bfe69e79dfdfad673c43c726c7c971f0df6428134`). `worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete` passes. Status remains **partial**. Next worker-owned CPU actions: materialize exact alternative case constructions/configurations and bind them into the selected case plan and execution manifest; replace synthetic site documents with an original Native map/camera site survey and source IDs; integrate `reverse_alternatives.py` into saved finalization and independent comparison/delivery audits; add required semantic proposals, fallbacks where risk is concrete, positive/changed-source negative, compatibility, physical-prep and scoped strict proofs. The existing crosswalk cases remain intact. No Native capture or legal/physical acceptance is claimed.

## 2026-11-24 alternative exact offline bundles and saved finalizer

The two alternative cases now each have an exact inline `cases/*-alternative-construction.json` and a staging `cases/alternative-offline-manifest.json`. Both materialize with `runtime.py offline`, run the CARLA-lazy entrypoint `--check`, and pass their materialized unit test. Current exact logs are `cases/intersection-alternative-offline.log` and `cases/street_corner-alternative-offline.log`, with hashes bound in the staging manifest and `result.json`. The bundles include `reverse_alternative_finalizer.py` and `reverse_alternatives.py` for independent saved-source body/heading measurements. The analyzer verifies the original site-packet, geometry, camera and (for corner) road-topology hashes; a changed geometry source is rejected. The package suite now passes 23 tests (`cpu-tests.log` SHA-256 `0d116a1cf5013ff127841150b5ceb48366659a737bc3e6d6226316da81453e9b`). The selected crosswalk execution manifest remains unchanged. `worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete` passes.

These alternative bundles are still diagnostic drafts against synthetic TownX sources; they have no full compatibility, saved-processing, physical-preparation, semantic, independent delivery or selected-manifest proofs. Preserve partial status and continue those CPU tasks. No Native execution was performed.

## 2026-11-24 alternative positive/stop-before comparison checkpoint

Expanded the separate alternative construction set to four exact cases: `reverse_into_intersection`, `reverse_stops_before_intersection`, `reverse_around_street_corner`, and `reverse_stops_before_street_corner`. The stop-before routes keep the planned complete body outside the selected region; the corner-entry route has a continuous reverse turn. Each exact construction passes `runtime.py offline` with its current source hash and 20 Hz/45-second four-camera contract. Current logs are `cases/alternative-0-offline.log` through `cases/alternative-3-offline.log`, bound in `cases/alternative-offline-manifest.json` and `result.json`.

Added `reverse_alternative_comparison.py`, an independent 900-frame original-source comparison that fixes map, road, region, site-source hashes, starting body/vehicle, camera profile, required atoms and capture duration while varying only the reverse route outcome. The synthetic CPU receipts `cases/intersection-alternative-comparison.json` and `cases/street_corner-alternative-comparison.json` each report 900 joined frames per case, no physical/legal acceptance, and explicit diagnostic provenance. Tests reject changed fixed road identity and a corner entry with no observed heading change. The package suite now passes 27 tests (`cpu-tests.log` SHA-256 `a80303de3109c26718ec47a3e82a3f25a6b905f4fe64829b2d7b4ed033b1d8cf`). Assignment-scoped `worker_check.py --complete` passes. C215286 stays partial until all alternatives are integrated and proved.

A requested no-flags whole-batch `worker_check.py` no longer fails on binary archives: the return-tree scan found 0 non-UTF-8 files among 10,434 files. It instead stops at `ValueError: Execution manifest binds another runtime` for a retained prior-ready package; log `.runtime-work/worker-check-quick-20261124.log`. Per current `START_HERE.md` and `AGENT_PROMPT.md`, preserve retained ready packages and use assignment-scoped checks for unfinished work. The latest status count is 34 ready, 9 partial. The full strict batch gate has not passed.

## 2026-11-24 alternative corner continuity and full-duration saved proof

The original-source analyzer now distinguishes a continuous reverse turn inside the authored street-corner region from an instantaneous heading jump. It requires at least three consecutive reverse-motion frames with same-direction, bounded heading increments while the complete body overlaps the region. This is a capture-continuity guard, not a legal turn threshold. The independent comparison rejects a single-frame 45-degree jump; the positive 900-frame synthetic fixture now turns gradually while reversing. The saved finalizer requires the exact 20 Hz, 45-second, 900-frame original join before writing channels and only matches the corner target when the turn is continuous.

All four inline construction bundles and staging-manifest construction hashes were refreshed; all four `runtime.py offline` proofs passed again. The two 900-frame synthetic comparison receipts were regenerated. The 28-test package suite passed. `cpu-tests.log` SHA-256 `c1d823f0448881bdfae62d177b2bea0e231765f6d559cd4684b05e3636869967`; `cases/alternative-offline-manifest.json` SHA-256 `7cee3c4a7c70400fae719a61e36a44377c922df5d9e7da676ab1a4101f3bbd45`; `cases/street_corner-alternative-comparison.json` SHA-256 `72d81633997d997c55fae6484d04b204fbd1fae8f57715923940f2119871d47f`. The assignment-scoped nonready check passes. C215286 remains partial: real Native site source/camera review, selected-manifest/proposal integration and remaining compatibility, saved-processing, physical and delivery CPU proofs are still needed. No Native or legal acceptance is claimed.

Final checkpoint checks: pinned runtime verify and CPU preflight pass; assignment-scoped `worker_check.py --complete` passes. Assignment-scoped `--complete --require-delivery-ready` fails at the final assertion because the truthful status remains partial. Return-tree scan after removing generated Python bytecode: 10,452 files, zero non-UTF-8, oversize, trailing-whitespace or conflict-marker issues. No Git command was run.

No-flags whole-batch `worker_check.py` was run after the UTF-8 return-tree cleanup. It exited 1 at `ValueError: Execution manifest binds another runtime` in a retained prior-ready package, not at Unicode decoding. Exact log: `.runtime-work/worker-check-quick-20261124-latest.log`. Per `START_HERE.md`, retained completion migration is deferred; C215286 scoped nonready check remains passing and its status remains partial.

## 2026-11-24 staged full-branch measurement and proposal integration

Four exact intersection/street-corner measurement contracts under `cases/*-measurement-contract.json` now bind the corresponding NRS 484B.113(2) requirement to `analyze_original_reverse_region` in the saved finalizer and list the case-specific site, geometry, camera, reverse-history and frame-map sources. The pinned runtime `measurement_contract.validate` accepted all four against `cases/alternative-measurement-plan.json`; log `cases/alternative-measurement-validation.log` SHA-256 `09d7795bea35584628435eaa75c940cb31ea39addd6ed6c5d86b9c4d085ccfbc`. The finalizer now emits the named method and a case-specific missing-site error; the 28-test suite exercises that negative. All four inline bundles and staging construction hashes were refreshed, and four exact offline proofs passed again.

`cases/build_alternative_selection.py` generated `cases/alternative-selected-case-plan.json` and `cases/alternative-selected-proposals.json`, covering six exact cases, three controlled comparisons, and all three statutory alternatives. The builder checks exact plan/proposal case-set equality. Log `cases/alternative-selection.log` SHA-256 `cf8efc4ffe25ccddb1dfcd152e9a2539b55bb0b2508f94ecb39e4f087c0354ed`. These are staged artifacts, not the selected manifest; real Native site sources and exact compatibility, saved-processing, physical-preparation, delivery and queue proof remain worker-owned CPU work. The selected crosswalk package remains intact. Pinned runtime verify/preflight and assignment-scoped `worker_check.py --complete` pass; status remains partial.

## 2026-11-24 Native capture site-review guard

`reverse_alternative_capture.py` now rejects the synthetic TownX site before importing CARLA or opening a Native client. A Native capture requires `site_review_status=reviewed_native_site`, a named reviewer, a site review basis and a camera review basis in the source-hashed site packet. Offline `--check` continues to test the diagnostic route without claiming physical readiness. A new CPU test proves capture rejects the current synthetic packet before CARLA import. All 29 package tests pass (`cpu-tests.log` SHA-256 `9bb176d02b4326606fff2308ec9bf133826a018cbdb420280a020df73c19c198`), all four inline bundles were updated and four exact offline proofs pass (`cases/alternative-offline-manifest.json` SHA-256 `416f31887899c1476d179fa66816104a6f00e417a7c045d70fdd672419c73dd2`). Assignment-scoped `worker_check.py --complete` passes. C215286 stays partial; Native site review, compatibility, saved-processing, physical and delivery proofs and selected-manifest/queue integration are still unfinished CPU work.

## 2026-11-24 alternative physical source and saved finalizer proof

The four staged intersection and street-corner construction configs now bind the pinned NRS 484B.113(2) physical assessor to `reverse_site_context.json` instead of its crosswalk default. `cases/bind_alternative_physical_context.py` refreshed their construction hashes and `cases/prove_alternative_offline.py` reran all four exact offline proofs. `cases/validate_alternative_physical_context.py` exercised the actual pinned physical assessor on 900 joined synthetic frames for each exact case: setup and authored reverse goal were met, and removing the site context made setup unverified. Log: `cases/alternative-physical-context-validation.log`.

`cases/prove_alternative_finalizer.py` materialized each exact construction under `.runtime-work/`, generated 900 original synthetic motion and frame joins, ran the real saved finalizer and pinned measurement-report verifier, and checked the synthetic physical result. All four passed, including an exact missing-site negative before finalization. The four camera files in these ignored attempts are placeholders; this proof does not decode video, establish Native provenance, or satisfy compatibility/saved-processing. Log: `cases/alternative-finalizer-proof.log`. The 29-test package suite and assignment-scoped nonready complete check pass. The scoped strict gate still rejects the truthful partial status.

C215286 remains **partial**. Next CPU work is a fixture recipe with decoded camera sources, exact positive/negative compatibility and recorded-only saved-processing receipts, physical-preparation and independent delivery audits for the four alternatives, then selection of the six-case plan/manifest and GPU queue entries. Actual Native site, camera and motion review remain later physical checks. No synthetic fixture is marked Native or legally accepted.

No-flags whole-batch `worker_check.py` was retried this turn into `.runtime-work/worker-check-quick-20261124-current.log`. It produced no output after more than ten minutes and was interrupted so CPU construction could continue; this run therefore has no pass/fail result. The last completed no-flags run had passed UTF-8 inspection and then failed at a retained prior-ready execution manifest bound to the previous runtime (`.runtime-work/worker-check-quick-20261124-latest.log`). Current independent return-tree scan found 10,470 files, all UTF-8 and under their caps, with zero trailing whitespace or conflict markers. The current scoped C215286 nonready check passes; status remains partial.

## 2026-11-24 alternative site-source separation

The staged compatibility path required original site, geometry, camera and corner-topology files to come from the fixture, but the earlier inline construction carried the same paths. `reverse_alternative_capture.py` now reads bundled `site_templates/` during offline checks and publishes byte-identical reviewed template files into the original attempt namespace before CARLA import. It refuses a different preexisting original file. Native capture still rejects the current synthetic TownX templates before import because site and camera review are absent. The 30-test suite includes template publication and changed-original rejection.

`cases/bind_alternative_physical_context.py` moved the four bundled site documents into `site_templates/`, rebound their runner source and construction hashes, and `cases/prove_alternative_offline.py` reran all four exact offline proofs. `cases/prove_alternative_finalizer.py` reran four 900-frame real saved-finalizer and measurement-report checks, including missing-site negatives. `cases/build_alternative_site_recipes.py` returned four source-only recipes and exact site documents under `cases/fixtures/`; the pinned `runtime.py fixture` materialized all four without construction overlap (`cases/alternative-site-materialization.log`). These recipes are not full compatibility fixtures yet: original motion, graph and decoded-camera source generation remains. The selected crosswalk manifest was not changed.

Runtime source verification, CPU preflight and the assignment-scoped nonready complete check pass. C215286 remains partial; next CPU action is to extend the four source recipes with 900-frame motion, graph and decodable camera fixtures, run exact compatibility and recorded-only saved processing, then integrate the full six-case selected manifest and queue after the remaining audits. No Native, pixel, physical or legal acceptance is claimed.

## 2026-11-24 full intersection-entry diagnostic compatibility

Built `cases/fixtures/0/full-diagnostic.json` (2,032,324 UTF-8 bytes) and its hash-bound recipe from the reviewed synthetic intersection site and 900 joined original-frame motion/evidence rows, 1,800 base/abstract graphs, and four 900-frame FFV1 diagnostic cameras. `cases/build_intersection_diagnostic.py` deterministically regenerates both. The exact fixture materialized via `runtime.py fixture`; no capture under `runtime/`.

A current-library Lean decoder was built under `.runtime-work/c215286-current-decoder`; the older cached decoder rejected the runtime ontology value `limousine`. The staged `runtime.py compatibility` run with the rebuilt decoder passes saved analysis, Native validation, Core conversion, decoder, four-camera audit, render, final decode, selected `reverse_intersection` measurement, and missing-site-source negative. Returned receipt/logs and hashes are in `cases/intersection-full-compatibility-ledger.json`. Its analysis/negative logs are returned; generated videos, graphs and decoder remain ignored under `.runtime-work/`. The synthetic diagnostic vehicle is Tesla, matching the synthetic recorder and supported decoder fixture; the authored CARLA route site still requests Audi and needs Native site/vehicle validation. No physical or legal acceptance is claimed.

Scoped `worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete` passes. Status remains partial; the other three alternatives and selected package integration still need full compatibility and delivery proofs. No prior-ready result was modified.

## 2026-11-24 four full-duration alternative compatibility receipts

The staged intersection-entry, intersection-stop, corner-entry and corner-stop alternatives now each have a hash-bound 900-frame diagnostic recipe and passing exact `runtime.py compatibility` receipt. Every run exercised the saved finalizer, Native result validator, four source camera decodes, Core conversion, current-library Lean decoder, render/final decode, selected measurement contract and missing-case-source negative. `cases/alternative-full-compatibility-index.json` binds four individual ledgers and proof hashes. The fixture builder `cases/build_intersection_diagnostic.py` accepts indices 0-3 and generates all four recipes from the reviewed synthetic site packets. The corner-entry generator retains required `world` evidence and uses only package-declared atom IDs.

All four are synthetic software compatibility evidence. They do not establish real CARLA site, observed pixels, physical causation or legal acceptance. The root selected manifest still has the crosswalk positive/stop pair. Next work is to integrate the four staged cases into the selected package, bind its full selected case plan/comparisons, and run saved-processing, physical-preparation and delivery positive/negative proofs before an assignment strict gate can be attempted. C215286 remains partial and 34/43 batch results remain ready.

## 2026-11-24 no-flags batch check after archive cleanup

Ran `.venv-cpu/bin/python worker_check.py` to completion. It passed the UTF-8/size traversal and failed later with `Execution manifest binds another runtime` during a retained ready package. The current `runtime/SOURCE-MANIFEST.json` SHA-256 is `5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3`; 29 of 34 ready execution manifests still bind the prior `5b4738624542c97f321a302bd49b9ec154cb2cf63778acf64ba6042f8d5b4fd3`. Exact traceback: `.runtime-work/worker-check-quick-c215286-full-20261124.log`. No ready status was changed and no stale proof was relabeled as current. The assignment-scoped C215286 `--complete` check passes. All four newly returned alternative compatibility receipts pass on the current runtime, but C215286 remains partial.
