# testing__C230223__NRS-484B-270-3__motor_vehicle_driver

Status: **ready** (delivery_prepared). This is CPU preparation; no physical or legal acceptance is claimed.

## Frozen scope and coverage

Law: The driver of a motor vehicle shall yield the right-of-way to any person riding a bicycle, an electric bicycle or an electric scooter or a pedestrian as provided in subsection 6 of NRS 484B.297 [NRS-484B-297-6] on the pathway or lane. The driver of a motor vehicle shall not enter, stop, stand, park or drive within a pathway or lane provided for bicycles, electric bicycles or electric scooters except: (a) When entering or exiting an alley or driveway; (b) When operating or parking a disabled vehicle; (c) To avoid conflict with other traffic; (d) In the performance of official duties; (e) In compliance with the directions of a police officer; or (f) In an emergency.

Cell C230223; actor motor_vehicle_driver. The source review found no accepted original recording suitable for reuse. The finite package has 22 selected exact cases and 12 controlled comparisons. All nine requirement dispositions in case-plan.json are selected and mapped to cases.

| Exact case ID | Road user | Vehicle request | Exception context |
| --- | --- | --- | --- |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__bicycle_yield | bicycle | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__bicycle_go_first | bicycle | outside / proceed_first | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__electric_bicycle_yield | electric_bicycle | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__electric_scooter_yield | electric_scooter | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_yield | qualified_pedestrian | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_go_first | qualified_pedestrian | outside / proceed_first | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_unqualified_yield | unqualified_pedestrian | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_no_entry | bicycle | outside / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_enter | bicycle | enter / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_stop | bicycle | stop / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_stand | bicycle | stand / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_park | bicycle | park / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_drive | bicycle | drive / yield | none |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__alley_enter | bicycle | enter / yield | alley_enter |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__alley_exit | bicycle | enter / yield | alley_exit |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__driveway_enter | bicycle | enter / yield | driveway_enter |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__driveway_exit | bicycle | enter / yield | driveway_exit |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__disabled_vehicle | bicycle | stop / yield | disabled_vehicle |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__avoid_conflict | bicycle | enter / yield | avoid_conflict |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__official_duties | bicycle | drive / yield | official_duties |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__police_direction | bicycle | drive / yield | police_direction |
| testing__C230223__NRS-484B-270-3__motor_vehicle_driver__emergency | bicycle | drive / yield | emergency |

The cases cover yield and precedence for bicycle, electric bicycle, electric scooter and qualified pedestrian; the unqualified pedestrian boundary; all five lane actions; alley and driveway entry/exit; disabled vehicle, traffic conflict, official duties, police direction and emergency. No numeric judgment cutoff was invented.

## Controlled comparisons

| Comparison | Exact case members |
| --- | --- |
| bicycle_precedence | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__bicycle_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__bicycle_go_first |
| qualifying_road_user | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__bicycle_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__electric_bicycle_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__electric_scooter_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_yield |
| pedestrian_qualification | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_unqualified_yield |
| pedestrian_precedence | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_yield, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__pedestrian_qualified_go_first |
| prohibited_lane_actions | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_no_entry, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_stop, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_stand, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_park, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_drive |
| alley_direction | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__alley_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__alley_exit |
| driveway_direction | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__driveway_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__driveway_exit |
| disabled_vehicle_exception | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_stop, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__disabled_vehicle |
| conflict_avoidance_exception | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_enter, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__avoid_conflict |
| official_duties_exception | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_drive, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__official_duties |
| police_direction_exception | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_drive, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__police_direction |
| emergency_exception | testing__C230223__NRS-484B-270-3__motor_vehicle_driver__lane_drive, testing__C230223__NRS-484B-270-3__motor_vehicle_driver__emergency |

comparison_audit.py checks the declared variable, fixed motor vehicle actor, camera plan, 45 s/20 Hz, source-reviewed map and facility polygon, participant route, packet hashes and measured original body occupancy/precedence. comparison-audit-specs.json binds positive and tampered-camera negative CPU proofs when available. Original Native comparison mode requires independent source review hashes.

## Construction, capture and finalization

- cycle_lane_2703.py validates reviewed site designation, distinct participant identity, exception circumstances and NRS 484B.297(6) pedestrian qualification before route construction. It measures 900 original 20 Hz body polygons and precedence without issuing a legal verdict.
- cycle_lane_native.py, runner.py and each cases/<slug>/construction.json implement source-gated Native creation, control, four-camera acquisition, original source sealing and restoration. Missing reviewed sources fail closed. Each case config keeps the 45 s, 20 Hz four-view profile and source-conditioned 2 m travel-progress completion measurement.
- analysis.py finalizes only saved original sources. cycle_lane_source_audit.py independently checks Native seals, participant/time joins and full camera decode. delivery_audit.py binds saved processing, human pixel review, physical completion, the promoted video/Core trace and the source-decode receipt for canonical local acceptance. prove_delivery_contract.py tests synthetic positive and original-source negative protocol paths.
- The exact case constructions record physical risk. No fallback is asserted without a measured Native failure trigger. Source-gated original CARLA motion, camera visibility and actual physical acceptance remain local checks after CPU delivery.

## Bound CPU proofs and resume commands

Preflight: `.venv-cpu/bin/python runtime.py preflight`.
Source tests: `.venv-cpu/bin/python -m unittest work/testing__C230223__NRS-484B-270-3__motor_vehicle_driver/tests/test_cycle_lane_2703.py`.
Each case has a source-hashed diagnostic recipe and exact offline/compatibility command in execution-manifest.json. Compatibility proves positive converter/render/decode and a missing-source rejection. Diagnostic fixtures are synthetic and cannot establish original visibility or legal compliance.
Each physical-preparation.json binds complete-motion, incomplete-motion and missing-evidence outcomes plus saved-only lifecycle ordering. Each process-saved.json is a receipt from `runtime.py process-saved` against an isolated synthetic attempt. No script replays or edits a Native source to fill missing law evidence.
gpu-queue-proposal.json supplies one canonical prepare/execute/accept, operator-supplied saved attempt owner-release, saved processing and original-source audit command per exact case, plus all 12 original comparison audit commands. The lead integrates these rows into the shared queue.
Assignment gate: `.venv-cpu/bin/python worker_check.py --assignment testing__C230223__NRS-484B-270-3__motor_vehicle_driver --complete --require-delivery-ready`.

CPU gate passed. First local delivery command is in result.json; the operator supplies CARLA Python, host, port and canonical job identifiers.
