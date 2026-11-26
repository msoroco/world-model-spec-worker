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

`runner.py`, `yield_scene_construction.py` and `native_capture.py` implement source-sealed selected construction, 900 frames at 20 Hz, four RGB cameras, readback, source custody and world restoration. `native_output_bridge.py` publishes pinned Core inputs. `saved_finalizer.py`, `through_motion_measurement.py` and `physical_completion.py` require complete original motion, source hashes, 900 frames and camera decode; they emit measurements and engineering status without legal acceptance. `delivery_audit.py` independently checks all three original case packets and two comparison pairs; `delivery_acceptance.py` rejects diagnostic evidence as original delivery. `gpu-queue-proposal.json` has three ordered exact-case commands and two comparison commands; it is a proposal, not dispatched.

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
| `execution-manifest.json` | `47144b08417e91d752e3cef49af1956832a44b80a6c45da76be05135f3eb63f7` |
| `gpu-queue-proposal.json` | `b8e1d9b832dafe8ab8550d5b566c96e6dd2010f3693d14f5cc7c441860ad3f0d` |
| `proposals/semantic-index.json` | `d5c3b7d48368b34781ce2f36939adfc0ec52175700b6dcde1263e7a4400a2769` |
| `result.json` | `57975a6ede73b5f037c4b3736f1ca0f92a712f046d9a2ec7fd62e9806846f8ea` |
| `cpu-queue-audit.log` | `33b5de3577b13676bd2627eb557cf69efec68158d430b0a20e98ef060bf7ccbd` |
| `unittest.log` | `cbbb4bd006b5139e227ad211d798b8a386f6bb08ff2ddc62fb61f4e1a9d095b1` |
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
