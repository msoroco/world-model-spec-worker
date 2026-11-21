# training__C111088__NRS-484B-307-5a__motor_vehicle_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

NRS 484B.307(5)(a): Where the signal is a green straight-through arrow alone: Vehicular traffic facing the signal may proceed straight through, but must not turn right or left. Such vehicular traffic must yield the right-of-way to other vehicles and to pedestrians lawfully within the intersection or an adjacent crosswalk at the time the signal is exhibited.

Cell: intersection / straight / other_vehicle; actor: motor_vehicle_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

sole green straight-through arrow facing ego; ego proceeds straight; other vehicle or pedestrian lawfully within intersection Vary only `lawful_conflict_participant_present` (bool) across [False, True]. Record native signal head and phase, lawful participant entry, conflict occupancy and ego response. The definitions are not selected recordings, and requested settings are not measured results.

## Blockers and resumption

Eight authored Native construction checks pass, but exact candidate offline compatibility, recorded-only saved processing, semantic/delivery and comparison proofs are absent. Straight-only turn prohibition is a separate branch requiring a turn attempt, incompatible with this fixed straight maneuver. Construct that case from the frozen law and cited sources. Build exact selected bundles, supported Core mapping and mandatory synchronized source channels; run primary and three fallback offline, positive/negative compatibility, saved-only and independent comparison audits. These are worker-owned CPU tasks. Recheck physical cause and camera evidence in CARLA later. Set `ready` / `delivery_prepared` only after worker CPU proofs pass and the scoped strict gate succeeds.

## Earlier CPU controller checkpoint, superseded by runner checkpoint below

`native/controller.py` chooses a straight route and brakes for a same-frame, lawfully within other vehicle or pedestrian under a sole governing green straight arrow. It rejects missing/mixed signal observations and incomplete participant evidence. `native/geometry.py` checks the authored prior-entered vehicle clears before the ego release frame; `native/test_controller.py` passes hold/release and source-specific rejection tests. These were the initial authored CPU controls; the runner and source-derived finalizer were added in the later checkpoint below.
Assignment-scoped static `worker_check.py --complete` passes after these additions; strict delivery readiness remains unclaimed.

## CPU Native runner and saved-source construction checkpoint

`native/runner.py` now defines an executable exclusive-server capture proposal for both existing straight/yield cases at 20 Hz for 42 seconds (840 frames). `native/engineering.py` supplies four distinct construction settings per case; `native/cameras.py` supplies overview, approach, reference-corner and driver-reference lossless source streams. The runner retains original signal actor states, other-vehicle prior entry and footprints, ego body/pose/speed, Core capture, and camera-to-Native frame maps; it has not run CARLA. Eight offline case/candidate checks pass (`native/runner-offline-check.log`).

`native/measure.py` and `native/finalize.py` reject broken original frame/body joins, missing decoded camera frames and absent independent source-pixel sole-arrow review. The finalizer requires a review receipt hashed to the original overview and reference-corner videos; the runner itself records `pixel_aspect_verified=false`. Six numerical/unit tests pass (`native/measure-controller-check.log`), including 840-frame yield/non-yield timing, a gradual prohibited turn, and a broken video join. Pinned `runtime.py preflight` and assignment-scoped static `worker_check.py --complete` pass; logs are `native/pinned-preflight.log` and `native/scoped-after-runner.log`. Source and proof hashes are in `result.json`.

Status remains partial. The eight offline checks are construction checks, not offline compatibility proof. Next worker-owned steps: produce exact selected case bundles and semantic stages, primary positive/negative compatibility and recorded-only saved-processing proof, then three distinct fallback proofs and comparison/delivery audits. Construct a separate turn-attempt case for the straight-only prohibition. Native execution, actual signal pixels, physical realization and legal acceptance remain unverified. The full batch gate is not passed; prior generated files under frozen runtime are untouched.
