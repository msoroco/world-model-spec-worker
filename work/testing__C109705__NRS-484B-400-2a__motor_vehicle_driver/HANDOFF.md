# C109705 CPU handoff — NRS 484B.400(2)(a)

Status: **partial**. The fixed cell is a left turn at an intersection with a centerline. The exact law requires both intersecting highways to be two-directional and the left-turn approach to occupy the portion of the right half nearest its centerline. It provides no numeric lateral cutoff.

`case-plan.json.evidence_review` reads all four frozen accepted recording metadata sources. Each identifies the assigned law/cell/actor, 900 frames and a passing decoder; the case names are near/far and imaginary-near/far centerline. The export does not contain their raw trace/video or delivery-audit contents, so it does not prove the actual highway directions, body positions or comparison isolation. No accepted original is replayed, and no reuse or new capture is declared definitively. Four conditional `__source_verified_*` cases cover gaps that remain after local original-source review.

`native_road_selection.py` calls the Native map waypoint inventory and requires opposite-signed driving lane IDs on both intersecting roads. This is an engineering preflight; legal two-directional status remains source review. `approach_measurements.py` joins original frame maps to complete ego body vertices, a sourced centerline and right-half polygon before intersection entry. It reports full-body containment and distances for controlled near/far comparisons without a legal verdict. Three CPU tests pass in `cpu-tests.log`, including near/far geometry, wrong road, stale frame and missing opposite-direction lane rejection.

Next CPU work: review original accepted raw sources locally for equivalence and close or retain each documented gap. Source a two-directional junction, construct exact marked and imaginary-centerline left-turn routes and controlled body offsets where gaps remain. Implement vehicle controller, all four raw cameras, original-frame capture and saved finalizer, three distinct physical-risk fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility and saved-processing proofs and the assignment delivery-ready gate. Physical road status, body offset, turn and visibility remain later source/CARLA checks; all listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C125697__NRS-484B-250-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.
