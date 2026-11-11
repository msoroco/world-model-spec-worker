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

### 2026-11-11 saved-only finalizer checkpoint

`alley_finalizer.py` now consumes the retained `participant_footprints.jsonl`, `ego_motion.jsonl`, `trace.jsonl` and `video_frames.jsonl` through `alley_measurement.measure`, checks the exact six-case identity, writes separate pedestrian/property original-gap channels and provenance hashes, and calls the pinned `physical_result` for source-based physical status. An original body-center before/after check records pedestrian and property passage separately. It returns false physical/legal acceptance and makes no legal speed cutoff. A synthetic original-source test validates the worker Native result schema and checks positive passage, wrong identity and missing motion source. The local suite now passes 17 tests (`cpu-tests.log` SHA-256 `2a0064aafe7242478a2a959aa92caab0b982a45b6ca2bceff85a28a2fb496402`). Assignment-scoped `worker_check.py --complete` exits 0. This is a saved-processing component proof, not an exact `runtime.py process-saved` receipt: the source-backed alley polygon, Native runner, construction/manifest and saved execution remain to be built. Status stays partial.

### 2026-11-11 exact settings, Native capture and semantic stage checkpoint

`alley_case_setup.py` validates all six exact person/property 3/5/7 m/s engineering cases, 160 original frames at 20 Hz, a named hashed alley polygon source, source coordinates matching the selected polygon, and a five-metre usable alley width. `native_alley_cases.py` is CARLA-lazy: it selects a source-bounded connected route, places and retains distinct Native subject, stationary pedestrian and property actors, captures original footprint/motion/trace/frame-map sources plus the four named lossless cameras, confirms extraction only after a complete capture, restores world settings and seals the completed lifecycle. The copied `alley_camera.py` enforces four synchronized original source streams. No exact source polygon has yet been selected or claimed; the synthetic polygon in the unit test proves the guard and tests source tamper rejection, not alley existence on a target Native map.

`build_semantic_proposals.py` now authors the exact-law relevance, template, judgment observables, alley binding and six selected case proposals with source hashes. `validate_semantic_stages.py` runs the pinned canonical stage validators successfully. The judgment sweep is explicitly incomplete because exact source geometry and generated points are not constructed; it does not insert a legal cutoff or anticipated judgment. Current 19-test `cpu-tests.log` SHA-256 is `df573b1849a32ae1c006e0d560572debdb6836d7d56ec458e8a210b147ca068d`; semantic validator log SHA-256 is `711092f208ab72b853c04d9a242f2188aa7967b355c9b9a6c53a26be258d1b15`; semantic index SHA-256 is `af08bf80d2d3b30af16916db09a0453289579e4249ad811c1713c01778d1d307`. Scoped `worker_check.py --complete` passes. The exact next CPU step is to select or construct a verifiable alley polygon source and bind first `__person_3mps` config/construction to the new runner/finalizer, then run exact offline, compatibility positive/negative and saved processing. Expand the remaining five cases and three distinct fallbacks each, complete the qualitative sweep and delivery/comparison audits, and run scoped strict only after their proofs pass. Status remains partial; no physical/legal result is asserted.

Status is **partial**. The geometry, original-source measurement, and draft comparison audit described below exist; no executable case, fallback, or saved-processing receipt exists yet, and no physical outcome is asserted. Read `inputs/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/assignment.json`, `evidence.json`, `witnesses.json` and the exact law in `inputs/coverage/branch-sources.json`. Build one primary exact case end-to-end using the pinned runtime, then build every other case and three distinct tested fallback constructions per selected case. Test finalizers against retained raw sources (including all four named cameras), exact offline and positive/negative compatibility, saved-only processing, and independent delivery/comparison audits. Add canonical semantic proposals and hash all current receipts. Do not treat fixture media as physical evidence.

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
when deceleration is absent; neither proxy is a legal cutoff.
`alley_comparison_audit.py` checks three exact case identities, declared fixed
conditions, original-source hash fields, measured speed order and measured gaps;
it reports an incomplete comparison when speed order is not realized. It is not
yet wired to saved processing or validated against promoted source bytes. Twelve
tests pass:

`.venv-cpu/bin/python -m unittest discover -s work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/tests -v`

The log is `cpu-tests.log` (SHA256
`d2965c04265f747fd8edaf1a3a7bbed69c56930946ce64fc6112304cfc24652a`),
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

## 2026-11-11 sourced alley route and feedback checkpoint

`alley_route.py` now selects a connected, nonjunction Native map lane inside a supplied alley polygon, with both east and west approach support. It requires a named original polygon source, checks that the complete vehicle width plus an engineering edge margin fits inside the polygon and mapped lane, and rejects an out-of-polygon, wrong-way, narrow or branching route. The pure feedback controller uses measured position, heading and velocity to request steering, throttle and brake toward a case speed. The polygon and target speed remain authored construction inputs; a speed command and diagnostic polygon do not establish actual endangerment or legal status. No selected C10364 alley polygon has yet been sourced, and no Native run is claimed.

`tests/test_alley_route.py` exercises both approach directions, missing source, geometry rejection and feedback response. The full local suite passes 15 tests: `.venv-cpu/bin/python -m unittest discover -s work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver/tests -v`; `cpu-tests.log` SHA-256 `d4c9317e3d52b8426dd40d21cacbe6d18eb4c0caca831af375b171daa233ccb6`. The assignment-scoped static check exits 0; `worker-check.log` SHA-256 `042998b01b6533c72a6cffdcfee0d7a8010973a06cf87259d4f5fd9907da5ebe`. Status remains partial.

Next CPU work: bind an actual source-backed alley polygon and participant placements to the first `__person_3mps` config, author the CARLA-lazy runner with four source cameras and original footprint/motion capture, then finalize and run exact offline, positive/negative compatibility and saved processing. Preserve the six planned cases, measured fixed-condition comparisons and unresolved endangerment judgment. Continue fallback, semantic and independent audit work after the first case passes.
