# C405341 NRS 484B.267(2)(c) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `6064afd7880b0185db0de8a665f52d6441c3239908b6aa7449d19842b977c432`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`emergency_motion_probe.py` requires sourced emergency/regulatory authorization, qualifying flashing-light and route context. It binds original frames for actual emergency-unit displacement, driver-view cue visibility, ego approach, flashing lights, ego braking response and officer direction. It rejects nonvisible movement, visibility flags without movement, missing source bindings and unqualified vehicle class. It leaves preparedness unresolved and does not require an actual stop under this clause.

`case-plan.json` now plans six exact cases and four controlled comparisons for movement visibility, ego response, officer direction and qualifying vehicle/cue alternatives. Each case has a physical risk assessment. These plans do not claim capture or delivery readiness.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `10de44f5c7aebb8744b58de72158afb142c3c69b0c5116e46e456c5dc407c81d`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C405341__NRS-484B-267-2c__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `eaa477f65f122575cce3c82819dc057edcbf20b8ec22a727a5585aea8626f4fe`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2c__motor_vehicle_driver`: exit 0, `static.log` SHA256 `7c575d4f9820be6300e0b723fbf247a5b4f7820feb27e9393ec6d8f58a225d20`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C405341__NRS-484B-267-2c__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects truthful partial status.

## Next CPU work

Construct authorized emergency and regulatory official vehicle actors, qualifying flashing equipment, actual visible movement and separate hand-signal cue, officer direction and ego approach/response controllers in CARLA. Bind driver-view visibility and original motion/control packets; implement exact saved finalizers. Add exact offline construction and positive/negative compatibility receipts, semantic proposals, saved-only processing, independent delivery/comparison audits, manifest and queue entries. Read DEF-NRS-484A-480-3 and preserve officer-direction exception. Actual movement and visual cue visibility require later CARLA verification.
