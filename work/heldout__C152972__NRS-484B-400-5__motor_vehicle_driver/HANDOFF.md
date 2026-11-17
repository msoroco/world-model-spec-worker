# Handoff: heldout__C152972__NRS-484B-400-5__motor_vehicle_driver

## Frozen scope

If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn where both intersecting highways are one-way, both the approach for the left turn and the left turn must be made as close as practicable to the left-hand curb or edge of the highway.

Cell C152972: one_way_to_one_way_intersection / left_turn / curb; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Both intersecting highways one-way and intended left turn at intersection.
- Compare approach body position close to left curb or edge while holding departure.
- Compare left-turn path body position close to left curb or edge while holding approach.
- No numeric legal cutoff for “as close as practicable.”

## Current checkpoint

Three cases now compare approach body distance from the source left curb and turn departure body distance from the destination left curb separately, holding the other motion fixed. `oneway_turn_geometry.py` reads original map curb lines and four-corner subject footprints; `oneway_turn_comparison_audit.py` rejects changed fixed conditions. Tests pass and reject wrong directionalities and missing turn phases. `cpu-tests.log` SHA256 is `7c6964cb69b6f1074215a67076f408fa13e887ccb22eafefe759369e4fda9d24`. The distances are engineering measurements, with no invented legal practicability cutoff.

Status remains partial. Exact Native construction, four-camera capture, finalizer integration, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C152972__NRS-484B-400-5__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C152972__NRS-484B-400-5__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C152972__NRS-484B-400-5__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## 2026-11-16 active source restoration and route target construction

The two archived original source files were verified against the `result.json` lossless tar and exact SHA-256 entries. Their geometry measurement and independent fixed-condition comparison functions are now restored in active `oneway_turn_geometry.py` (SHA-256 `c52242e524b2f7d76398e36a9f550e7aa087cbbdcc753b6ceeabf5050ce1d594`) under the returned file cap; the original bytes remain preserved in the archive. `tests/test_oneway_turn_geometry.py` imports the active module and now also proves source-hashed route waypoint targets for near/near, far-approach/near-departure and near-approach/far-departure without changing the held segment. The route function requires original map identity, one-way directionality, left turn, each curb line, each inward normal and road width; it rejects wrong inward orientation and targets beyond the road width. It asserts no physical realization or legal practicability threshold.

`PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C152972__NRS-484B-400-5__motor_vehicle_driver/tests -v` passes 4 tests; `cpu-tests.log` SHA-256 `f5baad1350dfdd73fa05e0c8d7a8199aa9b5db93ddb6388c8d43439864674f96`. `case-plan.json` now records this precise CPU construction checkpoint. Still partial: implement the CARLA-lazy Native runner and four-camera capture, source-retained finalizer and measurement contract, three distinct fallback constructions for each selected case, exact offline/compatibility and saved-processing proofs, semantic stage proposals, independent delivery positives/negatives, and scoped ready-only gate. These are worker-owned CPU tasks; no environmental dependency is claimed.

Comparison audit strengthening: `measure` now binds the exact original map and body-source SHA-256 values; `audit` independently reopens each source, rejects changed/missing bytes and preserves the earlier fixed-curb isolation check. The test uses distinct retained originals for each exact case and proves both tamper and missing-source rejection. Five tests pass; `cpu-tests.log` SHA-256 `65a18c7d6b350029f597e1e5f469c05983aa0f60596fde5970a70d455c23ff06`. This is a CPU source-integrity proof, not physical/legal acceptance.

## 2026-11-16 final CPU checkpoint and strict gate

Pinned CPU preflight passed (`.runtime-work/preflight-after-c111644-ready.log` SHA-256 `a39369a2219c5fa1e444d6024a5d5f697d6424a3e7cd204ffaad46d11642a51b`); repository unit tests passed 6 (`.runtime-work/repo-tests-after-c111644-sweep.log` SHA-256 `ad6f50518db3bdb399922279c14f90b46b2b67748a73eead7d5b5aa6b00c1f17`). The completed full strict command `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `runtime/scenario_pipeline/worker_exchange/preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain`; ignored transcript `.runtime-work/strict-gate-after-c111644-ready.log` SHA-256 `8a5196a775b4e25dcc5ad430d9aa36835506a570dd5afd41ee669c3da366a69e`. Frozen batch inventory is 43 ready / 8 partial; there is no missing CPU dependency. C111644 was corrected to partial because declared realized sweep observables are not emitted or proved by the current finalizer.

C152972 now has selected requirement dispositions for both curb clauses, a prospective four-camera 8 s coverage plan and exact source-observation mapping in `case-plan.json` SHA-256 `19e0fdd679dd65f892eb5234c88381509251548099d200af3be8207a312cb31b`. Its active source-hashed geometry, route target and comparison module SHA-256 is `15200c1ad64ebe296691aa4ff76f39f226b64315b1639f09595bbb587c747db7`. Five CPU unit tests pass, including missing/rehashed original-source rejection; `cpu-tests.log` SHA-256 `65a18c7d6b350029f597e1e5f469c05983aa0f60596fde5970a70d455c23ff06`. The assignment-scoped `worker_check.py --complete` passes, but this package remains partial pending Native runner/capture, finalizer, fallbacks and exact delivery proofs. No physical or legal acceptance is asserted.

The returned tree has 10200/10200 UTF-8 text files. One inactive C111644 historical negative log was losslessly added to `work/_shared/historical-receipts-bundle-20261116.json` SHA-256 `dad60ff27816d3e96f6b46dd2f19487fe0847f23cd82b20de38e4ca26826b452` to make room for the restored active C152972 module; C111644's scoped check passed after archival. Two attempted ready-package physical-log archives failed their scoped checks and were restored byte-for-byte; both ready-package scoped checks passed after restoration. No frozen input, runtime or batch file was edited and no Git command was run. The Goal remains active.

Source-retained finalizer checkpoint: `oneway_turn_geometry.py` now has `finalize_original_sources(attempt)` which requires SHA-256-sealed original map/body, trace, video frame map, and all four named camera video/frame-map sources. It joins Native frame IDs and timestamps, derives approach and departure left-curb distance streams, turn phase, one-way context and original curb geometry, and refuses preexisting derived streams or altered source bytes. This is a CPU fixture/source contract, not a full Native result or decoded physical video proof. Six unit tests pass, including tamper rejection; active module SHA-256 `70769035d8cbeddfd4ba292070876d17153556f3aeff20a034fe83df03043b22`, `cpu-tests.log` SHA-256 `ad0f54023870d338242cd20f11ce408fcc7b56b8d640bae46abd60c5c61489a0`. The full Native result schema, runner/capture/fallbacks and exact compatibility/saved proofs remain next worker-owned CPU work.

Finalizer join correction: the source-retained 20 Hz check now verifies trace and composed-video frame timestamps and video-frame order in addition to Native frame identity and four camera frame maps. Six tests still pass. Current active module SHA-256 `de8df9cf0195b3f94d1c9367787ce8983f4bf6a22e1eee2127ed23f92b7ff8a2`; current `cpu-tests.log` SHA-256 `ad0f54023870d338242cd20f11ce408fcc7b56b8d640bae46abd60c5c61489a0`. These hashes supersede the earlier hashes in this report.

## 2026-11-16 continued Native construction checkpoint

`oneway_turn_geometry.py` SHA-256 `9dffb2b7a0035ecc2cb4d6721c7e0a57630e394d854623b9fe33cc6a5873cde8` now builds all three source-bound route branches, checks travel-unit direction against each original curb, rejects a CARLA map-name mismatch, spawns the ego and four named RGB source cameras through injected CARLA interfaces, and applies a Native pose/velocity waypoint controller. `finalize_and_write --attempt` converts the sealed original inventory to five derived channels and uses the pinned `worker_exchange.native_output` validator/writer to create a Native-shaped `result.json`; it rejects a duplicate attempt. Source geometry and body corners now reject nonfinite coordinates. `case-plan.json` SHA-256 `311d1b21e7769561d9141d00763d939e149fdda61d7c9e0ffb317b1e0f9d78db` binds this construction checkpoint. No CARLA server was used and the two-frame mock media is diagnostic only.

`PYTHONPATH=runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/heldout__C152972__NRS-484B-400-5__motor_vehicle_driver/tests -v` passes nine tests; `cpu-tests.log` SHA-256 `c28352d167621f001385da4c44de9af4d91a6b930e5e132b71911e0464de50f3`. `.venv-cpu/bin/python worker_check.py --assignment heldout__C152972__NRS-484B-400-5__motor_vehicle_driver --complete` exits 0 for static checkpoint validation. Status remains partial: finish the actual 160-frame capture/encoder lifecycle with map and body readbacks, full exact recording descriptions and measurement contracts, one selected primary offline/positive-negative compatibility/saved proof, then three risk-triggered fallbacks per selected case, remaining exact cases, semantic proposals, independent delivery/comparison proofs, package queue and ready-only gate. These are CPU implementation/proof tasks; actual physical motion and visibility remain separate GPU checks.
