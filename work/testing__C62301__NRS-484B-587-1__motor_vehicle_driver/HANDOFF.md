# C62301 NRS 484B.587(1) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `452e7106d1cf8d36f448e781b710f5aaae7a6fc73336ec109a20a1769cddf6d2`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`access_probe.py` requires source-bound public-authority controlled-access determination, highway boundary and official erected device inventory. It computes original-frame route boundary crossings and checks entry/exit direction and crossing location against designated, visible-notice access points. It rejects missing authority, an unerected device, absent route sources and no crossing. A map road type alone is never treated as legal controlled-access status.

`case-plan.json` now plans five exact cases and three controlled comparisons for indicated versus unindicated entrances, notice visibility and indicated versus unindicated exits. Each case states a physical risk. These are plans, not delivery or capture claims.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `422020f6e4e43f6838ac4fa207d9ed0c76a939796d06729580d320577e39bf7b`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C62301__NRS-484B-587-1__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `c4b1758da37bc24876a18733574a710b4231e9d94d0936c83bd3976ef2e62eee`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C62301__NRS-484B-587-1__motor_vehicle_driver`: exit 0, `static.log` SHA256 `7316dd21f061a353ca071514f51a6bc8b7b8eed700915d521f4cca16a6319bb8`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C62301__NRS-484B-587-1__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects truthful partial status.

## Next CPU work

Source the actual authority access determination and notice designation; construct physical highway entrances/exits, erected official devices, route controllers and capture of original vehicle path and notice visibility. Add exact saved finalizers, offline construction and positive/negative compatibility receipts, semantic proposals, saved-only processing, independent delivery/comparison audits, manifest and queue entries. Recheck full law and contracts. Actual boundary crossing and device visibility require later CARLA verification.
