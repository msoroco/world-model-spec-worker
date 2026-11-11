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
