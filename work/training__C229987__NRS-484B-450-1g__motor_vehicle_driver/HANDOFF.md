# C229987 / NRS 484B.450(1)(g) driver handoff

This CPU prepared package selects nine exact cases and seven controlled comparisons. No original Native recording, accepted result, physical outcome or legal finding is claimed. The controlling assignment is `inputs/training__C229987__NRS-484B-450-1g__motor_vehicle_driver/assignment.json`, SHA-256 `d1c702e079fc386a31674cd406f6087a994a051efa247f940e92ff6fe3d851f0`.

## Cases and source meaning

Cases `25`, `30`, and `35` vary the requested front-edge stop gap around the 30-foot statutory distance. `stand_25` and `park_25` request distinct activity modes. `conflict_25`, `law_25`, `officer_25`, and `device_25` request the four statutory exception contexts. Each added branch compares with the `25` no-exception stop reference at the same requested gap. All IDs use prefix `training__C229987__NRS-484B-450-1g__motor_vehicle_driver__`. Requested controls and context actors are probes, not measured legal facts.

`case-plan.json` records exact cases, seven comparisons, two source gaps, deliberate differences and fixed conditions. `proposals/semantic-index.json` binds the literal law, distance condition, activities and exceptions to canonical cases. `execution-manifest.json` binds each inline construction, measurement contract, physical fallback, offline check, positive and negative compatibility proof, saved-only proof, physical proof and independent delivery audit proof. The root package selects case `25`; `config.supported_case_ids` lists all nine.

## Capture and review

`native/runner.py` authors the C229987 OpenDRIVE approach and roadside signal, checks the unique Native signal actor and governed lane, and captures body footprint, signal state and four camera streams across 600 synchronized 20 Hz frames. The traffic-conflict probe places a stationary lead vehicle immediately ahead of the requested halt. The other-law and device probes request a red signal. The officer and parking pedestrians are visual proxies; they cannot establish police authority, an actual direction or parking purpose by themselves. Original `context-survey.template.json` requires independent review of highway and official signal status, halt purpose, each exception, pixels and geometry. Other-law review must cite actual applicable authority.

`native/finalize.py` measures saved original four-corner gap and sustained rest. `delivery_audit.py` requires original Native provenance, source channels, 600 joined frames, affirmative source review for the selected activity and exception, source hashes and full media decode. `comparison_audit.py` checks fixed source-shaped conditions and rejects a missing road source. Synthetic diagnostics under `native/diagnostic/` provide no physical or legal acceptance.

The primary controller uses a 1.2-second braking lead. Every case has a 1.8-second fallback for observed physical overshoot. Candidate selection uses the original footprint and rest target check, never a desired legal label.

## Verification and local execution

Nine primary and nine fallback offline checks passed. All eighteen source-bound compatibility checks passed positive processing and missing-`signal_raw.json` rejection. Nine primary saved-only fixture runs passed. Semantic stages selected nine cases; execution-manifest and delivery-acceptance validators passed for nine. Physical complete/incomplete/missing and lifecycle predicates passed for nine. Seven comparison audits passed; the missing-road negative failed as expected. Root CPU unit tests passed. Receipts and hashes are in `execution-manifest.json`; generated attempts and videos are under `.runtime-work/c229987/`.

The first actual Native job uses the canonical `execute-delivery` command in `result.json`, followed by owner release, recorded-only processing, independent original review and delivery acceptance. Actual CARLA motion, official authority, pixels, participant visibility and legal interpretation remain local checks. The lead integrates the shared GPU queue and branch review after this assignment passes its scoped strict gate.
