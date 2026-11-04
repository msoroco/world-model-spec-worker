# training__C82860__NRS-484B-227-1__motor_vehicle_driver

Status: blocked. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.227(1): Every vehicle driven upon a divided highway must be driven only upon the right-hand roadway and must not be driven over, across or within any dividing space, barrier or section or make any left turn, semicircular turn or U-turn, except through an opening in the barrier or dividing section or space or at a crossover or intersection established by a public authority.

Cell: divided_road / u_turn / median_barrier; actor: motor_vehicle_driver. Frozen witness count: 2. Membership rows: {'demo-train': 2, 'full-train': 2}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

divided highway; same U-turn intent; genuine barrier and public-authority-established opening/crossover Vary only `median_crossing_location` (category) across ['authorized_opening', 'barrier_crossing']. Record native median geometry, barrier gap, crossing footprint, road direction and opening authority. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Physical gap alone does not prove public authority; left-turn/crossover/intersection alternatives need separate cases. Resolve exact statutory branches and external authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.
