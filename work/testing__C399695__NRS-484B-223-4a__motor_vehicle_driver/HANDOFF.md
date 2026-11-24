# C399695 NRS 484B.223(4)(a) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `4a9e941fc83d5b446b4f5a640e01051e65c45d4029e34c2ba479d65316db8440`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`right_turn_lane_probe.py` requires source-bound public highway, a single exclusive right-turn lane and a connected distinct right-turn exit at the T junction. It measures original-frame lane occupancy, observed connected right turn and independently sourced purpose recorded before lane entry. It rejects missing source bindings, disconnected route, nonexclusive lane design and late purpose. It keeps purpose sufficiency unresolved rather than inferring it from occupancy duration or turn completion.

`case-plan.json` now plans four exact cases and two controlled comparisons for right-turn purpose versus other purpose and purpose-route agreement. Each case has a physical risk assessment. These plans do not claim delivery or capture readiness.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `289a0a4db18b20715a41371005c71229a25653bca08a1d24493c03ff3f59cc55`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C399695__NRS-484B-223-4a__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `cab12123cc3deaa414eda1c27a1d4a3ecb3af2cbce89ea1dee740989cce65639`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C399695__NRS-484B-223-4a__motor_vehicle_driver`: exit 0, `static.log` SHA256 `34ac2ba7b6b800e062a8ec7c1b4212b33156e3e8074a8c71db8fce655c62fa5e`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C399695__NRS-484B-223-4a__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects truthful partial status.

## Next CPU work

Construct the actual single exclusive right-turn lane and connected T-junction route in CARLA; implement vehicle controllers and capture original lane-use, purpose and departure packets. Build exact saved finalizers, offline construction and positive/negative compatibility receipts for all cases, semantic proposals, saved-only processing, independent delivery and comparison audits, manifest and queue entries. Recheck full law and contracts. Actual lane occupation, turn and pixel coverage require later CARLA verification.
