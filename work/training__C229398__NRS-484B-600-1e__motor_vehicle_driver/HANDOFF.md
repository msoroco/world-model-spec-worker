# C229398 / NRS 484B.600(1)(e) CPU handoff

Status: **partial**. No selected delivery case or accepted-evidence equivalence is claimed. The fixed cell is `road / park / curb`; the statute concerns speed while driving or operating. Any approach-driving phase must be independently tied to this same parked-cell recording. The parked phase cannot be labeled a speeding event.

## Source review

- Frozen assignment SHA-256 `e0616cb9d29d5fc1ec7b3ec53f92b82513552d2e34e18c93f28e8b64146c9726`; witnesses `33c9937b8dc3f00c42a8e8ac940569540fa7b8a5bd568d4cc8fb030add936ff8`.
- `inputs/training__C229398__NRS-484B-600-1e__motor_vehicle_driver/review-context/review.json` SHA-256 `d02d08457019e02e85a3af4dc096d47400ee2fc9b190e38009809747dbbccac5` describes accepted above/at/below cases by **approach-speed requests** 37.9984, 35.5397 and 33.528 m/s. Its `receipt_sources` are empty and referenced versioned recording traces are absent from this export. Membership IDs establish context, not achieved speed, temporal phase, or current requirement equivalence.
- The three case-plan probes remain unselected. The `selected_required` disposition names the requirement for the partial-package validator; it is not a selected case or coverage claim. Probe 03 has a Native feasibility draft for an 85 mph *request* and curb stop; it does not assert the request was achieved or that the law was violated.

## CPU construction and proof

- `approach_speed_measure.py` SHA-256 `1cafa3db95a201196f583cd13e9ad906c5d13b830b7e72213508541f2482511b` reduces source velocity vectors only in explicitly scoped approach frames. It reports parked frames separately, leaves legal result null, and marks same-cell approach scope unverified. `prove_approach_speed.py` SHA-256 `2fbe157ffcee10359ca7660b251f31972f557f92b4df7ef8e468af789f75c9e9` proves 30 s/20 Hz above, at and below 80 mph synthetic samples, rejects missing scope and velocity, and checks the current source hashes. Both normal and `-O` runs pass; logs SHA-256 `45d715dd22bbd64c104748d3f325a2ec84b02d884f2c4d56911be94cb0fbf1d1` each. These samples are diagnostic, never original Native observations.
- `native/runner.py` has an executable survey-gated CARLA approach-to-curb controller, four source cameras, 600-frame capture, FrameMap and post-tick observed velocity trace joined to each Native frame. Controller phase and requested speed are labeled separately from observed velocity. Its construction SHA-256 is `41c5bba017bab0bce90dd52c4c5d7bd1c79e44680d1d971b8d44f9b62e9a409e`; partial manifest SHA-256 `7e602c2c04bc0d19324db044424752a750121d82df4d8545807dbf6283250298`. Four Native CPU tests pass (log SHA-256 `f79e5c1b2e74d0fbf2ac7c52e093f6057e54553377aa709cd4e36539dcdb695b`). Pinned `runtime.py offline` passes, with `simulation_started: false` (log SHA-256 `9cbcb1bed7817723735afc29e01ffbd4bdf125e39001267ad0e4af055f08a452`).
- Assignment-scoped `worker_check.py --complete` passes static checks. Strict ready gate was not invoked because no selected delivery case has a qualifying source or current-runtime saved-processing proof.

## Remaining worker-owned CPU work

1. Obtain the versioned source traces/receipts or other source-hashed original velocity and video for each accepted membership; check its actual approach speed, actor identity and time join, and whether that approach belongs within the frozen road/park/curb cell. Do not infer any speed from the request.
2. If same-cell source review establishes a valid uncovered approach-driving branch, select exact cases based on that review and implement the missing comparison, candidates, current-runtime positive/negative compatibility, saved processing and independent audit CPU proofs. If the accepted sources already cover it, record their source-backed equivalence and avoid replay. Keep a branch that cannot be established in this cell unselected.
3. Run `.venv-cpu/bin/python worker_check.py --assignment training__C229398__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` only after all selected CPU proofs are complete. Native motion, camera pixels and physical completion remain for local execution.
