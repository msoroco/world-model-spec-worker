# C24751 NRS 484B.310(1) heavy vehicle checkpoint

Status: partial CPU construction. Exact frozen assignment SHA256 `45337737418c28885bb05ac8cc0b8e5310f20c77df61ea97274bc7ff5ecc008c`; no accepted recording is listed in frozen evidence.

## Constructed and tested

`flashing_red_probe.py` selects surveyed crosswalk, marked limit line, or intersection entry alternatives for separate fixtures. It rejects a signal that governs a different approach, missing official device identity, missing actual occluder polygon, and a heavy vehicle too wide for the selected lane. Its rectangular sight-line segment test checks whether an occluder lies between the approach observer and target. Its original-frame probe requires bound motion and signal sources, monotone frame/time history, and intermittent red transitions, and records whether complete cessation occurred with the vehicle front before the surveyed reference. It does not infer a legal speed epsilon or a right to proceed.

`case-plan.json` now has four exact proposed cases and two comparisons: crosswalk stopping position, and the crosswalk/marked-line/unmarked-intersection reference alternatives. Each case has a physical risk assessment. The frozen evidence gap is explicit. These plans are not capture or delivery claims.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0, `preflight.log` SHA256 `ca171cb5845c4c9bd7f8080afab15b00e66159dbbcc2623ea477973b1e77f2cf`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C24751__NRS-484B-310-1__heavy_vehicle_driver -p 'test_*.py' -v`: exit 0, five tests, `cpu-tests.log` SHA256 `57d30880e782825de024d74f46e6080ef0cea486591ad3045b96017d936eea70`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C24751__NRS-484B-310-1__heavy_vehicle_driver`: exit 0, `static.log` SHA256 `c42430852ee4e57935b2bbeb09a3aab2cd5010d674eb05c473c298c1ea0e8d17`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C24751__NRS-484B-310-1__heavy_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`; strict checker rejects the truthful partial result.

## Next CPU work

Implement exact CARLA construction for the surveyed official flashing signal, occluder, heavy vehicle, route and cameras; bind original packet capture/finalizer to each case. Resolve incorporated post-stop rules from their sources without substituting a yield-only rule. Add case-specific offline and positive/negative compatibility recipes, semantic proposals, saved-only processing, independent delivery and comparison audits, and exact manifest/queue entries. Recheck the full law, inputs, risk fallbacks and every exact case before marking ready. Physical occlusion, motion, pixel coverage and capture quality require a later CARLA run only after CPU preparation passes.
