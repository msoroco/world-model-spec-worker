# NRS 484B.253, C109749: partial CPU implementation checkpoint

The assigned cell is an intersection with a left turn and an opposing vehicle. The exact statute has an initial yield duty for an opposing vehicle already within the intersection or so close as to be an immediate hazard. After yielding and signalling as required, the subject may turn and opposing drivers must then yield. The phrase “immediate hazard” remains a legal judgment; no time-to-conflict cutoff is asserted here.

## Work completed

- `case-plan.json` reviews all six accepted metadata records and the review-context groupings. The metadata confirms identity, frame count and decoder reports. The retained trace/video and per-frame delivery audits are outside this export, so the intended `inside_yield`, `approaching_yield`, `signal_omitted` and reciprocal cases cannot yet be claimed as source-backed equivalents. No accepted original is queued for replay.
- `measurements.py` measures body-level intersection occupancy, original-frame entry order, indicator samples and descriptive opposing time-to-conflict from retained raw interaction rows and a sourced intersection polygon. It requires the original frame map and hashes its source files. It rejects missing raw sources and inconsistent frame identity. It produces no legal verdict.
- `controller.py` implements an initial yield, continued wait until measured opposing clearance, a left-turn command and indicator policy. Its four-second release tuning is an engineering parameter, never an interpretation of “immediate hazard.” Ten CPU tests pass in `cpu-tests.log`.
- `construction.py` searches Native map waypoints for two opposing driving lanes entering the same junction, a connected left exit and at least 35 meters of approach; `spawn_pair` creates two owned actors and destroys the first if the second spawn fails. Fake-map tests exercise lane direction, route connectivity and cleanup. This is a construction component; it has not been run against a CARLA map.
- `config.json` and `case-plan.json` now name a tentative positive `__reciprocal_yield_after_turn` case, four source-camera views at the pinned profile, and a business/residential district signal-advance assumption sourced to the supplied NRS 484B.413(2) text. The pinned atom preflight passes in `atom-preflight.log`. The case remains tentative until the accepted originals are checked for an equivalent positive branch.
- `.venv-cpu/bin/python runtime.py preflight` passes with the pinned dependencies and tools. `.venv-cpu/bin/python runtime.py fixture --recipe runtime/fixtures/example-recipe.json --output .runtime-work/example` also passes, but that generic synthetic fixture is not this law's proof.

## Next CPU work

1. Finish a specific new case only after source review determines which conditional clause is uncovered. Integrate `construction.py` into a CARLA-lazy runner, verify the chosen junction and opposing routes against a real Native map, add four named source cameras and synchronized Native capture. Wire `controller.py` to measured actor states and emit the raw files consumed by `measurements.py`. The current modules are components, not a runnable construction.
2. Add the saved finalizer, measurement contract, case-specific diagnostic recipe, semantic proposals, physical-completion and lifecycle fixture checks. Run exact offline, positive/negative compatibility and saved-only processing for the primary selected case before expanding comparisons.
3. Implement the remaining exact cases and comparisons, with three distinct physical-risk fallbacks per case. Test and bind all construction, compatibility, saved-processing and independent delivery/comparison audit hashes. Review the law and all alternatives again before marking ready.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C109749__NRS-484B-253__motor_vehicle_driver --complete --require-delivery-ready`, then the batch strict gate. This checkpoint remains partial because those CPU deliverables are unfinished.

Physical motion, realized signal pixels, camera coverage and any legal judgment remain unverified.
