# C329654 / NRS-484B-400-2c — partial CPU checkpoint

Exact law: If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: Except as otherwise directed by official traffic-control devices, simultaneous left turns by opposing traffic must be made in front of each other.

Uncovered branch plan: Construct simultaneous opposing left turns at an intersection of two-directional highways, with measured front-of-each-other passing order. Compare crossing order while holding geometry and turn intent fixed; separately account for governing official-device directions.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C329654__NRS-484B-400-2c__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.

## 2026-11-18 exact case-design checkpoint

`case-plan.json` now defines five prospective exact cases: simultaneous front passing, crossing behind, staggered turn control, active official-device direction and inactive-device control. Three comparisons isolate crossing order, turn-window overlap and device governance. Four mandatory source observations require bidirectional lane topology, both full-body tracks, official device identity/state and synchronized original cameras. Implement a CARLA-lazy source capture and one exact end-to-end case, then distinct fallbacks and all remaining cases; run offline, positive/missing-source compatibility and clean saved processing. These designs contain no physical or legal result.

## 2026-11-20 same-law implementation route

The ready C109749/NRS-484B-400-2c package provides a concrete same-law `front_pass_no_device` construction, with a CARLA-lazy opposing-turn runner, original body/heading/map source capture, four camera sources, saved finalizer and exact CPU receipts. Its case purpose maps to this assignment's prospective `opposing_front_pass`; the assignment identity, diagnostic recipe, source hashes, exact proofs and physical risks must be rebound for C329654. The next worker-owned implementation step is to adapt that construction and prove C329654's first exact case end to end, then construct the crossing-order, simultaneity and device controls. This reuse is an implementation source, not transferred proof or an accepted recording. The return has no spare direct-file slot; lossless archival must preserve any referenced source path or rebind its manifest before a new construction file is added. A trial archive of C109749's direct control test was reversed after its scoped strict check showed that the manifest requires that source path; C109749 strict passes again. C329654 remains partial with no exact construction or proof yet.
