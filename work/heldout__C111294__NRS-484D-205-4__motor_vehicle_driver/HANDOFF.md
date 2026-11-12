# heldout__C111294__NRS-484D-205-4__motor_vehicle_driver: CPU preparation checkpoint

## 2026-11-11 original lamp and forward-motion measurement

`backup_lamp_measurement.py` now joins original equipment inventory, body
heading/velocity and Native backup-lamp state readbacks with the frame map for
every tick. It reports forward-motion frames and their overlap with the Native
lamp-state bit. It keeps actual emitted pixels and legal outcome unknown until
a separate source-bound rear-view pixel review exists; a state bit alone does
not prove lighting. No transition allowance is inferred from the planning
summary because the exact statute states the forward-motion condition without
one.

Two CPU tests pass for reverse/forward intervals, Native state overlap,
wrong-actor rejection and missing state rejection. Run `.venv-cpu/bin/python
-m unittest discover -s work/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/tests -v`;
`cpu-tests.log` SHA-256 is
`2ffabec6609e2b2a3ad26ec07878eb1eb7ba6cf97f7709cd2104b6ebd9d49209`.
Scoped complete passes; scoped strict rejects the truthful partial status.
Next, construct the first exact Native forward-motion case and four-camera
source capture, verify actual backup-lamp equipment capability and source
pixels, then prove exact offline, positive/negative compatibility and saved
processing. Preserve the conditional review's pending source and human audits.

## Frozen scope and source

- Law: NRS 484D.205(4) — Any motor vehicle may be equipped with one or more backup lamps either separately or in combination with other lamps. Backup lamps shall not be lighted when the vehicle is in forward motion.
- Cell/actor: C111294 / motor_vehicle_driver; layout `intersection`, maneuver `travel`, control `other_vehicle`.
- Exact input: `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/assignment.json` (SHA256 `46b011125b6f55d2eaa0ba343af53f19b8fe307e0f44de6dae25b38ff6a0481c`).
- Witness: `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/witnesses.json`; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: sig.reverse_lamp, kin.velocity, drv.backing, kin.heading, kin.speed.

## Required source and construction review

1. Construct the intersection route and a separate other vehicle's position, motion, priority and purpose.
2. Establish qualifying motor-vehicle classification and installed backup-lamp inventory.
3. Retain actual forward-motion intervals with synchronized heading, velocity, speed and lamp illumination.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C111294__NRS-484D-205-4__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## Conditional review and planned comparisons

The witness in `inputs/heldout__C111294__NRS-484D-205-4__motor_vehicle_driver/witnesses.json` cites `inputs/planning/law-split-demo-overlap-v2/reviews/NRS-484D-205-4.json` with source SHA256 `9bfc9ded14ad3093469812fd1a6a49acc63f5585df51153c665684cbb9efebe2`. Its verdict is `accept_conditional`; `source_audit_status` is `pending`, `human_review_status` is `unreviewed`, and `physical_feasibility` is `unverified`. The review says the separate other vehicle's mere presence supplies no activation evidence. These conditions are retained, and no physical fact or statutory outcome is claimed from this review.

`case-plan.json` now plans the exact cases `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__no_backup_lamp_installed`, `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_off`, and `heldout__C111294__NRS-484D-205-4__motor_vehicle_driver__forward_backup_lamp_on`. The first comparison varies optional equipment presence; the second varies lamp illumination while holding the forward route and other-vehicle context fixed. Every case requires actual blueprint equipment inventory, Native light state, synchronized forward heading/velocity, and full-decoded rear-facing pixels. These are planned only; no CARLA illumination capability or original footage has been verified.

## 2026-11-11 source-bound pixel audit continuation

`lamp_pixel_audit.py` binds an independent per-forward-frame rear-lamp pixel review to all four retained original camera SHA-256 values and a full-decode receipt with exact frame counts. It rejects stale camera bytes, omitted forward frames, incomplete decode, absent rear-detail view and visible emission conflicting with an empty equipment inventory. This is a CPU audit implementation; tests use small placeholder camera bytes and do not establish actual emitted pixels, Native visibility, physical completion or a legal result. The review must be filled from actual original footage after capture. Six tests pass in `cpu-tests.log` (SHA-256 `aed3df723b14e85d32af1842bd436fc76a20438dd0e1f5a9542dfdf71c40e50b`).

The current `.venv-cpu/bin/python runtime.py preflight` passes with the pinned environment. Exact next CPU work is a CARLA-lazy intersection runner retaining equipment, motion, lamp state and four cameras, then an exact first-case offline/positive-negative compatibility/saved-processing proof. Expand the other two exact cases, three distinct fallbacks each, semantic proposals and independent comparison/delivery audits. Keep the conditional source-hashed review pending. Scoped strict gate must pass before changing `partial`.

## 2026-11-11 original Native recorder continuation

`lamp_source_capture.py` now retains equipment identity and synchronized original-tick heading, velocity, full Native light-state integer and reverse-light-mask readback. Its CPU fake exercises a state transition and rejects missing/unordered frames and wrong equipment actor. It does not infer installed hardware from the Native state; the equipment inventory remains a separately sourced requirement. Eight unit tests pass in `cpu-tests.log` (SHA-256 `253556d25a873cb6669dd0b532d81241607414acde581ddf08fc9cc0a11a2964`). Scoped complete passed; scoped strict still rejects partial in `strict-gate.log` (SHA-256 `89a30e1a059e90fd63013ce8013c90439599f8902cd242e9ccbbf37d716c8292`). Next CPU action is integrating the recorder with the exact CARLA-lazy intersection runner and four-camera capture, then the selected saved-only finalizer and first exact offline/compatibility/saved proofs.

The source-recorder test now passes its generated original motion, equipment and canonical frame map directly into `backup_lamp_measurement.measure`, preserving the forward/lamp-state frame join. Current eight-test log SHA-256 is `b952e50d61616e175c97345fbccf93f9f5611c97db3879eefb8ae27719f4f4ae`.
