# C378809 / NRS 484B.477(1)(a) CPU handoff

Status: **partial**. All three delivery probes remain unselected. `case-plan.json` lists the statutory requirement as `selected_required` for the partial-package validator; that is a planning obligation, not a selected case or covered branch.

## Exact source and cell

- Current assignment SHA-256 `9403da615d8a0634526601f205cf715edf4e9cdfd99d3ea8f9fb410534c0a736`; witnesses SHA-256 `1900c0e356518fc1aa1a92ae97259c2fe7c464676b439adfd37d1a918c9d04b2`. No accepted recordings are listed.
- Fixed cell: `business_district_alley / park / alley_entrance`, actor `motor_vehicle_driver`. Exact text prohibits stopping, standing or parking within a business-district alley unless local ordinance provides otherwise or the stop is for expeditious loading/unloading of goods. The witness is conditional and low confidence; it asks for statutory alley/highway and district frontage facts and local authority context. Commercial vehicle status is not an element of this exact text.
- Probe 02 requests parking without loading. Neither that request nor an open door proves goods activity or its absence. “Expeditious” has no invented numeric cutoff; the CPU reducer reports elapsed dwell only. No expected legal label is assigned.

## CPU construction and proof

- `alley_dwell_measure.py` SHA-256 `e806c59619c32235eee9c8a2cf8e944816b9c096e1c389508055a32eafd51cac` requires source IDs for alley boundaries, public highway use, city block, rear service, entrance, non-cul-de-sac status, business-district frontage/building uses and ordinance jurisdiction/applicability. It joins 600 contiguous 20 Hz frames to the same vehicle, measures in-alley rest with an explicit 0.05 m/s sensor tolerance, records observed goods-transfer event IDs, and leaves expeditiousness and legal result null. `prove_alley_dwell.py` SHA-256 `a3cec3dc14aed73d03def32b8e8a6b7a719d7514f3600dd0d4d50d51ee69d0bd` runs synthetic goods/no-goods positive diagnostics and negative ordinance, district and goods-source tests, binding current input hashes. Normal and `-O` proof logs each SHA-256 `27dd859951000131e3bbaaff0d692ca2ece1b9f921e5a6724578b3f2cfbb8836`. Synthetic samples are CPU diagnostics, not original Native evidence.
- `native/runner.py` is an executable original-survey-gated CARLA draft for probe 02. It has a park-at-surveyed-point controller, four source cameras, 600-frame 20 Hz PipelineCapture, FrameMap, and post-tick original position/velocity trace. `requested_no_loading` and `no_goods_verified: false` remain distinct. Construction SHA-256 `7526b3c149ea48a326b9ec738b66803c4f66420dcaa1a817b8b039321cb661e9`; partial manifest SHA-256 `319af390785c0123a3343ecb7def1dd97349c09aa70c50efdd13c25002a59d20`. Four Native CPU tests pass (log SHA-256 `22a501d2965c92becc4ec2967f53cf2c242dea34fcc58068a8f81b5505e29b2a`). Pinned `runtime.py offline` passes with `simulation_started: false` (log SHA-256 `80c7833c38350e28846a6a5ebd2e4b744f29f901ee1633fb9da1faab02758e0e`).
- `.venv-cpu/bin/python worker_check.py --assignment training__C378809__NRS-484B-477-1a__motor_vehicle_driver --complete` passes static checks. No strict ready claim is made.

## Remaining worker-owned CPU work

1. Bind an original source-hashed site survey with statutory alley geometry/public-use facts, business-district 600-foot and 300-foot frontage/building-use evidence, exact entrance/parking endpoint and applicable local ordinance. The frozen cell label and witness alone do not prove these.
2. Implement saved processing that derives in-alley occupancy and stopped duration from original pose/map, and independently reviews goods movement and four videos. Absence of a scripted goods actor does not prove absence of goods activity. Keep purpose and expeditiousness separate from elapsed time.
3. Source-review and select exact cases only when justified, then build the loading and extended-dwell comparisons, risk-based candidates, current-runtime positive/negative compatibility, saved processing, semantic proposals and independent delivery/comparison audits. Run strict assignment ready gate only after these CPU proofs pass; Native physical realization and acceptance remain local execution work.
