# C111125 / NRS 484B.307(8)(d) / cycle or scooter operator

Status: **partial CPU construction, measurement and saved-processing checkpoint**. The fixed assigned witness is a bicycle proceeding straight after failed detection. Zero accepted recordings are listed in the frozen evidence inventory. No physical or legal outcome is claimed.

## Exact cases and comparisons

`case-plan.json` selects five exact cases: `two_cycles_failed_detection` (reference), `one_cycle`, `signal_changes`, `no_prior_stop`, and `fails_to_yield`. The four comparisons isolate observed complete cycle count, failed detection versus a changing signal, antecedent stop, and yielding to a signal-directed participant. Every case retains the C111125 intersection, bicycle, straight maneuver and official traffic light. No numeric legal threshold is invented; the two complete cycles are the statute's count. The packet records all phase transitions because the meaning of the applicable device's cycle boundary still needs original source and legal review.

The statute also names device malfunction, pedestrians and other traffic, three other road-user types, and right/left turns. The assigned witness fixes bicycle, failed detection and straight. The malfunction alternative and separate pedestrian/traffic yield contrasts could be added in this same cell after source review. Right/left turns conflict with this cell's fixed straight maneuver and need lead review of existing compatible cells; this package does not claim those alternatives covered.

## Implemented CPU path

`signal_trial.py` verifies source hashes for map, official device, detector link and bicycle blueprint packet before planning. Its CARLA-lazy `spawn_case` calls the injected Native world blueprint library, reads back the spawned blueprint and actor ID, installs a detector/device policy by injected adapter, and destroys an owned actor on failed setup. `control_step` requests stop, creep or straight travel from current readbacks while preserving each deliberate case contrast. Requested behavior is separate from measured behavior.

`measure_attempt` requires sealed original Native, device, detector and geometry files; the per-frame rows must exactly join those files. It rejects stale hashes, absent channels, discontinuous frames, non-20 Hz timestamps, wrong actor/device/map identity, missing straight entry and nonmonotone route. It measures stationary behavior before the source-bound stop boundary, observed red through entry, sensor-zone occupancy versus output, complete observed green/yellow/red rotations, and directed-participant conflict at entry. The output has no legal verdict or physical acceptance. `comparison_audit.py` independently checks exact pairs, fixed source identities, original bindings, intended measured differences and the reference prerequisites.

`tests/test_signal_trial.py` and `tests/test_comparison_audit.py` cover positive construction, source rejection, all five measurements, actor cleanup and all four comparisons. The fixtures are synthetic CPU packets and do not prove Native execution or video visibility.

`saved_attempt.py` is a CARLA-free saved attempt processor and CLI. It reads an exact `attempt.json` receipt, verifies the packet hash and its four original Native/device/detector/geometry source hashes, checks capture completion, actor readback, detector/device policy authority, frame count and case identity, and then invokes the original measurement path. Its default mode rejects diagnostic fixtures. Diagnostic mode is explicit, retains `diagnostic_fixture: true`, and always returns `physical_acceptance: false` and `legal_verdict: null`. The CLI writes measurement output outside the sealed attempt tree. `tests/test_saved_attempt.py` exercises the CLI plus source tampering, identity, incomplete Native exit, path escape and frame-count rejection. This is a CPU saved-processing component, not the full runtime `process-saved` delivery path.

## Proofs and exact gate

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator/tests -v` passed 13 tests. `cpu-tests.log` SHA256 `31c0e06306808a77360f72834458bda3cd7f831d9a9b243e88efb85e896bf0e6`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete` passed static checks. `assignment-check.log` SHA256 `4964b90f8269b5a5dd2d45705120e8c3f01610e9582d6f88892801ab4f035035`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator --complete --require-delivery-ready` failed, as expected for truthful partial status, at `Preparation acceptance failed: partial/missing packages remain`. See `strict-gate.log`.

## Exact remaining CPU work

Source a Native C111125 map/device/detector packet and an actor blueprint that substantively represents a bicycle with rider; make the policy adapter observe the detector-to-signal causal link. Connect the saved processor to a capture-time seal and the runtime process-saved finalizer. Author full canonical semantic proposals and `semantic-index.json`, exact per-case configurations, source-hashed diagnostics, manifest, offline and positive/negative compatibility receipts, runtime process-saved integration, independent delivery audit and video/source decode proofs. Assess whether malfunction and separate participant variants remain within the assigned branch. For the fixed straight cell, refer turns to the lead's branch binding review. Keep status partial until the exact strict gate passes. Then run the prepared GPU queue locally for actual motion, sensor behavior, camera visibility and full video review.
