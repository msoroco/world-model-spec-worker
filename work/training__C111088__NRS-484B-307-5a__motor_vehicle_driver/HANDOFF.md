# training__C111088__NRS-484B-307-5a__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.307(5)(a): Where the signal is a green straight-through arrow alone: Vehicular traffic facing the signal may proceed straight through, but must not turn right or left. Such vehicular traffic must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.

Cell: intersection / straight / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

sole green straight-through arrow facing ego; ego proceeds straight; other vehicle or pedestrian lawfully within intersection Vary only `lawful_conflict_participant_present` (bool) across [False, True]. Record native signal head and phase, lawful participant entry, conflict occupancy and ego response. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Straight-only turn prohibition is a separate branch requiring a turn attempt, incompatible with this fixed straight maneuver. Construct a source-grounded straight-arrow/yield pair and a separate turn-prohibition case from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and supported Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. These are worker-owned CPU tasks. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass and the scoped strict gate succeeds.

## CPU construction started after C110812

`native/controller.py` now chooses a straight route and brakes for a same-frame, lawfully within other vehicle or pedestrian under a sole governing green straight arrow. It rejects missing/mixed signal observations and incomplete participant evidence. `native/geometry.py` checks the authored prior-entered vehicle clears before the ego release frame; `native/test_controller.py` passes hold/release and source-specific rejection tests. These are authored CPU controls only. A Native runner, source-derived finalizer, exact candidate bundles, fallback and saved-processing proofs are still to be built; the assignment stays partial.
Assignment-scoped static `worker_check.py --complete` passes after these additions; strict delivery readiness remains unclaimed.
