# NRS-484B-223-3a at C394300

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `left_turn` / `center_turn_lane`.

Exact source: NRS 484B.223(3)(a). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Purpose restriction throughout center-turn-lane driving..

Controlled variable: `purpose and actual movement from center turn lane`. Requested pair: use center turn lane for left turn; use center turn lane for through travel. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 1. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Current worker-owned CPU construction: `native/geometry.py` generates a seven-road two-opportunity OpenDRIVE map and controlled route pair; `draft-construction/` saves the map, routes and route measurements. `audit-geometry.py` independently checks those saved files and rejects changed lane type or changed through path. `native/engineering.py` defines four distinct unselected command policies per case, `native/controller.py` the observed-pose controller, `native/cameras.py` four camera plans, `native/survey.py` the Native bidirectional lane readback, and `native/trigger_evidence.py` three source-hashed fallback decisions. The CPU test suite exercises candidate distinction, trigger decisions and Native survey readback rejection. These do not establish actual CARLA behavior, original pixels, driver intent or a legal verdict.

The saved movement processor now reads source-hashed map, lane survey, declared purpose and ordered frame/body rows. Two 480-frame CPU fixtures exercise the controlled pair; an independent saved audit recomputes full-body center occupancy and rejects a wrong law source and missing body footprint. This proves only the synthetic saved path. It does not establish Native motion, Core/Lean/video compatibility, original pixels or driver intent.

Remaining worker-owned work: assemble a full capture runner and exact pinned candidate bundles; execute offline and positive/negative portable compatibility proofs; build saved Core/Lean/video processing, independent selected delivery audit, runnable statutory coverage and ordered GPU queue. Physical realization remains a later GPU check. No case is selected or ready.

Resume: finish the Native capture runner and mandatory channels for both controlled routes, materialize and audit all eight exact candidate bundles, then run pinned offline and compatibility checks and saved positive/negative fixtures. Set `ready` only after the complete CPU delivery proofs pass.

Source-context review: Center lane must be designed for left turns in both travel directions. Preserve an explicit source-declared turn purpose separately from measured movement.
