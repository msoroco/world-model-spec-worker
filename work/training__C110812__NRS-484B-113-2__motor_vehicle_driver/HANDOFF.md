# training__C110812__NRS-484B-113-2__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.113(2): The driver of a vehicle: Shall not back into an intersection, on or over a crosswalk, or around a street corner.

Cell: intersection / reverse / street_corner; actor: motor_vehicle_driver. Frozen witness count: 3. Membership rows: {'demo-train': 0, 'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

intersection with street corner and crosswalk; reverse maneuver; same start and controller except requested stopping position Vary only `reverse_footprint_overlap` (bool) across [False, True]. Measure reverse trajectory and vehicle footprint against intersection, crosswalk and corner polygons. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Crosswalk and corner are alternative prohibited locations; each needs independent physical construction. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
