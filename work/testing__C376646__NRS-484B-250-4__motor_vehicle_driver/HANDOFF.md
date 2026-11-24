# C376646 NRS 484B.250(4) motor vehicle checkpoint

Status: partial CPU construction. Frozen assignment SHA256 `ff3f105b368edcf1abc866389aaa5aa9cd0c3a1604175df93d6308f94f49ff3a`. Frozen evidence has no accepted recording for this assignment.

## Constructed and tested

`inoperative_signal_probe.py` selects the statutory stop reference hierarchy: marked stop line, then near-side crosswalk, then surveyed nearest-view point. It binds original-frame ego motion and signal status, requires an installed uncovered inoperative signal at intersection entry, observes complete cessation at or before the selected reference, and identifies distinct vehicles with a prior completed stop or within-intersection occupancy. It rejects missing source bindings and wrong signal governance. It leaves cautious proceeding unresolved rather than inventing a speed threshold.

`case-plan.json` now has six exact planned cases and three controlled comparisons for priority interactions, stop-reference alternatives and late-stop position. Each case has a physical risk assessment. Plans are not capture or delivery claims.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `466389424fae7c3bade185ea36bc8352b0d49bc1736a1e4bb8fd62b11ce633a1`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C376646__NRS-484B-250-4__motor_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `7505fab72d2800fdebcdc8d17b4584b2894935f93ebcc8c8070022c443c614e7`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver`: exit 0, `static.log` SHA256 `61f61d4613193e63b7817d3e4fd26b167d06c4bf64fc9d1ac5e74864db32f2fe`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects the truthful partial result.

## Next CPU work

Construct the installed but uncovered fully inoperative signal at the actual entry frame, each surveyed stop reference, physical blind sight line, through-highway context and other-vehicle stop/occupancy controllers in CARLA. Bind original packet capture and exact saved finalizer for each case. Add exact offline and positive/negative compatibility receipts, semantic proposals, saved-only processing, independent delivery and comparison audits, manifest and queue entries. Review cautious proceeding against source context without a fabricated cutoff. Recheck full law and contracts. Actual motion, signal state, occlusion and pixel coverage require later CARLA verification.
