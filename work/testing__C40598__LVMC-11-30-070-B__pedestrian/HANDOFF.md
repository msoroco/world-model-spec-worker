# C40598 LVMC 11.30.070(B) pedestrian crossing

Status: ready for original-site GPU delivery after exact assignment CPU gate. This package covers the assigned pedestrian entering the roadway to cross in a business district.

Exact source: “No pedestrian shall cross a roadway other than in a marked crosswalk or within an unmarked crosswalk in any business district.” The four selected cases distinguish marked, unmarked, outside both, and the second district-frontage alternative. Three controlled comparisons isolate crosswalk category and district-frontage alternative. No legal numeric district or crosswalk cutoff is invented.

CPU package: `execution-manifest.json` contains four source-gated Native constructions, a bundled CARLA pedestrian adapter, 20 Hz / 45 s four-view capture, saved-only crossing measurement, and an independent original-source and video-pixel audit. The site review packet must bind original source hashes and separately review the 600-foot district span, occupied building uses and frontage on both alternatives, roadway/shoulder and public jurisdiction, all applicable crosswalk geometry, controls, curb zones, and complete afoot route. The original delivery audit requires a separate pixel-review receipt.

CPU evidence: eight offline executions, eight current-runtime positive/negative compatibility candidates, four saved-only finalizers, four independent delivery positive/missing-source pairs, three comparison audits with negative controls, four physical/lifecycle fixtures, a pinned physical criterion test, six source/measurement and offline unit tests and the selected runtime-validator sweep all pass. See `cpu-*-proofs.json`, `cpu-final-tests.log` and `cpu-current-validators.log` for receipts. Diagnostic sources and attempts are synthetic and make no physical or legal claim.

The GPU operator should use `gpu-queue-proposal.json` for the canonical prepare, execute and acceptance sequence and retain failed original attempts. Actual CARLA motion, camera visibility and original pixel/source audits remain to be performed there. Result status records CPU readiness only.
