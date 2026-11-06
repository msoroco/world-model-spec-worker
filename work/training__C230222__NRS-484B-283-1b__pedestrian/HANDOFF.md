# NRS-484B-283-1b at C230222

Actor: `pedestrian`. Frozen cell: `road` / `travel` / `curb`.

Exact statutory source: NRS 484B.283(1)(b). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Leaving a curb into a vehicle path..

Controlled planning variable: `driver_yield_feasibility_at_curb_departure`. Proposed requests: pedestrian waits until approaching vehicle can yield; pedestrian suddenly enters path when vehicle is too close to yield. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: 484B.287, 484B.290, 484B.350 cross-references; impossibility to yield must be measured.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

CPU construction completed this turn: `native/road.xodr` and `native/geometry.py` fix an authored 40 m, 7 m road with curb x=-3.5 m and vehicle path x=-1.75 m. The 240-frame synthetic pair in `curb-summary.json` changes only pedestrian departure time (0.5 s versus 3.5 s) with the same vehicle trace. Conditional stopping margins use assumed reaction 0.8–1.2 s and deceleration 3–5 m/s²; they do not prove actual driver capability or the statutory impossibility standard. Six malformed-source negatives and `audit-curb.py` pass. Both pinned measurement contracts and missing-source negatives pass (`curb-contract-summary.json`).

Eight unselected construction plans provide a primary and three distinct fallbacks for each probe (`curb-engineering-summary.json`). Fallbacks alter spawn/pre-roll, pedestrian acceleration control, or curb camera distance after specified original Native measurements. The only observed 0.88 m spawn clearance is synthetic; no physical trigger was measured. `native/runner.py` proposes two Native actors, four cameras, 240 frames, source hashes, lossless video and world restoration. All eight CPU preflights and wrong-case negatives pass (`curb-runner-summary.json`); no Native attempt ran and no accepted recording is claimed.

Eight source-exact unselected packages, bound to frozen runtime manifest SHA-256 `391baee19ccece687c5632aa2cc64ba3b958c8b492045b30e4bfc4caa131c235`, pass actual pinned `runtime.py offline` commands with four CPU tests each. `audit-draft-offline.py` independently checks source, construction and log hashes, identity, camera/12 s/20 Hz policy and four controlled pairs. This is CPU construction proof, without saved compatibility or Native observation.

Two retained 240-frame synthetic saved positives pass original trace/evidence/footprint/time joins and four source video decodes. Six damaged saved-source variants reject missing samples, wrong original footprint or missing video; `audit-saved-curb.py` independently checks the positives and negatives. All eight unselected exact v1 packages pass packaged finalization, pinned Native result validation, 240-scene Core processing, Lean decoder, render, final decode and unchanged acquisition. Eight missing-sample package negatives reject. `audit-package-curb.py` independently checks current construction/offline hashes, package receipts, source and Core outputs, false physical/legal/acceptance flags and four controlled pairs. These are synthetic software proofs, not Native observations.

Blocker: Native observation, physically measured triggers, strict v2 recipe compatibility, verified driver capability and statutory exception coverage, and independent delivery acceptance remain worker-owned. Legal outcome is unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.
