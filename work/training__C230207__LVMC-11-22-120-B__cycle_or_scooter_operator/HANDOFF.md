# training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator

Status: **ready / delivery_prepared**. The exact assignment CPU strict gate passed on 2026-11-26. The local Native capture and source review remain pending; no accepted recording or legal verdict is claimed.

## Selected delivery

- `probe_01`: human-propelled bicycle along the surveyed shoulder after the same sign; `probe_02`: bicycle on the driving roadway. Both retain 600 original pose/FrameMap rows over 30 seconds and four synchronized FFV1 views. The controlled difference is roadway use after the sign.
- Exact LVMC 11.22.120(B) separates the City Traffic Engineer designation of a heavily traveled street, an erected appropriate sign, the restriction actually stated on its face, and disobedience by a named traffic class. The bicycle subtype is selected because bicycles are expressly named. No scooter, moped or horse-drawn coverage is inferred from this pair.
- The authored OpenDRIVE sign metadata and synthetic fixture cannot establish an official designation, readable real sign, wheel subtype or physical completion. The local operator must inspect original sources and pixels, then keep the captured result and its independent delivery audit together.

## Bound CPU proof

- Pinned execution manifest: `execution-manifest.json` SHA-256 `dcc1a6bccb48b1ae8bc813bd8c6402140d5e0eb7e64bb46ef8f9b5c337206fbe`. Exact scoped command: `.venv-cpu/bin/python -B worker_check.py --assignment training__C230207__LVMC-11-22-120-B__cycle_or_scooter_operator --complete --require-delivery-ready`; result: `static_checks_passed: true`.
- Both primary and `fallback1` camera-placement constructions pass exact offline and current-runtime compatibility, including selected measurement, Core decode, four-view media and missing restriction-source negative checks. The fallback shifts only the reference camera when the original sign face is unreadable; case, law, sign and motion contract remain fixed.
- Both primary cases pass recorded-only `process-saved` on 600-frame diagnostic sources, preserving original inputs and rebuilding selected analysis and final four-view decode. Canonical semantic validation passes 7 stages, including both qualitative judgment phrases as unresolved source review. Physical/lifecycle proofs cover complete, incomplete and missing-source outcomes; independent delivery-audit selftests pass and reject missing pose sources.
- `native/comparison_audit.py` independently verifies the fixed sign, surveyed road, subtype, longitudinal route, timing and camera identities, with shoulder roadway-use count zero and roadway use positive. Its changed-sign negative fails as intended.

## Exact hashes

- `probe_01` primary construction `75abb42b0d9ff50760df9419961f53b4cc6111a3ffd23bcb717561abd5f3fbd5`; fallback `6a7a8748b32eba304f1ae0a49277c30de61b755027671be04c30713cc9ec2944`; primary compatibility receipt `e0f9d3e8aa7825d5c3495eec8ddea603934477e4195fda747cc0bb842d277d0c`; fallback compatibility receipt `dcb01618edb91946fb0549ffa745988970e549d0fc6eab7bb80dd1d3161d8735`; physical receipt `ab73ba56b00219980c9aaf2612e9aea097214a82f4518db61a37f7fb698f73dc`.
- `probe_02` primary construction `f863d5f619bf3cd09ef4f675d9d3772d77787a86275b2c990416d3ce94ce385e`; fallback `f24e0c3b9be9616e6e821bdf8ec4aa1fea12f94a5133dac922f1ea4c7fdd202a`; primary compatibility receipt `6fe26bd36d9e0a13593904d45175244599c23392f22378b5a9840807c4331b12`; fallback compatibility receipt `f6112893982d81afafdd9f3e9ea69e0cfb52d88f2cb2d69cf819a01e7722f842`; physical receipt `550fa1d90b73cf696c6141b4ba6fdc3400444d40325879091351973882f69e0e`.

All scratch and video are under `.runtime-work/`; returned files are source/text receipts under this assignment directory. The lead owns shared branch and queue integration.
