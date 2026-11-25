# C158196 CPU handoff — NRS 484B.257(2) signal cell

Status: **partial**. The fixed cell is one-way-to-two-way travel with `traffic_light` control. An operative signal actually controlling ego is an express exception to subsection 2's signed-entrance duty. A head elsewhere is insufficient. Frozen accepted-evidence inventory is empty.

`signal_control.py` selects the Native head by affected ego lane, applies a state with readback and restores it. `signal_yield_exception.py` joins original signal/head and frame maps to complete ego/other bodies, signed non-through entrance context and other occupancy. Three CPU tests pass for active, Off and nongoverning states, stale frame, wrong light and Native state restoration. The within-intersection observation does not decide immediate hazard or cautious yielding.

Next CPU work: source all entrance signs, signal governance and non-through status. Construct within-intersection and approaching-hazard traffic with exact signal states; implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual state and visibility remain later checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C160013__NRS-484B-127-3__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.

## 2026-11-25 signed-entrance saved-source measurement

`intersection_yield_measure.py` now hashes the original entrance inventory, crossing history and frame map; rejects incomplete/duplicate lane devices and a signed supposedly non-obligated other entrance; computes ego and other intersection occupancy from complete body vertices and a sourced polygon; joins original frame IDs; and exposes per-frame conflict times without a legal hazard cutoff. It separately records pre-entry stop observation, governing-signal exception candidacy and whether the other body was inside at entry. Judgment of immediate hazard and cautious progression remains unresolved. The six-test CPU suite passes, including missing-source, stale-frame, signed-other and controlled-signal negatives; `cpu-tests.log` is SHA-bound in `result.json`. Runtime verify and preflight passed on this turn.

Still required before readiness: Native entrance/device acquisition and full traffic construction; exact cases, four cameras and saved finalizer integration; approaching-hazard sweep; justified fallbacks; source-bound offline/compatibility/process-saved proofs; canonical proposals; independent delivery/comparison audits; assignment-scoped strict gate. Current result remains partial.

`original_crossing_capture.py` now acquires one same-frame Native sample with eight ego/other body vertices, speed, current lanes, sourced entrance-lane identities, affected-lane signal governance and distances to a supplied conflict point. It rejects same-entrance traffic and missing body data. The caller must still source the conflict point and entrance identities, join the frame with all cameras, and integrate this sampler into an exact runner. The package CPU suite now has eight passing tests.

Checkpoint validation: `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete` exited 0. A full `work/` text/size/whitespace/conflict scan found 12,145 files and zero errors after removing test-created bytecode. Run future package tests with `PYTHONDONTWRITEBYTECODE=1` to keep binary bytecode outside the returned tree. The ordinary whole-batch quick check is still running at this checkpoint.

The ordinary `.venv-cpu/bin/python worker_check.py` finished exit 1 after full-tree inspection with `ValueError: Execution manifest binds another runtime` in `execution_manifest.py`; it no longer raises `UnicodeDecodeError`. This is the expected retained-prior-readiness/current-runtime split in `START_HERE.md` and `RUNTIME_REFRESH.md`. Preserve the prior-ready packages and their recorded runtime revision; continue assignment-scoped work here.

`CrossingSourceWriter` now writes new original entrance, crossing-history and four-camera frame-map sources, rejecting stale/missing camera packets and nonmonotone frames; the saved analyzer rejects changed or absent camera frame identities. The package suite now has nine passing tests, run with bytecode disabled and SHA-bound in `result.json`. This is an acquisition component; actual camera pixels, actor control and exact case selection are still unfinished.

`crossing_drive.py` adds a CPU-tested hold-then-proceed ego script and continuous other-vehicle control, with distinct actors and bounded controls. The fixed hold length is a motion setup parameter, never a legal stop-duration or hazard threshold. Exact route geometry, stop-line/crosswalk reference, collision-free trajectories and physical progress still require construction and Native review. The package suite now passes eleven tests.

Final turn check: assignment-scoped `worker_check.py --complete` exits 0; the full `work/` scan finds 12,147 UTF-8 files with zero size, trailing-whitespace or conflict-marker errors. Keep `result.json` partial until the exact scoped strict delivery gate passes.

## 2026-11-25 six exact constructions and saved-source finalizer

Status remains **partial**. Six exact case IDs are now in `case-plan.json`, `motion-plan.json`, `diagnostic-manifest.json` and `construction-proof-index.json`:

- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__active_signal_controls`
- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__signal_off_signed_duty`
- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__signal_elsewhere_no_control`
- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__signal_off_stop_signed_duty`
- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__approaching_traffic_close`
- `testing__C158196__NRS-484B-257-2__motor_vehicle_driver__approaching_traffic_far`

Each exact inline construction passes current-runtime `runtime.py offline` using the command and source hashes in `construction-proof-index.json`; the six retained logs are `cases/<suffix>-offline.log`. `runner.py --check` validates primary config without importing CARLA. Authored signal, stop and visible-but-nongoverning sites, reversible signal state, bounded two-actor control, original body/signal sampling, synchronized four-camera frame mapping and FFV1 encoding are in the construction. The current source inventory flags legal site and Native governance review pending; motion-plan separations are engineering setups, not legal immediate-hazard cutoffs. Physical realization and sign validity are unobserved.

`saved_finalizer.py` checks exact case identity, retained source presence, complete crossing and camera frame joins, trace/evidence joins, and source hashes. It writes eight original-observation channels, a Native result with physical assessment and a separate unresolved-legal analysis. `config.json.physical_completion` binds the runtime physical assessor to `crossing_history.jsonl` and the original entrance polygon. The 18-test focused suite includes saved-only finalization and changed/missing-original-source negatives; it uses a textual fixture placeholder for media, so it does not test real video decoding or physical visibility. Run:

```sh
SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c158196-257-2-tests PYTHONPATH=runtime/scenario_pipeline PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-2__motor_vehicle_driver/tests -v
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-2__motor_vehicle_driver --complete
```

Current-runtime verify and preflight passed. The scoped static checker passed after renaming the diagnostic index to `construction-proof-index.json`, because its reserved `offline-` filename prefix failed return inspection. This is not a delivery-ready gate. Next worker-owned CPU work: canonical requirement dispositions and measurement contracts, source-bound positive/negative compatibility for each exact case, recorded-only process-saved proof, justified risk-based candidates, semantic proposals, independent physical/delivery/comparison audits, selected execution manifest and GPU queue, then scoped strict delivery-ready gate. The whole-batch strict gate remains open with five partial assignments. No prior-ready package was changed.

`comparison_audit.py` now independently rereads both saved source trees and checks exact case order, common camera/rate/duration/actor and ego motion settings, intersection geometry, non-obligated other entrance, and the declared signal, sign or approach-separation difference for all four planned comparison IDs. A positive active-versus-Off fixture and changed fixed-camera negative pass. It makes no immediate-hazard or legal verdict. The implementation is included in all six inline constructions and the current six offline receipts. It still needs source-bound end-to-end receipts for all four comparisons from full compatible saved attempts. The focused suite now passes 19 tests.

Independent law reread: subsection 2 also names police-officer control and incorporates subsection 1's stop/yield manner and stopping-reference hierarchy. The current six cases exercise signal control, signed entrance, within-intersection priority and approaching-distance setups, but do **not** yet construct an officer-control alternative or fully prove the subsection 1 stopping-reference hierarchy. Do not label the branch matrix complete or the assignment ready until those alternatives are mapped to source-backed cases or a justified existing-evidence binding and tested. The current fixture videos are structural placeholders, so compatibility and decode checks remain mandatory.

The motion parser now rejects nonfinite other-vehicle starting coordinates and out-of-range/nonfinite throttle before Native capture; the control call also rejects nonfinite throttle. Negative CPU cases cover both. Six exact offline receipts were refreshed against these changes and remain passing.

## 2026-11-25 source-bound measurement checkpoint

`case-plan.json` now selects four observable requirements for all six exact cases: operative signal at complete-body entry, ego entrance sign type, non-obligated other-body occupancy at entry, and pre-entry zero-speed observation. Each `cases/<suffix>-measurement-contract.json` binds the exact requirement and input files to a named top-level `saved_finalizer.py` method. The finalizer now emits `measurements` with values, method names and SHA-256 hashes of `entrance_inventory.json`, `crossing_history.jsonl` and `video_frames.jsonl`; missing crossing history reports the contract's `Missing required source` error. These are observations, not findings that signs were properly erected, a hazard was immediate, or the driver complied with subsection 1.

`measurement-contract-check.log` records six passing contract validations. `measurement-integration.log` records an executed saved-only positive for `signal_off_stop_signed_duty` and the missing crossing-history negative. The focused 19-test suite passes in `cpu-tests.log`. All six exact current-runtime offline constructions were rebuilt with the updated finalizer and pass in `cases/<suffix>-offline.log`; hashes and commands are in `construction-proof-index.json`. `runtime.py verify --runtime runtime`, `runtime.py preflight --runtime runtime`, and the scoped nonready `worker_check.py --complete` passed. This is a partial implementation checkpoint; the scoped strict ready gate was not run because its package prerequisites remain incomplete.

Next worker-owned CPU work: construct consistent source recipes with decodable four-view media, run positive/negative package compatibility for each case and recorded-only processing, add the officer-control and subsection 1 stopping-reference alternatives, justify and test fallbacks, select semantic proposals and an execution manifest, then obtain independent physical/delivery/comparison audits and the scoped strict ready gate. Actual Native sign governance, trajectories and legal hazard/caution remain unresolved.

Unscoped quick `worker_check.py` was started but interrupted during the retained ready-package revalidation, following `START_HERE.md`'s deferral of whole-batch checks. It did not produce a new pass. The prior completed quick run passed UTF-8 inspection and then reported `Execution manifest binds another runtime` on a retained prior-ready package. This turn's direct full-tree inspection found zero binary or portability violations; the C158196 scoped nonready check passed. The prior-ready package was preserved.

## 2026-11-25 diagnostic compatibility and saved processing

Six exact source recipes (`cases/<suffix>-fixture-recipe.json`) now bind each authored OpenDRIVE road and entrance inventory by SHA-256, and six explicit UTF-8 source specifications generate joined crossing/trace/evidence/frame records, Native adapter graphs and four three-frame FFV1 camera views. The specimens are labeled synthetic diagnostics. Their short clips exercise software compatibility and cannot establish a 30-second Native capture or physical visibility.

The first compatibility run exposed an actual recording defect: stopped actors have undefined time to conflict, while the plan required a scalar in every frame. `saved_finalizer.py` and all six exact constructions now retain each conflict-time channel as a structured `{defined, value_s}` record and provide the declared `entrance_inventory` context evidence. This keeps undefined values truthful and lets the runtime validate the full recording plan. All six current-runtime `runtime.py compatibility` commands now pass positive and missing-`crossing_history.jsonl` negative paths, with Native validation, Lean decoder, render and full media decode. All six `runtime.py process-saved` commands pass from those retained diagnostic attempts with original sources preserved and analysis complete. `source-proof-index.json` binds the returned compatibility and saved-processing receipts/logs; `construction-proof-index.json` binds six rebuilt offline proofs. `cpu-tests.log` has 19 passing tests. Runtime verify/preflight and assignment-scoped nonready `worker_check.py --complete` pass.

C158196-257-2 remains **partial**. The six diagnostic cases do not yet construct officer control or the full subsection 1 stopping-reference alternatives. Three-frame synthetic fixtures do not prove Native sign placement, governing head, 30-second behavior, camera visibility, immediate hazard or cautious traversal. Next worker-owned work is to add the missing exact alternatives and tested fallbacks, independent physical/delivery/comparison source audits, a complete selected execution manifest and the scoped strict delivery-ready gate. Prior-ready assignments were not changed.

Four planned pairwise comparison audits now pass against the retained diagnostic saved-source trees: active versus Off governing signal, governing versus elsewhere signal, yield versus stop sign, and close versus far approaching traffic. `cases/<comparison-id>-comparison.json` records each source hash and observed difference; `comparison-proof-index.json` binds the four receipts and `comparison-proofs.log`. The comparison auditor fixes shared camera, geometry, actor, route and motion inputs and checks the deliberate source difference. These are synthetic three-frame pair checks, not Native physical or legal conclusions. The assignment-scoped nonready checker passed after adding them.
