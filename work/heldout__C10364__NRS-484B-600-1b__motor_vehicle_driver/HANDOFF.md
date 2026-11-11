# heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver: CPU preparation checkpoint

## Frozen scope and source

- Law: NRS 484B.600(1)(b) — It is unlawful for any person to drive or operate a vehicle of any kind or character at: Such a rate of speed as to endanger the life, limb or property of any person.
- Cell/actor: C10364 / motor_vehicle_driver; layout `alley`, maneuver `travel`, control `person`.
- Exact input: `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/assignment.json` (SHA256 `c5bac8329baa1a05a6bd8b0f93ebc799b83b7cda9088e67ab6256b20c7866b63`).
- Witness: `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/witnesses.json`, source index 200; conditional witness is a planning lead, not physical or legal acceptance.
- Existing accepted recordings: 0; no source-backed reuse is claimed.
- Source observation terms: kin.speed, drv.time_to_conflict, rel.surface_gap, ru.pedestrian, drv.vulnerable_road_user, drv.stopping_distance, rel.contact, st.obstruction.

## Required source and construction review

1. Construct the person's location, motion and owned property relative to the ego route and verify alley clearance and actor support.
2. Establish qualifying motor vehicle, driving or operation, driver identity and automation status.
3. Establish qualifying vehicle, driving or operating activity, physical control and automation status.
4. Leave endangerment and all surrogate cutoffs unresolved; preserve missing statutory definition references.
5. Preserve life, limb and property as protected interests without requiring contact, injury or damage.
6. Realize the person as a stationary pedestrian beside the alley, as a construction choice rather than a catalog classification.
7. Retain speed, time to conflict, surface gaps, stopping distance, pedestrian and vulnerable-road-user observations, obstruction geometry and any contact outcome.
8. Specify alley geometry, clearance, the person's stationary location and owned property's geometry relative to ego.

## Current result and exact next CPU actions

Status is **partial**. No executable case, fallback, source measurement, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Decompose alternatives and exceptions; map them to controlled exact cases and comparisons, using an additional compatible cell only if the fixed cell cannot carry a branch. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

Resume gate: `.venv-cpu/bin/python worker_check.py --assignment heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver --complete --require-delivery-ready`.

The external CARLA run is a later operator action; remaining CPU omissions above are not external blockers. No GPU command has been executed.

## 2026-11-11 CPU continuation

The pinned `.venv-cpu/bin/python runtime.py preflight` now passes with the installed
NumPy/FFmpeg/Lean toolchain. The previous dependency diagnosis is obsolete.

`case-plan.json` now plans six exact cases: `__person_3mps`, `__person_5mps`,
`__person_7mps`, `__property_3mps`, `__property_5mps`, and `__property_7mps`
(each prefixed by this assignment ID). Its three comparisons sweep measured speed
for each protected interest and compare which object is nearer at the 5 m/s
target. These speeds are engineering probes; no statutory numeric boundary or
expected endangerment verdict is asserted. The frozen evidence inventory has zero
recordings, so neither branch claims existing-evidence reuse. Life and limb share
the same stationary pedestrian exposure; owned property is measured separately.

`alley_geometry.py` constructs a route-relative stationary pedestrian and property
position and rejects placements outside the alley or overlapping the nominal
vehicle corridor. Its CPU tests exercise both travel directions and a rotated
route. `alley_source_capture.py` writes measured original-tick ground footprints
and ego motion readbacks for three distinct Native actors and rejects missing
frames or bad geometry. `alley_measurement.py` reads those retained sources with
trace and frame-map, joins Native identities and times, measures original-frame
speed and surface gaps, and rejects missing sources and participant changes. It
also computes a forward-projection time-to-station proxy and a braking-distance
proxy from the original instantaneous acceleration. The braking proxy is unknown
when deceleration is absent; neither proxy is a legal cutoff. Nine tests pass:

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/tests -v`

The log is `cpu-tests.log` (SHA256
`2aaf660032db924d72109a5a3c5231fb5982ccf89b2f8f5dde34d0a923a97daa`),
also recorded in `result.json`. The checkpoint
command `.venv-cpu/bin/python worker_check.py --assignment heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver --complete`
passes static checks in `worker-check.log`. This is **partial**: the case plan is
not yet an executable case package. Next, select and verify a real C10364 alley
route and participants in a CARLA-lazy runner, retain four named camera sources
and original footprint/motion sources, then finish the first `__person_3mps` case
through exact offline, positive/negative compatibility and saved processing before
expanding its comparisons and risk-triggered fallbacks. Bind the raw-source
proxies through the finalizer and implement all audits and semantic proposals.
Rerun this assignment's strict gate after all CPU proofs pass; keep
physical motion and visibility as later GPU checks.

The rerun of `.venv-cpu/bin/python worker_check.py --complete --require-delivery-ready`
still fails with `Preparation acceptance failed: partial/missing packages remain`;
see `work/_shared/batch-strict-gate.log`. This package remains partial for the
CPU tasks above, as do other incomplete assignments. The failure is not a tool
or package dependency failure.
