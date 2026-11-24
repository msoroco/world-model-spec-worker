# NRS-484B-267-1c at C405647

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `travel` / `emergency_vehicle`.

Witness branch: Immediate approach of a moving authorized emergency vehicle using qualifying flashing lights..

Comparison variable: `emergency_vehicle_passage_wait`. Proposed physical probes: remain stopped until emergency vehicle passes; move before emergency vehicle passes. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C405647__NRS-484B-267-1c__motor_vehicle_driver/assignment.json`, SHA-256 `5338017255bb5da9bd266c59faca7844fffc00c3cc4e43d8df340c7a923dc757`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 exact draft construction and CPU proof

The current frozen assignment SHA-256 is `7d9cdf15e9b720cea7c70d8a1260b6b436d17db6e0fd30e85af12b7675426725`; the source hash above is historical. The exact law applies on the immediate approach of an authorized emergency or regulatory vehicle using qualifying flashing lights, except when otherwise directed by a law enforcement officer. The subject must stop and remain in position until the vehicle has passed. The request comparison tests this temporal distinction only. It does not infer legal authorization, a qualifying light pattern, a body-clearance cutoff or absence of officer direction from an authored request.

`native/emergency-road.xodr` authors a northbound street with two travel lanes and a right shoulder. `native/emergency_wait.py` checks exact law, actor and cell; 600 joined frames at 20 Hz; four source-camera geometries; ego and emergency positions; ego speed; and a requested emergency center crossing. It requires original authorization, qualifying-light, officer-direction and footprint sources before original-Native measurement. The right-edge position and whole-vehicle pass remain for Native readback.

`draft-native/probe_a/construction.json` SHA-256 `9fc24b964eb52f00f7de6cc0474430b25b4dc4bafe7746245489815061933564` requests ego release at frame 360, after the emergency center passes. `draft-native/probe_b/construction.json` SHA-256 `80a36b9c71e8b762f584483ab7f95cb9afa525aff365fada147f7347010b53b8` requests release at frame 240, before it passes. Both are 30 seconds at 20 Hz with four named cameras and the same emergency trajectory and flashing-light request. Pinned `runtime.py offline` returned `offline_passed: true`, `simulation_started: false` for both; see `native/proof-probe-a.log` and `native/proof-probe-b.log`. `native/request-comparison-proof.json` SHA-256 `48e2f04f2b0b00fd82664fab4535ea46f59bc7fe6fef88c45d38681796058a5d` independently checks hashes and the sole controller-timing change.

These are unselected authored requests. Native confirmation of emergency vehicle authorization and motion, qualifying flashes under the cited definition, any officer direction, the ego right-edge footprint and a full body pass is absent. Four candidate compatibility recipes, selected process-saved fixtures, semantic proposals and independent acceptance audit remain CPU work. Status remains `partial`; no legal verdict is claimed.
