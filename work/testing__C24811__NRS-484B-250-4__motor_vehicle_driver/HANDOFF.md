# C24811 CPU handoff — NRS 484B.250(4)

Status: **partial**. The frozen branch is a blind-intersection interaction under wholly inoperative installed, uncovered vehicular signals. The witness relocates it from C24757 because this `traffic_light` cell can also represent the operative-signal comparison. `inputs/testing__C24811__NRS-484B-250-4__motor_vehicle_driver/evidence.json` has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps the marked stop-line halt, distinct earlier-stopped and already-occupying vehicles, rolling response and operative-signal contrast. `signal_control.py` selects a Native governing light for each inventoried entrance, requests Off on all, reads back, and restores prior states. Off readback is an engineering setup fact; complete physical inoperability and uncovered heads still require original source review. `occluder_construction.py` spawns a real Native actor and checks its realized planar footprint against both approach sight rays, with cleanup. `blind_signal_measurements.py` joins the original video frames to all-head signal states and three separate complete-body vehicle histories. It reports stop and entry ordering without a legal verdict.

Four CPU tests pass in `cpu-tests.log`, including actual fake Native state and spawn calls, both approach-ray geometry, a non-obstructing negative case with cleanup, operative-head rejection, and stale-frame rejection. These are software diagnostics, not physical acceptance.

Next CPU work: source a genuine blind junction, every governing installed/uncovered head, a clearly marked stop line and a safe real occluder placement; construct synchronized ego/earlier/occupant routes and stopping controllers. Add all four raw source-camera streams, original-frame source capture, saved finalizer and measurement contract. Implement three distinct physical-risk fallbacks per selected case, canonical semantic proposals, independent delivery/comparison audits, and exact offline, compatibility and saved-processing proofs. Run the assignment-scoped delivery-ready gate after those proofs. Actual occlusion, head visibility, signal inoperability and motion remain later physical checks; all listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C24811__NRS-484B-250-4__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

The pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C412593__NRS-484B-413-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not a tool or external dependency.

## 2026-11-22 authored blind-junction construction checkpoint

`blind-inoperative-stop-line.xodr` is a byte-identical copy of the authored same-law C24757 two-head stop-line map (SHA-256 `36a15c42ccc9ce63623021d8935b094a308aa43fe3f1e4056207b513487d9e41`). `blind-site-candidate.json` binds the copy and declares the two governed entrance lanes, signal IDs, marked stop-line objects, approach sight rays and southwest-corner occluder footprint. `blind_site.py` parses the map and verifies the declared junction, lane signal governance, stop-line objects, both ray intersections and at least 4 m planned clearance from both vehicle corridor centerlines. Its proof reports 8.2 m ego and 11.8 m other clearance. The source map is only an authored candidate; these checks do not establish Native acceptance or pixel visibility.

`occluder_construction.py` now also checks the spawned Native actor's realized planar footprint against both travel corridors, requiring caller-provided positive engineering clearance. The six CPU tests pass, including reject-and-cleanup tests for a missed ray and corridor intrusion. `cpu-tests.log` is rebound in `result.json`; `worker_check.py --assignment testing__C24811__NRS-484B-250-4__motor_vehicle_driver --complete` passes. Status remains partial. Next construction step is synchronized ego, earlier-stopped and occupying-vehicle routes and stop/release controllers, followed by source cameras, saved finalizer, exact cases and three fallbacks per case, semantic and independent audits. The planned occluder footprint has no chosen Native blueprint or verified vertical geometry yet.

## 2026-11-22 exact comparison measurement checkpoint

`blind_signal_measurements.py` now supports a source-joined operative indication (Green, Yellow or Red) as well as Off. `analyze_exact_case` binds the five selected case IDs to the stop, earlier-stopped and occupying-body observations, rejects a history that fits another branch, and requires the operative indication explicitly for the operative comparison. No legal verdict is emitted. `signal_control.py` now restores each Native signal's original frozen state and checks the restoration readback. Eight CPU tests pass, including successful operative history, rejection of a mixed-state history, and rejection of mismatched exact comparison cases. The pinned `runtime.py preflight` and assignment-scoped partial check pass. These are synthetic fixture and source-contract proofs; the exact Native runner and saved capture path remain to be constructed. Status remains partial.

## 2026-11-22 three-vehicle route and source construction

`interaction-routes.json` and `interaction_routes.py` now bind the authored map SHA, two governed approach lanes, three distinct spawns and stop-line geometry. The earlier and occupant vehicles share the south approach with 32 m station spacing. Five exact case control variants cover Off/operative, full-halt/rolling, earlier-stop and occupant-presence contrasts. `release_permission` requires measured halt, entry, earlier clearance and a minimum 4 m ego/occupant complete-body separation as applicable. This is an engineering command gate, not a claim that Native actors followed it or that legal yielding occurred. `three_vehicle_sources.py` builds original-frame rows with complete body vertices, measured speeds, signed stop-line distances, distinct Native actor IDs and both observed governing signal states. It does not synthesize pixel or physical acceptance.

Twelve CPU tests pass, including source-row identity, route-map tamper, shared-lane overlap, release feedback and body-separation rejections. `runtime.py preflight` and assignment-scoped `worker_check.py --complete` pass. C24811 remains partial. Next worker-owned step: wire these controls and source rows into a synchronized Native runner with the real occluder and four raw source-camera streams; add saved finalizer, 3 physical-risk fallbacks for each of the 5 selected cases, semantic proposals, exact offline/compatibility/saved-processing proofs and independent delivery/comparison audits. Do not mark ready until the scoped strict gate passes.
