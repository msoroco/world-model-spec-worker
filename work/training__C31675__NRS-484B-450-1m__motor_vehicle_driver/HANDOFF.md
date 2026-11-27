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

## 2026-11-27 exact Native bridge construction checkpoint

The two exact planned cases (`__false` ground halt and `__true` bridge halt) now have source-hashed inline primary and fallback1 bundles under `cases/`, bound by `draft-execution-manifest.json`. The shared `native/geometry.py` authors a 300 m road with a surveyed elevated 100 m bridge deck; `native/runner.py` checks six Native lane/elevation samples, captures 600 frames at 20 Hz from four cameras, original ego/other-vehicle positions, body footprints, controls and frame joins, and restores the world. `native/controller.py` varies only the requested halt position. Fallback1 starts 10 m earlier for a measurable overshoot risk, keeping the exact comparison and capture profile fixed. Physical bridge support and realized halt remain unverified.

`native/finalize.py` runs the saved bridge measurement on source-hashed original map/body/speed samples, requires all four source videos and full 600-frame joins, and writes a Native-shaped result without asserting exceptions or legality. `native/comparison_audit.py` independently checks the observed full-versus-none stationary bridge relation and fixed law, actor, cell, cameras, duration, atoms, halt purpose and bridge-map hash. Six materialized CPU tests cover these paths, missing original source, bad frame join, wrong Native elevation and changed comparison duration.

Four exact current-runtime `.venv-cpu/bin/python runtime.py offline --manifest work/training__C31675__NRS-484B-450-1m__motor_vehicle_driver/draft-execution-manifest.json --case CASE --candidate primary|fallback1 --output .runtime-work/c31675-offline-CASE-CANDIDATE-final3` commands passed. Logs and SHA-256 are in `proofs/` and each manifest offline entry. This is construction/offline proof only; selected public compatibility, source-bound accepted-evidence equivalence, semantic proposals, exception/alternative branches, saved-only processing and delivery audit remain CPU work. The eight accepted review-context rows have `reuse=false` and no receipt sources; no physical equivalence claim is made. Resume with public positive/negative compatibility on these exact bytes, then full branch constructions and scoped strict gate.
