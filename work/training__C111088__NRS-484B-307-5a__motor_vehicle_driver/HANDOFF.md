# training__C111088__NRS-484B-307-5a__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.307(5)(a): Where the signal is a green straight-through arrow alone: Vehicular traffic facing the signal may proceed straight through, but must not turn right or left. Such vehicular traffic must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.

Cell: intersection / straight / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

sole green straight-through arrow facing ego; ego proceeds straight; other vehicle or pedestrian lawfully within intersection Vary only `lawful_conflict_participant_present` (bool) across [False, True]. Record native signal head and phase, lawful participant entry, conflict occupancy and ego response. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Straight-only turn prohibition is a separate branch requiring a turn attempt, incompatible with this fixed straight maneuver. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
