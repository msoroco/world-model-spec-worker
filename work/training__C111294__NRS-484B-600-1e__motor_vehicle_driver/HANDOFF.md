# training__C111294__NRS-484B-600-1e__motor_vehicle_driver

Status: blocked. No delivery recording is selected or claimed.

## Source review

Law: NRS 484B.600(1)(e). Exact text and topic inventory are referenced by hashes in `case-plan.json`. The 3 supplied witness row(s) are planning context, not execution proof. Membership rows: {'demo-train': 0, 'full-train': 0}. No accepted equivalence receipt was verified.

## Planned controlled comparison

measured speed around the strict 80 mph ceiling. Compare only `observed_speed` (mph) while fixing cell, actor, legal context, traffic controls, weather, other controller settings, and capture plan. The 3 case definitions are unselected and have no observed values.

## Blocker and resumption

An authored long-road OpenDRIVE and separate opposing vehicle route now cover the three 24 s/20 Hz planned speed settings. The pinned CPU map parser accepts 19 regions. Ten Native geometry/speed/policy tests pass, including changed-source, missing-frame, actor, motion, time, velocity and pose negatives. Three source-hashed 480-frame synthetic saved fixtures derive 75, 79.5 and 85 mph from velocity, and an independent reader verifies the controlled comparison. The 80 mph uncertainty probe is unresolved. Twelve unselected policy plans provide primary plus three distinct fallbacks for each case; their speed shortfall, lane error and speed overshoot gates are computed from hashed saved Native-shaped samples and tested at positive/negative thresholds. The plans have not been materialized as exact offline packages. These are software diagnostics, not physical Native speed observations or a legal verdict.

Build the executable Native capture, materialize the twelve exact candidates, prove offline and positive/negative portable compatibility, complete saved Core/Lean/video processing, independent delivery audit, semantic stages, and statutory runnable coverage. Preserve the unconditional 80 mph clause without adding a highway-only or posted-limit condition; resolve territorial and definition context from sources. Keep result blocked until all CPU proofs pass, then add ordered GPU queue commands. Historical equivalence remains unverified.
