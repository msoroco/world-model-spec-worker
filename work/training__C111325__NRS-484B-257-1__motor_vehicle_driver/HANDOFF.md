# training__C111325__NRS-484B-257-1__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.257(1): Except when traffic is being controlled by a police officer or a traffic-control signal: When proper signs have been erected, the driver of a vehicle shall stop or yield at a clearly marked stop line or, if there is none, before entering the crosswalk on the near side of the intersection or, if there is none, then at the point nearest the intersection where the driver has a view of approaching traffic on the through highway. After having stopped or, in the event of a yield sign, slowed or stopped, the driver shall yield the right-of-way to other vehicles which have entered the intersection from such through highway or which are approaching so closely on such through highway as to constitute an immediate hazard during the time such driver is moving across or within the intersection.

Cell: intersection / travel / stop_sign; actor: motor_vehicle_driver. Frozen witness count: 2. Membership rows: {'demo-train': 9, 'full-train': 9}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

stop sign with marked stop line and through-highway vehicle; no police/signal control Vary only `ego_stop_and_yield_sequence` (category) across ['complete_stop_then_yield', 'roll_through_conflict']. Measure wheel speed, stop-line crossing, other-vehicle approach and gap, ego crossing interval. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Yield-sign alternative and stop-line/crosswalk/no-mark hierarchy require distinct branches; safety judgment unresolved. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
