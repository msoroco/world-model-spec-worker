# NRS-484B-413-2 at C42387

Actor: `motor_vehicle_driver`. Frozen cell: `business_district` / `right_turn` / `other_vehicle`.

Witness branch: Business-district 100-foot signaling.

Comparison variable: `continuous_turn_signal_distance`. Proposed physical probes: signal continuously for at least 100 feet before turn in business district; signal for less than 100 feet before same turn. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C42387__NRS-484B-413-2__motor_vehicle_driver/assignment.json`, SHA-256 `873da9f3ff12cfa633a8d1222f638ad187b151e121fc5ae427ee277fd86e188c`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact draft construction and CPU proof

The current frozen assignment SHA-256 is `e5094e09edb8c17b05d10041b84d55435a00bf8d11e1d571261b1ea5ca200478`; the earlier source hash above is historical. Exact NRS 484B.413(2) requires a continuous turn or course-change signal for at least the last 100 feet in a business or residential district, or 300 feet in another area, regardless of weather. The frozen cell supports a business-district right turn. The other-area, left-turn and other course-change alternatives still require a compatible cell or source-backed coverage review; no accepted membership IDs are listed.

`native/business-turn-road.xodr` authors a 100 m eastbound business approach and a 50 m southbound right-turn exit. `native/signal_distance.py` checks the exact law, actor and cell, 600 joined frames at 20 Hz, four camera geometries, single requested right-turn onset and consecutive path distance while the right signal is continuously on. It uses the statutory 100 feet = 30.48 m; it does not convert the requirement to an unsupported time cutoff. District, original path, signal state and course change require Native source review. The clear-weather request is fixed across the pair and is not an exception.

`draft-native/probe_a/construction.json` SHA-256 `d46dd3dde5d3cfcb6fddb46fe410bffebe9edfcd40763b994f4c7bb75abeac75` requests signal onset at frame 260, 35 m before the turn. `draft-native/probe_b/construction.json` SHA-256 `a04a825c6f34f94766b4f153471b71eec1df8d075aedb92e18d875c29c2ad261` requests onset at frame 320, 20 m before the same turn. Both are 30 seconds, 20 Hz and four named cameras. Pinned `runtime.py offline` returned `offline_passed: true` and `simulation_started: false` for both; see `native/proof-probe-a.log` and `native/proof-probe-b.log`. `native/request-comparison-proof.json` SHA-256 `dbdb1a28055cf07fd59a0544bd2c3f3fa7022872620aa92baf542ba0a2a62fe8` independently checks hashes, fixed road/turn/path/weather/cameras and the sole signal-onset difference.

These are unselected authored requests. Original Native district status, turn path, signal continuity and camera visibility are unproved. Four candidate compatibility recipes, selected process-saved fixtures, semantic proposals and independent acceptance audit remain CPU work. Status stays `partial`; no legal verdict is claimed.
