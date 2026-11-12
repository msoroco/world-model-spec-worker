# C125763 CPU handoff — NRS 484B.250(2)

Status: **partial**. This frozen median-opening branch has a fixed yield sign. The witness relocates the device comparison from C125714. The exact law excludes official traffic-control-device intersections except as provided in subsection 4, so measured near-time entry at an official yield sign is not a violation finding. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps ego-left/right and close/separated entry timing plus opposite-direction left-turn exception context. `yield_sign_control.py` selects a Native sign whose trigger contains the approach waypoint. `simultaneous_entries.py` requires a source-declared single crossing, different highways, complete original-frame vehicle bodies, sign identity and video-frame joins. It reports body entry times and right-side geometry while leaving “approximately,” official status, legal yield and subsection-4 application unresolved. Three CPU tests pass in `cpu-tests.log`, including trigger selection, side geometry and wrong-sign/stale-frame rejection.

Next CPU work: source a real statutory crossing and official yield-sign governance, construct both vehicle routes and yield controller, capture four named raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical crossing, sign, motion and visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125763__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125763__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C144550__NRS-484B-223-1b__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## Median yield route construction checkpoint, 2026-11-12

`median_yield_route.py` now requires both declared routes to traverse the
interior of one source-reviewed median polygon. It checks different highways
for the ordinary comparison, or one highway with opposing headings and an
explicit other-driver left-turn intention for the exception case. It binds the
Native yield sign to ego's entrance lane and places the yield line before the
crossing. Its CPU controller brakes for an observed conflict, rejects passage
past the yield line into an uncleared conflict, and releases when clear. This
is a construction/controller component; no actual reviewed Native site or
physical sign status has been established.

Seven CPU tests pass in `cpu-tests.log`, including both approach routes,
opposite headings, wrong sign lane, wrong yield line, braking and release.
Next CPU work is the reviewed site packet, lazy Native actor/camera runner,
saved finalizer, diagnostic media, three distinct fallbacks per selected case,
semantic proposals and exact offline/compatibility/saved proofs. Status remains
partial and the work is worker-owned.

The latest assignment `worker_check.py --complete` exits 0 in
`assignment-check.log`. The final full
`worker_check.py --complete --require-delivery-ready` exits 1 in
`strict-gate.log` with `Preparation acceptance failed: partial/missing packages
remain`. The batch delivery gate has not passed. `result.json` remains partial
with the current seven-test log hash. No frozen inputs, runtime, batch file or
Git action was changed.
