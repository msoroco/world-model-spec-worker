# testing__C178759__NRS-484B-210-2__motor_vehicle_driver

Status: partial CPU construction and measurement. Exact static check passes; strict delivery readiness does not.

Exact law: NRS 484B.210(2), right-side overtaking only under conditions permitting movement in safety. The word safety has no authored numerical cutoff or legal verdict here. Frozen accepted evidence inventory contains zero recordings. The exported judgment-range file has no NRS-484B-210-2 entry.

## Case and source coverage

- `case-plan.json` names exact `__open_gap`, `__close_gap`, and `__cross_traffic` cases, controlled `approach_space` and `crossing_actor_proximity` comparisons, three source-based evidence gaps and mandatory map, actor, body, speed and conflict observations. All three cases have concrete physical-risk assessments.
- `right_pass.py` checks original Native paved-road cross sections every at most 5 m across both approach and exit, verifies a distinct same-direction right lane, rejects shoulder use and bodies outside pavement, and requires a sourced crossing actor pose for the conflict case. Its lazy `spawn_native` instantiates both vehicles (plus the conflict actor when relevant), reads actor identity/transform, and cleans up a failed partial spawn.
- `measure` requires original 20 Hz frame/time continuity and actor identities, measured body envelopes on pavement, actual same-direction ego overtaking speed, and observed behind/alongside/ahead phases with the ego on the right. It retains minimum approach gap and TTC, lateral body clearance and closest conflict-body separation as physical facts only. `finalize_sealed` verifies source SHA; `audit_comparison` rejects missing sources, changed fixed conditions and absent deliberate measured difference.
- Actual passing, conflict trajectory and visual visibility remain to be checked on an original Native capture. The small fake objects in the tests establish software behavior only.

## Checks

- `.venv-cpu/bin/python runtime.py preflight`: passed with pinned Lean/lake and CPU runtime.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C178759__NRS-484B-210-2__motor_vehicle_driver/tests -v`: 8 passed; `cpu-tests.log` SHA256 `706556ee51b6200bf9ba01d43b669187a6fc12919ad2c14d5dca4bb5dcf769be`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C178759__NRS-484B-210-2__motor_vehicle_driver --complete`: passed; `cpu-static-check.log` SHA256 `41003b27e11328b86c88a1529b619d93cb97dfd057554476503f922b61a69b89`.
- Same exact command plus `--require-delivery-ready`: exit 1, `Preparation acceptance failed: partial/missing packages remain`; `cpu-strict-check.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`.

## Next CPU work

1. Bind each exact case to a CARLA-capable primary bundle with config, runner, construction hash, source packets, camera/duration plan, measurement contract and diagnostic recipe. Recheck source map and crossing actor geometry on the chosen Native route.
2. Author source-preserving canonical semantic proposals and index, plus the execution manifest with justified fallback only if a measurable physical trigger requires one.
3. Run exact offline and positive/negative compatibility proofs for each case; implement and test `process-saved` finalization, independent delivery acceptance and comparison audits, then rerun the exact strict gate. Keep the unresolved judgment unlabeled.
