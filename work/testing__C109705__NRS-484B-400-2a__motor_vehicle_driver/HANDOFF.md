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

## Approach site and saved comparison checkpoint — 2026-11-16

`native_road_selection.validate_approach_site()` now binds six retained review-document hashes to a candidate Native map/intersection, exact selected approach lane, both-road opposite-direction lane inventories, marked/imaginary centerline, right-half polygon, junction and approach route. It rejects a stale document, wrong map or lane, and a route outside the right half. The test packet is synthetic; no real site or legal road status is claimed. `approach_measurements.compare_near_far()` independently reloads two saved original-frame source sets, requires fixed map/road/centerline/right-half context and both full bodies in the right half, and checks measured near/far centroid ordering without a legal cutoff. It rejects changed fixed context, reversed ordering and a body outside the right half. Seven CPU tests pass in `cpu-tests.log`.

Next worker-owned CPU step: supply a reviewed exact site packet and route for the first selected case, integrate `validate_approach_site()` into a CARLA-lazy four-camera runner, then author the saved finalizer and exact offline/compatibility/saved proofs before sweeping the other three cases and fallbacks. The current comparison is a tested implementation on synthetic sources, not a delivery acceptance receipt. Keep the package partial.

Verification: pinned `.venv-cpu/bin/python runtime.py preflight` exits 0. The seven-test command `.venv-cpu/bin/python -m unittest discover -s work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/tests -v` exits 0; `cpu-tests.log` SHA256 is `e9d06fb2ddb181208afbe46af139027c468f915cadaf8d3aec6abb45d67481a8`. Scoped `.venv-cpu/bin/python worker_check.py --assignment testing__C109705__NRS-484B-400-2a__motor_vehicle_driver --complete` exits 0. Full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 at `preparation.py:276`, `Preparation acceptance failed: partial/missing packages remain`; exact output is `.runtime-work/c109705-2a-strict-20261116.log` SHA256 `8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa`. This is unfinished worker-owned construction/proof work, not a missing dependency.

## First exact marked approach offline construction — 2026-11-16

`native_road_selection.py` now constructs a checked left-turn route preserving the source-bound right-half approach, a bounded CARLA-independent route follower, and explicit `overview`, `approach`, `reference_corner`, and `driver_reference` camera placement/dimension plans. Eight CPU tests pass (`cpu-tests.log`, SHA256 `43050aaf9cd441f3e8443dceacddb99a2f08a50ff6b2034a5e5a06f689884001`). They cover source/map/lane/route rejection, left-turn sense, controller command/brake behavior, all four camera names, near/far measurement ordering, and changed fixed context rejection.

The first selected case `testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__source_verified_near_centerline` now has an inline `construction.json` and `execution-manifest.json`. The packet and six source documents in this bundle explicitly identify themselves as synthetic CPU geometry; they are not a reviewed real Native site. `.venv-cpu/bin/python runtime.py offline --manifest work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/execution-manifest.json --case testing__C109705__NRS-484B-400-2a__motor_vehicle_driver__source_verified_near_centerline --output .runtime-work/c109705-2a-first-offline-v1` exits 0, materializes the exact bundle and runs its source-tamper test. `exact-offline.log` SHA256 is `6efa3868042945ddd4ea1e52bebb759a17ba1ac706b29ce8fba446b000dff4c9`; the manifest binds the construction and log hashes. Scoped `worker_check.py --complete` passes.

The entrypoint deliberately raises on Native capture because the four source camera encoder/recorder and saved finalizer are not integrated yet. Next CPU step is to implement those components in the exact construction and rerun offline, positive/negative compatibility and recorded-only saved processing. Then construct the other three selected cases and three distinct fallbacks each, semantic proposals and independent delivery audit. No physical or legal acceptance is claimed; status remains partial.

Final full strict gate after this offline checkpoint: `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exits 1 at `preparation.py:276` with `Preparation acceptance failed: partial/missing packages remain`; ignored `.runtime-work/c109705-2a-first-offline-strict.log` SHA256 `8aef413169724d9407e9d952cba2ff32a092e36fc56cfd20e5c6db11ce83d5aa`. The first exact primary is offline-proved only, not saved-processing ready.
