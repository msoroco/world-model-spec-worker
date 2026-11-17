# C158196 CPU handoff — NRS 484B.257(1)

Status: **partial**. The frozen branch label names yield-sign nearest-view, while this bound cell fixes a traffic light. The witness assigns the active-signal exception here because C158208 fixes a yield sign. This package observes whether a signal actually controls ego traffic at entry; it does not claim to cover nearest-view yield behavior. The frozen evidence inventory has zero accepted recordings.

`case-plan.json` maps an operative governing signal, a visible but non-governing light, an Off state and a no-signal-control yield reference. `signal_control.py` selects the Native signal by affected road/lane waypoints, changes state with readback, and restores it. `signal_exception_measurements.py` joins original signal/head identity and affected-lane control state to complete ego-body entry and video frames. It reports active control at entry while leaving official and legal exception status unresolved. Three CPU tests pass in `cpu-tests.log`, including Native selection/state/restore, active versus unrelated or Off signal, stale frame and wrong-light rejection.

Next CPU work: source the official signal and properly signed baseline entrance, construct both operative and non-governing control cases, actual vehicle routes, all four raw cameras and original signal/body evidence. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical head governance, visibility and motion remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158196__NRS-484B-257-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C158208__NRS-484B-257-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## 2026-11-17 Native signal comparison pair construction

`signal_control.py:construct_signal_comparison` now spawns distinct ego and through actors on two sourced Native approach lanes. It checks the selected map, original unprojected actor waypoints, the exact selected signal actor and its affected lane readback, then applies/restores the chosen Native state and destroys both actors on success or failure. This supports both the governing-head and visible non-governing-head comparison constructions without treating state readback as legal control or head visibility. The four CPU tests include positive governing and non-governing cases plus wrong-governance and wrong-lane rejection; `cpu-tests.log` SHA256 `84c73ecd12d8e8820efa6123e71f84e5950bf5520dd8f3bed592d69bf3353975`. Source SHA256 `eb21fcb5355285c2ce9ab194568644d2c7cb81de1565b70e7d03db948fcb9560`. `case-plan.json.native_signal_pair_construction_proof` and partial `result.json` bind the current test/source hashes.

Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0 in `.runtime-work/c158196-pair-construction-preflight.log` SHA256 `1d4332cc7f670a4509e36ac08376742cc3c54484eb37c6e1d98c38e25d43c709`. Assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment testing__C158196__NRS-484B-257-1__motor_vehicle_driver --complete` exits 0 in `.runtime-work/c158196-pair-construction-assignment.log` SHA256 `0a0f97d22284a9bb0013d70628066b3118e31f46b4f9ace51d67966a92558f81`. Full strict rerun exits 1 at frozen `preparation.py:97`, `Unapproved output: runtime/runs/scenario_pipeline/inputs/shared/manifest.json`; `.runtime-work/c158196-pair-construction-strict.log` SHA256 `1619540c7826a8754909c30b9a431397b0eb2ffd3d1e0a6dfdbc09ce68150e62`. Existing generated runtime output was left untouched.

C158196 stays partial. Next CPU construction is original source capture for the selected ego/through route and four cameras, then saved finalization, exact candidate fallbacks, semantic proposals, offline/compatibility/recorded-only saved proofs and independent audits. Physical sign/head review remains unverified. No frozen input, runtime, batch or Git action.
