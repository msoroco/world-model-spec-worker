# training__C110741__NRS-484B-113-2__motor_vehicle_driver

Status: blocked and unselected. Eight exact Native construction bundles and synthetic diagnostic proofs exist; strict delivery acceptance does not.

Exact law: The driver of a vehicle: Shall not back into an intersection, on or over a crosswalk, or around a street corner.

Selected witness scope: on or over a crosswalk. `statutory-review.json` maps the exact text and five exported topics, and distinguishes the separate intersection and corner clauses at frozen C110763 and C110812. The C110741 pair compares a reverse path clear of the marked crosswalk with one that overlaps it, while both stay outside the intersection. The authored body overlaps are 0 versus 3.52 m². The paths are CPU construction targets, not observed physical behavior or legal outcomes.

The local snapshot lists 0 accepted membership rows. No source-hashed equivalence receipt was available, so no historical recording is claimed reusable.

`draft-execution-manifest.json` has two exact, unselected cases with primary plus three distinct fallback constructions each. The runner requests reverse control from observed pose and signed velocity, reads the Native crosswalk and lane, records full body, trace, synchronized four-view lossless video and 480 original frames, and restores the exclusive world. Fallback 1 changes lateral correction on measured cross-track error > 0.25 m; fallback 2 changes brake margin on endpoint overshoot > 0.20 m; fallback 3 changes overview FOV on pixel margin < 40 px. Original trigger sources and physical behavior remain unobserved.

`synthetic-proof.log` and `synthetic-pair-audit.log` pass 480-frame source-bound simultaneous backing/overlap positives, four adversarial negatives per case and an independent controlled comparison. `pinned-offline-proof.log` records 8/8 exact `runtime.py offline` bundles with four unit tests each. `portable-proof-*` and associated logs record 8/8 exact synthetic `package_compatibility.run` positives through saved finalization, Native result validation, Core/Lean, render and final decode, plus removed Native-source negatives. `portable-matrix-audit.log`, `measurement-contract-audit.log` and `draft-package-audit.log` pass independent hash/controlled-pair checks and pinned five-topic measurement contract validation. These are software diagnostics only.

Strict v2 fixture-recipe compatibility, selected delivery acceptance, shared statutory matrix selection and GPU queue row remain incomplete. `probe-v2-recipe.py` reproduces the pinned-base constraint: the sole frozen runtime trace/evidence/frame-map fixture contains 3 rows, this exact bundle requires 480, and `fixture_recipe.inspect` rejects replacement of pinned trace with `Fixture addition shadows pinned source`. See `v2-recipe-diagnostic.json`. This tested limitation does not turn the worker-owned remaining packages into accepted originals. No accepted membership exists for this assignment. Keep blocked/unselected until every strict CPU proof passes.

Physical prerequisites: Measure reverse motion relative to actual intersection, crosswalk and corner polygons; isolate inside versus outside each location.

Legal limit: A street-corner case cannot substitute for an intersection or crosswalk branch.
