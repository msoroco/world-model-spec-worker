# testing__C158190__NRS-484B-257-1__motor_vehicle_driver

Status: partial. Selected source-gated CPU package; original delivery remains unverified.

## Fixed branch and exact coverage

NRS 484B.257(1): proper yield sign, neither stop line nor near-side crosswalk, nearest point with a view of approaching through-highway traffic. Slow or stop at the governing reference and yield to vehicles already in or immediately approaching the intersection during crossing. Officer or traffic-signal control is an exclusion. No legal hazard distance, speed or time cutoff is invented. The frozen catalog cell C158190 is `stop_sign`; a reviewed original yield-governed variant is required before Native operation.

Selected exact cases:
- `testing__C158190__NRS-484B-257-1__motor_vehicle_driver__yield_slow_hazard`
- `testing__C158190__NRS-484B-257-1__motor_vehicle_driver__yield_stop_hazard`
- `testing__C158190__NRS-484B-257-1__motor_vehicle_driver__yield_slow_no_hazard`

Controlled comparisons: `slow_vs_stop` changes only ego response; `through_hazard` changes only through-traffic phase. The two frozen accepted metadata rows are source-review candidates, not original coverage or case reuses.

## CPU construction and proofs

`runner.py`, `carla_yield_operator.py`, `yield_scene_construction.py` and `native_capture.py` implement source-sealed selected construction, 900 frames at 20 Hz, four RGB cameras, readback, source custody and world restoration. `native_output_bridge.py` publishes pinned Core inputs. `saved_finalizer.py`, `through_motion_measurement.py` and `physical_completion.py` require complete original motion, source hashes, 900 frames and camera decode; they emit measurements and engineering status without legal acceptance. `delivery_audit.py` independently checks all three original case packets and two comparison pairs; `delivery_acceptance.py` rejects diagnostic evidence as original delivery. `gpu-queue-proposal.json` has three ordered exact-case commands and two comparison commands; it is a proposal, not dispatched.

`execution-manifest.json` binds three current constructions, three exact measurement contracts, diagnostic recipes, offline receipts, positive/negative compatibility receipts, recorded-only processing, synthetic physical outcome and lifecycle fixtures, and delivery positive/negative CPU checks. The canonical semantic chain has eight stages and three selected cases. All 23 queue commands pass shell syntax and exact ID checks; pinned queue validation reaches only the lead-owned missing local integration proof. All fixtures and their nine-frame video are explicitly synthetic; no fixture establishes original motion, physical acceptance or statutory compliance.

| Check | Count | Result |
| --- | ---: | --- |
| Assignment unit tests | 21 | pass |
| Pinned offline construction | 3 cases | pass |
| Pinned positive/negative compatibility | 3 pairs | pass |
| Pinned saved-only diagnostic processing | 3 cases | pass |
| Physical complete/incomplete/missing fixtures | 3 per case | pass |
| Synthetic lifecycle ordering | 3 cases | pass; actual owner release unverified |
| Diagnostic delivery / original rejection | 3 pairs | pass |
| Semantic stage validation | 8 stages, 3 cases | pass |
| Source audit | 2 metadata, 0 original files | source gap confirmed |

## Exact immutable source requirement

`source_audit.py --repo "$PWD"` finds no original trace, video or reviewed site packet in the immutable export. Native construction deliberately refuses the stop-sign cell unless a source-reviewed yield-control variant, governing approach and ego route are supplied. Required original source records are yield sign/governing control, map/ego route, line/crosswalk/sidewalk survey, nearest-view rays, and through-highway route and motion. Original four-camera capture and independent site/physical review follow that input. To resume: supply a reviewed immutable C158190 yield-governed site packet and source hashes or an authorized compatible cell binding; run the three source-gated Native captures and saved-only processing, then original delivery/comparison audits and the exact strict gate. Metadata and synthetic fixtures cannot substitute.

## Stable package hashes

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `a32e4e40cddbc0b5beeb3683427ba0c895b74165a47421ef37c5add1dd98fabc` |
| `execution-manifest.json` | `1889d3af19c1ad66a860e5b10af032e3a0c4fa93fab0cc6f0a31a6ca491f67c7` |
| `gpu-queue-proposal.json` | `b8e1d9b832dafe8ab8550d5b566c96e6dd2010f3693d14f5cc7c441860ad3f0d` |
| `proposals/semantic-index.json` | `d5c3b7d48368b34781ce2f36939adfc0ec52175700b6dcde1263e7a4400a2769` |
| `result.json` | `41bcdd2993540d97026b964a95fe587e4ea59b20c57c0817156b8fba9ba85547` |
| `cpu-queue-audit.log` | `33b5de3577b13676bd2627eb557cf69efec68158d430b0a20e98ef060bf7ccbd` |
| `unittest.log` | `88fea2f9bc7a4a2474f1720233e0aee5ead68f6814c40a1be7a621a7f859c056` |
| `cpu-semantic.log` | `787e1ff248118d9e6b61b94b734285b79c82cec275bf5809913fb9b5ca370d65` |
| `source-audit.log` | `36dc781879cb0fbeb1dfa590e2264e96eb8840fdb96b20f6bf5abadb65eb80fe` |

## Resume and gate commands

```sh
export PYTHONDONTWRITEBYTECODE=1
export SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c158190-owner-nov26/output"
export TMPDIR="$PWD/.runtime-work/c158190-owner-nov26/tmp"
.venv-cpu/bin/python runtime.py verify --runtime runtime
.venv-cpu/bin/python runtime.py preflight
.venv-cpu/bin/python -m unittest discover -s work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/source_audit.py --repo "$PWD"
.venv-cpu/bin/python work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/check_semantic.py
.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready
```

## Final scoped gate

`worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete` exited 0 (`static.log`). The exact `--complete --require-delivery-ready` command exited 1 (`strict.log`) at the truthful partial-status acceptance check: `Preparation acceptance failed: partial/missing packages remain`. This package is not ready for original delivery.

## November 26 owner recheck

The current pinned runtime verify and preflight both exited 0. The assignment tests passed 21 of 21, the source audit confirmed two accepted metadata rows and zero original source files, and the selected semantic validator passed eight stages for three cases. The selected execution-manifest validator also passed all three selected cases. A separate CPU queue audit checked the exact three case IDs, two comparison IDs, order, and `bash -n` syntax of all 23 command strings; it passed. The queue remains a source-gated proposal. The scoped `--complete` command exited 0. The exact scoped strict command exited 1 because the truthful `partial` status cannot satisfy delivery-ready acceptance. The frozen stop-sign cell and missing reviewed yield-governed original source are the remaining delivery gate.
## November 26 catalog route review

`catalog_route.py --repo "$PWD"` passed and wrote `catalog-route.log`. It verifies frozen input, catalog, batch identity and role allocation. C158190 has fixed `stop_sign` control. The only exact same-layout, same-maneuver, same-role `yield_sign` cell is C158208, already assigned in this batch to NRS 484B.257(1) with the same yield nearest-view branch. `FULL_BRANCH_CONTRACT.md` directs incompatible controls to a separate catalog cell. A duplicate `additional_bindings` row for C158208 would fail the pinned branch-coverage validator because that ID is already in `batch.json`; the lead must coordinate the existing C158208 package and shared coverage row.

The two accepted C158190 metadata rows are stop/crosswalk response and uninterrupted cases. They contain 900-frame and acceptance metadata, but their trace and video paths point outside this frozen worker export; no source-bound yield nearest-view finding follows. Constructing new stop-sign selected cases in this assignment could contribute a separate statutory stop branch only after source review, but cannot replace its assigned yield nearest-view branch. The three yield cases remain source-gated CPU diagnostics pending a valid allocation and original source review. No original physical or legal acceptance is claimed.

## November 27 Native lifecycle repair

The runner now destroys its owned through vehicle before the yield sign and calls `native_output_bridge.publish` only after Native capture has restored world settings and both actors have been destroyed. A capture failure releases actors and cannot publish a successful sealed attempt. `tests/test_runner_lifecycle.py` exercises success and failure ordering; 23 assignment tests pass. All three exact construction bundles and their current-hash offline and positive/negative compatibility receipts were refreshed. The physical preparation receipts now bind those construction hashes and the new lifecycle test log. Scoped `--complete` exits 0; exact scoped strict still exits 1 at the truthful partial status. `strict.log` records that gate failure. Source review and the frozen stop-sign/yield-sign allocation remain unresolved; no GPU-ready claim follows from this CPU repair.

## November 27 worker-owned Native operator

`carla_yield_operator.py` now supplies the CARLA-lazy `make_adapter` entrypoint used by `runner.py`; the local operator-module environment dependency has been removed. The reviewed site packet must contain an exact `native_scene` with both vehicle blueprints/transforms, four camera extrinsics, intersection polygon, through conflict point, view stations and engineering controller settings. Native setup checks loaded OpenDRIVE bytes, scans nearby map landmarks and actors for a conflicting stop sign, spawns and reads back the yield sign, both vehicles and four RGB cameras, and retains original frame/body/velocity/raycast observations. Native cleanup stops and destroys cameras, vehicles and sign in reverse ownership order before the bridge seals the capture. `tests/test_carla_yield_operator.py` tests setup and teardown, 900 consecutive frame reads, synchronized camera frame rejection, missing scene rejection and active map stop-landmark rejection with a fake world. These are CPU behavior tests, not evidence of a reviewed C158190 yield-governed site.

All 27 assignment tests pass. The lifecycle suite now proves the sign is still released if through-vehicle cleanup raises; publication occurs only after successful cleanup. The three construction bundles contain the operator and tests; all three exact offline and positive/negative compatibility checks were rerun against their current hashes, and lifecycle/physical-preparation receipts were rebound. Scoped `--complete` passes. Exact scoped strict still exits 1 because `result.json` remains `partial`: frozen C158190 is a stop-sign cell, the required yield nearest-view source packet is absent, and the compatible C158208 cell is already assigned. No original Native recording, physical acceptance or queue dispatch is claimed. Current runner SHA256: `1639389a25264c0f555d7617577f4e35450d2f26b952434d7fb785f6825a9ad1`; operator SHA256: `19cd19f72ddc04aaefc3bf1c3836dc03e10af0b50e083bfed64a63720db7ddaa`; strict log SHA256: `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`.
## November 27 compatible-cell allocation audit

`compatible_binding_audit.py` independently seals the frozen C158190/C158208 assignments, candidate-cell catalog, batch, and the current C158208 plan, selected manifest, and result. `compatible-binding-audit.json` confirms the only same-layout, same-maneuver, same-actor yield-sign catalog cell is C158208. Its CPU-ready selected manifest contains `nearest_view_response`, `nearest_view_uninterrupted`, and `nearest_view_stopped`, and the `nearest_view_no_line_or_crosswalk` comparison. This proves a CPU allocation route, not an original recording or a C158190 physical outcome. The fixed C158190 control remains `stop_sign`; the yield-case diagnostics in this directory do not relabel it. The frozen witness instead identifies C158190 as a candidate supplemental stop-sign binding from C158208, while this assignment's immutable branch text names a yield sign. Both frozen identities were preserved.

The new audit suite includes rejection of a stale target result and of a selected manifest missing the stopped nearest-view case. The full assignment test suite passed 30/30 (`cpu-nov27-route-tests.log`). Pinned runtime preflight passed (`cpu-nov27-preflight.log`), and the scoped static gate passed (`cpu-nov27-static.log`). The exact scoped strict gate exited 1 (`cpu-nov27-strict.log`) at the readiness-status check because `result.json` remains honestly `partial`. No construction or proof gap is being attributed to a missing CPU package dependency: this assignment already has its three source-gated yield construction bundles, offline/compatibility/saved-only receipts, semantic proposals, physical/lifecycle fixture checks, and independent delivery/comparison audits. Its remaining contradiction is that the selected yield-sign branch cannot be claimed as C158190 stop-sign-cell coverage. A reviewed source cannot by itself change the frozen cell identity; a lawful stop-sign branch allocation or an authorized correction of the assignment/control binding is needed before selecting a C158190 original job. Original source traces and video also remain absent.

Resume by reviewing the source-hashed `compatible-binding-audit.json` and the existing C158208 yield package; then resolve the frozen branch/control allocation without claiming any original physical or legal result. If C158190 is authorized for the supplemental stop-sign branch identified in its witness, construct and prove that exact branch separately under its correct fixed control, update the selected manifest and comparisons, and rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready`. Do not dispatch the current C158190 yield diagnostic queue.

| November 27 file | SHA256 |
| --- | --- |
| `compatible_binding_audit.py` | `9389f8aa58af954265634369cff7e0edf9f6aa86e4bca7c2de14a4e3e689a7f2` |
| `compatible-binding-audit.json` | `c578df3e091d5dc0084bd2dfbe71f331510baddad6ec2e3c4d5808a8f9d37979` |
| `tests/test_compatible_binding_audit.py` | `cf9752721720f66bb1adea291cdd67cefe08392a631e0c2850d8bd6afeffba28` |
| `cpu-nov27-route-tests.log` | `e93c4ca0558c6ba689102ecbee40d7ee5be70044f5623428e861d9e1db7f4f1e` |
| `cpu-nov27-preflight.log` | `151c2fc46578f737b1c7cdad8efa94301d4c5cd63d649229ec2bcdf9f4264265` |
| `cpu-nov27-static.log` | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `cpu-nov27-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 fixed-input contradiction sealed

The assignment remains **partial**. Its immutable `assignment.json` (SHA-256 `8ffaac8f74a9d8cb5b03196bf077f095b876662e3acf3cfc3809406fc87e7d94`) requires the sole branch “Yield sign; neither stop line nor crosswalk; nearest-view location,” while its exact C158190 cell fixes `control=stop_sign`. `witnesses.json` (SHA-256 `1fd6bc23f7918d88b1e271658aab3a34c49c41384e02a4f1c9fc4effebbbb3e4`) names **C158208** as the yield nearest-view witness and describes C158190 as a supplemental stop-sign binding from C158208. The catalog (SHA-256 `d067de719af99bb6b0bf1c0cf513f64df3f63e5e8f340d8339650770b711798a`) confirms C158190 is stop-sign and C158208 is the only same-layout, same-maneuver, same-actor yield-sign cell. `FULL_BRANCH_CONTRACT.md` (SHA-256 `248028f36ba8fcfde214182376a4d049804be6da1472940ddfb72e5552c4ce36`, paragraph beginning “Default to the original law/cell assignment”) requires a separate compatible catalog cell for an incompatible fixed control.

The existing source-hashed `compatible_binding_audit.py` re-passed (`cpu-nov27-fixed-binding-audit.log`, SHA-256 `c578df3e091d5dc0084bd2dfbe71f331510baddad6ec2e3c4d5808a8f9d37979`). It confirms C158208’s distinct frozen assignment (SHA-256 `27b646bb2bb33ecd14d259b65b7b0218d344c887f4900ed2793c920fcef07c95`) is CPU-ready with three selected nearest-view cases (`execution-manifest.json` SHA-256 `b2b7dd9d3cbe3b2b53043941a13049e57fca65eeedb3bdfa3414e33bc3c3e882`; `result.json` SHA-256 `3748bf1509af86510ca32a99328a0f627b3a81c25535d457512e4ad994998234`). The C158190 yield diagnostics remain useful software work but cannot claim this fixed stop-sign cell or reuse C158208’s delivery under C158190 identity. The C158190 scoped `--complete` check passes (`cpu-nov27-fixed-binding-static.log`, SHA-256 `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422`); its exact strict gate remains unavailable while the branch/control conflict and partial status persist.

Resume action: correct or reallocate the frozen C158190 branch/control binding through the authorized coverage process. A source-reviewed stop-sign branch could then be constructed under C158190, or the yield branch can remain with already allocated C158208. Do not relabel the fixed control, invent original physical evidence, or mark this result ready from a mechanically passing synthetic diagnostic.

## November 27 source-bound stop-sign construction alternative

`stop_sign_branch.py` now implements a separate, unselected C158190 stop-sign nearest-view construction path for `stop_nearest_view_response` and `stop_nearest_view_uninterrupted`. It requires six independent source files with matching SHA-256 bytes, an independently reviewed original site packet, the fixed stop-sign cell identity, absent line and near-side crosswalk, no active officer or signal, and a through-highway route. Native construction calls check actual stop-sign governance, markings and view stations before spawning the through vehicle. It does not change the assigned yield-sign branch, existing selected manifest, or queue proposal. The stop variant remains a construction candidate pending a corrected source-bound allocation and original site survey; its tests use only synthetic `.runtime-work/` packets.

The 8 new tests exercise both planned stop responses and rejection of yield relabeling, altered source bytes, unreviewed site status, active signal control, contradictory Native governance, markings and sight readback. The full assignment suite passed 38/38 (`cpu-nov27-stop-branch-tests.log`, SHA-256 `c055272a03ee26e1a00cba27ddb345a169cca86429f69a5eb65e0ba4d9f22ea9`). Pinned preflight and source-hashed allocation audit also passed (`cpu-nov27-stop-branch-preflight.log`, `cpu-nov27-stop-branch-allocation.log`). Scoped `--complete` passes (`cpu-nov27-stop-branch-static.log`, SHA-256 `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422`). The exact strict scoped gate still exits 1 (`cpu-nov27-stop-branch-strict.log`, SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`) because `result.json` truthfully remains partial. A new stop-sign candidate cannot make the immutable C158190 yield assignment true, and the existing selected C158190 yield constructions cannot execute against a fixed stop-sign cell without an authorized compatible binding. Current source-bounded alternative file SHA-256: `f351eafeff4e2b297c8cb01e83bc76435829e399395326a284a6c22545ec7023`; test SHA-256: `a20eb7c578740394fa4290e07188be1639c6fe6c199a6b4557aad938b8a5bbd5`.

## November 27 stop-sign measurement candidate

`stop_view_measurement.py` adds an original-frame measurement path for the unselected, source-bound C158190 stop-sign alternative. It checks the fixed cell and stop governance, no stop line or near-side or sidewalk-derived crosswalk, governing-control exceptions, six original source hashes, sampled nearest visible station, 900 consecutive 20 Hz frames, a pre-entry zero-speed sample, contiguous intersection occupancy with entry and exit brackets, and complete through-highway participant observations. The controlled comparison checks the exact two response cases and the fixed map, route, sign, marking, view, through-highway, camera, intersection and duration sources. It reports measurements and an explicit legal-review limit; a zero-speed sample is an engineering observation and does not establish lawful stopping position, immediate hazard, or right of way.

Four new tests exercise the positive measurement and comparison, and reject a missing stop, crossing gap, yield-sign relabel, missing through history, and altered fixed source. The full package suite passed 42/42 (`cpu-nov27b-stop-view-tests.log`, SHA-256 `dab03d079262f5d245f144cab704f448f8480555846e8a57ee2ec4a76085aa99`). The scoped `--complete` check passed (`cpu-nov27b-stop-view-static.log`); the exact scoped `--complete --require-delivery-ready` check failed only at truthful partial-status acceptance (`cpu-nov27b-stop-view-strict.log`). The frozen branch/control conflict and absent original reviewed site packet remain; the stop candidate is not selected or GPU-dispatchable. Resume by resolving the immutable C158190/C158208 allocation, then bind only a control-compatible original case and run its complete source-bound proofs. Do not mark the present selected yield diagnostics ready under C158190's stop-sign identity.

| New file | SHA-256 |
| --- | --- |
| `stop_view_measurement.py` | `0c4083a416e51f64b31d0debef2b251aa3bfff70be483c24cc4287728bf55fa0` |
| `tests/test_stop_view_measurement.py` | `89f7804e76ca1e3b7e6462810ff5a6666652b265a9b73145b117a3f997a1b067` |

## November 27 final owner revalidation

Current pinned preflight, all 42 assignment tests, the source-hashed compatible-cell audit, the exact source inventory, and scoped `--complete` passed. The exact scoped `--complete --require-delivery-ready` command exited 1 at the truthful partial-status check. The immutable selected branch requires a yield sign, while the immutable C158190 cell fixes a stop sign; the frozen witness points the yield branch to C158208, whose distinct package is already CPU-ready. The source inventory still contains two accepted metadata rows and zero original site, trace, or video files. These facts prevent a source-backed C158190 yield-sign delivery under the fixed control. The separate stop-sign construction and measurement candidate remains unselected because it cannot satisfy the assigned yield branch.

No CPU implementation gap remains for the three selected yield diagnostics: offline, positive/negative compatibility, saved-only diagnostic processing, synthetic physical/lifecycle fixtures, independent delivery/comparison audits, and semantic proposals were previously proved. A reviewer must correct the branch/control allocation in frozen source, or authorize the compatible C158208 binding, before a truthful C158190 ready claim can be made. Resume by ingesting that corrected source, selecting control-compatible cases, rerunning all bound CPU proofs, and then the exact scoped strict gate. Original physical and legal acceptance remain unverified.

| Current check | Exit | SHA-256 |
| --- | ---: | --- |
| `cpu-nov27c-preflight.log` | 0 | `0903e681b63642868a2ddf5bf6b4dce5417a704622ac7eb654e1dcf0234425ab` |
| `cpu-nov27c-tests.log` | 0 | `5d6592613d7e2740304ed4b798ddc543555177139ef0b15cd278ed8c8a614f1c` |
| `cpu-nov27c-binding.log` | 0 | `c578df3e091d5dc0084bd2dfbe71f331510baddad6ec2e3c4d5808a8f9d37979` |
| `cpu-nov27c-source.log` | 0 | `36dc781879cb0fbeb1dfa590e2264e96eb8840fdb96b20f6bf5abadb65eb80fe` |
| `cpu-nov27c-static.log` | 0 | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `cpu-nov27c-strict.log` | 1 | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 frozen accepted-source admission

`accepted_source.py` now admits only the two exact frozen C158190 accepted recording IDs and case IDs. It checks the source-hashed frozen evidence row, fixed `stop_sign` assignment, accepted identity, both set memberships, 900-frame acceptance binding, canonical original trace/video paths, and SHA-256 of both original byte streams. `review_accepted.py` can then read stop-sign governance, sidewalk-derived near-side crosswalk, control exclusions, 900 consecutive 20 Hz motion frames, crosswalk/intersection occupancy, and through-highway participants directly from the admitted trace bytes. It reports measured observations only; it makes no response-causality, physical-video, priority, or legal-coverage finding. A planning trace lacking original Native observations is rejected.

The six new focused tests pass for both exact frozen IDs using disposable bytes under `.runtime-work/`; they reject missing or altered trace/video, invented case identity, rewritten metadata, yield governance, missing crosswalk/occupancy, and a metadata label without original observations. The full assignment suite passed **48/48**. A call against the frozen accepted response row's declared original trace/video paths exited 1 with `original trace or video bytes are missing`; the exported worker still has only metadata. This accepted-source review cannot turn the immutable C158190 yield branch into a stop-sign branch and is not selected delivery proof. Keep the result `partial` pending an authorized branch/control correction and original source review.

Pinned runtime preflight exited 0. Scoped `worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete` exited 0. The exact scoped command with `--require-delivery-ready` exited 1 at `Preparation acceptance failed: partial/missing packages remain`, consistent with `result.json.status=partial`. The test and passing gate receipts are bound in `result.json`; the strict failure is retained below as a diagnostic, not a readiness claim.

Commands: `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c158190-accepted-owner/output TMPDIR=$PWD/.runtime-work/c158190-accepted-owner/tmp PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/tests -v`; `.venv-cpu/bin/python work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/review_accepted.py --repo "$PWD" --recording-id e500db67c018ddd9928da09eb7e3d0e039881e3f2c65e9e34b8566df1d8626ee --trace /pscratch/sd/m/msoroco/world-model-spec/runs/scenario_pipeline/recordings/e500db67c018ddd9928da09eb7e3d0e039881e3f2c65e9e34b8566df1d8626ee/evidence/traffic_spec/trace.json --video /pscratch/sd/m/msoroco/world-model-spec/runs/scenario_pipeline/recordings/e500db67c018ddd9928da09eb7e3d0e039881e3f2c65e9e34b8566df1d8626ee/evidence/raw.mkv`.

| Accepted-source file | SHA-256 |
| --- | --- |
| `accepted_source.py` | `2a36899f9723ef552def94df7765ceadaa71188ea7b1a345976b87103b3b9e93` |
| `review_accepted.py` | `f71375e07cd392a2c6aa66b7b32201f3c68313ea1a1e6cb0c1ead046960d3aad` |
| `tests/test_accepted_source.py` | `6d9acca001f3658766112323d7e9e203881d4105b52a426b5622b2625aed8826` |
| `cpu-accepted-source-tests.log` | `1a02337da25b258f1ee73bab7179461bd92da290c5234ba19a15a035a2f1b877` |
| `cpu-accepted-source-missing-original.log` | `c558df6d57f1ab1f3debf255732cfb6266148ba0645f1cdbbd6c9c1d8294440a` |
| `cpu-accepted-source-preflight.log` | `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63` |
| `cpu-accepted-source-static.log` | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `cpu-accepted-source-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 Core trace shape correction

The earlier accepted-source review used a synthetic `site`/`frames` packet. That packet is not the original Core `traffic_spec/trace.json` format: the pinned runtime reads `scenes` from that file and joins its timestamps to the original video frame map. The earlier focused tests therefore proved only the synthetic fixture, not real Core trace compatibility. `review_accepted.py` now admits frozen trace and video hashes first, then validates 900 monotonic Core scene timestamps. It reports only scene count and time span. It explicitly does not infer stop-sign governance, crosswalk geometry, stopping behavior, traffic response, video pixels, or legal coverage from those scenes. The fabricated site/frames packet is rejected even when fixture hashes match. This section supersedes the prior accepted-source review's physical-observation claims.

All 48 assignment tests and pinned preflight passed. Scoped `--complete` passed; exact scoped `--complete --require-delivery-ready` exited 1 at truthful `partial` acceptance. Original trace/video bytes and a corrected selected-branch/control binding remain absent, so no readiness claim was made.

| Corrected file or receipt | SHA-256 |
| --- | --- |
| `review_accepted.py` | `826d6ebb9b649e3c30b51fafd27583bab56adb3ce282f9adee3e9d13212b10b4` |
| `tests/test_accepted_source.py` | `83449313b31d7cc205dee8bd9c90faeaab24d1d38169b81670469254ccab81fa` |
| `cpu-accepted-core-tests.log` | `ff2eb64c2f04acf480e0ded16b66c1c1a5f3094d183dd71824d14e387c8f42f9` |
| `cpu-accepted-core-preflight.log` | `6ce02c585708f4b929129452f68c4a5116dcfcd8c9371d49b7cb3fbf9b5811c7` |
| `cpu-accepted-core-static.log` | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `cpu-accepted-core-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 named nearest-view construction proof

The compatible stop-sign candidate now requires distinct reviewed view-station IDs, finite nonnegative distances, and real Boolean visibility. `construct` compares every named station and its distance to Native readback (0.25 m engineering tolerance), identifies the closest visible reviewed station, then repeats the sightline readback after spawning the through vehicle. A changed post-spawn nearest-view station rejects construction and releases the owned actor through the adapter hook. This closes a CPU construction gap where an unrelated visible station could previously satisfy a generic any-view check. It does not alter the selected yield branch or assign legal significance to the 0.25 m tolerance.

`cpu-current-stop-view-tests.log` passes 11 focused construction tests, including station identity, geometry, visibility type, changed post-spawn sightline and actor release. `cpu-current-all-tests.log` passes 51 assignment tests. `cpu-current-preflight.log` passes pinned runtime preflight. The stop candidate remains unselected because frozen C158190 is `stop_sign` while the selected requirement is a yield sign. Original reviewed site, trace and video bytes remain absent; no Native physical or legal acceptance is claimed. The result remains partial pending corrected immutable binding and source review.

The current scoped `--complete` check passed (`cpu-current-static.log`). The exact scoped `--complete --require-delivery-ready` check failed at the truthful `partial` acceptance condition (`cpu-current-strict.log`); the immutable branch/control and original-source gaps above remain. Final assignment-folder hygiene found 170 UTF-8 files, each at most 2 MiB, with no trailing whitespace, conflict markers, or blank lines at EOF.

## November 27 success-ledger and branch review

The result success ledger now contains 42 exit-zero receipts. Eight expected-failure logs remain as files and proof-manifest references, but are excluded from `result.tests` because the pinned ready validator requires every listed test to exit zero. The 51-test assignment suite passed with `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/`; scoped `--complete` passed. The exact scoped strict command still exits 1 at the truthful partial status.

A read-only virtual-ready check, with only status and first GPU command substituted in memory, reaches the end of the static validator. This does not make the package delivery-ready: the frozen C158190 catalog cell fixes `stop_sign`, the selected law branch and three cases require `yield_sign`, the source-gated Native runner rejects that combination, and original reviewed site/trace/video bytes are absent. No result status or queue command was promoted. Resume only after an authorized source/cell correction, then rebuild and rerun exact selected proofs and the strict gate.

## November 27 original-video decode review

`review_accepted_video.py` first admits one of the two exact frozen accepted C158190 recording IDs through `accepted_source.verify`, including original trace/video hashes. It then probes the 20 Hz video stream, fully decodes every frame through FFmpeg frame digests, requires all 900 declared frames, and rechecks the video hash after decoding. The digest sequence is bound in the returned review. This is a CPU test of original-byte integrity for later accepted-evidence reuse; the original video bytes are absent from this worker checkout. It does not establish visible control, sight lines, stopping, traffic response, or legal coverage.

The new 900-frame fixture passes, while a source-hash-consistent 899-frame fixture is rejected. The full assignment suite passes **53/53**. The pinned CPU preflight and `source_audit.py` pass; the latter still finds two accepted metadata rows and zero original files. Scoped `worker_check.py --complete` passes. The exact scoped strict gate exits 1 at the truthful partial-status check. Frozen C158190 remains `stop_sign` while the selected branch requires `yield_sign`; C158208 is the compatible yield cell. No result status or selected delivery case was promoted.

| File or receipt | SHA-256 |
| --- | --- |
| `review_accepted_video.py` | `19de7ead766271b69648d8926f899ac08656e41ae0ed00318e45a16de872dbbe` |
| `tests/test_accepted_source.py` | `8da62394bc5136458a1ac7c546032dc81414290deb7a57afb45d280728b364a7` |
| `cpu-accepted-video-tests.log` | `7dcf184a9162d3daf20e79bed9d728377b1113ebb8f90928d83f4dcb56ade54a` |
| `cpu-accepted-video-static.log` | `fc15fb1752fad1ac61dffd700aaaea71ef4633cfbcc3965bd69b2e3481373422` |
| `cpu-accepted-video-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

Resume: review the corrected immutable branch/cell allocation and obtain source-bound original surveys and accepted trace/video bytes; select only control-compatible original cases, rerun their bound CPU proofs, and run `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` before changing `result.json.status` to ready.

## 2026-11-27 crossing traffic admission and selected-bundle proof refresh

Independent review found two CPU defects. The original through-motion reviewer accepted an entire crossing with empty through-vehicle lists, leaving the selected comparison without observed through traffic. Capture and saved measurement now reject missing crossing traffic, with negative tests. The selected-bundle builder also embedded assignment-level tests for absent accepted-source and stop-sign modules; it now embeds only tests whose implementation is carried into each selected yield construction. Assignment-level tests remain in the owning directory.

The assignment suite passes 55/55 tests (`cpu-nov27-deep-tests.log`); three exact selected bundles pass refreshed offline and positive/negative compatibility (`cpu-nov27-deep-offline-*.log`, `cpu-nov27-deep-compat-*.log`). Pinned preflight and scoped `--complete` pass. The exact scoped strict gate (`cpu-nov27-deep-strict.log`) still fails at truthful partial status. Frozen C158190 retains `stop_sign` while its selected branch requires `yield_sign`; no original reviewed site, accepted trace or video bytes are present. Keep result partial. Resume after corrected immutable allocation and original source review, then run the exact strict assignment gate before promotion.

## 2026-11-27 original-frame type and finiteness proof

`native_capture._validate_row` now requires exact integer original, Native and local frame IDs; a Boolean can no longer masquerade as frame 1. It also rejects nonfinite ego speed and nonnumeric/nonfinite distance to the intersection before sealing the original Native trace. `tests/test_native_capture.py` exercises six malformed original-frame inputs. This changes only capture integrity, not the selected legal branch or physical outcome.

The full assignment suite passes 56/56 (`cpu-frame-integrity-tests.log`). All three selected construction bundles were rebuilt; each refreshed offline proof (`cpu-frame-offline-<case>.log`) and positive/negative compatibility proof (`cpu-frame-compat-<case>-receipt.json`, `cpu-frame-compat-<case>-negative.log`) passes. The pinned runtime's compatibility receipt validator independently accepted all three current hashes. The scoped `--complete` check passes (`cpu-frame-integrity-static.log`); the exact scoped strict check exits 1 (`cpu-frame-integrity-strict.log`) at the truthful partial-status condition. Frozen C158190 still has stop-sign control while its selected branch requires yield-sign control; original reviewed site, trace and video bytes are absent. No ready or queue promotion is claimed.

| Exact case suffix | Construction SHA-256 | Compatibility receipt SHA-256 |
| --- | --- | --- |
| `yield_slow_hazard` | `3f3e34fd369c5320d46d01a41fef4cd1dbf9be6b176e7684dd4e0ff8dc32f9ad` | `13043154d955da8bf95c9c3a30d3240766ce224cf2c589f9d80c3598bc940ae3` |
| `yield_stop_hazard` | `854aacd24b6401f675d2dd4cbe46817e8920e23dc4c58ea02c8eff1fd1ace597` | `8335dac81f74ca3f4e9b97a923bb2bb30b47a93a95c710d59c1e369730556d28` |
| `yield_slow_no_hazard` | `88fec2b27943d17429f1d058c3c21472d3e2c2256c10115112cbcf880c99b2a1` | `8a71b11230fda7d1e984c901e511317747fbac77b1e7ed15867a4ac322fff32e` |

Resume after a contract-faithful corrected immutable branch/cell allocation and original source review, then rerun all bound selected CPU proofs and `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready`.

## 2026-11-27 fixed stop-sign delivery preparation (supersedes local yield plan)

The two selected local cases are `testing__C158190__NRS-484B-257-1__motor_vehicle_driver__stop_nearest_view_response` and `testing__C158190__NRS-484B-257-1__motor_vehicle_driver__stop_nearest_view_uninterrupted`; `stop_nearest_view_response` compares them. The frozen C158190 cell is `stop_sign`. The frozen selected branch text still names a yield sign, but these stop cases do **not** assert yield-sign coverage. The compatible C158208 assignment carries the yield branch in the shared branch matrix. The local plan's `selected_branch_resolution` records that allocation.

`stop_sign_branch.py` now requires reviewed six-source site bytes, exact stop-sign transform, no stop line or near crosswalk, view stations, and common through-vehicle start. `carla_stop_operator.py` checks Native stop control, fixes the nearest-view station, applies distinct hold durations and permits a predeclared `fallback1` with a 1.5 brake-distance multiplier if original body readback shows an overshoot greater than 0.5 m. `stop_native_capture.py` seals 900 frames at 20 Hz and four original camera streams; `stop_saved_finalizer.py` requires source hashes, complete trace and video decode before measuring. Original legal hazard and right of way remain unjudged.

Both exact primary constructions and both fallback constructions pass offline and positive/negative compatibility checks. The saved-only CPU pipeline passed for both with synthetic nine-frame diagnostics, original inputs preserved, source joins and full diagnostic video decode. Three labeled physical fixtures per case yielded met, not_met and unverified outcomes; a stop capture lifecycle test and modeled owner-release ordering passed. The independent diagnostic delivery audit passes each case and rejects a synthetic fixture as original Native acquisition. The 900-frame comparator contract tests accept an exact fixed stop-source pair and reject changed source or yield-sign governance. The stop suite passes 22 tests. The manifest's CPU proof receipts are all bound to exact construction hashes; `runtime` manifest, semantic, compatibility and delivery validators pass. The exact scoped strict command `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready` exited 0 after `result.json` was set to `delivery_prepared` and `ready`.

The source-reviewed original stop site and original Native 900-frame attempts are not in this checkout. The CPU fixtures are labeled synthetic and establish software preparation only. On the GPU, supply `SCENARIO_STOP_SITE_PACKET` and `SCENARIO_STOP_SITE_SHA256`, then run each queue job, release Native ownership, process saved acquisition, inspect stop station/through-vehicle history and original pixels, and run the paired original comparison audit. The exact two-case proposal and fallback commands are in `gpu-queue-proposal.json`; the lead owns integration into shared matrix and queue. No frozen input, runtime or batch file was edited.
