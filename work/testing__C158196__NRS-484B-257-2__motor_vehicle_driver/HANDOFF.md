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
