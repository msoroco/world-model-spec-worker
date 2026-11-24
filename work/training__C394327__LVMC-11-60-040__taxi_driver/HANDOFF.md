# LVMC-11-60-040 at C394327

Actor: `taxi_driver`. Frozen cell: `road` / `load_unload` / `taxi_stand`.

Witness branch: Passenger-loading exception and distinct merchandise activity.

Comparison variable: `taxi_stand_and_passenger_loading`. Proposed physical probes: stand at designated stand or temporarily load passengers; stand outside designated stand without passenger loading. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C394327__LVMC-11-60-040__taxi_driver/assignment.json`, SHA-256 `34ff923b7662e4706c7055e229c472e45b8730c4307dcbe291e03a8424830b7c`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact draft construction and CPU proof

Current frozen assignment SHA-256 is `ce11275342ea11057ab5c3f7eb336b4ed50de18cc3156640e24756ba6624d027`; the earlier source hash above is historical. The exact law bars standing or parking a taxicab on a street outside a designated stand, except a temporary stop while actually engaged in expeditious passenger loading or unloading and in accordance with other stopping and parking regulations. The witness also asks for distinct merchandise activity. This construction compares passenger and merchandise loading at the same outside-stand location. It does not infer a numeric legal meaning for “temporarily” or “expeditious.”

`native/taxi-road.xodr` authors a street, curb lane and proposed designated taxi stand sign. `native/taxi_loading.py` requires exact case, law, actor, timing and four source cameras; it checks 600 joined rows, stopped taxi request, outside-stand request, door state, loading activity and occupant count. Passenger loading requests an occupant-count transition; merchandise loading holds count fixed. It requires original taxi identity, participant activity and other-regulation review before any original-Native measurement. The authored sign is not proof of legal stand designation.

`draft-native/probe_a/construction.json` SHA-256 `00a41f6627a19fc607fb77da60a3659da64550a807eb3e302366ddcd20bdd622` requests passenger loading; `draft-native/probe_b/construction.json` SHA-256 `2490469a02f5ff19470802a15b8ec58a90af13ee75eef36332c21108d4c53daf` requests merchandise loading. Both are 30 seconds at 20 Hz with four named cameras. Each has a 240-frame requested loading window. Pinned `runtime.py offline` returned `offline_passed: true` and `simulation_started: false` for both, logged in `native/proof-probe-a.log` and `native/proof-probe-b.log`. The independent paired-request audit at `native/request-comparison-proof.json`, SHA-256 `63aad4511dab807d4335fb18d57172d0573e19268a556dbee791879dabe80987`, verifies hashes, shared road/curb/stop/door timing/cameras and the intended activity/occupant-count difference.

Both requests remain unselected. Native readback of taxi identity, actual stand designation, vehicle footprint, door/participant activity, passenger exchange, and other stopping or parking regulations is required. Four candidate compatibility recipes, selected process-saved processing, semantic proposals and independent acceptance audit remain CPU work. Status stays `partial` and no legal verdict is claimed.
