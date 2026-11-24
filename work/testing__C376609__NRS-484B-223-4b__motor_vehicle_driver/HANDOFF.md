# testing__C376609__NRS-484B-223-4b__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No physical recording or delivered case is claimed.

Exact law: NRS 484B.223(4)(b): on a highway designed with a single right lane used only for turning, a vehicle driven in that lane must not travel through an intersection. Assigned cell is C376609, blind-intersection straight traversal, motor-vehicle driver. Frozen evidence inventory has zero accepted recordings and zero judgment-range entries for this exact law and actor.

## Constructed CPU work

`case-plan.json` defines nine unexecuted exact cases and eight controlled comparisons. It isolates straight-through travel from a right turn, stop before the junction, adjacent through lane, lane change before entry, nonexclusive or multiple right-turn-lane designs, alley status, and an unobstructed sightline control. Each case has an independent route intent and a capture/source request; the variants do not imply legal outcomes.

`turn_lane_observations.py` consumes a hash-sealed original Native source receipt, map context, and 20 Hz actor trace. It requires public-highway and roadway-boundary sources; lane design and exclusive control; intersection type and entry/exit bounds; straight/right routes; sightline obstruction; driver, motor vehicle and independent intent sources. It checks exact case identity, frame cadence/count, lane identities and interval bounds, then reports first frame within and beyond the intersection station interval and lane occupancy. It leaves travel-through and exclusive-lane legal judgments unresolved and physical acceptance unverified. Seven focused tests cover positive extraction, diagnostic and changed-source rejection, missing lane, malformed bounds and bad approach start.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C376609__NRS-484B-223-4b__motor_vehicle_driver/tests -v`: exit 0; `cpu-turn-tests.log` SHA256 `05e54a3a0ab723bdf1240f72d2d9a2b8caf048e494b7f45e282ea1ea2ee0f7d5`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C376609__NRS-484B-223-4b__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `df567e83768db4c22728cbf435e5969dfb549d35a5d5658d0fe1a82987aedb89`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C376609__NRS-484B-223-4b__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build and prove the exact scene and traffic controller, source-bound original Native capture and finalizer, case-specific semantic proposal, saved compatibility and processing, and delivery/comparison audits for all variants. Then run the exact scoped strict gate. Actual CARLA motion, four-camera visibility and capture quality remain physical checks after CPU preparation. Earlier dependency/tool diagnoses are no longer blockers.
