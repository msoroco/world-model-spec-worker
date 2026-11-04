# training__C245490__NRS-484B-413-2__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.413(2): A signal of intention to turn right or left, or otherwise turn a vehicle from a direct course, shall be given continuously during not less than the last 100 feet traveled in a business or residential district and not less than the last 300 feet traveled in any other area prior to changing the course of a vehicle. This rule shall be observed, regardless of the weather.

Cell: same_direction_multilane / change_lane / lane_marking; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 6}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

hold district category fixed within each boundary triple; same turn or lane change; weather sampled separately Vary only `continuous_signal_distance_before_course_change` (ft) across [90, 100, 110, 290, 300, 310]. Integrate path distance along actual trajectory while turn indication remains continuous immediately before measured course change. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Business/residential 100 ft and other-area 300 ft need separate comparable triples; indicator API and actual course change may diverge. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
