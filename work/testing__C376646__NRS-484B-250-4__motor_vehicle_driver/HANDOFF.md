# C376646 CPU handoff — NRS 484B.250(4)

Status: **partial**. Fixed blind-intersection cell with stop line. The rule requires installed, uncovered vehicular signals to be inoperative when ego enters; then all entrances are treated as stop signs. Ego must stop using the marked-line/crosswalk/nearest-view hierarchy, then proceed cautiously and yield to earlier-stopped or already present vehicles. Frozen accepted-evidence inventory is empty.

`signal_control.py` inventories every Native entrance head, sets Off with readback and restores prior states. `inoperative_stop.py` joins original frame maps to all-head Off states, complete-body stop-reference position, ego stop and other prior-stop/inside status. Three CPU tests pass across all three reference branches, priority negatives, active-head rejection, stale frame and Native restoration. Off readback and synthetic frames are implementation checks, not proof of physical inoperability or cautious yielding.

Next CPU work: source installed/uncovered head inventory, blind sight and stop references; construct exact post-stop interactions. Implement runner, four raw cameras, saved finalizer, three distinct fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. These are worker-owned CPU actions; actual physical state and visibility remain later checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C376646__NRS-484B-250-4__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. All 43 assignments now have `result.json`, but each remains partial. Complete strict gate reports `Preparation acceptance failed: partial/missing packages remain`. No dependency or tool preflight is blocked; exact primary runner, four-camera saved-processing proofs, fallbacks, semantic proposals and independent audits remain worker-owned CPU work.
