# C150911 NRS 484B.283(1)(d)(1) pedestrian handoff

Status: `ready`, `delivery_prepared`. Exact scoped strict gate passed with exit 0 on 2026-11-25:

```text
PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT=$PWD/.runtime-work/c150911-owner/pipeline TMPDIR=$PWD/.runtime-work/c150911-owner/tmp .venv-cpu/bin/python worker_check.py --assignment testing__C150911__NRS-484B-283-1d1__pedestrian --complete --require-delivery-ready
```

`cpu-final-strict.log` SHA256: `3f36fadd0c7fd5a27fc4774615b7dbc7e98f5d696ef4efedd918953f9cf12a3b`.

## Selected CPU package

`execution-manifest.json` SHA256: `f4b9449beee7395f28feddb306d749a6411b90f86f356e3dd76525575d7c40eb`. Four exact delivery cases and one speed fallback each are selected. The selected production construction is source deferred: `reviewed_site.py` requires an externally reviewed, source-hashed original OpenDRIVE, qualified crosswalk, official pedestrian signal, pedestrian route, separate vehicle route, exception review and four camera poses before Native world mutation. `runner.py` requires the packet, source root and adapter module at capture. `native_entry.py` records 900 synchronized original signal, walker, driver and four-camera frames and seals Native ownership. `analysis.py` derives the first crosswalk-entry measurement from the saved original packet, receipt and frame/time joins. Pedestrian WALK permission and the separate driver duty remain distinct measurements; NRS 484B.287, 484B.290 and 484B.350 remain independent review questions.

The selected diagnostic fixtures are explicitly synthetic 9-frame software probes. They do not establish original WALK state, actual crosswalk motion, video visibility, statutory exception absence or a legal verdict. Frozen accepted recording inventory for this exact branch is empty.

## Proven CPU checks

- Eight of eight primary and fallback offline constructions passed (`cpu-offline-proofs.json`, SHA256 `aaf496b540e5bb4e972a62de330ad5f7c8bbce210e10436a3d8142916e483f85`).
- Eight of eight selected positive and missing-source compatibility receipts passed (`cpu-compatibility-proofs.json`, SHA256 `f66ebad777239d1b18a95da8dab25387a5c6037644dfabe8bc029d60f274fc6a`).
- Four of four saved-only processing proofs passed (`cpu-saved-proofs.json`, SHA256 `fbb48e33a13af18e575878cf31e41ba095c463ea71e5edc474dfc7493e2e0b8d`).
- Four independent delivery positive and missing-original-source negatives passed, including frame/time joins and full four-video decode (`cpu-independent-proofs.json`, SHA256 `bec99de36dd5f0f098e03a6a36718291fb7cc840bea4664988bf4b0053ffb251`).
- Twelve physical outcome fixtures and four Native closure/owner-release lifecycle fixtures passed in each case's `physical-preparation.json`; these prove diagnostic checker behavior only.
- Three exact saved diagnostic comparisons and missing-source negatives passed (`cpu-comparison-proofs.json`, SHA256 `9e9d69f41ee9c8650cff568bb4eb8890cc45e5650bd6e5a2a101364e88252363`).
- Selected execution manifest, semantic, delivery handoff and compatibility validators passed (`cpu-current-validators.log`, SHA256 `c56c7cdcdb83ea3ea21e31bea3392affffc2e3827a3760267fdb71e5b5ce97e9`). Six CPU unit tests passed (`cpu-final-tests.log`, SHA256 `590c49fa52d08d783215015fe187abc9781501276cbcc8869daf96f98a541aea`).

## Queue and GPU review

`gpu-queue-proposal.json` contains four exact case jobs and three comparison audits (SHA256 `f335fb56fa4bdd885da6c93393dc7ff0c72a7f626618fbfe40b500f9df417d64`). Before execution, provide `C150911_WALK_REVIEW_PACKET`, `C150911_WALK_SOURCE_ROOT` and `C150911_WALK_ADAPTER_MODULE` for independently reviewed original sources. Run actual CARLA capture, inspect four-view signal/crosswalk/driver pixels and motion, audit saved original packets, then review the cited statutory exceptions and separate driver duty. Keep source and legal acceptance distinct from CPU diagnostic proof.
