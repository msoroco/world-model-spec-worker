# C147331 NRS 484B.587(2)(a) delivery handoff

Status: CPU prepared for exact local Native delivery. The scoped strict gate passes. No original CARLA capture or legal acceptance is claimed.

## Legal and case coverage

The assigned prohibition concerns driving on a controlled-access highway outside a marked traffic lane or marked entrance/exit lane. The supplied text also requires an emergency necessity branch, subsection 3 authorization, and the qualifying vehicle plus lawful sign plus paved shoulder context. The 11 cases in the exact manifest cover:
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_marked`: Marked traffic lane baseline; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_outside`: Outside marked lanes and shoulder; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__south_marked`: Opposite approach marked baseline; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__south_outside`: Opposite approach outside marked lanes; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_shoulder_unsigned`: Paved shoulder without permissive sign; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_shoulder_signed_qualified`: Paved shoulder with sign and sourced 484B.210(4) class; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_shoulder_signed_ordinary`: Paved shoulder with sign and ordinary class; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_outside_emergency`: Emergency necessity context outside marked lanes; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_shoulder_authorized`: Subsection 3 vehicle and signed paved shoulder context; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_entrance`: Marked entrance lane control; retain source and original trajectory for human statutory review
- `testing__C147331__NRS-484B-587-2a__motor_vehicle_driver__north_exit`: Marked exit lane control; retain source and original trajectory for human statutory review

Nine controlled comparisons in `comparison-proposal.json` isolate approach, marked versus outside travel, signed paved shoulder, vehicle class, emergency, subsection 3, and marked entrance/exit controls. `comparison_audit.py` checks sealed 900-frame source histories and rejects stale hashes. There is no numeric statutory occupancy cutoff or exact-law judgment range in the supplied inventory.

## Construction and source boundary

`reviewed_site.py` requires separately hashed legal authority, public highway boundary, markings, lane direction, paving, sign legend/placement, vehicle class, emergency, subsection 3, Native spawn, and camera plans. `outside_lane.py` builds source-gated route variants. `lane_native.py` captures 900 frames at 20 Hz using FrameMap, four synchronized cameras, original history and receipts, then restores world settings and releases ownership. `analysis.py` finalizes from saved original evidence only; `saved_audit.py` checks the sealed chronology. The primary route uses steering gain .025 and the source-bound fallback uses .02 only after the declared route-convergence or camera-coverage trigger.

## CPU proof map

`execution-manifest.json` binds each of 11 primary and 11 fallback constructions, with exact offline logs and positive/negative compatibility receipts. `proof-saved-*.log` covers saved processing and missing-source rejection for each primary case. `physical-*-receipt.json` covers complete, incomplete and missing-evidence diagnostic outcomes plus capture-to-owner-release lifecycle ordering. `delivery-acceptance-*.json` covers independent delivery protocol positive and missing-view rejection for each case; `delivery_audit.py` requires original Native provenance, full frame joins, four-view decode and pixel review. `comparison-proposal.json` binds all nine comparison positive and stale-source negative proofs. `proposals/semantic-index.json` binds the canonical relevance, template, bindings and cases proposals. All fixtures are synthetic CPU protocol tests and carry that provenance.

## Local execution

The first exact job command is in `result.json.first_gpu_delivery_command`. Supply the reviewed C147331 source packet in `C147331_REVIEWED_SITE` and local CARLA variables, then inspect original authority, markings, route traversal, body occupancy, sign visibility, four-view pixels and physical completion before acceptance. The executor must run saved processing after Native ownership release.

## Validation

`cpu-tests.log`: nine passing unit tests. `strict-check.log`: `.venv-cpu/bin/python worker_check.py --assignment testing__C147331__NRS-484B-587-2a__motor_vehicle_driver --complete --require-delivery-ready` exit 0. The package is ready for physical verification only.
