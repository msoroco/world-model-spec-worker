# C229023 exact delivery preparation

Assignment: `testing__C229023__NRS-486-351-2__motorcycle_or_moped_operator`.
Target set: `full-test`. Exact law: NRS 486.351(2), read with the subsection (3) sentence supplied in `assignment.json`: motorcycles and mopeds may operate no more than two abreast in one lane with the drivers' consent. The five selected cases test same-lane passing, different-lane passing, consented two abreast, unconsented two abreast, and three abreast. The three comparisons isolate lane scope, consent, and rider count. There are no frozen accepted recordings.

## CPU construction and proofs

- `case-plan.json`, `proposals/cases.json`, `construction.json`, `config.json`, and `execution-manifest.json` bind all five exact selected cases. Each has a primary and fallback1 construction, source-bound fixture recipe, selected measurement contract, physical preparation and lifecycle proof, offline proof, compatibility proof, independent delivery audit, and saved-only replay proof.
- Ten exact offline proofs and ten compatibility proofs passed. Compatibility executed selected analysis and required observations, original fixture integrity, four-camera source decode, existing Native validation, Core/Lean conversion, final review render/decode, selected measurements, and a missing-source negative. These are synthetic diagnostic fixtures, not accepted Native recordings.
- Five physical preparation proofs exercised complete motion, incomplete motion and missing evidence, with lifecycle checks. All five saved-only replays passed from freshly materialized primary attempts, joining 900 original frames and preserving original sources. No replay claims legal or physical acceptance.
- Five independent delivery audits passed their diagnostic positive and original-only rejection checks. Three independent controlled-comparison audits passed exact positive pairs and wrong-pair negatives. `comparison-audit-specs.json` and the per-case `delivery_acceptance` receipts bind those checks.
- `gpu-queue-proposal.json` gives exact Native prepare, execute, accept, fallback, owner-release, saved-processing and original-only audit commands. Every owner-release command contains its exact case ID. The lead integrates this proposal into the shared queue.
- Local unit tests: 12 passed. Exact scoped strict readiness passed with exit 0 using `.venv-cpu/bin/python worker_check.py --assignment testing__C229023__NRS-486-351-2__motorcycle_or_moped_operator --complete --require-delivery-ready`.

## Native source and review requirements

`scene_review.py` requires an independently reviewed original map/lane survey and route, rider and other-vehicle classifications, driver identities, consent source, and subsection (3) review. The three-abreast original-only audit also requires a source-backed third-rider classification. `original_capture.py` archives the reviewed source packet, hashes it, and records original Native actors and four synchronized views at 20 Hz for 45 seconds. `delivery_audit.py` verifies the archived source hashes, all original joins and participants, four FFV1 decodes, acquisition seal and original pixel review. `comparison_audit.py` checks exact pairs and one declared difference while holding road, lane width, timing, engineering and camera conditions fixed.

The assigned text contains the subsection (3) two-abreast allowance. Actual driver consent and whether that allowance applies to a recorded event require independent original sources. The CPU fixtures and geometry cannot establish those facts or a legal conclusion. Actual CARLA motion, camera visibility, participant count and source review remain the Native delivery steps.
