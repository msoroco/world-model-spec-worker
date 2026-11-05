# Full-train delivery best-effort return

**Status: incomplete. Strict delivery gate failed.** The 253 results remain `blocked`; none is marked `ready` or `delivery_prepared`. No CARLA run, NERSC/SQLite access, accepted recording, or agent Git publication occurred. The separate timer published a checkpoint at 2026-11-05T21:58:14Z; the inspected checkpoint log shows success.

## Inventory

| Partition | Assignments | Blocked | Unselected case drafts | Unverified comparisons |
| --- | ---: | ---: | ---: | ---: |
| full-train-01 | 32 | 32 | 72 | 32 |
| full-train-02 | 32 | 32 | 64 | 32 |
| full-train-03 | 32 | 32 | 64 | 32 |
| full-train-04 | 32 | 32 | 65 | 32 |
| full-train-05 | 32 | 32 | 81 | 32 |
| full-train-06 | 31 | 31 | 75 | 31 |
| full-train-07 | 31 | 31 | 62 | 31 |
| full-train-08 | 31 | 31 | 141 | 66 |
| **Total** | **253** | **253** | **624** | **288** |

The 624 definitions are unverified drafts, not selected GPU jobs. Selected delivery cases, fully proven candidate sets, exact compatibility receipts, independent saved acceptance audits, equivalence reuses, and accepted recordings: **0** each. The 221-law, 776-topic branch inventory remains pending statutory and physical review; no runnable branch is certified. The GPU queue has no dispatchable row. C329610 (2)(a) has **eight unselected exact construction drafts with passing offline CPU checks**; these are not delivery-ready candidates.

## Work completed in this continuation

- Reverified the pinned runtime, rebuilt the decoder in `.runtime-work/decoder-refresh-20261105`, and passed the full CPU selftest with three negative fixtures against runtime manifest `391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235`. Refreshed `runtime-proof.json` and `runtime-verification.json` to that hash. The first build command targeted an existing output directory and exited 1 with `FileExistsError`; the fresh-directory rebuild exited 0.
- Repaired **31** case plans missing all four required lists: `observations`, `sources`, `existing_evidence`, and `runtime_uncertainties`. Their values derive from each draft’s existing source observation terms, hashed dependencies, membership snapshot, and stated runtime gaps. Added requirement dispositions. No draft was promoted to a selected job.
- For `training__C329610__NRS-484B-400-2a__motor_vehicle_driver`, reconciled the duplicate witness label with the exact statutory clause and added an explicit activation, time-scoped measurement draft, planned evidence mapping, a 20 Hz synchronized four-view capture draft, and three measurable candidate risks. Added an authored two-way intersection/route geometry module and checked XML links, route continuity, two distinct approach positions, pavement containment and a prospective vehicle body proxy. Added a saved-only measurement prototype with five passing positive/adversarial CPU unit tests. This is a CPU prototype; no CARLA capture or accepted recording exists. The assignment remains blocked.
- Independently reviewed `training__C329610__NRS-484B-400-2b__motor_vehicle_driver` against its exact clause. Collapsed a duplicate witness label and drafted the distinct full-body exit measurement, two-directional activation evidence, and three candidate risks. It has no executable selected case or CPU delivery proof and remains blocked.
- Continued C329610 (2)(a) into an observed-pose Native runner draft, controller, camera policies, saved finalizer and five semantic stage proposals. Both case IDs have primary plus three structurally distinct fallback bundles with measurable triggers. All **eight** `runtime.py offline` executions pass **15** tests each; independent draft audits verify the source hashes, changed knobs and controlled-input comparison. A four-frame synthetic local saved fixture passes positive finalization, four source-video decodes and Native attempt validation for both case IDs; removing the case-specific Native samples is rejected. The validator sets `rebuild_required: true`. No exact runtime compatibility recipe, saved Core trace or independent delivery acceptance exists, so selected case and proven-delivery counts remain zero.
- Continued C329610 (2)(b) with same-cell authored exit routes, prospective body/surface checks, a synthetic bicycle control diagnostic, and a Native-frame full-body exit-side measurement prototype. Five CPU tests pass, including wrong-side and missing-direction cases. No selected runner or four-candidate delivery bundle exists.
- Repaired a worker-owned packaging failure found on the refreshed static check: retained per-candidate diagnostic files named `offline-*` under `work/` violated the lean-return rule. Renamed them to `draft-command.log` and `draft-receipt.json`, updated all source-bound references and the summary hash, and reran the independent eight-bundle audit. The static checker now passes. A probe of the four-frame synthetic fixture through the pinned Core converter failed at the fixture's missing `capture/native/frames.jsonl`; that fixture still needs a complete Native-shaped capture and Core/render proof. This is worker-owned unfinished construction, not an external blocker.
- Reproduced a **frozen semantic checker field mismatch**: all 253 frozen `assignment.json` inputs contain `law_record` and lack `law`, but `semantic_delivery.validate` reads `assignment["law"]` and raises `ValueError: Assignment lacks exact law text`. The exact C329610 input, command, failure log and hashes are in `work/_shared/frozen-semantic-checker-defect.json`. An in-memory alias (`law = law_record`) validates all five C329610 semantic stages without editing frozen files. This defect is independent of the remaining worker-owned construction and proof gaps.
- The static checker and independent package/source audit pass. The complete strict gate now reaches branch coverage and fails on pending branches. The earlier `KeyError: branch` is not reproduced by the current pinned plural-branch checker.

## Exact checks

| Check | Command | Exit | SHA-256 of log |
| --- | --- | ---: | --- |
| Runtime verify | `python3.11 runtime.py verify --runtime runtime/pipeline` | 0 | `e63dee921a6e4bdca8993964e3d5772efd51499fef90189bd29062aa42049c8d` |
| Decoder build | `ELAN_HOME="$PWD/.runtime-work/elan" .venv-cpu/bin/python runtime.py build-decoder --library runtime/pipeline/library --output .runtime-work/decoder-refresh-20261105 --lake .runtime-work/elan/bin/lake` | 0 | `1a31bde21ef30ab86bc0daceb14f1c93643ffa894c2ae9d813d4c48b535beea0` |
| CPU selftest | `PATH="$PWD/.runtime-work/linux_arm64:$PATH" LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python runtime.py selftest --runtime runtime/pipeline --output .runtime-work/selftest-refresh-20261105 --validator .runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck` | 0 | `fabf5ec585643ca37cf2b3b4a878ea48acc31b97edd9ef07c5d930c1ebc7a174` |
| C329610 geometry | `LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/native/geometry.py --output .runtime-work/c329610-geometry-20261105` | 0 | `80a937583c7ba4902e1f5c8c83e6c394a4e6a92114a93041ce070e133c97627d` |
| C329610 saved measurement prototype | `LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python -m unittest discover -s work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/native -p 'test_measure.py' -v` | 0 | `7e90db28650d948e7142afbe49fb649ee093562e32670577c1a5a1b87323446c` |
| Static checker | `python3.11 worker_check.py` | 0 | `f1217f0dd145369ec9166735381c99ca2cae46c9146986af41d9c982c59f92ec` (`work/_shared/static-check-refresh.log`) |
| Independent audit | `python3.11 work/_shared/audit-return.py` | 0 | `ec1b6933e6c5f33046a9c125ec445267623b04360f3efa6d7ccb4aaabf5feabd` (`work/_shared/audit-return-refresh.log`) |
| Strict gate | `python3.11 worker_check.py --complete --require-delivery-ready` | 1 | `d2da876474dfa6ffe7c23286eef51bf03f1eefeff39a9db5dca5fdd06835f6e4` (`work/_shared/strict-gate-refresh.log`) |

Strict gate failure: `runtime/pipeline/scenario_pipeline/worker_exchange/branch_coverage.py:59` raises `ValueError: Branch cannot be left pending`. This is accurate: all 221 law rows remain `pending_review` across 776 inventoried source topics. The `--complete` nonstrict gate fails at the same check. This is worker-owned unfinished review, not an external blocker or frozen checker defect.

## Current C329610 draft diagnostics

| Check | Command | Exit | SHA-256 of log |
| --- | --- | ---: | --- |
| Exact draft offline audit | `python3.11 work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/audit-draft-offline.py` | 0 | `ed06ed8a2de51ad4185a020d3078d7789072b73f6ce0d852b8b6201c0ce67236` |
| Controlled-input audit | `python3.11 work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/audit-draft-comparison.py` | 0 | Recorded in the case plan |
| Synthetic saved positive/negative proof | `PATH="$PWD/.runtime-work/linux_arm64:$PATH" python3.11 work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/saved-fixture-proof.py` | 0 | Recorded in the case plan |
| Semantic stage validation with in-memory input alias | `python3.11 work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/validate-semantic-draft.py` | 0 | Recorded in the case plan |
| Frozen checker mismatch reproduction | `python3.11 work/training__C329610__NRS-484B-400-2a__motor_vehicle_driver/reproduce-semantic-defect.py` | 1 | Recorded in `frozen-semantic-checker-defect.json` |
| C329610 (2)(b) Native-shaped prototype | `LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python -m unittest discover -s work/training__C329610__NRS-484B-400-2b__motor_vehicle_driver/native -p 'test*.py' -v` | 0 | Recorded in its case plan |

## Remaining worker-owned work

Reconcile all statutory branches and exceptions against exact law text and Native capability. For every genuinely selected case, finish semantic proposal, Native construction, measurement contract, cameras and capture; prove primary plus three distinct fallbacks with exact positive/negative pinned-runtime compatibility, physical-preparation fixtures, saved Core processing and independent acceptance/comparison audits. Populate the ordered GPU queue and run canonical synthetic local integration. Rerun affected proofs and hashes, mark an assignment ready only when its CPU checks pass, and rerun the strict gate. These are **worker-owned unfinished tasks**. The frozen semantic checker mismatch is tested and recorded separately; it does not excuse or complete the worker-owned work. All physical route, controller, camera, measured observable, and legal outcome assumptions remain unverified.

Use each assignment’s `HANDOFF.md` and `case-plan.json` to resume. First finish C329610: complete pinned-runtime compatibility fixtures and exact positive/negative receipts for the eight draft bundles, physical-preparation and independent saved audits, full Core processing, controlled saved comparisons, and semantic checker repair through the authorized runtime owner. Continue the other 252 assignments and shared branch matrix independently. Do not infer equivalence from membership-only accepted recording snapshots. Do not claim CPU fixture success as CARLA physical success. The separate timer's inspected checkpoint log shows successful publication at 2026-11-05T21:58:14Z; no failed checkpoint was observed and the agent made no Git commit or push.
