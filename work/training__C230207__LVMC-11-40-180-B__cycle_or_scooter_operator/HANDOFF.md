# C230207 signed roadway access handoff

Selected LVMC 11.40.180(B) branch: a bicycle, electric bicycle, or electric scooter rider on a roadway or sidewalk where an erected prohibition sign governs. The Director of Public Works determination and sign applicability are administrative and visual review inputs. This package does not make a legal verdict.

## Exact selected delivery

- `witness_1`: the rider stays outside the sign-governed roadway interval.
- `witness_2`: the rider enters it. The selected construction fixes the OpenDRIVE road, governed interval, machine type, four cameras and 600-frame/20-Hz window.
- Both exact bundles passed CPU offline checks. The Native runner surveys the physical sign prop, covered machine, four cameras and road source, captures synchronized source video and rider frames, and seals after restoration. Local delivery must inspect sign pixels, Director determination and roadway access sources before labeling original review complete.
- `native/signed-access-proof.json` records the 600-frame synthetic riding comparison: 0 versus 400 frames inside the governed interval, plus missing-source negatives. This is diagnostic, not actual Native motion or legal acceptance.
- Public compatibility used separate 9-frame synthetic pixel fixtures for each case. Both passed selected finalization, native validation, decoder, render, video decode and missing-setup negative. The 9-frame fixtures do not prove 600-frame camera capture.
- Saved-only processing passed for both 9-frame attempts, preserving originals and timestamp joins. Independent delivery audit decodes actual pixels and checks the separate 600-frame synthetic receipt. Independent comparison audit rejects a changed held interval.

## Local delivery

Set `CARLA_PYTHON`, `CARLA_HOST`, `CARLA_PORT`, `JOB_ID`, `DB`, and `RUN`; execute the `first_gpu_delivery_command` from `result.json`. Capture must provide original sign pixels, the Director determination and exact interval applicability, and a full 600-frame four-camera source join. Process only saved capture after Native exit, restoration and owner release. A 9-frame public fixture never substitutes for original source review.

## Bound CPU evidence

- `construction.json` SHA-256 `a4c7dcb869c3958109785f10d8cd22c1d48723d53a06aeaabb335125689655f6`
- `cases/witness_2/construction.json` SHA-256 `2d9f183addfe00a780d26c7e29a59965a19c02ee0ad171bdea11e56f881a1bb6`
- `execution-manifest.json` SHA-256 `3ce1896041f6687c89cc2da6f8a543e5beabde065d94b66441baa3857f18dde4`
- `native/signed-access-proof.json` SHA-256 `4c0c06d8df904cbebba921a09a38d4b7108827d95d57daf800bbec0323f020f6`
- `proposals/semantic-index.json` SHA-256 `79a2bef1d6314ec6cf7679ac3dff550cf2296eacbf93d41111d98c4037c8e366`
- `compat-witness_1.json` SHA-256 `fa33723d76b2d8cd099aa953271abab9d79ee2aa29a7ea910ba0ee028637995b`
- `compat-witness_2.json` SHA-256 `690144cfd6ffffeacb0c18878e93b23a869f955a9f25dcfbe99e3a12363a0217`
- `saved-witness_1.json` SHA-256 `b112245dbdd5d4d4325f0e2009eba971d84330881564af9e87a61a68894582d3`
- `saved-witness_2.json` SHA-256 `b477a2ca4724d928277e398038b78024eb8e19c6b33b2d89862490d67256c5ab`
- `native/comparison-positive.log` SHA-256 `06a518791e5b640f1b4844a476a69660d20b6bfc085ed10c2a43170c2d642644`
- `native/comparison-negative.log` SHA-256 `b9a3bd5621543b88b3ddd6b41b16c35c03f2181b741ea55d0ac19865ebe2b9fa`

Final scoped strict command: `.venv-cpu/bin/python worker_check.py --assignment training__C230207__LVMC-11-40-180-B__cycle_or_scooter_operator --complete --require-delivery-ready`. It passed on the prepared package; recheck after this handoff update.
