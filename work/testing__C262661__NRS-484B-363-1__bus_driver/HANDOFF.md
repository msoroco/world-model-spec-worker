# testing__C262661__NRS-484B-363-1__bus_driver

Status: partial, source-gated CPU construction and analysis checkpoint. No original CARLA recording or legal/physical acceptance is claimed.

## Frozen scope and selected coverage

Assigned branch: Motor bus in a school zone with children. Law: NRS 484B.363(1) and beacon definition in subsection (9). Cell C262661, bus_driver. Frozen accepted recordings: zero. The 15-mph rule, four exceptions and two-or-more alternating-yellow-light definition are mapped to seven selected requirement dispositions in `case-plan.json`; all source facts remain independently reviewable.

Exact cases (15):
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_14_9`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__no_session_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__after_operation_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__before_next_start_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_not_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_off_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_on_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_one_yellow_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_non_alternating_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__outside_zone_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__no_children_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__ordinary_car_15_1`

Exact controlled comparisons (12):
- `below_versus_at_15_mph`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_14_9`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`
- `at_versus_above_15_mph`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`
- `school_not_in_session`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__no_session_15_1`
- `half_hour_after_operation`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__after_operation_15_1`
- `half_hour_before_next_operation`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__before_next_start_15_1`
- `class_hours_beacon_flashing`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_not_flashing_15_1`
- `nonbeacon_sign_time_indication`: `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_on_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_off_15_1`
- `two_yellow_light_definition`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_one_yellow_15_1`
- `alternating_flash_definition`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_non_alternating_15_1`
- `designated_zone_boundary`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__outside_zone_15_1`
- `children_presence_is_not_independent_exception`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__no_children_15_1`
- `bus_versus_other_motor_vehicle`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__ordinary_car_15_1`

## Current construction and CPU proofs

`school_scene_construction.py` and `school_timing.py` require a reviewed 16-record source-hashed school site, bus/driver/children, designated zone and route, calendar/clock, and beacon/sign facts. `runner.py` additionally checks the reviewed operator hash and loaded OpenDRIVE bytes. `native_capture.py` checks 900 consecutive 20-Hz bus/child/body/device readbacks and four synchronized FFV1 camera streams and restores world settings. `native_output_bridge.py` publishes exact source frames, adapter graphs, evidence, frame map and Native seal. `analysis.py` separates bounded diagnostic measurement from original 900-frame saved finalization. `comparison_audit.py` rejects changed fixed sources and missing declared differences. All are CPU-tested; original motion remains unverified.

Current construction hashes are recorded per case in `execution-manifest.json`. Every one of its 15 offline commands passed with exit code 0 and hash-bound logs, against the current plan and embedded analysis. The local `gpu-queue-proposal.json` includes 15 exact production commands and 12 comparison commands. Shell-token and case/comparison-ID binding checks passed; the lead owns shared queue integration.

- `case-plan.json` SHA-256 `56f082d960a068a05bdd1787a3c6b03c7e6f1f5e6cf014843fbbe11db35e96af`
- `construction.json` SHA-256 `efcfac9007ee37da32b60c655c400a538b852fd35de626f0f8821629f58910c9`
- `execution-manifest.json` SHA-256 `0dc9ae77213881b44d3b9c28de00d2de3ab9576837405c0332a46c696aa094cc`
- `gpu-queue-proposal.json` SHA-256 `09f6e9b28656838c54fb7b6285bfc664f26f2499c0d8d4ac371debdb00d3da2c`
- `native_capture.py` SHA-256 `c02609fc34eaae54299430659cd5b7868e1faf09bd7fdfc6729c42644ad05f64`
- `native_output_bridge.py` SHA-256 `559d6e0a4ddc3bcf0a10f252ffb7c9b723022e74cd75a5abcc3b79fadef94465`
- `analysis.py` SHA-256 `982744c30c133ae487207d79c686fc263e0e1c94f6ac52e5439a357afcd1662a`
- `saved_finalizer.py` SHA-256 `38dde3f126edfac6019e9a5d25a443aa69badc7fdab5b6ec3261ec425bb3c95d`
- `comparison_audit.py` SHA-256 `31a76a97fae384608a88d6c0f372cf296115ce198149a25ea7b0fe5d99604806`
- `cpu-school-tests-nov26.log` SHA-256 `74aa91c3e4df5603fe95bd6f050a63e7906fedb7fe62380487d05a05b60e6ef3`
- `assignment-check-nov26.log` SHA-256 `5a8a41eecd92d272be71cb394065baa5466c89b04d79dc3bc55f408fe79e2edb`
- `strict-gate-nov26.log` SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`

Focused tests: `.venv-cpu/bin/python -m unittest discover -s work/testing__C262661__NRS-484B-363-1__bus_driver/tests -v`, exit 0, 21 tests. Pinned runtime verify and preflight passed. Scoped `.venv-cpu/bin/python worker_check.py --assignment testing__C262661__NRS-484B-363-1__bus_driver --complete` passed. Scoped strict with `--require-delivery-ready` exited 1 because `result.json.status` truthfully remains `partial`; this does not certify delivery readiness.

## Next CPU work

1. Bind all 15 cases to source-hashed diagnostic recipes and selected-requirement measurement contracts; run positive and negative compatibility through the pinned Native validator, converter, Lean and video path.
2. Author and validate the six canonical semantic stages and exact cases proposal.
3. Prove saved-only postprocessing, physical/lifecycle and independent delivery/comparison audits, then rerun the scoped strict gate.
4. Only after strict passes, mark ready and release the local queue proposal for shared integration. Original site/operator and physical capture remain later local inputs; missing CPU work is not an external blocker.
