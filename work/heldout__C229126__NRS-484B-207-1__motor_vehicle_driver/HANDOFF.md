# C229126 / NRS-484B-207-1 — partial CPU checkpoint

Exact law: The driver of a vehicle overtaking another vehicle proceeding in the same direction shall pass to the left thereof at a safe distance and shall not again drive to the right side of the highway until safely clear of the overtaken vehicle.

Uncovered branch plan: Construct overtaking a same-direction vehicle; compare left-pass geometry, surface clearance and return-to-right timing. Keep “safe distance” and “safely clear” unresolved, with measured physical sweeps.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C229126__NRS-484B-207-1__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.
