# C109705 CPU handoff — NRS 484B.400(2)(b)

Status: **partial**. Both intersecting highways must be two-directional. After left-turn entry, the complete body must leave the intersection to the right of the **destination** centerline. This differs from 400(2)(a), which governs approach position. No numeric legal lateral cutoff is supplied.

`case-plan.json.evidence_review` assesses all four frozen accepted metadata sources. Each identifies the fixed law/cell/actor, 900 frames and a passing decoder. Raw traces, video and delivery audits are not exported, so accepted labels and the shared manifest cannot prove destination exit position or comparison isolation. No original is replayed or claimed reusable. Four conditional source-verified cases address unresolved gaps.

`native_road_selection.py` inventories opposite-signed Native driving lanes on both roads. `departure_measurements.py` joins original telemetry and frame maps, requires observed entry before a complete-body exit on the outgoing road, and measures destination right-half containment and centerline clearance. Three CPU tests pass, including near/far, wrong side, wrong road, stale frame and missing exit/lane rejection. These are implementation tests, not a physical or legal verdict.

Next CPU work: review original accepted raw sources when available for exact equivalence; retain unknowns until verified. Source a two-directional junction and marked/imaginary destination references; implement exact left-turn runner, four raw cameras, original-frame capture, saved finalizer, three distinct physical-risk fallbacks per selected case, semantic proposals and independent delivery/comparison audits. Run exact offline, compatibility and saved-processing proofs and assignment strict gate. All construction and proofs are worker-owned CPU work.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2b__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2b__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

No frozen input, runtime or batch file was edited; no Git command was run. Pinned CPU preflight passes. Assignment and full-gate outputs are retained in `assignment-check.log` and `strict-gate.log`.

Checkpoint: assignment-scoped static check passed. Complete strict gate next reports missing result `testing__C125714__NRS-484B-250-1__motor_vehicle_driver`; this is unfinished worker preparation, not an external dependency.
