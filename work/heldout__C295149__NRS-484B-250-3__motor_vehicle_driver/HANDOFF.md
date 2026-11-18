# C295149 / NRS-484B-250-3 — partial CPU checkpoint

Exact law: When two vehicles enter an intersection at approximately the same time, one vehicle traveling on a highway which ends at the intersection and the other vehicle traveling on a through highway, the driver of the vehicle on the highway which ends at the intersection shall yield the right-of-way to the other vehicle. Except as otherwise provided in subsection 4 [NRS-484B-250-4], this section does not apply at intersections controlled by official traffic-control devices or to vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn.

Uncovered branch plan: Construct ending-highway and through-highway simultaneous entry and yielding; separately cover official-control and opposing-left-turn exceptions, with source-backed intersection and approach identities. Preserve “approximately the same time” as a judgment phrase.

Frozen evidence.json lists no accepted recordings for this assignment. The source-backed scope review is in `case-plan.json`; no physical or legal conclusion is asserted.

Next CPU action: define exact cases and controlled comparisons for every branch above, then implement and test construction, source cameras, measurement/finalization, three distinct fallbacks for each selected case, semantic proposals, saved processing and independent audits. Run exact `runtime.py offline` and `runtime.py compatibility` for each construction, then `.venv-cpu/bin/python worker_check.py --assignment heldout__C295149__NRS-484B-250-3__motor_vehicle_driver --complete --require-delivery-ready`. The current missing work is CPU work, not a GPU blocker.

## 2026-11-18 exact case-design checkpoint

`case-plan.json` now defines six prospective exact cases and four comparisons for ending-versus-through yielding, arrival-window control, active/inoperative official control and the opposing-left-turn exception. Five mandatory observations require original lane-successor topology, both actor arrival and clearance tracks, turn intent and motion, official device governance and four synchronized source cameras. “Approximately the same time” remains a review judgment. The opposing-left exception probe changes approach topology, so its comparison explicitly records that difference. Implement CARLA-lazy source capture and exact candidates with three fallbacks each, then run offline, positive/missing-source compatibility and clean saved processing. These designs contain no physical or legal result.
