# Full-train delivery best-effort return

**Status: blocked; strict delivery gate failed.** This is a source-grounded planning return, not a deployable GPU delivery. All 253 assignment results remain `blocked` with no `delivery_prepared` claim. The frozen `batch.json`, inputs, partitions, pinned runtime sources and ontology were preserved. The agent did not commit or push; a separate timer owns Git checkpoints.

## Inventory and completed work

| Partition | Assignments | Blocked | Planning-only case definitions | Unverified comparisons |
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

The planning definitions are **unselected and unverified**. Selected delivery cases: **0**. Proven four-plan candidate sets: **0**. Individual proven candidates: **0**. Source-hashed accepted-recording reuses: **0**. CARLA runs and accepted recordings: **0**. The 221-law, 776-source-topic inventory is in `branch-coverage.json`; its 221 grouped records are **pending source inventories**, not certified statutory branches. Runnable branches and tested physical capability blockers: **0**. `branch-review.json` lists all 221 laws as awaiting statutory and candidate review. `gpu-queue.json` is explicitly blocked and empty because there is no exact prepared candidate to dispatch.

Every assignment has `result.json`, `case-plan.json` and `HANDOFF.md` in its own directory. The plans retain exact source links, law/cell/actor identity, source terms, proposed comparison variables and missing proof work. `blocker-inventory.json` identifies the unresolved reason and uncertainty list for **every assignment**; the individual handoffs give the law-specific resumption context. Historical membership IDs were recorded as context only; none was counted as an equivalence receipt or reused recording.

## CPU and gate evidence

| Check | Exact command | Exit | SHA-256 log |
| --- | --- | ---: | --- |
| Pinned runtime source verification | `python3.11 runtime.py verify --runtime runtime/pipeline` | 0 | `e63dee921a6e4bdca8993964e3d5772efd51499fef90189bd29062aa42049c8d` (`runtime-verify.log`) |
| Decoder build | `ELAN_HOME="$PWD/.runtime-work/elan" .venv-cpu/bin/python runtime.py build-decoder --library runtime/pipeline/library --output .runtime-work/decoder --lake .runtime-work/elan/bin/lake` | 0 | `f54da486b72398d43b668203f98193117a43ef7dae61ba111e2e99112f3a5fcf` (`decoder-build.log`) |
| CPU selftest | `PATH="$PWD/.runtime-work/linux_arm64:$PATH" LD_LIBRARY_PATH="$PWD/.runtime-work/geos-wheel/shapely.libs" .venv-cpu/bin/python runtime.py selftest --runtime runtime/pipeline --output .runtime-work/selftest-geos-ffmpeg --validator .runtime-work/decoder/.lake/build/bin/adapterCheck` | 0 | `5b0387e07e93b84acff467ba6032340fa55131dbe113eaff7686b86ce2e2af30` (`runtime-selftest.log`) |
| Independent package/source/link audit | `python3.11 work/_shared/audit-return.py` | 0 | `ec1b6933e6c5f33046a9c125ec445267623b04360f3efa6d7ccb4aaabf5feabd` (`package-audit.log`) |
| **Strict delivery gate** | **`python3.11 worker_check.py --complete --require-delivery-ready`** | **1** | **`a66ade0dfca00813b4a734028216ec75f4a9f77e4b5bb45500aa76a026044a61`** (`strict-gate.log`) |

`runtime-proof.json` binds the passing selftest and `runtime-verification.json` to runtime source-manifest SHA-256 `81990701a92a9e5653c1b87a1a396ea2df7d2352bc8a4db82bae584ef35dabc8`. The selftest is a retained three-frame CPU fixture and decoder/render regression proof; it establishes no physical CARLA feasibility or accepted delivery case. The first selftest attempts failed on missing local GEOS and ffprobe; their exact logs are retained as `runtime-selftest-geos-failure.log` and `runtime-selftest-ffprobe-failure.log`. GEOS and ffmpeg/ffprobe were installed only under ignored `.runtime-work/`; CPU packages and Lean 4.28.0 are private under ignored `.venv-cpu/` and `.runtime-work/`.

The strict gate reaches `runtime/pipeline/scenario_pipeline/worker_exchange/preparation.py:159` and raises `KeyError: 'branch'`: it reads `original['branch']`, while frozen `inputs/<assignment-id>/assignment.json` records have `branches[]` and no top-level `branch`. This is a baseline checker/input schema mismatch, and the pinned runtime cannot be edited without invalidating the batch's source-manifest hash. The same failure occurs in the nonstrict checker after package files are discovered. This exception occurs before the gate can report the independently real delivery incompleteness. Earlier untracked launcher/status scripts at the repository root also failed the gate's output allowlist; they were preserved under ignored `.runtime-work/` so the final gate reached the checker defect. No frozen file was changed.

## Unresolved delivery blockers

1. **Exact statutory coverage:** All 776 source topics are inventoried, but their alternatives, exceptions, judgment phrases and physical branch dispositions have not been independently reconciled into proven runnable comparisons or tested capability-blocker receipts. The grouped inventory is not evidence of full branch coverage.
2. **Case preparation:** The 624 planning definitions have no selected execution manifests, semantic stage validation, Native construction, controllers, verified physical cause, measurement contract or camera/capture proof. No comparison has a measured isolation audit.
3. **Four distinct candidates per selected case:** No primary or fallback construction has a construction SHA, offline route/footprint/control check, measurable fallback trigger, or positive/negative compatibility recipe. Thus no case can truthfully be marked delivery ready.
4. **Saved and independent evidence:** No exact positive/negative saved fixture, Core mapping, saved-only processing receipt, delivery acceptance audit, canonical candidate queue or synthetic local integration proof exists for a selected case. No historically accepted recording has a source-hashed same-case equivalence receipt.
5. **Specific source/cell conflicts:** Examples recorded in the affected handoffs include `training__C230259__NRS-484B-600-1e__motor_vehicle_driver` (a parked cell does not establish driving), `training__C230289__NRS-484B-633-2__motor_vehicle_driver` (bridge context unproved), and the partition-05 school-bus and overpass/roadway-crossing assignments. Authority, exception, pedestrian-device and judgment contexts also require exact source and physical review. See `blocker-inventory.json` for every assignment and its precise reason.
6. **Strict checker defect:** The frozen `branches[]` versus `original['branch']` mismatch prevents the gate from evaluating even a blocked package. A coordinated, source-hashed runtime/batch correction is needed before a future strict pass; silently adding a fabricated singular branch to frozen input would violate this return.

All physical route connectivity, maneuver completion, device state, actor visibility, camera framing, measured observables and legal outcomes remain unverified. A CPU fixture is not a CARLA execution or an accepted recording.

## Resume instructions

Start with `blocker-inventory.json` and each assignment's `HANDOFF.md`. Resolve the pinned checker/input schema mismatch through an authorized source-manifest update that preserves frozen input provenance, then rerun runtime verification, decoder build and CPU selftest against that new source hash. Reconcile exact law text, witnesses, summaries and accepted membership for each branch. Prepare same-cell controlled cases and independently test any unsupported physical branch. For every selected case, materialize semantic stages and Native construction, add four genuinely distinct candidates, run exact offline and positive/negative compatibility proofs, saved fixtures, Core mapping, independent acceptance and comparison audits. Populate the ordered GPU queue and local integration proof only after those receipts pass. Mark only proven packages `ready`/`delivery_prepared`, then rerun `python3.11 worker_check.py --complete --require-delivery-ready` and record its new log hash.

No `.runtime-work/worker-run.*/checkpoint.log` existed at report time, so there is no checkpoint failure text to report. Git publication remains the separate timer's responsibility.
