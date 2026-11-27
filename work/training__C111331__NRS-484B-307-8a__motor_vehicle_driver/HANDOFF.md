# C111331 NRS-484B-307-8a handoff

Assignment: `training__C111331__NRS-484B-307-8a__motor_vehicle_driver`. Frozen cell: intersection / straight travel / traffic light. Actor: motor vehicle driver.

## Canonical delivery

Probe A is the full stop before the sourced applicable reference, red hold and green departure. Probe B continues through that reference while red. The two cases share one comparison; the 24-case statutory review is separate planning analysis. Four synchronized views at 20 Hz for 24 seconds provide 480 frames per case.

Law topics text-0 and text-1 are selected here. Text-2 and reviewed-scope-0 are mapped in case-plan.json to the separate right-turn C110919 assignment where applicable; left-turn and paragraph (d) are not claimed by this frozen straight-travel pair. The stop reference follows the sourced crosswalk/sign/marking hierarchy and falls back to intersection entry only when those references are absent.

## CPU evidence

Exact constructions: probe A `07d9a14072a3574ca265dde883e2f285286bfaf11cb06910418f5e476d01fb07`; probe B `d40dd4b1aaceea06d12ba49db0b32c71f0e8127ea0855ce8a75800f2c55a9f0c`.

Each case passed runtime.py offline, runtime.py compatibility with positive and missing-source negative fixtures, and runtime.py process-saved on 480-frame/four-camera diagnostic sources. Both saved-only receipts preserve source hashes and make no original capture claim. Synthetic physical fixtures distinguish met/not-met/unverified; lifecycle rejects owner release before Native exit. Independent delivery-audit selftests pass positive and reject missing original Native negative. Semantic stage validation passed seven stages with two selected cases. Comparison/unit tests passed nine tests.

Original Native signal state, governing head, stop reference, physical motion, actual pixels and legal outcome remain pending capture and independent review. Existing four membership IDs lack source-hashed original receipts and are not reused.

## Reproduce

`.venv-cpu/bin/python worker_check.py --assignment training__C111331__NRS-484B-307-8a__motor_vehicle_driver --complete --require-delivery-ready`

First GPU command: `PYTHONPATH=runtime:runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange execute-delivery --repo . --batch full-train-delivery --db $DB --assignment training__C111331__NRS-484B-307-8a__motor_vehicle_driver --case training__C111331__NRS-484B-307-8a__motor_vehicle_driver__probe_a --run $RUN --job $JOB_ID --python $CARLA_PYTHON --host $CARLA_HOST --port $CARLA_PORT`

The case-plan, execution-manifest, proof logs, physical receipts and delivery audit scripts are under this assignment directory.

## Strict gate

The assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment training__C111331__NRS-484B-307-8a__motor_vehicle_driver --complete --require-delivery-ready` completed with exit code 0 on 2026-11-27 after all bound CPU proofs. Batch-wide delivery readiness is separate and still depends on the remaining assignments.
