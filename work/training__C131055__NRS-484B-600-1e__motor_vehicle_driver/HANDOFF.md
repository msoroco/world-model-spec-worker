# Current CPU delivery handoff

Status: **ready for CPU delivery preparation**. The assignment-scoped strict ready gate passed and was independently rerun by the lead. The revised Native runner uses synchronized overview 1920×1080 and three detail 1280×720 cameras. No original Native recording, measured original speed, pixel review, or physical legal acceptance is claimed.

## Final source-hashed CPU proofs

Execution manifest SHA-256: `4d434b1335525f16cf108b49eeb835d8548da079d9f30019d14f7b742172bb4a`. All six selected primary/fallback candidates passed current v2 offline, public compatibility, missing-source negative, recorded-only saved processing and diagnostic delivery audit. Non-diagnostic delivery checks reject each synthetic source.

| Case | Candidate | Compatibility SHA-256 | Saved SHA-256 | Diagnostic delivery SHA-256 |
| --- | --- | --- | --- | --- |
| controlled_1 | primary | `1fd21b5024133cdeb7c41325a86f249fb6ac54e77449a1fe5172a0a2bf4a6c19` | `a1d1c97f7baac6652688e03eefbd381924c16b8a3c6732c60b3c1304d854c223` | `82b9b479b1463560d9012dd760567e39708766e596a48fd84d9c4165f3ae0bbb` |
| controlled_1 | fallback | `e072eec4dc182b6f30ac775f5cc85ed4623b8ec5745bb6fba401441e970c224b` | `99e56289090154689d17855a0935041bb56b98f74919c1390906b03e64ed506f` | `97a79802195b18b1448a02fcae028b2d46e050bfb35ea748dc569fd0ef923883` |
| controlled_2 | primary | `13ad0157df04553ad852b38b43f968c7ca6b3aea770cb3395c9ea1d5902805c2` | `54660f2f42a7fc10dab6111638b2ed4a06748789f58b96d67f14d57658e094d0` | `24a09cdcd96ad077292335e96c94441c4e943162ecb360a6e5d08a56463820ec` |
| controlled_2 | fallback | `98dfeb3e31dce829850523eb11c82702bc02ddecfc2479e2e42a83d0f6e6f76c` | `573bcb6424887c92d03a93b14f114c39c6655e012aabca87d06100f6cd6372df` | `dd45bf3a5d38f9b5b54700c38b5d89c14143536df2c3195929f39353d3f2d864` |
| controlled_3 | primary | `b8b1e5fff03a1b41db6fc83472d65a8c4fdb2cfc4d5fb981d296312245110154` | `5c262f4178f0db4c0b46b7d4a8820993d6bed5c478e66bb55e5c0001df6c4b1d` | `5b194a7722bcef502cede13935c0b15a6be7b98500819696b519d9ef8a38949c` |
| controlled_3 | fallback | `d3bda34b61e73c9c6c012fcd0807c7b416ca22891bf3152517173b65d0f322be` | `13ff368620c9d99ae7dacec5691113c09589c5572ae8bd4adf80ae2475715d57` | `6d5cd36637bd568048c6f953c00616cc0dbf6752c4ed4a80789dfa99163b779f` |

Each row has retained `boundary-final-I-KIND-offline.log`, `boundary-final-I-KIND-negative-analysis.log`, `boundary-final-I-KIND-delivery-negative.log`, and the three receipts under this work directory. Positive compatibility attempt and saved output remain under `.runtime-work/owner199/boundary-final-I-KIND-compat` and `boundary-final-I-KIND-saved/v0001/processing.json`.

## Replay from repository root

Set `PYTHONDONTWRITEBYTECODE=1`, `SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/owner199"`, and `TMPDIR="$PWD/.runtime-work"`. Substitute `I=1,2,3`, `KIND=primary,fallback`, and `CANDIDATE=primary,fallback1`:

```sh
.venv-cpu/bin/python runtime.py offline --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --candidate CANDIDATE --output .runtime-work/owner199/boundary-final-I-KIND-offline --python "$PWD/.venv-cpu/bin/python"
.venv-cpu/bin/python runtime.py compatibility --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --candidate CANDIDATE --output .runtime-work/owner199/boundary-final-I-KIND-compat --library runtime/library --validator .runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck
.venv-cpu/bin/python runtime.py process-saved --manifest work/training__C131055__NRS-484B-600-1e__motor_vehicle_driver/execution-manifest.json --case training__C131055__NRS-484B-600-1e__motor_vehicle_driver__controlled_I --attempt .runtime-work/owner199/boundary-final-I-KIND-compat --output .runtime-work/owner199/boundary-final-I-KIND-saved --library runtime/library --validator .runtime-work/owner199/decoder-current/.lake/build/bin/adapterCheck
```

`process-saved` infers candidate from the compatibility attempt. Each saved receipt says `passed=true`, `recorded_only=true`, `physical_acceptance_claimed=false`.

## Independent CPU validation

Selected comparison `cb0ce1e6c5d9a1f44869b2761b85edc58ec479afc3fc81824316861905bbcc09`; fallback isolation `61b9d201d3b30adcfcad62abe1ccf3501741f24c04e7c936234f82d2cd11f082`; canonical semantic log `413c1a64a8cc9912e68f08e157842274032dc70efb7edf55f1a51f83322f77d7`; canonical delivery log `e57ad15e155b0c5e25a1cbec078fff76d195020fe1081a52e2d97ee5c6790545`; root unit suite (3 tests) `7710749a44d87b2928443280b55e2f8ef9fa7a8c39764c43341285f50c4c8f09`. Direct future physical audit source-shape tests for controlled_2 and controlled_3 passed, including stale camera review rejection: `0fa65e0e129b84e7cdedf5d19f82bbd345dac5a2b36e359e12b83876a69aefb6`, `ce951fb111a182fb3e48879875d75007e0618f83d2f39eefbe0e19f73b408efe`. These fake-source tests are diagnostic only.

The three physical preparation receipts bind complete arc/exit, incomplete motion and missing evidence CPU fixtures plus Native ownership lifecycle order. Direct execution-manifest, semantic-delivery, delivery-handoff, package-compatibility and physical-preparation validators passed. Assignment-scoped `worker_check.py --complete` passed.

The strict greater-than-80-mph predicate compares original velocity magnitude squared using Decimal against exactly 35.7632² m²/s² before display rounding. Synthetic exact-at controlled_3 has 600 equality samples and zero above. Accepted at membership provides requested 35.5397 m/s only, no original velocity; zero accepted reuse. The actual Native measurement remains for delivery.

The first GPU command is recorded in `result.json`. Native delivery and independent pixel review remain downstream. The assignment-scoped strict ready gate passed with `static_checks_passed: true`; see `strict-scoped-ready.log`. The lead independently reran the exact gate and it passed.
