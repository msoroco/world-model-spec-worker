# C323986 / NRS 484B.627(1)(a) motor vehicle driver

Status: partial CPU construction in progress. No original recording has been accepted or reviewed; frozen `evidence.json` lists none. The exact law conditions the extreme-right duty on slow driving that impedes traffic immediately behind, a highway with one lane in each direction, and paved width permitting the movement. It also refers conditionally to NRS 484B.630. No legal threshold or verdict is inferred from a fixture or requested controller value.

## Exact coverage and comparison isolation

`case-plan.json` contains fourteen selected exact cases: five base cases `slow_center_wide`, `slow_right_wide`, `slow_center_narrow`, `slow_center_no_follower`, and `slow_center_obstruction_near`. Four base comparisons vary only requested right-side body path, paved right-side width/map profile, immediately following vehicle relation, or physical obstruction placement, respectively. Three additional source-gated engineering sweeps request subject speeds 4/5/6 m/s, paved right edges 3.5/4.1/4.7 m and right-path offsets 0/0.55/1.1 m, with three exact cases each and seven comparisons total. These are physical coverage requests, never legal cutoffs. Frozen witness 471 and the exact law are retained in the plan. There are no applicable training judgment ranges for this exact law/actor in the supplied range inventory.

The site packet is an external original-source gate. `reviewed_scene.py` requires SHA-bound site and OpenDRIVE files, source-verified lanes in each direction, per-case paved/highway edge geometry and physical static-prop blueprint, participant stations, and four camera profiles. No diagnostic fixture is accepted as physical proof. The `runner.py` bridge requests 900 frames at 20 Hz. `native_adapter.py` spawns a separate follower and a physical roadside prop, retains original bounding-box vertices and participant state, captures four synchronized views, destroys owned resources and restores synchronous settings. Original physical completion remains unverified.

`right_side_measurement.py` measures original subject/follower speed and gap, body position relative to paved/highway right edges, and prop position/clearance without a legal cutoff. `finalize_original.py` joins sealed original motion, independent follower relation, and four-view frame map by exact frame/time/actor identity; it rejects absent sources and stale case/frame-map bindings. Five focused synthetic CPU tests in `tests/test_reviewed_scene.py` pass, including all fourteen scene calls through a fake adapter and positive/negative sealed joins. `cpu-tests.log` contains the passing output. These are construction and source-format tests, not accepted physical evidence.

## Remaining CPU work on this assignment

1. Complete saved-only finalization into the Native result and pinned converter, with case-specific source packets and positive/negative compatibility fixtures for all fourteen primary cases.
2. The seven draft canonical semantic stage proposals now validate, including deterministic expansion of all three judgment sweeps. Finish per-case measurement contracts, offline construction checks, physical/lifecycle checker tests and independent delivery/comparison audits.
3. Assess concrete fallback triggers, provide justified source-bound fallback constructions where physical risk warrants, then bind every selected case into `execution-manifest.json` and an exact queue proposal.
4. Run the exact strict gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C323986__NRS-484B-627-1a__motor_vehicle_driver --complete --require-delivery-ready`. Keep `result.json` partial until this passes.

All scratch and generated fixture media belong under `.runtime-work/`. No GPU or original recording is required to complete the remaining CPU code and proofs.
