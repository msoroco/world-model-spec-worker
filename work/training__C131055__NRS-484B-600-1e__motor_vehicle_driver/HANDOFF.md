# training__C131055__NRS-484B-600-1e__motor_vehicle_driver handoff

Status: **partial**. Three exact selected below, at and above 80 mph CPU diagnostic cases and their three shared fallbacks pass current v2 offline, public compatibility, missing-source negative, recorded-only saved processing and independent diagnostic delivery checks. No original Native recording or physical acceptance is claimed.

## Exact boundary and source meaning

NRS 484B.600(1)(e) uses a strict greater-than-80-mph boundary. The revised `native/measure.py` compares Decimal squared original velocity magnitude with 35.7632² m²/s² before any mph display rounding. `native/finalize_v2.py` requires zero above samples and at least one exact equality sample for controlled_3. The synthetic exact-at source has 600 equality samples and zero above. Native requested speed is not measured speed. The accepted at membership mentions only 35.5397 m/s requested (~79.50004 mph), has no original velocity receipt and is **not reused**. `boundary-disposition.json` and the canonical semantic validator record this distinction.

## Retained current v2 CPU proof

`execution-manifest.json` SHA-256 `106e9a93fdbe7fe035edc79f953edd23fffa9f3e63fb2c6b11a9d97f8cc3f7d3` binds three selected source-hashed constructions and the same `fallback1` throttle gain change (0.35 to 0.55) for each. All six fresh `boundary-v2-*` receipts below supersede the older selected/fallback receipts, whose embedded meter was rounded.

| Case | Candidate | Compatibility SHA-256 | Recorded-only saved SHA-256 | Delivery diagnostic SHA-256 |
| --- | --- | --- | --- | --- |
| controlled_1 | primary | `e7d2b04366b68ef1d401e40de8ac62af20b5b39edf4762f93fe88b77bf00e16d` | `0df4d99a113880225402f5c36c40886e2f3d7be079854ae3aeecd3d92f159c6c` | `1fffdd1dd45a1c3b66d60b7c87e4c424894c77b3d9859071ab7084f5cba38042` |
| controlled_1 | fallback | `9e477e0fac8ef4210340745b5d6208d7afa5544b69ba0662eda1638ca626fe8a` | `e43cf742b952e2255a8c9c04c3e0246c176244dd2ea590a28940b73c1832bd39` | `012ab4e2ef881574ea70072c6c9244ec3086838e9de6387f7c6292ca4391d478` |
| controlled_2 | primary | `8cfb4865aebeed5e82d2363d5ff401197f3191434e2cec194d0046fc04b632b8` | `20d8bd885690f892a02663d6bda6c9efe66e92e35335e33e1ad2facdd1a0c903` | `6c599accf3599e4e16efb1ad95d731c4731928a0c548e8e187e78a20a96b2228` |
| controlled_2 | fallback | `9308b2170d394c14a44de0a3ea748f7632bfc00290a9e1310961833f3ba0b9eb` | `548922fb33b8fc64a695c9a55f8d26ffe2f652041b4c058f547357917c2c33cf` | `693e6ffab7fc8be4b31ed2b3905a3ce1d54a27a54e265a2375c9c7a973ff8359` |
| controlled_3 | primary | `340a433845e08c695ec8cd18e5e6a6e4250bf2dc7861a316b3a6d5142111f363` | `5c0295d95371935c7d6953f6267fcb66a29af5ebd0853bc2d4748eb359acd5cc` | `05fa68447b2d2786649c58531c89a385d83ba57cfcfc346e6e428885f2dc0d7c` |
| controlled_3 | fallback | `e752e09f4a60e21acac43167a3d6a85c7d8960fb4a6dee5db0d535cce0eeecf0` | `1ffce2c22f5ca759fe533c2bb34a2dbf2b87d5bb0a2a1279360ccf4f19f9bdae` | `76894709abd19e464449aca3eacc3af4d9e8bbc6b58ea30a322878b8fbf956fd` |

Exact command pattern from repository root, with `PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/owner199" TMPDIR="$PWD/.runtime-work"` exported first:

```sh
.venv-cpu/bin/python runtime.py offline --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --candidate CANDIDATE --output .runtime-work/owner199/boundary-v2-I-KIND-offline --python "$PWD/.venv-cpu/bin/python"
.venv-cpu/bin/python runtime.py compatibility --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --candidate CANDIDATE --output .runtime-work/owner199/boundary-v2-I-KIND-compat --library runtime/library --validator .runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck
.venv-cpu/bin/python runtime.py process-saved --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --attempt .runtime-work/owner199/boundary-v2-I-KIND-compat --output .runtime-work/owner199/boundary-v2-I-KIND-saved --library runtime/library --validator .runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck
```

Substitute `I=1,2,3`, `KIND=primary,fallback`, and `CANDIDATE=primary,fallback1` respectively. Process-saved infers the candidate from the attempt and has no `--candidate` argument. Exact offline logs are `boundary-v2-I-KIND-offline.log`; positive compatibility receipts, expected missing `roundabout-speed-history.jsonl` negative logs, and saved receipts are retained alongside this handoff. All saved receipts report `passed: true`, `recorded_only: true`, `physical_acceptance_claimed: false`.

## Independent checks

`boundary-v2-selected-comparison-receipt.json` SHA-256 `d57d535c6db41a393a0e414a11f0c65730b0e26a311cdfe653bbecf70dbb9869` checks selected construction and recipe source hashes, 600 frame/time/subject/route joins, fixed conditions and the synthetic below/at/above velocity difference. `fallback-isolation-v3-receipt.json` SHA-256 `2d926cacf518b3717f4b8e5e63459538acba8326024921cf3e85b406f357a8f9` proves only the shared throttle gain changed. `boundary-disposition.json` SHA-256 `d9feee1cf7e57d6beb3c3ec2af66459f6e979234b07e02db9d9ab6cc204df754` records zero accepted-membership reuse.

Diagnostic `delivery_audit.py` receipts above decode four 600-frame videos and verify source/saved hashes and joins; each `boundary-v2-I-KIND-delivery-negative.log` rejects the same synthetic source without `--diagnostic` with `Original Native roundabout source required`. Canonical `validate_delivery_local.py` exited 0, log SHA-256 `b7ba2bdfef622930512441e98a5336b670eb23fc0fe6ab61529a7bdf8cd3396a`. Canonical `validate_semantic_local.py` exited 0, log SHA-256 `f4c7575561634133fd7dbec46eb763a3e695df8cc513ea5c3b33e8e1bf075e75`. Native meter unit test exited 0, log SHA-256 `800346069b7c77896a63bf9caf4716560e8342f5599a74f58ff8b74006e44266`.

The future physical audit branch was exercised with source-shaped **fake** Native originals for controlled_2 and exact-at controlled_3. Run `OWNER199_SOURCE_SHAPE_CASE=2` or `3` with `.venv-cpu/bin/python work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/tests/test_delivery_audit.py`; both direct commands exited 0 and rejected a stale camera pixel-review hash. Logs: `boundary-v2-source-shape-2.log` SHA-256 `0fa65e0e129b84e7cdedf5d19f82bbd345dac5a2b36e359e12b83876a69aefb6`, `boundary-v2-source-shape-3.log` SHA-256 `ce951fb111a182fb3e48879875d75007e0618f83d2f39eefbe0e19f73b408efe`. These are CPU branch tests only, not evidence of reviewed real pixels.

Assignment-scoped `.venv-cpu/bin/python worker_check.py --assignment training__C131055__NRS-484B-600-1e__motor_vehicle_driver --complete` passed; `scoped-check.log` retains its output. Status remains partial. Original Native arc/exit traversal, measured 80 mph boundary, four-camera pixels and independent review, source-hashed equivalence to any accepted recording, and physical completion remain unverified. A strict ready gate must follow genuine completion; no ready claim is made.
