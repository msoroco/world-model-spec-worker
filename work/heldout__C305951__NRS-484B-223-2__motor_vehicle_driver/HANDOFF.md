# Handoff: heldout__C305951__NRS-484B-223-2__motor_vehicle_driver

## Frozen scope

Upon a highway which has been divided into three clearly marked lanes, a vehicle must not be driven in the extreme left lane at any time. A vehicle on such a highway must not be driven in the center lane except: (a) When overtaking and passing another vehicle where the highway is clearly visible and the center lane is clear of traffic for a safe distance; (b) In preparation for a left turn; or (c) When the center lane is allocated exclusively to traffic moving in the direction in which the vehicle is proceeding and a sign is posted to give notice of such allocation.

Cell C305951: three_lane_road / travel / lane_marking; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Three clearly marked lane highway: extreme-left lane prohibition.
- Center lane exception (a): overtaking/passing with clearly visible highway and clear center lane for safe distance.
- Center lane exception (b): preparation for left turn.
- Center lane exception (c): center lane exclusively allocated to travel direction and posted sign.
- Compare center travel with each exception held or absent; no numeric safe-distance legal cutoff is given.

## Current checkpoint

Eight planned cases cover the extreme-left prohibition, center lane without exception, visible/occluded passing context, left-turn preparation, and center-lane allocation with and without a posted sign. `three_lane.py` requests actual markings, a passing actor, a sight-blocking occluder, turn route and allocation sign through an adapter; it measures original lane occupancy and checks source presence. Tests exercise feature creation and missing-source/fixed-condition rejection; `cpu-tests.log` SHA256 is `a14a836e617e577bea18de5ac6eee35d08fc837cbc2d50a4dad7f520a8e9ba96`. The sight and safe-distance judgments remain open.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C305951__NRS-484B-223-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C305951__NRS-484B-223-2__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C305951__NRS-484B-223-2__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.
