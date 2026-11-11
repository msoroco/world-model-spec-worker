# C152976 / NRS-484B-400-5 — partial CPU checkpoint

Exact law: If the driver of a vehicle intends to turn at an intersection and: The turn is a left turn where both intersecting highways are one-way, both the approach for the left turn and the left turn must be made as close as practicable to the left-hand curb or edge of the highway.

Uncovered branch plan: Construct one-way intersecting highways and a left turn; compare measured approach and departure body proximity to the left curb or edge while holding turn geometry fixed. Keep “as close as practicable” unresolved.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C152976__NRS-484B-400-5__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.
