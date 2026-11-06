# NRS-484B-283-1b at C230222

Actor: `pedestrian`. Frozen cell: `road` / `travel` / `curb`.

Exact statutory source: NRS 484B.283(1)(b). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Leaving a curb into a vehicle path..

Controlled planning variable: `driver_yield_feasibility_at_curb_departure`. Proposed requests: pedestrian waits until approaching vehicle can yield; pedestrian suddenly enters path when vehicle is too close to yield. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: 484B.287, 484B.290, 484B.350 cross-references; impossibility to yield must be measured.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

CPU construction completed this turn: `native/road.xodr` and `native/geometry.py` fix an authored 40 m, 7 m road with curb x=-3.5 m and vehicle path x=-1.75 m. The 240-frame synthetic pair in `curb-summary.json` changes only pedestrian departure time (0.5 s versus 3.5 s) with the same vehicle trace. Conditional stopping margins use assumed reaction 0.8–1.2 s and deceleration 3–5 m/s²; they do not prove actual driver capability or the statutory impossibility standard. Six malformed-source negatives and `audit-curb.py` pass. Both pinned measurement contracts and missing-source negatives pass (`curb-contract-summary.json`).

Eight unselected construction plans provide a primary and three distinct fallbacks for each probe (`curb-engineering-summary.json`). Fallbacks alter spawn/pre-roll, pedestrian acceleration control, or curb camera distance after specified original Native measurements. The only observed 0.88 m spawn clearance is synthetic; no physical trigger was measured. `native/runner.py` proposes two Native actors, four cameras, 240 frames, source hashes, lossless video and world restoration. All eight CPU preflights and wrong-case negatives pass (`curb-runner-summary.json`); no Native attempt ran and no accepted recording is claimed.

Blocker: Native observation, physically measured triggers, exact offline and positive/negative compatibility, saved Core/video processing, verified driver capability and statutory exception coverage, and independent delivery acceptance remain worker-owned. Legal outcome is unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.
