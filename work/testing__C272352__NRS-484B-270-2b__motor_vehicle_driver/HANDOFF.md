# C272352 NRS 484B.270(2)(b) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `89722507ed1c3bd0ffd23b89edbd97c65a1c3ceb795aba29cb2e96bb122925e6`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`passing_probe.py` measures the shortest body-envelope gap through original-frame longitudinal passing overlap, applies the express 3-foot (0.9144 m) floor, observes left-of-bicycle position and return-right ordering against the bicycle front, and rejects missing source bindings, non-monotone original frames, an absent actual pass, multiple same-direction lanes, invalid participant classes and invalid envelopes. This is an engineering measurement, not a conclusion about due care, safe distance, safely clear, or the incorporated NRS 484B.213/217 exceptions.

`case-plan.json` now plans nine exact alternatives and four controlled comparisons for below/at/above three-foot clearance, return ordering, qualifying participant classes, and centerline/no-passing-zone route authorization. Every case states a physical risk. These plans do not claim capture or delivery readiness.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `3ab87ec8c5a1d09e1b1318d4a932c654fae20cb853359cbe3dc57d1bd9fd92ab`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C272352__NRS-484B-270-2b__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `e27cb389cc654701783bb4ea5d9c708852e028a8c7f22e6ca010a54d75c61eb9`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C272352__NRS-484B-270-2b__motor_vehicle_driver`: exit 0, `static.log` SHA256 `f578921ccde69034aa40146ea36ec3ce45a87fe1e99a12e0dc574425bc514fd6`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C272352__NRS-484B-270-2b__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects the truthful partial result.

## Next CPU work

Build exact CARLA bicycle/electric bicycle/scooter actors, single-direction-lane public-highway route, measured participant extents, pass-left and return controllers, surveyed centerline and no-passing controls, opposing-traffic cases, packet capture and exact saved finalizer. Source the incorporated exceptions and safe-passing context without inventing a legal threshold beyond 3 feet. Add every exact offline construction receipt, positive/negative compatibility recipe, semantic proposal, saved-only processing proof, independent delivery/comparison audit, manifest and queue entry. Recheck the full law and contracts. Actual motion, realized separation and pixel visibility remain for later CARLA verification.
