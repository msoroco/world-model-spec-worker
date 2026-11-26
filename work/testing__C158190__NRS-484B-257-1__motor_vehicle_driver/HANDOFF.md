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

`execution-manifest.json` binds three current constructions, three exact measurement contracts, diagnostic recipes, offline receipts, positive/negative compatibility receipts, recorded-only processing, synthetic physical outcome and lifecycle fixtures, and delivery positive/negative CPU checks. The canonical semantic chain has eight stages and three selected cases. All fixtures and their nine-frame video are explicitly synthetic; no fixture establishes original motion, physical acceptance or statutory compliance.

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
| `case-plan.json` | `aaf3189a8a9951226af12d619f7f4a99488df0f6fad63d7182e395f7744fb02a` |
| `execution-manifest.json` | `31f2d00eef38c9ffb3365347281c25ed9bc0c9fadf73aa1ee25d05053d850d9b` |
| `gpu-queue-proposal.json` | `d3bb19692c2e3f943a44cf52ab6d09eb3653c58d6ccc9fb3911ca52de322a695` |
| `proposals/semantic-index.json` | `d5c3b7d48368b34781ce2f36939adfc0ec52175700b6dcde1263e7a4400a2769` |
| `result.json` | `2a864b0c41afe67655475bc76d0e2b720ef17a8b88025c91dca5618609507eee` |
| `unittest.log` | `144b5eb0158af7e641b57cce1edac7e7e24a19c653b70fb390c9cb0f9b488d98` |
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
