# training__C31675__NRS-484B-450-1m__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.450(1)(m): A person shall not stop, stand or park a vehicle, except when necessary to avoid conflict with other traffic or in compliance with law or the directions of a police officer or official traffic-control device, in any of the following places: Upon any bridge or other elevated structure or within a highway tunnel.

Cell: bridge / stop_stand / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 8}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

physical bridge; ego voluntary stop/stand; no conflict or authority exception Vary only `stationary_footprint_on_bridge` (bool) across [False, True]. Record bridge surface geometry, vehicle footprint, stop interval and stop cause. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Executable Native construction and four candidate offline/compatibility proofs absent; saved audit and comparison proof absent. Tunnel/elevated-structure alternatives require distinct physical setting. Resolve exact statutory branches and source authority from the frozen law and cited sources. Build semantic stages, Native construction, primary plus three truly distinct fallbacks per selected case, mandatory synchronized capture and Core mapping; run exact offline, positive/negative compatibility, saved-only and independent comparison audits. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass.

## Current CPU construction checkpoint

`bridge_measure.py` measures the spatial relation between a source-hashed convex bridge deck and saved per-frame vehicle footprint, separating full, partial and absent overlap. It records observed speed and a stationary candidate filter without making a legal determination. The polygon check uses convex separation, including edge crossings with no contained corners. It rejects hash mismatch, nonbridge structure, malformed geometry, missing speed, missing/reordered frames and 20 Hz time gaps. `bridge-measurement-contract.json` states original map, body, velocity, halt-purpose and traffic-conflict sources required before this can be used for an exact selected case.

`.venv-cpu/bin/python work/training__C31675__NRS-484B-450-1m__motor_vehicle_driver/prove_bridge_measure.py` exited 0. Its `bridge-measurement-cpu.log` SHA-256 is `dd1eaecbab92d1a6b016feca7e119f96ce88be7045210e38db4e8954647634b5`; synthetic source-shaped full/partial/none relations, moving and stationary controls, and four negative-source probes pass. The script has not been integrated into an exact selected-case finalizer and does not establish bridge construction, Native movement, exception facts, legal compliance or accepted-recording equivalence.
