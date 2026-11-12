# C125745 CPU handoff — NRS 484B.250(2)

Status: **partial**. The frozen branch measures entry timing at a median-opening crossing in a stop-sign cell. The witness relocates this device comparison from C125714. The exact law excludes intersections controlled by official traffic-control devices except as provided in subsection 4, so near-time entry at an official stop sign is an observation, not a violation finding. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` names ego-left/right and close/separated entry-time cases plus opposite-direction left-turn exception context. `stop_sign_control.py` selects a Native stop sign whose trigger contains the ego approach point. `simultaneous_entries.py` requires a source-declared shared median crossing, two different highways, complete original-frame vehicle bodies and sign identity. It reports body entry times and spatial right-side geometry while leaving “approximately,” official-device status, legal yield and subsection-4 questions unresolved. Three CPU tests pass in `cpu-tests.log`, exercising trigger selection, side geometry and wrong-sign/stale-frame rejection.

Next CPU work: source a real statutory crossing through the opening, official sign status and all entrance obligations; construct two routes and stop/yield controllers; capture four named raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Actual sign, crossing, body timing and visibility remain later source/CARLA checks; the listed construction and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C125763__NRS-484B-250-2__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## Median route and opposite exception checkpoint, 2026-11-12

`median_route_control.py` now validates two declared routes through the same sourced median polygon, different-highway or opposite-direction relations, the Native stop sign bound to ego's lane, and an ego stop line before the crossing. `stop_yield_control` commands braking to a recorded stop and holds it while the conflict is uncleared. This is pure CPU control logic; scene coordinates remain a reviewed Native input, not a fabricated site. `simultaneous_entries.py` now accepts an opposite-direction left-turn source contract separately from its different-highway branch and returns right-side geometry as inapplicable for that exception. It still leaves official-device, approximate timing, yield and legal conclusions unresolved.

Run `.venv-cpu/bin/python -m unittest discover -s work/testing__C125745__NRS-484B-250-2__motor_vehicle_driver/tests -v`; eight CPU tests pass in `cpu-tests.log`, including rejection of a wrong sign lane, route outside the crossing, missing left-turn intention and passage beyond the stop line without a stop. Pinned `.venv-cpu/bin/python runtime.py preflight` passed this turn. The assignment remains **partial**. Next construction work: source the actual median-opening site and all entrance/sign identities, bind the four case routes, implement the lazy Native runner and four-camera capture, then exact saved finalizers/fallbacks/proofs and independent audits. These are worker-owned CPU tasks. No frozen input, runtime, batch file or Git action was changed.

The pinned preflight output is retained in `preflight.log` (exit 0). The scoped `worker_check.py --assignment testing__C125745__NRS-484B-250-2__motor_vehicle_driver --complete` output is retained in `assignment-check.log` (exit 0). The full `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` run is retained in `strict-gate.log` (exit 1, `Preparation acceptance failed: partial/missing packages remain`). This package and the batch are still partial; the gate was not passed.
The opposite-direction analyzer additionally checks the original pre-entry body centroids against both declared approach headings; a heading/body mismatch fails. The revised eight-test suite passes in `cpu-tests.log`.
After the heading/body check, the assignment `--complete` recheck still exits 0; the final full strict recheck exits 1 at `Preparation acceptance failed: partial/missing packages remain` in `strict-gate.log`. `result.json` remains partial with the final eight-test log hash.
