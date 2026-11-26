# C111325 / NRS 484B.257(1) CPU checkpoint

Status: partial. None of the ten planned cases is selected for delivery. No original Native event, legal verdict, physical success, or accepted-recording reuse is claimed.

The frozen witness is a stop sign, marked stop line, and through-highway occupancy in cell C111325. The exact statute also covers the yield-sign alternative, the stop-line/crosswalk/nearest-viewpoint hierarchy, the duty while crossing or within the intersection, and police and signal-control exceptions. Existing nine demo and nine full-train membership rows are not source-hashed proof of what those recordings show; inspect the frozen evidence inventory before allocating duplicate recordings.

## Constructed diagnostic

`stop_yield_scene.py` authors perpendicular roads, a governing STOP sign, a marked approach line, a through-highway vehicle, distinct ego controller policies, and four cameras for 600 frames at 20 Hz. `measure_stop_yield.py` requires hashes of original map, sign, line, road, vehicle bodies/motion, control state and visibility, joins every Native frame to four camera identities, and measures front-bumper line crossing, recorded pre-line rest, the full intersection crossing interval, and simultaneous through-vehicle occupancy. `stop-yield-measurement-contract.json` records the engineering diagnostics and unresolved legal judgments.

Run `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_stop_yield.py`. The generated `stop-yield-proof.json` contains source-shaped synthetic fixtures for `complete_stop_then_yield` and `roll_through_conflict`, plus six negative source, control, frame and camera tests. Fixture hashes and motion are synthetic; the proof is not an exact runtime offline/compatibility or process-saved receipt.

## Source review and statutory plan

`case-plan.json.evidence_review` inspects all nine unique accepted membership rows against their frozen review summaries and hashes. The frozen summaries describe requested stop actions, four stopping-reference alternatives and three through-traffic phases; most hazard/yield judgments are unresolved. They do not supply original Native packet hashes or independently audited full crossing histories. No equivalence reuse is asserted. The five explicit gaps and each case gap ID are in the plan.

Ten exact cases and seven controlled comparisons now account for STOP versus YIELD, the stop-line/crosswalk/nearest-viewpoint hierarchy, through-highway entered versus approaching traffic, continuing duty while within the intersection, and separate officer/signal control exceptions. `stop_yield_scene.py` emits source-distinct requests for each; `prove_branch_requests.py` checks all ten requests and rejects missing crosswalk, viewpoint, exception source and altered governing sign. These remain authored scene requests, not CARLA-validated exact runtime constructions.

## Remaining CPU work

Acquire original accepted recording source packets if reuse is pursued; current summaries do not justify reuse. Select exact cases, implement the pinned runtime construction/controller and source acquisition, run exact offline and positive/negative compatibility for primary and risk-based fallbacks, run actual saved processing, then implement independent delivery and comparison audits and semantic proposals. Promote only after the scoped strict gate passes. CARLA execution, pixel review and canonical acceptance remain local operator work.

## Latest CPU checks

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_branch_requests.py`: passed ten scene requests and six negative checks.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_stop_yield.py`: passed two source-shaped diagnostics and six negative checks.
- `SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/nrs257-output TMPDIR=$PWD/.runtime-work/nrs257-tmp .venv-cpu/bin/python -B worker_check.py --assignment training__C111325__NRS-484B-257-1__motor_vehicle_driver --complete`: passed static partial check.

## Saved-source measurement core

`measure_statutory.py` measures each of the ten exact planned branches from 600 joined 20 Hz source rows. It records governing sign, reference hierarchy, original body extents, pre-reference rest, full intersection occupancy, through-highway entered/approaching frames, and source identities. Officer or signal control is a distinct observed exception. It never assigns an immediate-hazard or legal verdict. `measure_saved_packet.py` checks the bytes of seven declared saved source files and a 600-row motion packet before calling the meter; paths cannot escape the saved attempt. This is a reusable CPU core for later exact finalizers, not a runtime compatibility or accepted Native receipt.

- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_statutory_measurement.py`: ten source-shaped measurements and seven negative checks passed.
- `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C111325__NRS-484B-257-1__motor_vehicle_driver/prove_saved_packet.py`: saved packet byte-binding and changed-source, wrong-case and path-escape rejection passed. Disposable packets were created only under `.runtime-work/`.
