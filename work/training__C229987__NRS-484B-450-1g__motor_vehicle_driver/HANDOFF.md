# training__C229987__NRS-484B-450-1g__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.450(1)(g): A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Within 30 feet upon the approach to any official traffic-control signal located at the side of a highway.

Cell: road / stop_stand / traffic_light; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

official signal at highway side; same approach and voluntary stop/stand; no conflict or official direction Vary only `stop_distance_on_signal_approach` (ft) across [25, 30, 35]. Measure vehicle footprint to signal along approach; record stop duration and reason. The definitions are not selected recordings, and requested settings are not measured results.

## Current CPU measurement proof

`analysis/signal_approach.py` is a saved-source processor for raw frame times, speed, four-corner vehicle footprints, road approach geometry, roadside signal position, and context source references. It computes front-edge, centre and rear longitudinal distances to the signal's roadway station for every frame. It preserves geometry uncertainty and low-speed samples, and emits no legal verdict. This is an executable component for future exact-case finalizers; it has not processed a Native recording.

`analysis/measurement-contract.json` identifies each required raw source, output, comparison invariant and unresolved statutory interpretation. It retains all three existing 25/30/35-foot requested settings as planned probes; requested settings are never treated as measured results. The signal station differs from a stop line or intersection boundary.

CPU command: `.venv-cpu/bin/python -m unittest discover -s work/training__C229987__NRS-484B-450-1g__motor_vehicle_driver/analysis -p 'test_*.py' -v`. Exit code 0; six tests passed. Log: `analysis/cpu-measurement-test.log`, SHA-256 `0cafaed40268ab6a0e1dc3fec0c88fa6861b115821d4fa876c5bcc4274d11c13`. Processor SHA-256 `e0e98815568712547bdec9cdb87be0ae24d41a0fd696deee8c236d08a3a9ec12`; contract SHA-256 `c3b4025e13dbb2384cf02a7dbe7c9b0fbbaef0f214086702fff379a23eabfcdf`. Tests use invented raw-shaped data only and prove CPU logic and rejection, not physical realization.

Assignment checkpoint: `.venv-cpu/bin/python worker_check.py --assignment training__C229987__NRS-484B-450-1g__motor_vehicle_driver --complete` exited 0. Strict delivery-ready gate was not invoked because selected-case proof is incomplete.

## Remaining construction and resumption

Exact 30-foot boundary requires geometric uncertainty; stop/stand/park modes differ. Resolve statutory alternatives and exceptions from the frozen law and cited sources. Select exact cases, build semantic stages and Native construction, primary plus three distinct tested fallbacks per selected case, mandatory synchronized four-camera capture and Core mapping. Integrate this measurement component into each exact saved finalizer; run offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after the assignment-scoped strict CPU gate passes.
