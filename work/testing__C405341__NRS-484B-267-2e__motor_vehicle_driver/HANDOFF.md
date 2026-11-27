# testing__C405341__NRS-484B-267-2e__motor_vehicle_driver

Status: partial CPU construction and offline preparation. This is not delivery-ready.

Exact clause: NRS 484B.267(2)(e), including visible movement/hand-signal preparation under subsection (4). Frozen accepted evidence has zero recordings; no original lane or conditional-context evidence is reused.

Eleven selected exact cases and nine controlled comparisons are in case-plan.json. They cover available nonadjacent lane use versus adjacent use; traffic, roadway, weather and law-enforcement direction circumstances; emergency/regulatory target; moving versus visible preparation cues; flashing and approach activation. No numeric safety or possibility threshold is invented.

Construction: build_constructions.py materializes all exact inline bundles. emergency_construction.py gates reviewed Native lane graph, connected routes, qualifying equipment, authorization, original condition sources and controller actions. runner.py opens only a hash-bound reviewed Native adapter and restores/readbacks world state. lane_probe.py and analysis.py require all 900 original frame/camera joins, lane and condition histories, and source hashes. Diagnostic recipes under diagnostics/ are synthetic software fixtures only.

Proofs completed: 15/15 exact primary/fallback runtime.py offline checks; prove_physical.py exercises three physical state outcomes and lifecycle for all 11 cases; 10 CPU construction/audit tests pass in cpu-tests.log. Positive/negative compatibility is running.

Next CPU actions: complete prove_compatibility.py and repair any failures; run saved-only processing for all 11; bind independent delivery acceptance, comparison audit commands and direct queue proposal; rerun complete strict assignment gate and fix any failure before marking ready. Actual CARLA lane trajectories, target movement, traffic/weather realization and original pixel review remain later GPU/local checks.
