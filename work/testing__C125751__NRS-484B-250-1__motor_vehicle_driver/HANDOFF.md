# C125751 CPU handoff — NRS 484B.250(1) traffic-light cell

Status: **partial**. The fixed cell has `traffic_light` control. A governing official device excludes subsection 1 despite earlier entry by a different-highway vehicle; an inoperative signal invokes a separate subsection-4 qualification. Native Off readback alone cannot establish complete physical inoperability.

`case-plan.json.evidence_review` reads the frozen accepted precedence metadata: assigned law/cell/actor, 1100 frames and passing decoder. Its raw trace, video and audit are not exported, so no source-backed equivalence or reuse is claimed. Conditional cases separate active-signal exclusion from an Off/subsection-4 review; neither claims a subsection-1 violation.

`crossing_precedence.py` joins original frame maps to both complete bodies and sourced crossing geometry, measuring entry order and other occupancy. It reports the active-device exclusion or subsection-4 qualification explicitly. `signal_control.py` selects one Native governing head for ego's entrance and reads its state. Three CPU tests pass for Red versus Off applicability, missing control, stale original frame and Native lane matching.

Next CPU work: source-review accepted raw evidence for signal identity/state and same crossing when available. Construct actual median-opening approaches and control state; implement runner, all four cameras, saved finalizer, three distinct fallbacks, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility, saved-processing and assignment strict gates. All are worker-owned CPU actions; physical state and visibility remain later checks.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125751__NRS-484B-250-1__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125751__NRS-484B-250-1__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight passes. No frozen input, runtime or batch file was edited; no Git command was run. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C126120__NRS-484B-227-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
