# C394566 / LVMC 11.48.050 current CPU checkpoint (2026-11-27)

Status: partial. The original law has eight planned controlled comparisons and 16 unselected cases: truck route designation, unladen weight at/above 8000 lb, residence district, each side of the 7 p.m. and 6 a.m. clock transitions, written permit presence, permit route/time scope, and movement. The exact 19:00 and 06:00 endpoints remain unresolved legal questions; the existing factual meter probes them without assigning a legal result. No case has a selected construction or public/saved proof yet.

`native/source_contract.py` now joins 600 original-route rows to 600 frame-map rows, verifies a source seal and five independently cited factual authority files, and rejects missing or changed sources. `native/route_measurement.py` connects that joined packet to the existing 8000-lb/nighttime/residence/route/permit factual meter. `native/prove_source_contract.py` passes a synthetic positive and missing authority, changed seal and changed frame-join negatives; its log is `native/source-contract-cpu.log`. This is a diagnostic source contract, not an original authority review.

`native/runner.py` is a prospective CARLA route controller that requires a reviewed Native map/route survey and five cited original context files. It records 600 synchronized four-view source frames, original road/speed rows, PipelineCapture and canonical frame map, seals source bytes, and restores the world. Its CPU `--check` passes in `native/runner-check.log`. It has not been selected into a construction or tested in CARLA. The new source and runner files remain worker-owned CPU work to integrate into per-case finalization and selected proof chains.

Next CPU work: build exact per-case finalizer and measurement contracts, construct and offline-check the first route comparison, run public positive/missing-source and saved-only chain, then expand the other branches and independent audits. Keep administrative permit authenticity, physical route and legal meaning for independent original delivery review. Runtime verify and CPU preflight passed this checkpoint.

## Earlier handoff

# training__C394566__LVMC-11-48-050__heavy_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.48.050: No vehicle in excess of eight thousand pounds unladen weight shall be operated or moved upon any street (other than a truck route), in any residence district between the hours of seven p.m. and six a.m.; provided, however, that the Department of Public Works may, at its discretion, upon application in writing, issue a special permit in writing authorizing the applicant to operate or move such vehicle between the hours of seven p.m. and six a.m. In issuing such permit, the Department may impose such conditions thereon, such as routes to be followed, time of operation or movement, or other matters, as it deems necessary or desirable.

Cell: road / travel / truck_route_designation; actor: heavy_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

unladen weight above 8000 lb, residence district, 7 p.m. to 6 a.m.; no written permit Vary only `heavy_vehicle_restricted_street_operation` (category) across ['truck_route', 'non_truck_route']. Record certified unladen weight, district boundary, local time, route designation, movement. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Written permit and attached conditions require authoritative source review. Resolve exact statutory branches from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## Current CPU construction checkpoint

`restriction_measure.py` checks source-hashed factual inputs for vehicle-specific unladen weight, residence-district class, truck-route designation, civil time with UTC offset, observed movement and written-permit status. It returns the 7 p.m. to 6 a.m. window in the local timezone and preserves both exact clock endpoints as unresolved. A permit-present flag remains insufficient to verify applicant, vehicle, route, time and attached conditions. `restriction-measurement-contract.json` records the authoritative sources required before an exact case can use the evaluator. None of these synthetic source packets establishes administrative authenticity or legal compliance.

`.venv-cpu/bin/python work/training__C394566__LVMC-11-48-050__heavy_vehicle_driver/prove_restriction_measure.py` exited 0. `restriction-measurement-cpu.log` SHA-256 is `f4b694af93a685fe3dd3827fe0e3eb1822554971a1ed3bcdcca2a0ce58f4e1e3`; seven civil-time probes, seven weight/route/movement/permit probes, and six negative-source probes pass. The evaluator remains to be integrated into a selected-case finalizer and tested against retained raw acquisition. No original Native or accepted-recording claim is made.
