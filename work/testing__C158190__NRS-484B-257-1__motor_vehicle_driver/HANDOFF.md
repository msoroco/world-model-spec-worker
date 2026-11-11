# C158190 CPU handoff — NRS 484B.257(1)

Status: **partial**. The selected frozen branch requires a yield sign, no stop line, no near-side crosswalk, and a stopping/slowing point nearest the intersection with a view of approaching traffic. The frozen cell's `control` is `stop_sign`; this scope tension is recorded in `case-plan.json`. It does not authorize replacing the selected yield-sign branch with a stop-sign case. Frozen `evidence.json` contains no accepted recordings, so no reuse is claimed.

`case-plan.json` proposes selected nearest-view cases with approaching, entered and absent through-highway vehicles, plus an ego no-slow contrast. These are planned cases, not completed capture constructions. The law exempts officer and signal control, and includes an immediate-hazard judgment with no numeric legal cutoff in the source text.

`yield_measurements.py` joins raw approach speeds to original video frames, validates sourced sign/road/marking context, requires sight ray provenance, and reports the closest sampled approach location with visible through traffic. It rejects a present stop line/crosswalk, signal exception, absent sight ray and stale frame join. Three CPU tests passed in `cpu-tests.log` using `.venv-cpu/bin/python -m unittest discover -s work/testing__C158190__NRS-484B-257-1__motor_vehicle_driver/tests -v`. A context declaration of absent markings is not itself proof; the runner/finalizer must retain the Native and image sources that support it.

Next CPU work: implement the actual source-grounded yield-sign-governed one-way-to-two-way junction construction, nearest-view point discovery, through-highway actor/controller, four source cameras and raw histories; finalize and independently audit the selected cases. Supply three distinct physical-risk fallback constructions per selected case and exact offline, compatibility, saved-processing and comparison proofs. Then run `.venv-cpu/bin/python worker_check.py --assignment testing__C158190__NRS-484B-257-1__motor_vehicle_driver --complete --require-delivery-ready`. Actual sight lines, motion and camera visibility remain later physical checks. All listed implementation and CPU proofs remain worker-owned.

The pinned CPU preflight passes. No frozen input, runtime or batch file was edited.

Checkpoint: assignment-scoped `worker_check.py --complete` passed; see `assignment-check.log`. The batch strict gate then failed at missing C158196 result in `strict-gate.log`; that assignment has since received a partial checkpoint.
