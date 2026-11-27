# NRS 484B.260 at C177626

Exact law: The driver of a vehicle about to enter or cross a highway from a private way shall yield the right-of-way to all vehicles approaching on such highway.

## Selected CPU package

- Two exact Native private-way entry cases: probe_a yields through both highway arrivals; probe_b enters between arrivals. Both remain requested physical targets until original capture.
- The same authored 350 m paved highway, two approaching highway vehicles, private-way geometry, 600 frames at 20 Hz, and four synchronized cameras are fixed across the comparison. Primary and camera-visibility fallback constructions are source-hashed for each case.
- Four current-runtime offline and public positive/missing-source negative compatibility runs passed. Both primary cases passed recorded-only saved processing with original-source hashes. Semantic stage validation passed 6 stages.
- Source-shaped synthetic physical/lifecycle, independent delivery positive and synthetic-negative, and source-hashed comparison audits passed. The comparison verifies both highway trajectories fixed and measured 2 versus 1 highway vehicles before ego entry.
- Accepted memberships: none. No accepted-recording reuse is claimed. Arrival order and speed changes are evidence for independent legal review, not legal cutoffs.

## Local delivery checks

Run the exact assignment gate: `SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c177626-entry .venv-cpu/bin/python -B worker_check.py --assignment training__C177626__NRS-484B-260__motor_vehicle_driver --complete --require-delivery-ready`.

Original Native capture must verify road/lane and private-way identity, all approaching highway vehicles, continuous full-body entry/occupancy and synchronized actual pixels. Independent review decides physical completion and right-of-way from the original sources before accepted delivery.
