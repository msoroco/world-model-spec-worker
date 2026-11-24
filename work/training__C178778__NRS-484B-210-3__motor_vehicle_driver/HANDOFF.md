# training__C178778__NRS-484B-210-3__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Current source-bound CPU checkpoint

`native/assess_corridor.py` now computes overlap of the two vehicle bodies, whether the full ego footprint leaves the measured paved interval, and the locally available paved corridor to the right of the lead vehicle. Its input is a hashed pavement/shoulder geometry file and 600 contiguous actor samples at 20 Hz. This adds a geometric test of a possible paved alternative without equating one local corridor measurement with the statute's word "requires." The first synthetic source has 181 right-pass overlap frames, zero off-pavement overlap frames and a paved corridor in all 181. The second has the same overlap timing, 181 off-pavement overlap frames and no locally feasible paved right corridor at those frames. The proof also rejects changed hashes, a missing lead source, a frame/time gap and unknown shoulder paving.

`.venv-cpu/bin/python work/training__C178778__NRS-484B-210-3__motor_vehicle_driver/prove-corridor.py` exits 0; `corridor-proof.json` SHA-256 `f8f75c4dd0e085672425e3aaa3075af68c94ed0aa838cc73c2799d286c01ea90`, log SHA-256 `6a7446d901b3d61630d132033ea6e1137a62e415cadc8c72813dbe4544faee34`. Independent `.venv-cpu/bin/python work/training__C178778__NRS-484B-210-3__motor_vehicle_driver/audit-corridor.py` exits 0 and recomputes the counts directly from the retained rows; `corridor-audit.json` SHA-256 `32a40ffb7bbdc86e1a1bf3b311bbec09fc9b3c3687b58a14d14c25a167b5a4bb`, log SHA-256 `49d807b2c731fc5fb116c0c8c92d3b8a4c1a624eafb4b9843d9ebf08caa39aa8`. `.venv-cpu/bin/python worker_check.py --assignment training__C178778__NRS-484B-210-3__motor_vehicle_driver --complete` exits 0; `current-scoped-complete.log` SHA-256 `d3b61b777ca80092ffda1d751fc312e257cdfd8af6a549ce9d895bc215fe1b5b`. That scoped command validates a truthful partial checkpoint only.

These diagnostic rows are invented CPU poses, not Native motion. The local paved-corridor calculation omits alternate timing and paths, actual highway/pavement boundaries and physical constraints; it cannot settle whether this movement required leaving pavement. The diagnostic pair changes both lead and ego lateral positions, so it is not the planned controlled comparison. Final selected cases must hold the appropriate scene conditions fixed and measure realized Native sources.

## Source and scope

NRS 484B.210(3): The driver of a vehicle shall not overtake and pass another vehicle upon the right when such movement requires driving off the paved portion of the highway.

Cell: paved_road / overtake_right / road_edge; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

right-side pass of same-direction vehicle; paved edge physically measured Vary only `overtaking_footprint_off_pavement` (bool) across [False, True]. Record paved-surface polygon and full ego wheel/footprint sweep during passing. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and primary plus three candidate offline/compatibility proofs remain absent; selected semantic stages, saved-only processing, delivery audit and controlled comparison proof remain worker-owned CPU work. A lane lookup alone cannot prove pavement departure, and a local geometric bound alone cannot prove the operative "requires" condition. Resolve exact statutory branches and source authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs and the assignment-scoped strict gate pass.
