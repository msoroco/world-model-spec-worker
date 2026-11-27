# C230266 pedestrian due-care handoff

Status: CPU delivery prepared. The selected source-bound package has passed its in-memory ready-path validation; the exact scoped strict gate passed. Original CARLA capture, independently reviewed pixels and physical motion, and legal due-care judgment remain pending.

## Exact selected comparison

- Law: NRS 484B.280(1)(a), motor vehicle driver, frozen C230266 road/pedestrian cell. The duty to exercise due care has no numeric legal cutoff here.
- Condition A requests distance-triggered slowing; condition B maintains the vehicle request. The original road/pedestrian survey, 20 Hz, 30 seconds, four camera names and source joins are fixed.
- Each selected case has primary and fallback1. Fallback1 changes only the shared approach throttle request from 0.22 to 0.32 if original source shows less than 10 m ego displacement despite the surveyed pedestrian path. It is selected by physical failure evidence, never legal outcome.

### Condition A

- Case: `training__C230266__NRS-484B-280-1a__motor_vehicle_driver__selected_90e3f1aa__condition_a`
- Primary construction SHA-256: `24313ea3d080013971e5740fe5e14d6fcffd3156ba855dc1cc010b8d08177d82`; official compatibility receipt: `477ff19c3f6134ba57a8a13319d32b5457ee42392a081f1eebef784877d4cac5`.
- Fallback1 construction SHA-256: `65988a59acc6abe1688fda521920f4db31995853eaa22ccfecd23519eb3c46a3`; official compatibility receipt: `8673f65f769447f6a80fa5d60029064ec675dd79073c1340f88db57e8e2b38e4`.
- Synthetic physical preparation receipt: `f46981ff324376473ca21fdc74a281ba7fe12b2a9cd48a62d32ad67718a5ec1a`. It tests complete, incomplete, and missing source states; it does not establish original motion.
- Saved-only positive receipt: `0bc9fa6571651a77f621aa05f5fd4f6684b098f3195aef4495ec07e1a875e42d`. Original fixture sources are preserved and 600 frame/time joins pass.
- Independent diagnostic delivery audit has positive and missing-source negative tests; the real audit requires original Native provenance and independent pixel review.

### Condition B

- Case: `training__C230266__NRS-484B-280-1a__motor_vehicle_driver__selected_90e3f1aa__condition_b`
- Primary construction SHA-256: `1de4c3cc36b7cd77b6668a9df685bd45766eea96d0388d683b4de94058175c52`; official compatibility receipt: `aa6f4e9aef60382c7afffe5416898f7cd752012f00ecdf764bad5967ea7cf40b`.
- Fallback1 construction SHA-256: `cb873a1706960190e4e09af5aa87d10f26b099edb11899a620263dcb1796eba1`; official compatibility receipt: `b614eeecc45c860c6b8e776f5e821690f40e425dd3d34295ec2db920d3227cbf`.
- Synthetic physical preparation receipt: `14ef4b4b2d3591c830f64853efe9599f21c082b34f0dab19d19741cc52ffbd58`. It tests complete, incomplete, and missing source states; it does not establish original motion.
- Saved-only positive receipt: `8c96440322b443cbdaac3f6c9c3751d42a097be761c81b987761dc67f89ba77a`. Original fixture sources are preserved and 600 frame/time joins pass.
- Independent diagnostic delivery audit has positive and missing-source negative tests; the real audit requires original Native provenance and independent pixel review.

## Additional proof

- Both public primary and fallback compatibility chains passed source integrity, selected measurements, negative source rejection, Native validation, Core/Lean, render and full 600-frame decode. These are synthetic fixtures.
- The selected A missing contact-event saved-only replay passed with `missing_evidence: true`, preserved originals and actionable feedback.
- Six draft semantic stages validate against the pinned runtime. The categorical response pair leaves an explicitly incomplete numeric sweep and unresolved legal judgment.
- The independent comparison diagnostic passed fixed context and controller-difference checks; its negative test rejected a missing B audit.
- Exact execution manifest, physical, semantic and delivery acceptance validators pass on current bytes. The exact scoped strict gate passed on the returned files.

## Original execution prerequisites

- Provide an original map and independently surveyed pedestrian path via `C230266_ROAD_SURVEY` for the selected runner. Verify actor spawn, crossing, all four source views, collision sensor and 600-frame encoding in CARLA.
- After Native exit and owner release, run saved processing, inspect failure feedback, independently review original pixels and source data, and resolve the statutory due-care judgment. Do not use synthetic fixture diagnostics as physical or legal acceptance.
- Parent owns shared branch matrix, GPU queue and local integration proof. This assignment owns only its work directory.

Result SHA-256: `45ebc80683f8d71bba76215415dce949035b10301f18923c7356c72c212772a6`.
