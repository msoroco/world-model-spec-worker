# NRS 484B.307(12)(a) C230247 motor vehicle driver handoff

Status: ready for canonical GPU delivery. Exact scoped CPU strict gate passed on 2026-11-26. No original Native capture, physical acceptance, or legal verdict is claimed.

## Exact cases and proof

- Condition a: target lane -1 under the arrow; construction SHA-256 `181f14a5b007950063d94e1da21143f1fb1350353a29afaec2777d58e3bad290`; compatibility receipt SHA-256 `ca27ffdcc51f37eae6ed1ef90aaf633c5660dc2b3f1a831fde99bd345a6b5150`; physical receipt SHA-256 `e9825491772d516c02ee8cf277ddd1319a7928a1fa06965ed449e10359b58a4f`.
- Condition b: target lane -2 adjacent to the arrow; construction SHA-256 `9b09addaedef7dfe1e267b9f9ecdecb7cba1c85bcca58b47e7c7c109d552dc49`; compatibility receipt SHA-256 `e2e1f40c096d29c95eeca25ff30d999570ab9c6cddf61978f2b1970f252d04d1`; physical receipt SHA-256 `5d466152eae78f53c19884ee66815e8858a430b3e5466caffdfa5171a141f5d4`.

Current-runtime offline, public diagnostic positive and missing-source negative compatibility, six source-derived synthetic physical outcomes, and four saved-only positive/missing-source paths passed. The saved-only proof preserves originals and covers 600 joined frames in each path. The saved-only test ran before receipt annotations were bound into the final manifest; construction and finalizer bytes were unchanged by that binding.

The six-stage semantic proposal chain passed canonical validation. Independent delivery and comparison source-structure checks passed their positive and missing-source/changed-map negatives. These diagnostic checks establish CPU readiness only.

## Original delivery and review

NRS 484B.307(12)(a) permits a driver facing a downward green arrow to drive in the lane over which it is displayed. Condition B tests an adjacent lane without asserting that the green arrow prohibits it. At GPU delivery, require original Native overhead lane-control actor ID 100, exact `green_down_arrow` state, map lane validity, the driver-facing signal pixels, original actor body lane, and four synchronized cameras. A generic green traffic light is rejected. Independently review official device authority, actual pixels and physical completion before acceptance.

First command: `PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment training__C230247__NRS-484B-307-12a__motor_vehicle_driver --case training__C230247__NRS-484B-307-12a__motor_vehicle_driver__selected_378a10ff__condition_a --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT`

Exact scoped check: `TMPDIR=$PWD/.runtime-work PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c230247 .venv-cpu/bin/python worker_check.py --assignment training__C230247__NRS-484B-307-12a__motor_vehicle_driver --complete --require-delivery-ready`

Manifest SHA-256: `ba1289882122b59e272f6dcbc9bf9fe293aa361cb040a570df8d4c676e34eb9b`. Recorded-only proof SHA-256: `0becf050eaceca8740c3809e10f7aaa11f9b19bf13640a7afbfe608eb8e2e4dc`. Semantic index SHA-256: `59eec576fafade42c94bb613b80842a9368b3cb09cb257e589880f468d303ee0`.
