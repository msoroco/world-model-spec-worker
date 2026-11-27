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
