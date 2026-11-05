# Full-train delivery best-effort return

**Status: incomplete. Strict delivery gate failed.** The 253 results remain `blocked`; none is marked `ready` or `delivery_prepared`. No CARLA run, NERSC/SQLite access, accepted recording, or agent Git publication occurred. The separate timer published a checkpoint at 2026-11-04T19:41:00Z; the inspected checkpoint log shows success.

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

The 624 definitions are unverified drafts, not selected GPU jobs. Selected delivery cases, proven candidate sets, candidate proofs, saved audits, equivalence reuses, and accepted recordings: **0** each. The 221-law, 776-topic branch inventory remains pending statutory and physical review; no runnable branch is certified. The GPU queue has no dispatchable row.

## Work completed in this continuation

- Reverified the pinned runtime, rebuilt the decoder in `.runtime-work/decoder-current`, and passed the full CPU selftest with three negative fixtures against runtime manifest `391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235`. Refreshed `runtime-proof.json` and `runtime-verification.json` to that hash.
- Repaired **31** case plans missing all four required lists: `observations`, `sources`, `existing_evidence`, and `runtime_uncertainties`. Their values derive from each draft’s existing source observation terms, hashed dependencies, membership snapshot, and stated runtime gaps. Added requirement dispositions. No draft was promoted to a selected job.
- For `training__C329610__NRS-484B-400-2a__motor_vehicle_driver`, reconciled the duplicate witness label with the exact statutory clause and added an explicit activation, time-scoped measurement draft, planned evidence mapping, and three measurable candidate risks. The Native construction and all CPU candidate/saved proofs remain missing, so it remains blocked.
- The static checker and independent package/source audit pass. The complete strict gate now reaches branch coverage and fails on pending branches. The earlier `KeyError: branch` is not reproduced by the current pinned plural-branch checker.

## Exact checks

| Check | Command | Exit | SHA-256 of log |
| --- | --- | ---: | --- |
| Runtime verify | `python3.11 runtime.py verify --runtime runtime/pipeline` | 0 | `e63dee921a6e4bdca8993964e3d5772efd51499fef90189bd29062aa42049c8d` |
| Decoder build | `ELAN_HOME="$PWD/.runtime-work/elan" .venv-cpu/bin/python runtime.py build-decoder --library runtime/pipeline/library --output .runtime-work/decoder-current --lake .runtime-work/elan/bin/lake` | 0 | `16db62a91b9a713b88a1a18a315518e22dc0b6ee03ba75594fadcaab913fcfea` |
| CPU selftest | `PATH="$PWD/.runtime-work/linux_arm64:$PATH" LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python runtime.py selftest --runtime runtime/pipeline --output .runtime-work/selftest-current --validator .runtime-work/decoder-current/.lake/build/bin/adapterCheck` | 0 | `fabf5ec585643ca37cf2b3b4a878ea48acc31b97edd9ef07c5d930c1ebc7a174` |
| Static checker | `python3.11 worker_check.py` | 0 | `f1217f0dd145369ec9166735381c99ca2cae46c9146986af41d9c982c59f92ec` |
| Independent audit | `python3.11 work/_shared/audit-return.py` | 0 | `ec1b6933e6c5f33046a9c125ec445267623b04360f3efa6d7ccb4aaabf5feabd` |
| Strict gate | `python3.11 worker_check.py --complete --require-delivery-ready` | 1 | `d2da876474dfa6ffe7c23286eef51bf03f1eefeff39a9db5dca5fdd06835f6e4` |

Strict gate failure: `runtime/pipeline/scenario_pipeline/worker_exchange/branch_coverage.py:59` raises `ValueError: Branch cannot be left pending`. This is accurate: the branch matrix has not been certified. The `--complete` nonstrict gate fails at the same check.

## Remaining worker-owned work

Reconcile all statutory branches and exceptions against exact law text and Native capability. For every genuinely selected case, author a semantic proposal, Native construction, measurement contract, cameras and capture; provide a primary plus three distinct fallbacks with exact offline and positive/negative compatibility receipts. Complete saved-only processing, independent acceptance and comparison audits, populate the ordered GPU queue, and run synthetic local integration. Rerun affected proofs and hashes, mark an assignment ready only when its CPU checks pass, and rerun the strict gate. These are **worker-owned unfinished tasks**, not tested external blockers. The current report identifies no tested external blocker. All physical route, controller, camera, measured observable, and legal outcome assumptions remain unverified.

Use each assignment’s `HANDOFF.md` and `case-plan.json` to resume. Do not infer equivalence from membership-only accepted recording snapshots. Do not claim CPU fixture success as CARLA physical success.
