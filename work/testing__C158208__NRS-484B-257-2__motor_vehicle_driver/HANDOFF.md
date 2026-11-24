# C158208 CPU handoff — NRS 484B.257(2)

Status: **partial**. The fixed cell is a one-way-to-two-way intersection with a yield sign. Subsection 2 requires the signed-entrance response in the manner prescribed by subsection 1 and continued caution/yield to vehicles not obligated to stop or yield that are inside or immediately approaching, except during actual officer or signal control. The frozen evidence inventory has zero accepted recordings; no reuse is claimed.

`case-plan.json` maps other already inside, approaching, separately obligated, no-slow response and officer exception context. `yield_sign_control.py` checks an actual Native sign trigger against the ego approach. `yield_entry_measurements.py` joins original frames to pre-entry ego speed/reference position, complete ego and other bodies, non-through-highway status and an all-entrance device inventory. It reports observed slowing and other occupancy/obligation without judging immediate hazard or caution. Three CPU tests pass in `cpu-tests.log`, including Native trigger selection, another entrance's stop obligation, active-signal exclusion and stale-frame rejection.

Next CPU work: construct/source the subsection-1 stop-line/crosswalk/nearest-view hierarchy, proper yield sign and all entrance devices; build connected ego/other routes and approaching timing sweep; capture all four raw cameras and original body/sign/road sources. Implement saved finalizer and measurement contract, three distinct physical-risk fallbacks per selected case, semantic proposals, independent delivery/comparison audits and exact offline, compatibility and saved-processing proofs. Physical sign, status, motion, sight and visibility remain later source/CARLA checks; the listed implementation and CPU proofs are worker-owned.

Resume commands:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C158208__NRS-484B-257-2__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C158208__NRS-484B-257-2__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready
```

Pinned CPU preflight and repository tests pass. No frozen input, runtime or batch file was edited. Assignment and full-gate output are retained in `assignment-check.log` and `strict-gate.log` after this checkpoint.

Checkpoint: assignment-scoped `worker_check.py --complete` passed. The complete strict gate next reports missing result `testing__C179789__NRS-484B-600-1a__motor_vehicle_driver` in `strict-gate.log`. This is unfinished worker preparation, not an external dependency.

## 2026-11-24 subsection-1 reference implementation

`yield_reference.py` now binds the signed-entrance review to the exact context SHA-256, yield actor ID and all four original camera hashes. It selects the ordered subsection-1 response reference: marked stop line, else near crosswalk, else finite nearest-view point. It preserves proper-sign, safe-speed and nearest-view judgments as unresolved. `yield_entry_measurements.py` now requires this source review and returns the selected reference with its source hash. Four focused tests pass in `cpu-tests.log`, including ordered fallback, missing nearest-view source and changed-camera rejection. The assignment-scoped complete nonready check passed in `.runtime-work/c158208-scoped-reference.log`. Status remains **partial**. Next worker-owned work: Native runner and synchronized four-camera capture, exact case constructions and risk-based fallback, saved finalizer, semantic stages and all CPU delivery proofs. Synthetic test camera bytes are only hash-binding fixtures, not decoded physical evidence.

The ordered-reference test also rejects an intersection context changed after site review. Four focused tests and the scoped complete nonready check passed again in `.runtime-work/c158208-scoped-reference-v2.log`.
