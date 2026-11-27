# C233871 NRS 484B.280(1)(c) motor-vehicle driver

Status: ready, `delivery_prepared`. The exact strict assignment gate passed with exit 0 after all listed CPU proofs. Frozen assignment and inputs are unchanged. No original CARLA recording or legal verdict is claimed.

## Source and scope

Exact selected witness: pedestrian bodily on a road without a sidewalk during motor-vehicle travel. The full statute also names pedestrian near a highway/street/road, transit-stop/boarding alternatives and school-zone/crosswalk alternatives; those other locations are not represented as facts of this fixed C233871 road-without-sidewalk cell. The source witness has low confidence and requires original road classification/edges, absence of a sidewalk, distinct pedestrian and motor vehicle identities, driver control, and an observation source separate from visibility. There are zero frozen accepted recordings and zero judgment-range entries for this exact law/actor. `case-plan.json` records the source-backed gap and two selected exact cases.

The instrumented scripted-driver input event in `native_capture.py` is a recorded controller input, not evidence of human cognition. The saved measurement and audits preserve that distinction. Neither the 15 m engineering trigger nor the 2 m deferred brake trigger defines statutory “near” or “proper caution.”

## Exact cases and comparison

- `testing__C233871__NRS-484B-280-1c__motor_vehicle_driver__prompt_brake`: same road, on-road pedestrian and original scripted-driver input, prompt engineering brake.
- `testing__C233871__NRS-484B-280-1c__motor_vehicle_driver__deferred_brake`: identical planned encounter with a later engineering brake command.
- `on_road_response_timing`: fixed map, road/no-sidewalk context, participant identities, routes, camera/duration and observation trigger; measured original brake response delay differs. The independent comparison rejects a changed map or absent delay difference and leaves legal judgment unresolved.

Both cases have 20 Hz, 30 s, four cameras at the pinned profile. `road_scene.py` checks source-hashed original OpenDRIVE, road classification/edges, no-sidewalk status, on-road pedestrian route/body and separate driver input. `native_capture.py` lazily imports CARLA, checks the Native road/lane and sidewalk, spawns distinct vehicle and pedestrian actors, captures original bodies, controls, contact sensor, frame map and four FFV1 videos, seals the acquisition and verifies world restoration. `runner.py --check` validates identity and construction geometry without CARLA. `analysis.py` runs saved-only, rejects stale/missing original sources and bad frame joins, and emits a source-hashed `pedestrian_on_road_caution_measurement` with legal verdict unresolved.

Each primary case has `fallback1`, a 3 m upstream ego spawn on the same road, triggered only if the primary Native ego spawn is occupied/rejected. The same fallback is available for both linked cases; it preserves the comparison variable, case identity, four cameras and 30 s contract. It was CPU-tested offline and through positive/negative compatibility. `execution-manifest.json` binds exact constructions and proofs. `queue-proposal.json` contains the two exact canonical jobs and comparison command for lead integration.

## CPU proofs

- `.venv-cpu/bin/python runtime.py preflight` passed on pinned Python, Lean and FFmpeg environment.
- `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c233871-runtime" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C233871__NRS-484B-280-1c__motor_vehicle_driver/tests -v` passed 13 focused tests. The tests exercise source hash/road/sidewalk/participant rejection, Native waypoint creation calls, saved frame joins, measured response and independent audits.
- Canonical semantic stage validation passed relevance_batch, relevance, template, judgment_observables, bindings and cases (`semantic-stage-check.log`).
- Four exact offline bundle checks passed: two primaries and two fallback1 alternatives (`proof-*-*.log`).
- Four exact positive/negative compatibility runs passed through saved analysis, Native validator, Core conversion, Lean decoder, renderer and full video decode (`compat-*-receipt.json`). The missing `encounter-history.jsonl` negative is rejected.
- Two physical/lifecycle CPU probes passed complete, incomplete and missing source classifications with closure order (`physical-*-proof.json`). These are synthetic protocol proofs only.
- Both exact saved-only `runtime.py process-saved` runs passed (`saved-*.log`), with no Native replay and original-source preservation.
- Independent delivery audit positive and sealed-source-negative proofs passed for both cases (`audit-*-positive.log`, `audit-*-negative.log`). Independent comparison positive and changed-map-negative proofs passed (`comparison-positive.log`, `comparison-negative.log`).
- Exact `.venv-cpu/bin/python worker_check.py --assignment testing__C233871__NRS-484B-280-1c__motor_vehicle_driver --complete --require-delivery-ready` passed with exit 0; local command output is retained at `.runtime-work/c233871-strict-final.log`.

## Local physical review

Use the lead-integrated GPU queue and a CARLA-capable local Python. Confirm a map with the selected road without sidewalk, distinct on-road pedestrian body, source-recorded controller input, actual participant motion, no unintended ambient actor occlusion, exact frame/video joins, all four camera pixels, and physical completion. Evaluate human observation and statutory proper caution separately; this package does not decide them. Actual CARLA motion, pixel coverage and canonical acceptance remain unverified.

Resume CPU check: `.venv-cpu/bin/python worker_check.py --assignment testing__C233871__NRS-484B-280-1c__motor_vehicle_driver --complete --require-delivery-ready`.
