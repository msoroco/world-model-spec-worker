# C104538 / LVMC-11-12-060 — partial CPU checkpoint

Exact law: No vehicle in front of the driveway, entrance or approaches to a fire station shall be turned so as to proceed in the opposite direction. No vehicle shall use the driveway entrance or approaches to a fire station for the purpose of turning so as to proceed in the opposite direction.

Uncovered branch plan: Construct and compare opposite-direction turns in front of the fire-station driveway/entrance/approaches and use of the driveway/approaches for that purpose. Resolve entrance geometry and intent from source-backed setup, rather than a generic U-turn flag.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C104538__LVMC-11-12-060__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.
