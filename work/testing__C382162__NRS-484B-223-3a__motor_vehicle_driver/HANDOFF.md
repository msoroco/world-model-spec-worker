# C382162 NRS 484B.223(3)(a) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `225b78ce191a1b0d04cacedaa37cfd23158ffdbf514ab71292b60b4c2b706b51`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`center_lane_probe.py` requires source-bound highway status and a single shared center lane designed solely for turns by both directions. It measures original-frame occupancy, observed left-turn frames and independently sourced purpose recorded before center-lane entry. It distinguishes left turn onto and from the highway, rejects alley junctions, absent occupancy, missing route or purpose source and invalid lane design. It keeps purpose sufficiency unresolved rather than inferring it from lane distance or a completed trajectory.

`case-plan.json` now plans five exact cases and three controlled comparisons for turn direction, purpose versus trajectory, and alley classification. Each case states a physical risk. These plans are not delivery or capture claims.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `cdfe9f5cd5c14a877a9e8a6a098f5a93944bc5537b06bc8171a692063db39c60`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C382162__NRS-484B-223-3a__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `0a6636cb04eded184e7e90f360164b748235afbf589447e2b341c70a7cfbe250`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C382162__NRS-484B-223-3a__motor_vehicle_driver`: exit 0, `static.log` SHA256 `0f43c0f1ba4182c6ec5ec2da65c4c81ae8d9593bac6c0973be2fee9b38d2f156`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C382162__NRS-484B-223-3a__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects truthful partial status.

## Next CPU work

Construct the actual bidirectional shared center turn lane, highway and street intersection map geometry and motor-vehicle routes for turns onto and from the highway. Bind route intent independently before entry, capture original lane occupancy and exact saved finalizer for every case. Add exact offline construction and positive/negative compatibility receipts, semantic proposals, saved-only processing, independent delivery/comparison audits, manifest and queue entries. Review purpose evidence without an invented distance or time cutoff. Actual lane use, intersection geometry and pixel evidence require later CARLA verification.
