# C109749 / NRS-484B-400-2c — partial CPU checkpoint

Exact law: If the driver of a vehicle intends to turn at an intersection and: Both intersecting highways are two-directional: Except as otherwise directed by official traffic-control devices, simultaneous left turns by opposing traffic must be made in front of each other.

Uncovered branch plan: Construct simultaneous opposing left turns at an intersection of two-directional highways, with measured front-of-each-other passing order. Compare crossing order while holding geometry and turn intent fixed; separately account for governing official-device directions.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C109749__NRS-484B-400-2c__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.
