# heldout__C111610__NRS-484B-413-1__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 branch and original signal-timing continuation

`case-plan.json` now names four exact pedestrian, other-vehicle and combined-user
cases with three controlled comparisons. The same intersection, turn route,
vehicle, cameras, audio acquisition and duration must be held fixed. The
planned horn and indicator differences are construction targets; affectedness
and legal safety are not presumed.

`turn_signal_measurement.py` joins each original turn-state and Native signal
readback to the frame map, requires source-cited highway/turn route and road
users, and reports horn-command and indicator frames before observed turn onset.
It leaves actual horn emission, pedestrian reception/audibility, possible
effect, signal appropriateness and reasonable safety unknown. A commanded horn
is not proof that a pedestrian heard it. Two CPU tests pass with wrong-frame
and uncited-user rejection. Run `.venv-cpu/bin/python -m unittest discover -s
work/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`cdde17f7f8ccaf9ff26cdea64c4bd46045872131fc6be749144bff68f93a1a70`.
Scoped complete passes; strict still rejects the truthful partial result.

Next, implement the first exact Native turn, pedestrian route and acoustic
source acquisition, including a microphone or equivalent original source at
the pedestrian position, and retain four synchronized camera streams. Run its
source-bound finalizer through exact offline, positive/negative compatibility
and saved processing before linked comparisons and fallbacks. No physical or
legal acceptance is claimed.

## Frozen scope and source

- Law: NRS 484B.413(1) — A driver shall not turn a vehicle from a direct course upon a highway unless and until such movement can be made with reasonable safety, and then only after giving a clearly audible signal by sounding the horn if any pedestrian may be affected by such movement and after giving an appropriate signal if any other vehicle may be affected by such movement.
- Cell/actor: C111610 / motor_vehicle_driver; layout `intersection`, maneuver `turn`, control `pedestrian`.
- Exact input: `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/assignment.json` (SHA256 `c0c7db22fa23340f1dcbf392684a9481578d6ab648dbed7f6e49fc145fb5cdc7`).
- Witness: `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: drv.turning, drv.lane_change, drv.time_to_conflict, ru.pedestrian, sig.horn, sig.turn_indicator, sig.hand_signal, drv.following, rel.surface_gap.

## Required source and construction review

1. Construct the direct approach, turn route, pedestrian route and intersection governance.
2. Establish driver physical control, an ordinary motor vehicle and highway status.
3. Establish highway status, qualifying vehicle and actual driver control.
4. For an emitted-horn example, provide actual emission and received acoustic evidence at the pedestrian, including timing and ambient conditions; a command alone is insufficient.
5. Preserve reasonable safety, possible effect and clearly audible as unresolved standards.
6. Provide actual horn emission and received acoustic evidence at the pedestrian, including timing and ambient conditions.
7. Specify the direct approach, turn, pedestrian route and intersection governance.
8. Use a person afoot and retain their position and motion relative to the turn.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C111610__NRS-484B-413-1__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

### 2026-11-12 pedestrian horn construction and CPU proof checkpoint

`native_horn/` now contains a CARLA-lazy affected-pedestrian horn construction adapted to this exact cell and case, with an independent listener PCM source, horn relay, four named cameras and a turn finalizer. `native-horn-primary-construction.json`, the source-hashed `pedestrian-horn-diagnostic.json` recipe, measurement contract and first canonical case proposal are returned. The primary passes exact offline and compatibility checks, including original-source negative validation, and `prove_horn_primary.py` confirms saved processing from an independently materialized source-complete attempt with originals preserved. `prove_horn_fallbacks.py` builds three distinct risk-triggered fallbacks (pedestrian offset, PCM rate, overview camera mount); all three pass exact offline and compatibility with negative source checks. The assignment-scoped nonstrict `worker_check.py --complete` exits 0. The package remains **partial**: physical protocol, independent delivery audit, complete selected-case/controlled comparison set, semantic stage proposals and scoped strict acceptance still need construction and proof. No synthetic fixture is claimed to establish physical audibility or legal sufficiency.

### 2026-11-12 four-case construction and proof continuation

`execution-manifest.json` now contains all four exact cases in `case-plan.json`: `pedestrian_horn_before_turn`, `pedestrian_no_horn_before_turn`, `other_vehicle_signal_before_turn`, and `both_users_both_signals` (each prefixed by this assignment ID). The latter three adapt same-law, source-proved C111603 constructions to the C111610 cell using `build_no_horn_case.py` and `build_remaining_turn_cases.py`. Each construction has its own exact case identity, four-camera 20 Hz configuration, retained original turn/signal/participant/listener sources as applicable, and three distinct risk-triggered fallback constructions. `prove_no_horn_case.py` and `build_remaining_turn_cases.py` ran exact offline and positive/missing-source compatibility for each candidate. `prove_no_horn_saved.py` and `build_remaining_turn_cases.py` ran saved-only processing for each added primary; the receipts report originals preserved. The first horn primary's prior saved proof remains in `pedestrian-horn-primary-saved-receipt.json`.

The exact receipts and hashes are in each `execution-manifest.json` case under `offline`, `compatibility`, `candidates` and `saved_processing`. Generated diagnostic media remain only under ignored `.runtime-work/`. The three planned comparisons have a source-shaped independent implementation in `comparison_audit.py` and a passing `comparison-audit.log`; `tests/test_comparison_audit.py` rejects stale construction and missing horn contrast. The audit fixes law, cell, actor, 20 Hz, duration, four cameras, engineering controls, turn-motion source and turn onset while checking the declared pedestrian horn, other-vehicle signal and combined-user differences. It makes no physical or legal finding.

`cpu-tests.log` records four tests and `native-horn-tests.log` records 14 original-source tests. The nonstrict scoped gate passed after these additions. Resume commands: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/tests -v`; `.venv-cpu/bin/python work/heldout__C111610__NRS-484B-413-1__motor_vehicle_driver/comparison_audit.py`; `.venv-cpu/bin/python worker_check.py --assignment heldout__C111610__NRS-484B-413-1__motor_vehicle_driver --complete --require-delivery-ready`.

Status remains **partial**. Implement and test physical protocol and independent delivery acceptance audits, then bind `post_capture` and `delivery_acceptance` for every exact case, complete the semantic stage proposals and source observation mapping, and rerun all affected proofs after any construction or finalizer change. Audit the original text again for omitted conditional branches and the distinction between audible signal evidence and legal judgment. The CPU fixture cannot establish realized pedestrian effect, actual horn audibility, turn safety or camera visibility. Those physical findings remain for later original recording review; the listed missing audit and proposal work is still CPU preparation.

### Strict batch gate and return-file count

The 2026-11-12 full strict command `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:87` with `ValueError: Return contains too many generated files`. At that check, `work/` held 10,276 files against frozen `batch.json.max_return_files=10200`. Removing 29 generated Python caches and 15 unreferenced C111610 compatibility stdout logs left 10,232 files; all source-bound compatibility receipts, analysis logs, negative logs, saved receipts and manifest references remain. The remaining 32-file excess is worker-owned return compaction work before the batch gate can reach its partial-package check. Do not delete referenced proof files or change the frozen cap to force a pass. The package itself remains partial for the CPU deliverables listed above.

The return-file excess was then resolved by dropping 35 redundant compatibility stdout copies cited only by historical test entries in C125714 (29) and C230627 (6). Their receipts, analysis and negative logs remain; both assignment-scoped strict gates still pass. `work/` now has 10,197 files, below the frozen 10,200 cap. Future work must manage the cap before adding new return files.

Final batch strict gate rerun after compaction: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `preparation.py:276` with `ValueError: Preparation acceptance failed: partial/missing packages remain`. The file-count precondition now passes; 16 assignment results, including this package, remain truthful partial checkpoints. Resume the CPU audit/proposal work above and the other partial assignments in `batch.json`, then rerun the exact scoped and complete strict gates.

### 2026-11-12 independent turn delivery audit continuation

`turn_delivery_audit.py` now audits each of the four exact saved attempts against its current saved receipt and construction hash. It verifies original source hashes, frame-map/trace/body joins, listener PCM packets or explicit no-pedestrian collection status, pre-turn horn relay acknowledgement where applicable, and full decode of all four named cameras. `turn-delivery-audit-proofs.json` (SHA-256 `0f1f6f8c4a71fc715109d570250fccec9c0654b49a16ee856b5810ced36ff0cc`) records four passing positives and four nonzero missing-original listener negatives. The script SHA-256 is `3314876f8ec8ae9b7afdba0a6c4e674038ab1664378332fa41993e53b36aa5c8`; each `execution-manifest.json` case now binds that independent audit and passes pinned `delivery_handoff.validate_case` for held-out. The scoped nonstrict `worker_check.py --assignment heldout__C111610__NRS-484B-413-1__motor_vehicle_driver --complete` exits 0.

Status remains **partial**. Next CPU actions: implement and bind the three source-shaped physical outcomes and ordered Native/saved lifecycle for each exact case, bind `post_capture`, finish the canonical semantic stage chain and source-observation mapping, review the original-law alternatives against the case plan, and rerun affected exact/saved and scoped strict proofs. Four-camera synthetic decode and relay acknowledgement do not establish actual horn emission, listener audibility, pedestrian effect, visibility, reasonable safety or legal acceptance. Keep return inventory below 10,200 files by source-hash archiving only verified unbound historical logs; current inventory after this audit is 10,199.

`physical_fixture.py` was added after the delivery audit. It exercises source-shaped joined turn yaw and lateral travel for each of the four exact cases, with complete, incomplete and missing-motion outcomes; all **12 probes pass** in ignored `.runtime-work/c111610-physical-protocol/`. These fixture outputs are not yet returned or bound in `physical_preparation`, and the ordered lifecycle/post-capture proof remains to implement. The probe deliberately sets `actual_native_capture: false` and makes no physical or legal finding. Before adding proof receipts, free verified return slots under the frozen 10,200-file cap without deleting referenced logs.

The full strict rerun `timeout 90s .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 124 without output while traversing the complete return tree; the last completed full strict result remains the partial/missing-package rejection. This is a full-gate execution limit, not a package-ready result. The scoped nonstrict check passed after the delivery audit binding. Resume the strict gate after the remaining worker-owned CPU deliverables are bound.
